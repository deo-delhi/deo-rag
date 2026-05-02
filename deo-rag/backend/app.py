from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from threading import Lock, Thread
import re
import uuid
import shutil
import json

from fastapi import FastAPI, File, HTTPException, Query as FastAPIQuery, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from httpx import ReadTimeout
from urllib.parse import quote

from .config import SETTINGS
from .ingest import ingest_to_dict
from .rag_pipeline import (
    get_vectorstore,
    debug_retrieve_with_threshold,
    debug_mmr_retrieve,
    generate_fallback_answer_from_docs,
    retrieve_with_scores,
)


def _map_llm_error(exc: Exception) -> HTTPException | None:
    """
    Convert common provider failures (especially Ollama) into a clear HTTP error
    so the UI does not surface a generic 500.
    """
    message = str(exc) or exc.__class__.__name__
    lowered = message.lower()

    # Ollama: missing model or bad tag -> 404 from ollama client.
    # Example: ollama._types.ResponseError: model "gemma3:270m" not found ... (status code: 404)
    if "status code: 404" in lowered and "model" in lowered and "not found" in lowered:
        configured = runtime_settings.get("llm_model", SETTINGS.llm_model)
        hint = (
            f'Ollama model "{configured}" is not available locally. '
            f'Fix: run `ollama pull {configured}` and retry (or change the model in Settings).'
        )
        return HTTPException(status_code=503, detail=hint)

    # Ollama: server down / connection issues.
    if "ollama" in lowered and ("connection refused" in lowered or "failed to connect" in lowered):
        return HTTPException(
            status_code=503,
            detail="Ollama is not reachable. Start Ollama (`ollama serve`) and retry.",
        )

    # Generic timeout-ish failures (not caught by ReadTimeout/FuturesTimeoutError).
    if "timed out" in lowered or "timeout" in lowered:
        return HTTPException(
            status_code=504,
            detail="The model request timed out. Try a shorter question or increase ASK_TIMEOUT_SECONDS / OLLAMA_REQUEST_TIMEOUT_SECONDS.",
        )

    return None


app = FastAPI(title="DEO RAG API", version="0.1.0")


@app.on_event("startup")
def _initialize_hardware_placement() -> None:
    from .hardware_calibration import initialize_hardware_profile

    initialize_hardware_profile()


