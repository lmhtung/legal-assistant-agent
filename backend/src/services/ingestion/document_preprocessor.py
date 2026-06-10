from __future__ import annotations

from pathlib import Path

from src.services.ocr.client import MinerUClient


class DocumentPreprocessor:
    def __init__(self, ocr_client: MinerUClient | None = None, output_dir: Path | None = None) -> None:
        self.ocr_client = ocr_client or MinerUClient(output_dir=str(output_dir) if output_dir else None)

    def to_markdown(self, input_path: Path, use_ocr: bool | None = None) -> Path:
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        suffix = input_path.suffix.lower()
        if suffix == ".md":
            return input_path
        if suffix in {".txt", ".text"}:
            return self._text_to_markdown(input_path)
        if suffix == ".pdf" and use_ocr is not True:
            markdown_path = self._pdf_text_to_markdown(input_path)
            if markdown_path is not None:
                return markdown_path
        if suffix == ".pdf":
            return self.ocr_client.parse_to_markdown(str(input_path))
        raise ValueError(f"Unsupported input type: {input_path.suffix}")

    def _text_to_markdown(self, input_path: Path) -> Path:
        output_path = input_path.with_suffix(".md")
        output_path.write_text(input_path.read_text(encoding="utf-8"), encoding="utf-8")
        return output_path

    def _pdf_text_to_markdown(self, input_path: Path) -> Path | None:
        try:
            from pypdf import PdfReader
        except ImportError:
            return None
        reader = PdfReader(str(input_path))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        text = "\n\n".join(page for page in pages if page)
        if not text.strip():
            return None
        output_path = input_path.with_suffix(".md")
        output_path.write_text(text, encoding="utf-8")
        return output_path
