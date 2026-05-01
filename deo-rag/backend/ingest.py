from __future__ import annotations

import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from langchain_community.vectorstores import PGVector
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .config import SETTINGS
from .parser import ensure_searchable_pdf, parse_pdf
from .rag_pipeline import get_embeddings


@dataclass
class IngestResult:
    scanned_files: int
    parsed_documents: int
    chunks_created: int
    failed_files: list[str]


def _load_documents(documents_dir: Path):
    docs = []
    failed_files: list[str] = []

    for pdf in documents_dir.glob("*.pdf"):
        try:
            docs.extend(parse_pdf(pdf))
        except Exception as exc:
            failed_files.append(f"{pdf.name}: {exc}")

    return docs, failed_files


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        # Postgres rejects NUL bytes in text fields.
        return value.replace("\x00", "")

    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]

    if isinstance(value, tuple):
        return tuple(_sanitize_value(v) for v in value)

    return value


def _sanitize_documents(docs: list[Document]) -> list[Document]:
    sanitized: list[Document] = []
    for doc in docs:
        sanitized.append(
            Document(
                page_content=_sanitize_value(doc.page_content),
                metadata=_sanitize_value(doc.metadata),
            )
        )
    return sanitized


def ingest(
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    replace_collection: bool = False,
    documents_dir: Path | None = None,
    collection_name: str | None = None,
    library: str | None = None,
    progress_callback: Callable[[dict], None] | None = None,
) -> IngestResult:
    chunk_size = chunk_size if chunk_size is not None else SETTINGS.ingest_chunk_size
    chunk_overlap = chunk_overlap if chunk_overlap is not None else SETTINGS.ingest_chunk_overlap

    resolved_documents_dir = documents_dir or (Path(__file__).resolve().parent / SETTINGS.documents_dir)
    resolved_documents_dir = resolved_documents_dir.resolve()

    pdf_files = sorted(resolved_documents_dir.glob("*.pdf"), key=lambda p: p.name.lower())

    if not pdf_files:
        print(f"No PDFs found in {resolved_documents_dir}")
        return IngestResult(
            scanned_files=0,
            parsed_documents=0,
            chunks_created=0,
            failed_files=[],
        )

    file_progress = {
        pdf.name: {"file": pdf.name, "status": "pending", "progress": 0, "chunks": 0}
        for pdf in pdf_files
    }
    total_files = len(pdf_files)
    completed_files = 0
    successful_files = 0
    failed_files: list[str] = []
    parsed_documents_total = 0
    chunks_indexed_total = 0

    def emit_progress(current_file: str | None, current_file_index: int, current_file_progress: int) -> None:
        if not progress_callback:
            return

        ordered_files = [file_progress[pdf.name] for pdf in pdf_files]
        progress_callback(
            {
                "total_files": total_files,
                "completed_files": completed_files,
                "successful_files": successful_files,
                "failed_files_count": len(failed_files),
                "current_file": current_file,
                "current_file_index": current_file_index,
                "current_file_progress": current_file_progress,
                "chunks_indexed": chunks_indexed_total,
                "files": ordered_files,
            }
        )

    emit_progress(None, 0, 0)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " "],
    )

    embeddings = get_embeddings()
    vectorstore = PGVector(
        connection_string=SETTINGS.database_url,
        collection_name=collection_name or SETTINGS.collection_name,
        embedding_function=embeddings,
    )

    if replace_collection:
        vectorstore.delete_collection()

    # Recreate the collection when it was deleted (or does not exist yet)
    # so re-ingestion after a clear always has a valid target.
    vectorstore.create_collection()

    for index, pdf_file in enumerate(pdf_files, start=1):
        file_key = pdf_file.name
        file_progress[file_key]["status"] = "parsing"
        file_progress[file_key]["progress"] = 5
        emit_progress(file_key, index, 5)

        try:
            searchable_pdf_path, ocr_status = ensure_searchable_pdf(
                pdf_file,
                resolved_documents_dir / ".searchable",
            )
            docs = _sanitize_documents(
                parse_pdf(
                    pdf_file,
                    library=library,
                    searchable_pdf=searchable_pdf_path.name if searchable_pdf_path else None,
                    ocr_status=ocr_status,
                )
            )
            parsed_documents_total += len(docs)

            file_progress[file_key]["status"] = "chunking"
            file_progress[file_key]["progress"] = 45
            emit_progress(file_key, index, 45)

            chunks = splitter.split_documents(docs)
            file_progress[file_key]["chunks"] = len(chunks)

            file_progress[file_key]["status"] = "indexing"
            file_progress[file_key]["progress"] = 75
            emit_progress(file_key, index, 75)

            if chunks:
                total_chunks = len(chunks)
                # Batch inserts provide better observability and reduce long single-transaction pauses.
                batch_size = 1

                for start in range(0, total_chunks, batch_size):
                    batch = chunks[start : start + batch_size]
                    indexed_before = start
                    indexed_after = min(total_chunks, start + len(batch))

                    print(
                        f"[ingest] {file_key}: indexing batch {indexed_before + 1}-{indexed_after}/{total_chunks}"
                    )
                    vectorstore.add_documents(batch)
                    chunks_indexed_total += len(batch)

                    indexed_in_file = indexed_after
                    indexing_progress = 75 + int((indexed_in_file / total_chunks) * 24)
                    file_progress[file_key]["progress"] = min(indexing_progress, 99)
                    emit_progress(file_key, index, file_progress[file_key]["progress"])

                    print(
                        f"[ingest] {file_key}: indexed {indexed_in_file}/{total_chunks} chunks"
                    )

            successful_files += 1
            completed_files += 1
            file_progress[file_key]["status"] = "completed"
            file_progress[file_key]["progress"] = 100
            emit_progress(file_key, index, 100)
        except Exception as exc:
            completed_files += 1
            failed_files.append(f"{file_key}: {exc}")
            print(f"[ingest][error] {file_key}: {exc!r}")
            print(traceback.format_exc())
            file_progress[file_key]["status"] = "failed"
            file_progress[file_key]["progress"] = 100
            emit_progress(file_key, index, 100)

    emit_progress(None, total_files, 100)

    print(f"Ingested {chunks_indexed_total} chunks from {parsed_documents_total} parsed documents")
    return IngestResult(
        scanned_files=len(pdf_files),
        parsed_documents=parsed_documents_total,
        chunks_created=chunks_indexed_total,
        failed_files=failed_files,
    )


def ingest_to_dict(**kwargs) -> dict:
    return asdict(ingest(**kwargs))


if __name__ == "__main__":
    print(ingest_to_dict())