app.add_middleware(
    CORSMiddleware,
    allow_origins=list(SETTINGS.allowed_origins),
    allow_origin_regex=SETTINGS.allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

runtime_settings = {
    "llm_model": SETTINGS.llm_model,
    "llm_temperature": SETTINGS.llm_temperature,
    "ollama_num_ctx": SETTINGS.ollama_num_ctx,
    "ollama_num_predict": SETTINGS.ollama_num_predict,
    "retriever_top_k": SETTINGS.retriever_top_k,
    "ingest_chunk_size": SETTINGS.ingest_chunk_size,
    "ingest_chunk_overlap": SETTINGS.ingest_chunk_overlap,
}

ask_executor = ThreadPoolExecutor(max_workers=4)
documents_root_dir = (Path(__file__).resolve().parent / SETTINGS.documents_dir).resolve()
documents_root_dir.mkdir(parents=True, exist_ok=True)

DEFAULT_KNOWLEDGE_BASE = "unflagged"
LEGACY_DEFAULT_KNOWLEDGE_BASE = "default"
active_knowledge_base = DEFAULT_KNOWLEDGE_BASE

SETTINGS_FILE = (Path(__file__).resolve().parent.parent / ".run-logs" / "runtime_settings.json").resolve()

def load_persisted_settings():
    global active_knowledge_base
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                if "active_knowledge_base" in data:
                    active_knowledge_base = data["active_knowledge_base"]
                if "runtime_settings" in data:
                    for k, v in data["runtime_settings"].items():
                        if k in runtime_settings:
                            runtime_settings[k] = v
        except Exception:
            pass

def save_persisted_settings():
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump({
                "active_knowledge_base": active_knowledge_base,
                "runtime_settings": runtime_settings
            }, f)
    except Exception:
        pass

load_persisted_settings()

ingest_lock = Lock()
ingest_states: dict[str, dict] = {}


def _empty_ingest_state() -> dict:
    return {
        "status": "idle",
        "job_id": None,
        "started_at": None,
        "finished_at": None,
        "error": None,
        "result": None,
        "progress": None,
    }


def _validate_knowledge_base_name(name: str) -> str:
    normalized = name.strip()
    if normalized == "":
        raise HTTPException(status_code=400, detail="data_library must not be empty")
    if "/" in normalized or "\\" in normalized or normalized in {".", ".."}:
        raise HTTPException(status_code=400, detail="data_library contains invalid path characters")
    if normalized == LEGACY_DEFAULT_KNOWLEDGE_BASE:
        return DEFAULT_KNOWLEDGE_BASE
    return normalized


def _resolve_knowledge_base_name(knowledge_base: str | None) -> str:
    if knowledge_base is None:
        return active_knowledge_base
    return _validate_knowledge_base_name(knowledge_base)


def _knowledge_base_dir(knowledge_base: str, *, create: bool = True) -> Path:
    knowledge_base = _validate_knowledge_base_name(knowledge_base)
    kb_path = (documents_root_dir / knowledge_base).resolve()
    if kb_path.parent != documents_root_dir:
        raise HTTPException(status_code=400, detail="data_library must be a direct folder name")
    if create:
        kb_path.mkdir(parents=True, exist_ok=True)
    return kb_path


def _knowledge_base_collection_name(knowledge_base: str) -> str:
    suffix = re.sub(r"[^a-zA-Z0-9]+", "_", knowledge_base.lower()).strip("_") or "default"
    return f"{SETTINGS.collection_name}__{suffix}"


def _get_ingest_state(knowledge_base: str) -> dict:
    if knowledge_base not in ingest_states:
        ingest_states[knowledge_base] = _empty_ingest_state()
    return ingest_states[knowledge_base]


def _list_knowledge_bases() -> list[str]:
    existing = [
        _validate_knowledge_base_name(p.name)
        for p in documents_root_dir.iterdir()
        if p.is_dir() and p.name != ".searchable"
    ]
    existing = sorted(set(existing), key=lambda name: name.lower())
    if DEFAULT_KNOWLEDGE_BASE not in existing:
        _knowledge_base_dir(DEFAULT_KNOWLEDGE_BASE, create=True)
        existing.append(DEFAULT_KNOWLEDGE_BASE)
    return sorted(existing, key=lambda name: name.lower())


def _matching_knowledge_base_dirs(normalized_name: str) -> list[Path]:
    return [
        path
        for path in documents_root_dir.iterdir()
        if path.is_dir() and path.name.strip() == normalized_name
    ]


def _migrate_legacy_root_pdfs() -> None:
    default_dir = _knowledge_base_dir(DEFAULT_KNOWLEDGE_BASE, create=True)
    for legacy_pdf in documents_root_dir.glob("*.pdf"):
        target = default_dir / legacy_pdf.name
        if target.exists():
            target = default_dir / f"{legacy_pdf.stem}_{int(datetime.now(tz=timezone.utc).timestamp())}{legacy_pdf.suffix}"
        legacy_pdf.rename(target)


def _migrate_legacy_default_library() -> None:
    legacy_dir = documents_root_dir / LEGACY_DEFAULT_KNOWLEDGE_BASE
    if not legacy_dir.exists() or not legacy_dir.is_dir():
        return

    target_dir = _knowledge_base_dir(DEFAULT_KNOWLEDGE_BASE, create=True)
    for item in legacy_dir.iterdir():
        target = target_dir / item.name
        if target.exists():
            timestamp = int(datetime.now(tz=timezone.utc).timestamp())
            target = target_dir / f"{item.stem}_{timestamp}{item.suffix}"
        shutil.move(str(item), str(target))

    try:
        legacy_dir.rmdir()
    except OSError:
        pass


_knowledge_base_dir(DEFAULT_KNOWLEDGE_BASE, create=True)
_migrate_legacy_default_library()
_migrate_legacy_root_pdfs()


@app.on_event("shutdown")
def _shutdown_executor() -> None:
    # Release executor-owned synchronization primitives on clean app shutdown.
    ask_executor.shutdown(wait=False, cancel_futures=True)


_ABSTAIN_PHRASES = (
    "the document does not contain this information.",
    "insufficient evidence in the provided documents to answer this question.",
    "insufficient evidence in the active library for this document.",
)


def _is_abstain_answer(answer: str) -> bool:
    if not isinstance(answer, str):
        return False
    return answer.strip().lower() in _ABSTAIN_PHRASES


def _looks_incomplete_answer(question: str, answer: str) -> bool:
    """
    Detect if an answer appears to be incomplete or truncated.
    
    Checks for:
    - Empty or whitespace-only answers
    - Leaked internal labels
    - Suspiciously short answers for complex questions
    - Answers ending abruptly without proper punctuation
    - Common truncation patterns
    
    Args:
        question: The original question asked
        answer: The generated answer
        
    Returns:
        True if answer appears incomplete, False otherwise
    """
    if not isinstance(answer, str):
        return True

    cleaned = answer.strip()
    if cleaned == "":
        return True

    # Honest abstentions are not "incomplete"; do not regenerate them.
    if _is_abstain_answer(cleaned):
        return False

    # Check for common leakage from instruction-heavy prompts
    leaked_labels = ("**STRUCTURED**", "FACT/SHORT", "DESCRIPTIVE", "Mode", "**Classification**")
    if any(token in cleaned for token in leaked_labels):
        return True

    # For longer, more complex questions, very short answers are often truncated
    # Descriptive questions (7+ words) should typically produce longer answers
    question_word_count = len(question.split())
    
    # Strict threshold for complex descriptive questions
    if question_word_count >= 7:
        # For questions like "What are the stages of..." or "How do... manage...", expect detailed answers
        if "what are" in question.lower() or "how" in question.lower() or "explain" in question.lower():
            if len(cleaned) < 300:  # Very comprehensive answers should be longer
                return True
        # For other descriptive questions, 260 chars minimum
        elif len(cleaned) < 260:
            return True

    # Single word or very short factual answers are usually complete
    elif question_word_count <= 3:
        # These should be short, so don't flag them
        pass
    else:
        # Medium-length questions (4-6 words) should have reasonable answers
        if len(cleaned) < 150:
            return True

    # Answers ending abruptly without proper punctuation often indicate token cut-off
    # Allow for cases where answer ends with a quote, closing bracket, etc.
    if cleaned[-1] not in {'.', '!', '?', ')', ']', '}', '"', "'", '*', '-', '—'}:
        # But allow single words or very short answers
        if len(cleaned) > 50:
            return True

    # Check for incomplete sentences
    # If answer has many commas but no periods, it might be incomplete
    if cleaned.count(',') > 3 and cleaned.count('.') == 0:
        if len(cleaned) > 200:
            return True

    return False


def _extractive_rescue_answer(question: str, source_documents: list) -> str:
    """Build a best-effort answer from retrieved chunks when LLM is overly strict."""
    if not source_documents:
        return "The document does not contain this information."

    tokens = [t for t in re.findall(r"[a-zA-Z0-9]+", question.lower()) if len(t) > 3]
    selected: list[str] = []

    for doc in source_documents[:6]:
        text = doc.page_content.strip()
        if not text:
            continue
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for sentence in sentences:
            s = sentence.strip()
            if len(s) < 40:
                continue
            if any(token in s.lower() for token in tokens[:8]):
                selected.append(s)
            if len(selected) >= 4:
                break
        if len(selected) >= 4:
            break

    if not selected:
        for doc in source_documents[:3]:
            compact = " ".join(doc.page_content.split())
            if compact:
                selected.append(compact[:260].rstrip())
            if len(selected) >= 2:
                break

    if not selected:
        return "The document does not contain this information."

    return " ".join(selected)


def _source_url(library: str, filename: str, *, searchable: bool = True) -> str:
    suffix = "?searchable=true" if searchable else ""
    return f"/sources/{quote(library)}/{quote(filename)}{suffix}"


_SOURCE_MATCH_STOPWORDS = {
    "and",
    "anr",
    "anrs",
    "etc",
    "ors",
    "others",
    "the",
    "versus",
    "vs",
}

_SOURCE_MATCH_COMMON_TOKENS = {
    "government",
    "india",
    "state",
    "union",
}


def _title_tokens(value: str) -> set[str]:
    normalized = value.lower().replace("&", " and ")
    normalized = re.sub(r"\.(pdf|PDF)$", "", normalized)
    normalized = normalized.replace("uoi", " union india ")
    normalized = normalized.replace("goi", " government india ")
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized)
        if len(token) > 2 and token not in _SOURCE_MATCH_STOPWORDS
    }


