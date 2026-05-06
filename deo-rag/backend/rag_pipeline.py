from __future__ import annotations

from langchain_classic.chains import RetrievalQA
from langchain_community.vectorstores import PGVector
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document
import logging

from .config import SETTINGS
from .torch_device import preferred_torch_device
from .reranker import Reranker

logger = logging.getLogger(__name__)

_RERANKER = None

def get_reranker(model_name: str | None = None):
    global _RERANKER
    if model_name and _RERANKER and _RERANKER.model_name != model_name:
        # If a different model is requested, create a new one
        return Reranker(model_name=model_name)
    if _RERANKER is None:
        _RERANKER = Reranker(model_name=model_name)
    return _RERANKER


PROMPT = PromptTemplate(
    template="""You are a Defence Estates Organisation records assistant answering from retrieved context only.

Using the context below, answer the question directly and concisely.

Rules:
- Base your answer entirely on the provided context.
- If the question is descriptive like "Give summary of X", provide a structured answer with clear section headers.
- If the question is fact-based like "What is X?", provide a short, direct answer without section headers.
- If the context contains relevant information, provide a complete answer from that evidence.
- If context is partial but relevant, provide the best answer you can support.
- Never use external knowledge or assumptions beyond what the context states.
- Do not provide legal, financial, title, or administrative conclusions unless the provided context directly supports them.
- Do not output any internal formatting labels like STRUCTURED, FACT/SHORT, DESCRIPTIVE, Mode, or Classification.
- Plain text only; no unnecessary formatting.
- Only reply "The document does not contain this information." if the context is completely unrelated to the question.

Context:
{context}

Question:
{question}

Answer:""",
    input_variables=["context", "question"],
)


def get_vectorstore(collection_name: str | None = None) -> PGVector:
    embeddings = get_embeddings()
    return PGVector(
        connection_string=SETTINGS.database_url,
        collection_name=collection_name or SETTINGS.collection_name,
        embedding_function=embeddings,
    )


def get_embeddings():
    if SETTINGS.embedding_provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(model=SETTINGS.embedding_model)

    if SETTINGS.embedding_provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        # langchain-ollama >= 0.3 requires keep_alive as int (seconds).
        # Convert human-friendly strings like "24h" / "-1" to integer.
        raw_ka = SETTINGS.ollama_keep_alive
        try:
            if raw_ka.lower().endswith("h"):
                ka_seconds = int(raw_ka[:-1]) * 3600
            elif raw_ka.lower().endswith("m"):
                ka_seconds = int(raw_ka[:-1]) * 60
            else:
                ka_seconds = int(raw_ka)
        except (ValueError, AttributeError):
            ka_seconds = 86400  # default 24 hours

        return OllamaEmbeddings(
            model=SETTINGS.embedding_model,
            base_url=SETTINGS.ollama_base_url,
            keep_alive=ka_seconds,
            client_kwargs={"timeout": SETTINGS.ollama_request_timeout_seconds},
        )

    if SETTINGS.embedding_provider == "huggingface":
        from langchain_community.embeddings import HuggingFaceEmbeddings

        device = preferred_torch_device()
        configured = SETTINGS.ingest_hf_encode_batch_size
        if configured and configured > 0:
            encode_batch_size = configured
        elif device == "cuda":
            # Larger batches amortize Python overhead and keep the GPU fed; tune down if OOM.
            encode_batch_size = 96
        elif device == "xpu":
            encode_batch_size = 64
        else:
            encode_batch_size = 16
        return HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-en",
            model_kwargs={"device": device},
            encode_kwargs={"batch_size": encode_batch_size, "normalize_embeddings": True},
        )

    raise ValueError(
        "Unsupported EMBEDDING_PROVIDER. Use 'openai', 'ollama', or 'huggingface'."
    )


