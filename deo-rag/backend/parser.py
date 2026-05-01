from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile

from langchain_core.documents import Document


@dataclass
class ParsedDocument:
    text: str
    metadata: dict


def _parse_with_docling(file_path: Path) -> str:
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(file_path))
    return result.document.export_to_markdown()


def _parse_with_pypdf(file_path: Path) -> list[Document]:
    from langchain_community.document_loaders import PyPDFLoader

    loader = PyPDFLoader(str(file_path))
    docs = loader.load()
    for d in docs:
        d.metadata["source"] = file_path.name
    return docs


def _pdf_text_length(file_path: Path) -> int:
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
    """Create a best-effort searchable sidecar PDF for scanned/low-text PDFs."""
    source_path = Path(file_path)
    output_path = Path(output_dir) / source_path.name

    native_text_length = _pdf_text_length(source_path)
    if native_text_length >= min_native_text_chars:
        return None, "native_text"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        return output_path, "searchable_pdf_exists"

    try:
        import fitz
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang="en")
        with fitz.open(source_path) as doc:
            with tempfile.TemporaryDirectory() as tmp_dir:
                for page_number, page in enumerate(doc, start=1):
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image_path = Path(tmp_dir) / f"page-{page_number}.png"
                    pixmap.save(image_path)

                    ocr_result = ocr.ocr(str(image_path), cls=True)
                    if not ocr_result:
                        continue

                    scale_x = page.rect.width / pixmap.width
                    scale_y = page.rect.height / pixmap.height
                    for page_result in ocr_result:
                        for item in page_result or []:
                            if not item or len(item) < 2:
                                continue
                            points, text_payload = item[0], item[1]
                            text = text_payload[0] if text_payload else ""
                            if not text:
                                continue

                            xs = [point[0] * scale_x for point in points]
                            ys = [point[1] * scale_y for point in points]
                            rect = fitz.Rect(min(xs), min(ys), max(xs), max(ys))
                            if rect.is_empty:
                                continue
                            fontsize = max(4, min(14, rect.height * 0.8))
                            page.insert_textbox(
                                rect,
                                text,
                                fontsize=fontsize,
                                render_mode=3,
                                overlay=True,
                            )

                doc.save(output_path)

        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path, "searchable_pdf_created"
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        try:
            shutil.copy2(source_path, output_path)
            return output_path, f"ocr_failed_original_copied: {exc.__class__.__name__}"
        except Exception:
            return None, f"ocr_failed: {exc.__class__.__name__}"

    return None, "ocr_no_text"


def parse_pdf(
    file_path: str | Path,
    *,
    library: str | None = None,
    searchable_pdf: str | None = None,
    ocr_status: str | None = None,
) -> list[Document]:
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
        text = _parse_with_docling(path)
        return [
            Document(
                page_content=text,
                metadata={
                    **metadata,
                    "page": 1,
                },
            )
        ]
    except Exception:
        # Fallback to robust page-level PDF parsing if Docling fails.
        docs = _parse_with_pypdf(path)
        for d in docs:
            d.metadata.update(metadata)
            d.metadata["document_type"] = d.metadata.get("document_type", "deo_record")
        return docs