def _matching_sources_for_question(question: str, library: str) -> list[str]:
    query_tokens = _title_tokens(question)
    if len(query_tokens) < 2:
        return []

    matches: list[tuple[float, str]] = []
    for pdf in _knowledge_base_dir(library, create=True).glob("*.pdf"):
        source_tokens = _title_tokens(pdf.stem)
        if not source_tokens:
            continue

        overlap = source_tokens & query_tokens
        if len(overlap) < 2:
            continue
        if not (overlap - _SOURCE_MATCH_COMMON_TOKENS):
            continue

        coverage = len(overlap) / len(source_tokens)
        query_coverage = len(overlap) / len(query_tokens)
        # Document-name intent: two or more distinctive title words are present
        # and they account for a meaningful part of either the title or the query.
        if coverage >= 0.25 or query_coverage >= 0.4:
            matches.append((max(coverage, query_coverage), pdf.name))

    matches.sort(reverse=True)
    return [name for _score, name in matches[:2]]


def _snippet(text: str, limit: int = 260) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


def _enrich_doc_metadata(doc, *, library: str, score: float | None = None) -> None:
    doc.metadata["library"] = doc.metadata.get("library") or library
    doc.metadata["retrieval_score"] = score
    source = doc.metadata.get("source") or doc.metadata.get("source_path") or "unknown"
    doc.metadata["source"] = source
    doc.metadata["source_path"] = doc.metadata.get("source_path") or source
    searchable_pdf = doc.metadata.get("searchable_pdf")
    doc.metadata["source_url"] = _source_url(
        library,
        searchable_pdf or source,
        searchable=bool(searchable_pdf),
    )


def _retrieve_for_libraries(question: str, libraries: list[str]) -> list[tuple[object, float]]:
    from .hybrid_retrieval import hybrid_retrieve

    retrieved: list[tuple[object, float]] = []
    top_k = runtime_settings["retriever_top_k"]

    for library in libraries:
        collection_name = _knowledge_base_collection_name(library)
        matched_sources = _matching_sources_for_question(question, library)
        try:
            if matched_sources:
                docs_with_scores = []
                for source in matched_sources:
                    docs_with_scores.extend(
                        hybrid_retrieve(
                            question,
                            collection_name=collection_name,
                            top_k=max(top_k, 6),
                            metadata_filter={"source": source},
                        )
                    )
            else:
                docs_with_scores = hybrid_retrieve(
                    question,
                    collection_name=collection_name,
                    top_k=max(top_k, 6),
                )
        except Exception:
            continue

        for doc, score in docs_with_scores:
            _enrich_doc_metadata(doc, library=library, score=score)
            retrieved.append((doc, score))

    retrieved.sort(key=lambda item: item[1])
    if len(libraries) <= 1:
        return retrieved[:top_k]

    return retrieved[: max(top_k, min(len(retrieved), top_k * 3))]