def get_llm(
    *,
    llm_model: str | None = None,
    llm_temperature: float | None = None,
    ollama_num_ctx: int | None = None,
    ollama_num_predict: int | None = None,
):
    model = llm_model or SETTINGS.llm_model
    temperature = SETTINGS.llm_temperature if llm_temperature is None else llm_temperature
    num_ctx = SETTINGS.ollama_num_ctx if ollama_num_ctx is None else ollama_num_ctx
    num_predict = SETTINGS.ollama_num_predict if ollama_num_predict is None else ollama_num_predict

    if SETTINGS.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, temperature=temperature)

    if SETTINGS.llm_provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            base_url=SETTINGS.ollama_base_url,
            temperature=temperature,
            num_ctx=num_ctx,
            num_predict=num_predict,
            keep_alive=SETTINGS.ollama_keep_alive,
            client_kwargs={"timeout": SETTINGS.ollama_request_timeout_seconds},
        )

    raise ValueError("Unsupported LLM_PROVIDER. Use 'openai' or 'ollama'.")


def expand_to_parent_context(docs: list[Document], collection_name: str) -> list[Document]:
    """Expands documents to their full representations if they are summaries/keywords."""
    expanded_docs = []
    seen_parent_ids = set()
    
    # We need to fetch the 'full' representation for chunks that matched via summary/keywords
    parent_ids_to_fetch = []
    for doc in docs:
        parent_id = doc.metadata.get("parent_chunk_id")
        rep = doc.metadata.get("representation")
        
        if parent_id and rep != "full":
            if parent_id not in seen_parent_ids:
                parent_ids_to_fetch.append(parent_id)
                seen_parent_ids.add(parent_id)
        else:
            expanded_docs.append(doc)
            if parent_id:
                seen_parent_ids.add(parent_id)
                
    if parent_ids_to_fetch:
        vectorstore = get_vectorstore(collection_name=collection_name)
        # Fetch 'full' representations
        for pid in parent_ids_to_fetch:
            # This is a bit slow as it's one by one, but LangChain's PGVector 
            # doesn't easily support arbitrary metadata filtering in a batch fetch without custom SQL
            # For now, we'll just use what we have or skip expansion if too many
            results = vectorstore.similarity_search("", k=1, filter={"parent_chunk_id": pid, "representation": "full"})
            if results:
                expanded_docs.extend(results)
                
    return expanded_docs

from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from typing import List

class HybridRerankRetriever(BaseRetriever):
    collection_name: str
    top_k: int
    rerank: bool = True
    reranker_model: str | None = None
    
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        from .hybrid_retrieval import hybrid_retrieve
        
        # 1. Hybrid Retrieval (BM25 + Dense)
        hits = hybrid_retrieve(
            query, 
            collection_name=self.collection_name, 
            top_k=self.top_k * 3 # Fetch more for reranking
        )
        docs = [doc for doc, score in hits]
        
        # 2. Parent Context Expansion
        if SETTINGS.enable_multi_vector:
            docs = expand_to_parent_context(docs, self.collection_name)
            
        # 3. Reranking
        if self.rerank:
            reranker = get_reranker(model_name=self.reranker_model)
            docs = reranker.rerank(query, docs, top_k=self.top_k)
        else:
            docs = docs[:self.top_k]
            
        return docs

def build_qa_chain(
    *,
    retriever_top_k: int | None = None,
    llm_model: str | None = None,
    reranker_model: str | None = None,
    llm_temperature: float | None = None,
    ollama_num_ctx: int | None = None,
    ollama_num_predict: int | None = None,
    collection_name: str | None = None,
    use_mmr: bool = False,
) -> RetrievalQA:
    top_k = SETTINGS.retriever_top_k if retriever_top_k is None else retriever_top_k

    # Use the new HybridRerankRetriever
    retriever = HybridRerankRetriever(
        collection_name=collection_name or SETTINGS.collection_name,
        top_k=top_k,
        rerank=True,
        reranker_model=reranker_model
    )

    llm = get_llm(
        llm_model=llm_model,
        llm_temperature=llm_temperature,
        ollama_num_ctx=ollama_num_ctx,
        ollama_num_predict=ollama_num_predict,
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": PROMPT},
    )
    return qa_chain


