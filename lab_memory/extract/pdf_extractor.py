"""PDF text extractor for research papers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


def extract_pdf(file_path: Path) -> dict[str, Any]:
    """Extract text content from a PDF file."""
    doc = fitz.open(str(file_path))
    pages = []

    for page_num, page in enumerate(doc, 1):
        text = page.get_text("text").strip()
        if text:
            pages.append({
                "page_number": page_num,
                "text": text,
            })

    doc.close()

    return {
        "source_file": file_path.name,
        "source_path": str(file_path),
        "type": "pdf",
        "total_pages": len(pages),
        "pages": pages,
    }


def extract_pdf_to_json(file_path: Path, output_dir: Path) -> str:
    """Extract PDF and save as JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    result = extract_pdf(file_path)
    out_path = output_dir / f"{file_path.stem}.json"
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return str(out_path)