def _group_source_entries(source_documents: list) -> list[dict]:
    grouped: dict[tuple[str, str], dict] = {}

    for doc in source_documents:
        metadata = doc.metadata or {}
        library = metadata.get("library") or DEFAULT_KNOWLEDGE_BASE
        source = metadata.get("source") or metadata.get("source_path") or "unknown"
        key = (library, source)
        page = metadata.get("page")
        score = metadata.get("retrieval_score")
        source_url = metadata.get("source_url") or _source_url(library, source, searchable=False)
        entry = grouped.setdefault(
            key,
            {
                "library": library,
                "source": source,
                "parent_source": source,
                "page": page,
                "pages": [],
                "snippet": _snippet(doc.page_content),
                "snippets": [],
                "score": score,
                "source_url": source_url,
                "ocr_status": metadata.get("ocr_status"),
                "searchable_pdf": metadata.get("searchable_pdf"),
            },
        )

        if page is not None and page not in entry["pages"]:
            entry["pages"].append(page)
        if len(entry["snippets"]) < 3:
            entry["snippets"].append(_snippet(doc.page_content, limit=180))
        if score is not None and (entry["score"] is None or score < entry["score"]):
            entry["score"] = score
        if metadata.get("searchable_pdf"):
            entry["source_url"] = source_url
            entry["searchable_pdf"] = metadata.get("searchable_pdf")

    return list(grouped.values())


class Query(BaseModel):
    question: str
    knowledge_base: str | None = None
    query_scope: str = "active"


class IngestRequest(BaseModel):
    chunk_size: int = runtime_settings["ingest_chunk_size"]
    chunk_overlap: int = runtime_settings["ingest_chunk_overlap"]
    replace_collection: bool = False
    knowledge_base: str | None = None


class SettingsUpdateRequest(BaseModel):
    llm_model: str | None = None
    llm_temperature: float | None = None
    ollama_num_ctx: int | None = None
    ollama_num_predict: int | None = None
    retriever_top_k: int | None = None
    ingest_chunk_size: int | None = None
    ingest_chunk_overlap: int | None = None


class ClearDataRequest(BaseModel):
    delete_files: bool = True
    delete_vectorstore: bool = True
    knowledge_base: str | None = None


class KnowledgeBaseRequest(BaseModel):
    knowledge_base: str


@app.get("/settings")
def get_settings() -> dict:
    active_dir = _knowledge_base_dir(active_knowledge_base, create=True)
    return {
        "llm_provider": SETTINGS.llm_provider,
        "llm_model": runtime_settings["llm_model"],
        "llm_temperature": runtime_settings["llm_temperature"],
        "ollama_num_ctx": runtime_settings["ollama_num_ctx"],
        "ollama_num_predict": runtime_settings["ollama_num_predict"],
        "embedding_provider": SETTINGS.embedding_provider,
        "embedding_model": SETTINGS.embedding_model,
        "retriever_top_k": runtime_settings["retriever_top_k"],
        "ingest_chunk_size": runtime_settings["ingest_chunk_size"],
        "ingest_chunk_overlap": runtime_settings["ingest_chunk_overlap"],
        "database_url": SETTINGS.database_url,
        "collection_name": _knowledge_base_collection_name(active_knowledge_base),
        "base_collection_name": SETTINGS.collection_name,
        "documents_dir": str(active_dir),
        "documents_root_dir": str(documents_root_dir),
        "active_knowledge_base": active_knowledge_base,
    }


@app.get("/knowledge-bases")
def list_knowledge_bases() -> dict:
    return {
        "active_knowledge_base": active_knowledge_base,
        "knowledge_bases": _list_knowledge_bases(),
    }


@app.post("/knowledge-bases")
def create_knowledge_base(request: KnowledgeBaseRequest) -> dict:
    knowledge_base = _validate_knowledge_base_name(request.knowledge_base)
    _knowledge_base_dir(knowledge_base, create=True)
    _get_ingest_state(knowledge_base)
    return {
        "status": "created",
        "knowledge_base": knowledge_base,
        "documents_dir": str(_knowledge_base_dir(knowledge_base, create=True)),
        "collection_name": _knowledge_base_collection_name(knowledge_base),
    }


@app.put("/knowledge-bases/active")
def set_active_knowledge_base(request: KnowledgeBaseRequest) -> dict:
    global active_knowledge_base

    knowledge_base = _validate_knowledge_base_name(request.knowledge_base)
    _knowledge_base_dir(knowledge_base, create=True)
    active_knowledge_base = knowledge_base
    _get_ingest_state(knowledge_base)
    save_persisted_settings()
    return {
        "status": "active_updated",
        "active_knowledge_base": active_knowledge_base,
        "documents_dir": str(_knowledge_base_dir(active_knowledge_base, create=True)),
        "collection_name": _knowledge_base_collection_name(active_knowledge_base),
    }