FALLBACK_ANSWER_PROMPT = PromptTemplate(
    template="""You are a Defence Estates Organisation records assistant. You answer ONLY from the snippets between <CONTEXT> and </CONTEXT>.

Hard rules - follow exactly:
1. Each snippet is labelled `[snippet N] source: <filename> | page: <P>`. Treat that filename as the document the snippet belongs to.
2. If the user names or clearly refers to a specific document, use ONLY snippets whose `source` matches that document. Ignore all other snippets, even if they look similar.
3. Never use prior knowledge of cases, parties, dates, statutes, citations, or rulings. Do not infer or "fill in" anything that is not literally written in the snippets you are using.
4. For summary requests (e.g., "summarise", "give summary"), synthesize all the provided snippets from the matching document to provide a comprehensive and structured overview. Provide as much detail as possible from the evidence.
5. Quote facts directly from the snippets. If two snippets disagree, state the disagreement and quote both.
6. If the snippets do not contain enough evidence to answer the question at all, reply exactly:
   Insufficient evidence in the provided documents to answer this question.
   However, for summary requests, do your best to provide a summary based on the available snippets even if they are incomplete. Do not guess facts not present.
7. End the answer with a `Sources:` line listing each cited document as `<filename> (page <P>)`. Only list documents you actually used.
8. Plain text. No filler. No labels such as STRUCTURED, FACT/SHORT, DESCRIPTIVE, or Mode.

<CONTEXT>
{context}
</CONTEXT>

Question: {question}

Answer:""",
    input_variables=["context", "question"],
)


def generate_fallback_answer_from_docs(
    question: str,
    docs: list[Document],
    *,
    llm_model: str | None = None,
    llm_temperature: float | None = None,
    ollama_num_ctx: int | None = None,
    ollama_num_predict: int | None = None,
    system_prompt: str | None = None,
) -> str:
    """Generate a direct answer from already-retrieved docs when QA chain is overly strict."""
    if not docs:
        return "The document does not contain this information."

    llm = get_llm(
        llm_model=llm_model,
        llm_temperature=llm_temperature,
        ollama_num_ctx=ollama_num_ctx,
        ollama_num_predict=ollama_num_predict,
    )
    context_parts: list[str] = []
    # Increase to 100 snippets to leverage larger context window
    for i, doc in enumerate(docs[:100], start=1):
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "N/A")
        context_parts.append(
            f"[snippet {i}] source: {source} | page: {page}\n{doc.page_content}"
        )

    context = "\n\n".join(context_parts)
    
    # sequence: [relevant chunks] + [system prompt] + [query]
    if system_prompt:
        # Construct a custom prompt that follows the requested sequence
        final_prompt = f"""<documents>
{context}
</documents>

{system_prompt}

<query>
{question}
</query>"""
    else:
        final_prompt = FALLBACK_ANSWER_PROMPT.format(context=context, question=question)
    
    print(f"--- RAG PROMPT ---")
    print(final_prompt)
    print(f"--- END RAG PROMPT ---")

    result = llm.invoke(final_prompt)
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content.strip()
    return str(result).strip()


def retrieve_with_scores(
    query: str,
    *,
    top_k: int | None = None,
    collection_name: str | None = None,
    metadata_filter: dict | None = None,
) -> list[tuple[Document, float]]:
    k = SETTINGS.retriever_top_k if top_k is None else top_k
    vectorstore = get_vectorstore(collection_name=collection_name)
    return [
        (doc, float(score))
        for doc, score in vectorstore.similarity_search_with_score(
            query,
            k=k,
            filter=metadata_filter,
        )
    ]


