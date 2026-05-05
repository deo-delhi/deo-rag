from typing import List, Any
from langchain_core.documents import Document
from .config import SETTINGS

def get_docling_chunks(conversion_result: Any) -> List[Document]:
    """
    Transforms Docling ConversionResult into structured LangChain Documents using HybridChunker.
    """
    try:
        from docling.chunking import HybridChunker
        from docling_core.types.doc import DocItemType
    except ImportError:
        # Fallback if docling version doesn't have HybridChunker (unlikely for 2.x)
        return [Document(
            page_content=conversion_result.document.export_to_markdown(),
            metadata={"source": conversion_result.input.file.name}
        )]

    # Use a tokenizer that matches or is compatible with the embedding model
    # For local-first, we can use a generic one or none (let HybridChunker decide)
    chunker = HybridChunker(
        max_tokens=SETTINGS.ingest_chunk_size,
    )

    lc_docs = []
    chunks = chunker.chunk(conversion_result.document)
    
    for i, chunk in enumerate(chunks):
        # Extract metadata
        page_numbers = sorted(list(set(p.page_no for item in chunk.meta.doc_items for p in item.prov if item.prov)))
        headings = chunk.meta.headings if chunk.meta.headings else []
        
        metadata = {
            "source": conversion_result.input.file.name,
            "page": page_numbers[0] if page_numbers else 1,
            "all_pages": page_numbers,
            "heading": " > ".join(headings) if headings else None,
            "chunk_index": i,
            "is_table": any(item.label == DocItemType.TABLE for item in chunk.meta.doc_items),
            "docling_chunk": True
        }
        
        lc_docs.append(Document(
            page_content=chunk.text,
            metadata=metadata
        ))
        
    return lc_docs
