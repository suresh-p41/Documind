import math
from dataclasses import dataclass, field
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    OcrMode,
    PdfPipelineOptions,
    RapidOcrOptions,
)
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
)


def create_pdf_converter():
    """Create a PDF converter with cross-platform RapidOCR."""

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.ocr_options = RapidOcrOptions(
        lang=["en"],
        mode=OcrMode.FULL_PAGE,
        replace_broken_text_layer=True,
    )

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options
            )
        }
    )

    return converter


# Pages with OCR confidence below this are flagged for human verification
LOW_OCR_SCORE = 0.85


@dataclass
class PdfExtraction:
    text: str
    page_count: int
    # Docling's OCR confidence for the whole document, 0-1
    # (None if it could not be measured)
    ocr_score: float | None
    # Lowest OCR confidence of any single page, 0-1
    min_page_ocr_score: float | None
    # Page numbers whose OCR confidence is below LOW_OCR_SCORE
    low_quality_pages: list[int] = field(default_factory=list)
    # Page numbers where no text was found at all
    empty_pages: list[int] = field(default_factory=list)


def _score(value) -> float | None:
    # Docling uses NaN when a score doesn't apply
    return None if value is None or math.isnan(value) else round(float(value), 3)


def extract_pdf(file_path: str) -> PdfExtraction:
    """Extract text from a digital or scanned PDF, plus OCR quality info."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are supported")

    converter = create_pdf_converter()

    result = converter.convert(str(path))

    extracted_text = result.document.export_to_markdown()

    if not extracted_text.strip():
        raise ValueError("No text could be extracted from the PDF")

    page_numbers = sorted(result.document.pages)
    empty_pages = [
        n for n in page_numbers
        if not result.document.export_to_markdown(page_no=n)
        .replace("<!-- image -->", "").strip()
    ]

    # Use only the OCR score. Docling's overall page "grade" also mixes in
    # layout analysis, which marks clean digital invoices as "fair".
    page_scores = {
        page_no: score
        for page_no, page_conf in result.confidence.pages.items()
        if (score := _score(page_conf.ocr_score)) is not None
    }

    return PdfExtraction(
        text=extracted_text,
        page_count=len(page_numbers),
        ocr_score=_score(result.confidence.ocr_score),
        min_page_ocr_score=min(page_scores.values()) if page_scores else None,
        low_quality_pages=sorted(p for p, s in page_scores.items() if s < LOW_OCR_SCORE),
        empty_pages=empty_pages,
    )


def extract_pdf_text(file_path: str) -> str:
    """Extract text from a digital or scanned PDF."""
    return extract_pdf(file_path).text