def debug_retrieve(
    query: str,
    top_k: int | None = None,
    include_scores: bool = True,
    collection_name: str | None = None,
) -> list[dict]:
    """
    Debug retrieval to inspect which chunks are being retrieved for a query.
    Returns detailed information about each retrieved document including similarity scores.
    
    Args:
        query: The search query
        top_k: Number of documents to retrieve (defaults to SETTINGS.retriever_top_k)
        include_scores: Whether to include similarity scores
    
    Returns:
        List of dicts with document content, metadata, and similarity scores
    """
    k = SETTINGS.retriever_top_k if top_k is None else top_k
    
    vectorstore = get_vectorstore(collection_name=collection_name)
    embeddings = get_embeddings()
    
    # Get similarity search with scores
    if include_scores:
        docs_with_scores = vectorstore.similarity_search_with_score(query, k=k)
        results = []
        for i, (doc, score) in enumerate(docs_with_scores):
            results.append({
                "rank": i + 1,
                "similarity_score": round(float(score), 4),
                "source": doc.metadata.get("source", "unknown"),
                "page": doc.metadata.get("page", "N/A"),
                "content_preview": doc.page_content[:500],
                "content_full": doc.page_content,
                "metadata": dict(doc.metadata),
            })
        return results
    else:
        docs = vectorstore.similarity_search(query, k=k)
        results = []
        for i, doc in enumerate(docs):
            results.append({
                "rank": i + 1,
                "source": doc.metadata.get("source", "unknown"),
                "page": doc.metadata.get("page", "N/A"),
                "content_preview": doc.page_content[:500],
                "content_full": doc.page_content,
                "metadata": dict(doc.metadata),
            })
        return results


def debug_retrieve_with_threshold(
    query: str,
    similarity_threshold: float = 0.5,
    top_k: int | None = None,
    collection_name: str | None = None,
) -> list[dict]:
    """
    Retrieve documents only if they meet a minimum similarity threshold.
    Useful for filtering out low-quality matches.
    
    Args:
        query: The search query
        similarity_threshold: Minimum score (0-1) to include a document
        top_k: Maximum documents to retrieve before filtering
    
    Returns:
        List of dicts with documents above threshold
    """
    k = SETTINGS.retriever_top_k * 2 if top_k is None else top_k
    
    vectorstore = get_vectorstore(collection_name=collection_name)
    docs_with_scores = vectorstore.similarity_search_with_score(query, k=k)
    
    results = []
    for i, (doc, score) in enumerate(docs_with_scores):
        if score >= similarity_threshold:
            results.append({
                "rank": i + 1,
                "similarity_score": round(float(score), 4),
                "source": doc.metadata.get("source", "unknown"),
                "page": doc.metadata.get("page", "N/A"),
                "content_preview": doc.page_content[:500],
                "content_full": doc.page_content,
                "metadata": dict(doc.metadata),
            })
    
    return results


def debug_mmr_retrieve(
    query: str,
    top_k: int | None = None,
    lambda_mult: float = 0.5,
    collection_name: str | None = None,
) -> list[dict]:
    """
    Use Maximal Marginal Relevance (MMR) to retrieve diverse, relevant documents.
    MMR reduces redundancy by penalizing documents similar to already-selected ones.
    
    Args:
        query: The search query
        top_k: Number of documents to retrieve
        lambda_mult: Balance between relevance (1.0) and diversity (0.0)
    
    Returns:
        List of diverse documents ordered by MMR score
    """
    k = SETTINGS.retriever_top_k if top_k is None else top_k
    
    vectorstore = get_vectorstore(collection_name=collection_name)
    docs = vectorstore.max_marginal_relevance_search(query, k=k, fetch_k=k * 3, lambda_mult=lambda_mult)
    
    results = []
    for i, doc in enumerate(docs):
        results.append({
            "rank": i + 1,
            "source": doc.metadata.get("source", "unknown"),
            "page": doc.metadata.get("page", "N/A"),
            "content_preview": doc.page_content[:500],
            "content_full": doc.page_content,
            "metadata": dict(doc.metadata),
        })
    
    return results
