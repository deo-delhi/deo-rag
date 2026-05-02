"""Hybrid retrieval (BM25 + dense vector) with Reciprocal Rank Fusion.

BM25 catches exact tokens (party names, statute numbers, citations) that pure
dense embeddings miss; dense vectors catch paraphrases. Fusing them with RRF
produces the same recall+precision win that production RAG stacks rely on
without any extra hardware.

The BM25 index is built lazily per PGVector collection from the existing
``langchain_pg_embedding`` rows so the corpus stays in lock-step with whatever
ingestion has already produced. The cache is invalidated when the chunk count
for a collection changes.
"""

from __future__ import annotations

import re
import threading
from typing import Iterable

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
from sqlalchemy import create_engine, text as sa_text

from .config import SETTINGS
from .rag_pipeline import retrieve_with_scores


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_RRF_K = 60.0

_BM25_LOCK = threading.Lock()
_BM25_CACHE: dict[str, tuple[int, BM25Okapi | None, list[Document]]] = {}
_ENGINE = None


def _engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(SETTINGS.database_url, pool_pre_ping=True)
    return _ENGINE


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _chunk_count(collection_name: str) -> int:
    sql = sa_text(
        """
        select count(*)
        from langchain_pg_embedding e
        join langchain_pg_collection c on e.collection_id = c.uuid
        where c.name = :cname
        """
    )
    with _engine().connect() as conn:
        return int(conn.execute(sql, {"cname": collection_name}).scalar() or 0)


def _load_chunks(collection_name: str) -> list[Document]:
    sql = sa_text(
        """
        select e.document, e.cmetadata
        from langchain_pg_embedding e
        join langchain_pg_collection c on e.collection_id = c.uuid
        where c.name = :cname
        """
    )
    docs: list[Document] = []
    with _engine().connect() as conn:
        for row in conn.execute(sql, {"cname": collection_name}):
            text, meta = row[0], row[1] or {}
            docs.append(Document(page_content=text or "", metadata=dict(meta)))
    return docs


def _get_bm25(collection_name: str) -> tuple[BM25Okapi | None, list[Document]]:
    n = _chunk_count(collection_name)
    with _BM25_LOCK:
        cached = _BM25_CACHE.get(collection_name)
        if cached is not None and cached[0] == n:
            return cached[1], cached[2]

        chunks = _load_chunks(collection_name)
        corpus = [_tokenize(d.page_content) for d in chunks]
        if any(corpus):
            bm25 = BM25Okapi(corpus)
        else:
            bm25 = None
        _BM25_CACHE[collection_name] = (n, bm25, chunks)
        return bm25, chunks


def invalidate_collection(collection_name: str) -> None:
    """Drop cached BM25 for one collection (call after re-ingest)."""
    with _BM25_LOCK:
        _BM25_CACHE.pop(collection_name, None)


def invalidate_all() -> None:
    with _BM25_LOCK:
        _BM25_CACHE.clear()


def _doc_key(doc: Document) -> str:
    src = (doc.metadata or {}).get("source") or "unknown"
    head = (doc.page_content or "")[:80]
    return f"{src}::{head}"


def hybrid_retrieve(
    query: str,
    *,
    collection_name: str,
    top_k: int,
    metadata_filter: dict | None = None,
    candidate_pool: int | None = None,
) -> list[tuple[Document, float]]:
    """Return up to ``top_k`` documents fused from BM25 and dense retrieval.

    Score returned is ``-rrf_score`` so that callers which sort ascending
    (smaller = better, matching PGVector's L2 distance convention) keep working
    without changes.
    """
    pool = candidate_pool or max(top_k * 5, 20)

    try:
        vector_hits = retrieve_with_scores(
            query,
            top_k=pool,
            collection_name=collection_name,
            metadata_filter=metadata_filter,
        )
    except Exception:
        vector_hits = []

    bm25, all_chunks = _get_bm25(collection_name)
    bm25_hits: list[tuple[Document, float]] = []
    if bm25 is not None and all_chunks:
        scores = bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(all_chunks)), key=lambda i: scores[i], reverse=True)
        for idx in ranked[:pool]:
            doc = all_chunks[idx]
            if metadata_filter:
                meta = doc.metadata or {}
                if any(meta.get(k) != v for k, v in metadata_filter.items()):
                    continue
            if scores[idx] <= 0:
                continue
            bm25_hits.append((doc, float(scores[idx])))

    fused: dict[str, dict] = {}

    def _accumulate(hits: Iterable[tuple[Document, float]], origin: str) -> None:
        for rank, (doc, _score) in enumerate(hits):
            key = _doc_key(doc)
            entry = fused.setdefault(
                key,
                {"doc": doc, "rrf": 0.0, "origins": set()},
            )
            entry["rrf"] += 1.0 / (_RRF_K + rank + 1)
            entry["origins"].add(origin)

    _accumulate(vector_hits, "vector")
    _accumulate(bm25_hits, "bm25")

    if not fused:
        return vector_hits[:top_k]

    ordered = sorted(fused.values(), key=lambda e: e["rrf"], reverse=True)[:top_k]
    return [(e["doc"], -float(e["rrf"])) for e in ordered]
