import sys
from pathlib import Path

from app.services.llm_service import extract_information
from app.services.pdf_service import extract_pdf_text

OUTPUT_DIR = Path(__file__).parent / "output"


def process(pdf: Path) -> Path:
    text = extract_pdf_text(str(pdf))
    result = extract_information(text)

    out_file = OUTPUT_DIR / f"{pdf.stem}.json"
    out_file.write_text(result.model_dump_json(indent=2))
    return out_file


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("uploads")
    pdfs = sorted(target.glob("*.pdf")) if target.is_dir() else [target]

    OUTPUT_DIR.mkdir(exist_ok=True)

    for pdf in pdfs:
        try:
            print(f"OK      {pdf.name} -> {process(pdf)}")
        except Exception as e:
            print(f"FAILED  {pdf.name}: {e}")


if __name__ == "__main__":
    main()