@app.delete("/knowledge-bases/{knowledge_base_name}")
def delete_knowledge_base(knowledge_base_name: str) -> dict:
    global active_knowledge_base

    knowledge_base = _validate_knowledge_base_name(knowledge_base_name)

    # Prevent deletion of the unflagged Data Library
    if knowledge_base == DEFAULT_KNOWLEDGE_BASE:
        raise HTTPException(status_code=400, detail="Cannot delete the unflagged data library")

    matching_state_keys = [key for key in ingest_states if key.strip() == knowledge_base]
    if any(ingest_states[key]["status"] == "running" for key in matching_state_keys):
        raise HTTPException(status_code=409, detail="Cannot delete data library while ingestion is running")

    # Delete all matching Data Library folders (handles legacy trailing spaces in folder names)
    matching_dirs = _matching_knowledge_base_dirs(knowledge_base)
    deleted_files: list[str] = []
    deleted_directories: list[str] = []
    for kb_dir in matching_dirs:
        for pdf_file in kb_dir.glob("*.pdf"):
            deleted_files.append(pdf_file.name)
        shutil.rmtree(kb_dir, ignore_errors=True)
        deleted_directories.append(kb_dir.name)

    # Delete the vector collection from the database
    target_collection_name = _knowledge_base_collection_name(knowledge_base)
    deleted_vectorstore = False
    try:
        vectorstore = get_vectorstore(collection_name=target_collection_name)
        vectorstore.delete_collection()
        deleted_vectorstore = True
    except Exception:
        deleted_vectorstore = False

    # Clean up ingest states, including legacy keys with trailing spaces
    for kb_key in list(ingest_states.keys()):
        if kb_key.strip() == knowledge_base:
            del ingest_states[kb_key]

    # Switch to default KB if the deleted KB was active
    if active_knowledge_base.strip() == knowledge_base:
        active_knowledge_base = DEFAULT_KNOWLEDGE_BASE

    save_persisted_settings()

    return {
        "status": "deleted",
        "knowledge_base": knowledge_base,
        "deleted_directories": deleted_directories,
        "deleted_files": deleted_files,
        "deleted_vectorstore": deleted_vectorstore,
        "active_knowledge_base": active_knowledge_base,
    }


@app.put("/settings")
def update_settings(request: SettingsUpdateRequest) -> dict:
    updates = request.model_dump(exclude_none=True)
    if not updates:
        return {"status": "unchanged", "settings": get_settings()}

    if "retriever_top_k" in updates and updates["retriever_top_k"] <= 0:
        raise HTTPException(status_code=400, detail="retriever_top_k must be > 0")

    if "ingest_chunk_size" in updates and updates["ingest_chunk_size"] <= 0:
        raise HTTPException(status_code=400, detail="ingest_chunk_size must be > 0")

    if "ingest_chunk_overlap" in updates and updates["ingest_chunk_overlap"] < 0:
        raise HTTPException(status_code=400, detail="ingest_chunk_overlap must be >= 0")

    next_chunk_size = updates.get("ingest_chunk_size", runtime_settings["ingest_chunk_size"])
    next_chunk_overlap = updates.get("ingest_chunk_overlap", runtime_settings["ingest_chunk_overlap"])
    if next_chunk_overlap >= next_chunk_size:
        raise HTTPException(status_code=400, detail="ingest_chunk_overlap must be less than ingest_chunk_size")

    if "ollama_num_ctx" in updates and updates["ollama_num_ctx"] <= 0:
        raise HTTPException(status_code=400, detail="ollama_num_ctx must be > 0")

    if "ollama_num_predict" in updates and updates["ollama_num_predict"] <= 0:
        raise HTTPException(status_code=400, detail="ollama_num_predict must be > 0")

    runtime_settings.update(updates)
    save_persisted_settings()

    return {"status": "updated", "settings": get_settings()}


