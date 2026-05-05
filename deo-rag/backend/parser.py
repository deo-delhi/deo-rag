from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
import logging

from langchain_core.documents import Document
from .torch_device import docling_accelerator_device

from .structure_chunking import get_docling_chunks

logger = logging.getLogger(__name__)

@dataclass
class ParsedDocument:
    text: str
    metadata: dict

def _parse_with_docling(file_path: Path) -> list[Document]:
    """Primary layout-aware parser using Docling with hardware acceleration."""
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions

    device = docling_accelerator_device()
    cpu_count = os.cpu_count() or 4
    
    # Scale threads based on device
    if device == "cuda":
        num_threads = max(4, cpu_count // 2)
    else:
        num_threads = min(16, cpu_count)
        
    pipeline_options = ThreadedPdfPipelineOptions(
        accelerator_options=AcceleratorOptions(device=device, num_threads=num_threads),
    )
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        },
    )
    result = converter.convert(str(file_path))
    return get_docling_chunks(result)

def _parse_with_pdfplumber(file_path: Path) -> list[Document]:
    """Fallback / Initial attempt parser as per Repository Guidelines."""
    import pdfplumber
    
    docs = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                docs.append(Document(
                    page_content=text,
                    metadata={"source": file_path.name, "page": i + 1}
                ))
    return docs

def _pdf_text_length(file_path: Path) -> int:
    """Quickly assess if PDF is scanned or searchable."""
    try:
        import fitz
        total = 0
        with fitz.open(file_path) as doc:
            for page in doc:
                total += len(page.get_text("text").strip())
        return total
    except Exception:
        return 0

def ensure_searchable_pdf(
    file_path: str | Path,
    output_dir: str | Path,
    *,
    min_native_text_chars: int = 100,
) -> tuple[Path | None, str]:
    """
    OCR Layer & PDF Normalization using OCRmyPDF.
    Ensures maximum hardware utilization (tesseract-ocr usually uses multiple cores).
    """
    source_path = Path(file_path)
    output_path = Path(output_dir) / source_path.name

    native_text_length = _pdf_text_length(source_path)
    if native_text_length >= min_native_text_chars:
        return None, "native_text"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        return output_path, "searchable_pdf_exists"

    try:
        # OCRmyPDF normalization pipeline
        # --skip-text: skip pages that already have text
        # --deskew: fix crooked scans
        # --rotate-pages: fix orientation
        # --jobs: use all available cores for Tesseract
        cmd = [
            "ocrmypdf",
            "--skip-text",
            "--deskew",
            "--rotate-pages",
            "--jobs", str(os.cpu_count() or 4),
            str(source_path),
            str(output_path)
        ]
        # In a production environment, we'd ensure 'ocrmypdf' is in PATH.
        # For this setup, we assume it's correctly installed in the environment.
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            return output_path, "searchable_pdf_created"
        else:
            logger.warning(f"OCRmyPDF failed: {result.stderr}")
            # Fallback to simple copy if OCR fails
            shutil.copy2(source_path, output_path)
            return output_path, f"ocr_failed_original_copied: {result.returncode}"
            
    except Exception as exc:
        logger.error(f"OCR Layer exception: {exc}")
        return None, f"ocr_error: {str(exc)}"

def parse_pdf(
    file_path: str | Path,
    *,
    library: str | None = None,
    searchable_pdf: str | None = None,
    ocr_status: str | None = None,
) -> list[Document]:
    """
    Final Doc Processing Pipeline:
    1. Input Doc -> 2. OCR Layer (via ensure_searchable_pdf) -> 3. Layout Parsing (Docling)
    """
    path = Path(file_path)
    metadata = {
        "source": path.name,
        "source_path": path.name,
        "document_type": "deo_record",
        "library": library or "unflagged",
        "searchable_pdf": searchable_pdf,
        "ocr_status": ocr_status or "not_checked",
    }

    try:
        # Step 3: Layout Parsing with Docling (High-quality markdown extraction)
        docs = _parse_with_docling(path)
        for d in docs:
            d.metadata.update(metadata)
            d.metadata["parser"] = "docling"
        return docs
    except Exception as e:
        logger.warning(f"Docling failed for {path.name}: {e}. Falling back to pdfplumber.")
        # Step 4 (Fallback): Traditional parsing as per repository guidelines
        try:
            docs = _parse_with_pdfplumber(path)
            for d in docs:
                d.metadata.update(metadata)
                d.metadata["parser"] = "pdfplumber"
            return docs
        except Exception as e2:
            logger.error(f"All parsers failed for {path.name}: {e2}")
            return []