@app.post("/data/clear")
def clear_data(request: ClearDataRequest) -> dict:
    knowledge_base = _resolve_knowledge_base_name(request.knowledge_base)
    state = _get_ingest_state(knowledge_base)
    if state["status"] == "running":
        raise HTTPException(status_code=409, detail="Cannot clear data while ingestion is running for this data library")

    target_documents_dir = _knowledge_base_dir(knowledge_base, create=True)
    target_collection_name = _knowledge_base_collection_name(knowledge_base)

    deleted_files: list[str] = []
    deleted_vectorstore = False

    if request.delete_files:
        for pdf_file in target_documents_dir.glob("*.pdf"):
            pdf_file.unlink(missing_ok=True)
            deleted_files.append(pdf_file.name)
        searchable_dir = target_documents_dir / ".searchable"
        if searchable_dir.exists():
            for pdf_file in searchable_dir.glob("*.pdf"):
                pdf_file.unlink(missing_ok=True)

    if request.delete_vectorstore:
        try:
            vectorstore = get_vectorstore(collection_name=target_collection_name)
            vectorstore.delete_collection()
            deleted_vectorstore = True
        except Exception:
            deleted_vectorstore = False

    state.update(
        {
            "status": "idle",
            "job_id": None,
            "started_at": None,
            "finished_at": None,
            "error": None,
            "result": None,
            "progress": None,
        }
    )

    return {
        "status": "cleared",
        "knowledge_base": knowledge_base,
        "deleted_files": deleted_files,
        "deleted_vectorstore": deleted_vectorstore,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/hardware")
def hardware_snapshot() -> dict:
    from .hardware_calibration import get_active_profile, initialize_hardware_profile, profile_for_api

    if get_active_profile() is None:
        initialize_hardware_profile()
    return profile_for_api()


@app.post("/hardware/recalibrate")
def hardware_recalibrate() -> dict:
    from .hardware_calibration import recalibrate

    return recalibrate()


@app.get("/documents")
def list_documents(knowledge_base: str | None = FastAPIQuery(default=None)) -> dict:
    resolved_knowledge_base = _resolve_knowledge_base_name(knowledge_base)
    target_documents_dir = _knowledge_base_dir(resolved_knowledge_base, create=True)
    files = sorted([f.name for f in target_documents_dir.glob("*.pdf")])
    return {
        "knowledge_base": resolved_knowledge_base,
        "count": len(files),
        "documents": files,
    }


@app.get("/sources/{library}/{filename}")
def get_source_pdf(
    library: str,
    filename: str,
    searchable: bool = FastAPIQuery(default=True),
) -> FileResponse:
    resolved_library = _resolve_knowledge_base_name(library)
    safe_filename = Path(filename).name
    if safe_filename != filename or not safe_filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid source filename")

    library_dir = _knowledge_base_dir(resolved_library, create=True)
    candidates = []
    if searchable:
        candidates.append(library_dir / ".searchable" / safe_filename)
    candidates.append(library_dir / safe_filename)

    for candidate in candidates:
        resolved_candidate = candidate.resolve()
        allowed_roots = [library_dir.resolve(), (library_dir / ".searchable").resolve()]
        if not any(resolved_candidate.parent == root for root in allowed_roots):
            raise HTTPException(status_code=400, detail="Invalid source path")
        if resolved_candidate.exists() and resolved_candidate.is_file():
            return FileResponse(
                resolved_candidate,
                media_type="application/pdf",
                filename=safe_filename,
                headers={"Content-Disposition": f'inline; filename="{safe_filename}"'},
            )

    raise HTTPException(status_code=404, detail="Source PDF not found")


@app.post("/upload")
async def upload_documents(
    files: list[UploadFile] = File(...),
    knowledge_base: str | None = FastAPIQuery(default=None),
) -> dict:
    resolved_knowledge_base = _resolve_knowledge_base_name(knowledge_base)
    target_documents_dir = _knowledge_base_dir(resolved_knowledge_base, create=True)
    saved: list[str] = []

    for file in files:
        if not file.filename:
            continue

        source_name = Path(file.filename).name
        if not source_name.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"Only PDF files are supported: {source_name}")

        target_path = target_documents_dir / source_name
        if target_path.exists():
            stem = target_path.stem
            suffix = target_path.suffix
            target_path = target_documents_dir / f"{stem}_{int(datetime.now(tz=timezone.utc).timestamp())}{suffix}"

        payload = await file.read()
        target_path.write_bytes(payload)
        saved.append(target_path.name)

    return {
        "knowledge_base": resolved_knowledge_base,
        "uploaded": saved,
        "count": len(saved),
    }


def _run_ingest_job(
    *,
    knowledge_base: str,
    chunk_size: int,
    chunk_overlap: int,
    replace_collection: bool,
) -> None:
    target_documents_dir = _knowledge_base_dir(knowledge_base, create=True)
    target_collection_name = _knowledge_base_collection_name(knowledge_base)
    state = _get_ingest_state(knowledge_base)

    with ingest_lock:
        state["status"] = "running"
        state["started_at"] = datetime.now(tz=timezone.utc).isoformat()
        state["finished_at"] = None
        state["error"] = None
        state["result"] = None
        state["progress"] = {
            "total_files": 0,
            "completed_files": 0,
            "successful_files": 0,
            "failed_files_count": 0,
            "current_file": None,
            "current_file_index": 0,
            "current_file_progress": 0,
            "chunks_indexed": 0,
            "files": [],
        }

        try:
            result = ingest_to_dict(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                replace_collection=replace_collection,
                documents_dir=target_documents_dir,
                collection_name=target_collection_name,
                library=knowledge_base,
                progress_callback=lambda progress: state.__setitem__("progress", progress),
            )
            state["status"] = "completed"
            state["result"] = result
            try:
                from .hybrid_retrieval import invalidate_collection

                invalidate_collection(target_collection_name)
            except Exception:
                pass
        except Exception as exc:
            state["status"] = "failed"
            state["error"] = str(exc)
        finally:
            state["finished_at"] = datetime.now(tz=timezone.utc).isoformat()


@app.post("/ingest/start")
def start_ingestion(request: IngestRequest) -> dict:
    knowledge_base = _resolve_knowledge_base_name(request.knowledge_base)

    running_knowledge_bases = [name for name, entry in ingest_states.items() if entry.get("status") == "running"]
    if running_knowledge_bases:
        raise HTTPException(
            status_code=409,
            detail=f"Ingestion is already running for data library: {running_knowledge_bases[0]}",
        )

    state = _get_ingest_state(knowledge_base)
    if state["status"] == "running":
        raise HTTPException(status_code=409, detail="Ingestion is already running for this data library")

    if request.chunk_size <= 0:
        raise HTTPException(status_code=400, detail="chunk_size must be > 0")

    if request.chunk_overlap < 0:
        raise HTTPException(status_code=400, detail="chunk_overlap must be >= 0")

    if request.chunk_overlap >= request.chunk_size:
        raise HTTPException(status_code=400, detail="chunk_overlap must be less than chunk_size")

    runtime_settings["ingest_chunk_size"] = request.chunk_size
    runtime_settings["ingest_chunk_overlap"] = request.chunk_overlap

    _knowledge_base_dir(knowledge_base, create=True)

    job_id = str(uuid.uuid4())
    state["job_id"] = job_id

    thread = Thread(
        target=_run_ingest_job,
        kwargs={
            "knowledge_base": knowledge_base,
            "chunk_size": request.chunk_size,
            "chunk_overlap": request.chunk_overlap,
            "replace_collection": request.replace_collection,
        },
        daemon=True,
    )
    thread.start()

    return {
        "status": "started",
        "job_id": job_id,
        "knowledge_base": knowledge_base,
        "collection_name": _knowledge_base_collection_name(knowledge_base),
    }


@app.get("/ingest/status")
def get_ingest_status(knowledge_base: str | None = FastAPIQuery(default=None)) -> dict:
    resolved_knowledge_base = _resolve_knowledge_base_name(knowledge_base)
    state = _get_ingest_state(resolved_knowledge_base)
    return {
        **state,
        "knowledge_base": resolved_knowledge_base,
        "collection_name": _knowledge_base_collection_name(resolved_knowledge_base),
    }


@app.post("/ask")
def ask(query: Query) -> dict:
    if query.question.strip() == "":
        raise HTTPException(status_code=400, detail="question must not be empty")

    knowledge_base = _resolve_knowledge_base_name(query.knowledge_base)
    query_scope = query.query_scope.strip().lower()
    if query_scope not in {"active", "global"}:
        raise HTTPException(status_code=400, detail="query_scope must be 'active' or 'global'")

    target_libraries = [knowledge_base] if query_scope == "active" else _list_knowledge_bases()
    target_collection_name = (
        _knowledge_base_collection_name(knowledge_base)
        if query_scope == "active"
        else "global"
    )

    # Track which paths are taken for monitoring
    debug_flags = {
        "used_fallback": False,
        "used_rescue": False,
        "used_incomplete_detection": False,
        "answer_length": 0,
        "retrieved_count": 0,
        "top_similarity_score": None,
        "matched_sources": [],
        "abstained_no_matching_chunks": False,
    }

    # If the question clearly names a document but no chunks from any of the
    # named documents are reachable in this scope, abstain immediately. This
    # is the single biggest cause of confident-but-wrong summaries: the LLM
    # is forced to "answer" from chunks of unrelated cases.
    if query_scope == "active":
        matched_sources_for_abstention = _matching_sources_for_question(
            query.question, knowledge_base
        )
    else:
        matched_sources_for_abstention = []
        for lib in target_libraries:
            matched_sources_for_abstention.extend(
                _matching_sources_for_question(query.question, lib)
            )
    debug_flags["matched_sources"] = sorted(set(matched_sources_for_abstention))

    try:
        docs_with_scores = _retrieve_for_libraries(query.question, target_libraries)
        source_documents = [doc for doc, _score in docs_with_scores]
        debug_flags["retrieved_count"] = len(source_documents)
        if docs_with_scores:
            debug_flags["top_similarity_score"] = round(float(docs_with_scores[0][1]), 4)

        if matched_sources_for_abstention:
            wanted = set(matched_sources_for_abstention)
            keep = [
                (doc, score)
                for doc, score in docs_with_scores
                if (doc.metadata or {}).get("source") in wanted
            ]
            if not keep:
                debug_flags["abstained_no_matching_chunks"] = True
                abstain_msg = (
                    "Insufficient evidence in the provided documents to answer this question. "
                    "I detected that you named one of these documents: "
                    f"{', '.join(sorted(wanted))}, but no indexed chunks from "
                    "those documents were retrieved. Re-ingest the active library and try again."
                )
                return {
                    "knowledge_base": knowledge_base,
                    "data_library": knowledge_base,
                    "query_scope": query_scope,
                    "searched_libraries": target_libraries,
                    "collection_name": target_collection_name,
                    "answer": abstain_msg,
                    "sources": [],
                    "debug": debug_flags,
                }
            docs_with_scores = keep
            source_documents = [doc for doc, _ in keep]
            debug_flags["retrieved_count"] = len(source_documents)

        future = ask_executor.submit(
            generate_fallback_answer_from_docs,
            query.question,
            source_documents,
            llm_model=runtime_settings["llm_model"],
            llm_temperature=runtime_settings["llm_temperature"],
            ollama_num_ctx=runtime_settings["ollama_num_ctx"],
            ollama_num_predict=runtime_settings["ollama_num_predict"],
        )
        answer = future.result(timeout=SETTINGS.ask_timeout_seconds)
    except ReadTimeout as exc:
        raise HTTPException(status_code=504, detail="The answer request timed out. Try a shorter question or increase the timeout.") from exc
    except FuturesTimeoutError as exc:
        raise HTTPException(status_code=504, detail="The answer request timed out. Try a shorter question or increase the timeout.") from exc
    except Exception as exc:
        mapped = _map_llm_error(exc)
        if mapped is not None:
            raise mapped from exc
        error_name = exc.__class__.__name__
        if error_name in {"ReadTimeout", "TimeoutException", "TimeoutError"} or "timed out" in str(exc).lower():
            raise HTTPException(status_code=504, detail="The answer request timed out. Try a shorter question or increase the timeout.") from exc
        raise

    debug_flags["answer_length"] = len(answer)

    # Fallback pass: if retrieval found docs but first pass was too conservative,
    # answer directly from retrieved chunks using a simpler prompt.
    if (
        isinstance(answer, str)
        and answer.strip().lower() == "the document does not contain this information."
        and source_documents
    ):
        try:
            answer = generate_fallback_answer_from_docs(
                query.question,
                source_documents,
                llm_model=runtime_settings["llm_model"],
                llm_temperature=runtime_settings["llm_temperature"],
                ollama_num_ctx=max(runtime_settings["ollama_num_ctx"], 8192),
                ollama_num_predict=max(runtime_settings["ollama_num_predict"], 1024),
            )
            debug_flags["used_fallback"] = True
            debug_flags["answer_length"] = len(answer)
        except Exception as exc:
            mapped = _map_llm_error(exc)
            if mapped is not None:
                raise mapped from exc
            # Keep the original answer if fallback fails for other reasons.

    # Second pass for incomplete/truncated answers.
    if source_documents and _looks_incomplete_answer(query.question, answer):
        try:
            answer = generate_fallback_answer_from_docs(
                query.question,
                source_documents,
                llm_model=runtime_settings["llm_model"],
                llm_temperature=runtime_settings["llm_temperature"],
                ollama_num_ctx=max(runtime_settings["ollama_num_ctx"], 8192),
                ollama_num_predict=max(runtime_settings["ollama_num_predict"], 1024),
            )
            debug_flags["used_incomplete_detection"] = True
            debug_flags["answer_length"] = len(answer)
        except Exception as exc:
            mapped = _map_llm_error(exc)
            if mapped is not None:
                raise mapped from exc
            # Keep the original answer if regeneration fails for other reasons.

    # Final rescue: when sources exist and the model used the legacy abstain
    # phrase, build an extractive best-effort answer. We deliberately do NOT
    # rescue the new "Insufficient evidence ..." phrase — that is an honest
    # abstention from the strict grounding prompt and stitching unrelated
    # sentences only re-introduces hallucinations.
    if (
        source_documents
        and isinstance(answer, str)
        and answer.strip().lower() == "the document does not contain this information."
    ):
        answer = _extractive_rescue_answer(query.question, source_documents)
        debug_flags["used_rescue"] = True
        debug_flags["answer_length"] = len(answer)

    return {
        "knowledge_base": knowledge_base,
        "data_library": knowledge_base,
        "query_scope": query_scope,
        "searched_libraries": target_libraries,
        "collection_name": target_collection_name,
        "answer": answer,
        "sources": _group_source_entries(source_documents),
        "debug": debug_flags,
    }


@app.post("/debug/retrieve")
def debug_retrieve_endpoint(query: Query) -> dict:
    """
    Debug endpoint: Shows all retrieved chunks with similarity scores.
    Use this to inspect what documents are being retrieved for your query.
    """
    if query.question.strip() == "":
        raise HTTPException(status_code=400, detail="question must not be empty")
    
    knowledge_base = _resolve_knowledge_base_name(query.knowledge_base)
    docs_with_scores = _retrieve_for_libraries(query.question, [knowledge_base])
    results = [
        {
            "rank": i + 1,
            "similarity_score": round(float(score), 4),
            "source": doc.metadata.get("source", "unknown"),
            "page": doc.metadata.get("page", "N/A"),
            "content_preview": doc.page_content[:500],
            "content_full": doc.page_content,
            "metadata": dict(doc.metadata),
        }
        for i, (doc, score) in enumerate(docs_with_scores)
    ]
    return {
        "knowledge_base": knowledge_base,
        "query": query.question,
        "matched_sources": _matching_sources_for_question(query.question, knowledge_base),
        "retrieved_count": len(results),
        "documents": results,
    }


@app.post("/debug/retrieve-threshold")
def debug_retrieve_threshold_endpoint(query: Query, threshold: float = 0.5) -> dict:
    """
    Debug endpoint: Returns only chunks above a similarity threshold.
    Helps identify minimum quality thresholds for relevant documents.
    
    threshold: Similarity score (0-1, lower is more permissive)
    """
    if query.question.strip() == "":
        raise HTTPException(status_code=400, detail="question must not be empty")
    
    if not (0 <= threshold <= 1):
        raise HTTPException(status_code=400, detail="threshold must be between 0 and 1")
    
    knowledge_base = _resolve_knowledge_base_name(query.knowledge_base)
    results = debug_retrieve_with_threshold(
        query.question,
        similarity_threshold=threshold,
        collection_name=_knowledge_base_collection_name(knowledge_base),
    )
    return {
        "knowledge_base": knowledge_base,
        "query": query.question,
        "threshold": threshold,
        "retrieved_count": len(results),
        "documents": results,
    }


@app.post("/debug/retrieve-mmr")
def debug_retrieve_mmr_endpoint(query: Query, lambda_mult: float = 0.5) -> dict:
    """
    Debug endpoint: Uses Maximal Marginal Relevance (MMR) for diverse results.
    MMR reduces redundancy between chunks while maintaining relevance.
    
    lambda_mult: 
      - 1.0 = pure relevance (like similarity search)
      - 0.5 = balance between relevance and diversity
      - 0.0 = pure diversity
    """
    if query.question.strip() == "":
        raise HTTPException(status_code=400, detail="question must not be empty")
    
    if not (0 <= lambda_mult <= 1):
        raise HTTPException(status_code=400, detail="lambda_mult must be between 0 and 1")
    
    knowledge_base = _resolve_knowledge_base_name(query.knowledge_base)
    results = debug_mmr_retrieve(
        query.question,
        lambda_mult=lambda_mult,
        collection_name=_knowledge_base_collection_name(knowledge_base),
    )
    return {
        "knowledge_base": knowledge_base,
        "query": query.question,
        "lambda_mult": lambda_mult,
        "retrieved_count": len(results),
        "documents": results,
    }
