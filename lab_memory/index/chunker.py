"""Text chunking for extracted documents."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Chunk:
    text: str
    metadata: dict = field(default_factory=dict)
    chunk_id: str = ""


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (1 token ≈ 4 chars for mixed ko/en)."""
    return len(text) // 3  # Korean chars are ~1-2 tokens each


def chunk_pptx(data: dict, min_length: int = 100) -> list[Chunk]:
    """Chunk PPTX data by slide, merging short slides."""
    chunks = []
    buffer_parts = []
    buffer_meta: dict = {}
    buffer_slides: list[int] = []

    source_file = data["source_file"]
    date = data.get("date", "")

    for slide in data["slides"]:
        parts = []
        if slide["title"]:
            parts.append(f"# {slide['title']}")
        if slide["body"]:
            parts.append(slide["body"])
        for table in slide.get("tables", []):
            parts.append(table)
        if slide["notes"]:
            parts.append(f"[Notes] {slide['notes']}")

        text = "\n\n".join(parts).strip()
        if not text:
            continue

        slide_num = slide["slide_number"]

        if len(text) < min_length and buffer_parts:
            # Merge with buffer
            buffer_parts.append(text)
            buffer_slides.append(slide_num)
        elif len(text) < min_length and not buffer_parts:
            # Start buffer
            buffer_parts.append(text)
            buffer_slides.append(slide_num)
            buffer_meta = {
                "date": date,
                "source_file": source_file,
                "slide_number": slide_num,
                "title": slide.get("title", ""),
                "type": "pptx",
            }
        else:
            # Flush buffer if exists (without current slide)
            if buffer_parts:
                merged = "\n\n".join(buffer_parts)
                chunk_id = f"{source_file}:s{buffer_slides[0]}-{buffer_slides[-1]}"
                chunks.append(Chunk(
                    text=merged,
                    metadata=buffer_meta,
                    chunk_id=chunk_id,
                ))
                buffer_parts = []
                buffer_slides = []
                buffer_meta = {}
            # Add current slide as its own chunk
            chunk_id = f"{source_file}:s{slide_num}"
            chunks.append(Chunk(
                text=text,
                metadata={
                    "date": date,
                    "source_file": source_file,
                    "slide_number": slide_num,
                    "title": slide.get("title", ""),
                    "type": "pptx",
                },
                chunk_id=chunk_id,
            ))

    # Flush remaining buffer
    if buffer_parts:
        merged = "\n\n".join(buffer_parts)
        chunk_id = f"{source_file}:s{buffer_slides[0]}-{buffer_slides[-1]}"
        chunks.append(Chunk(
            text=merged,
            metadata=buffer_meta,
            chunk_id=chunk_id,
        ))

    return chunks


def chunk_pdf(
    data: dict,
    max_tokens: int = 512,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    """Chunk PDF data with token-based splitting and overlap."""
    source_file = data["source_file"]
    chunks = []

    # Concatenate all pages
    full_text = ""
    page_boundaries = []  # (char_offset, page_number)

    for page in data["pages"]:
        page_boundaries.append((len(full_text), page["page_number"]))
        full_text += page["text"] + "\n\n"

    if not full_text.strip():
        return []

    # Split into chunks by token count
    max_chars = max_tokens * 3  # approximate
    overlap_chars = overlap_tokens * 3

    start = 0
    chunk_num = 0
    while start < len(full_text):
        end = min(start + max_chars, len(full_text))

        # Try to break at paragraph boundary
        if end < len(full_text):
            newline_pos = full_text.rfind("\n\n", start, end)
            if newline_pos > start + max_chars // 2:
                end = newline_pos + 2

        chunk_text = full_text[start:end].strip()
        if chunk_text:
            # Find which page this chunk starts on
            page_num = 1
            for offset, pn in page_boundaries:
                if offset <= start:
                    page_num = pn

            chunk_num += 1
            chunks.append(Chunk(
                text=chunk_text,
                metadata={
                    "source_file": source_file,
                    "page_number": page_num,
                    "type": "pdf",
                    "chunk_index": chunk_num,
                },
                chunk_id=f"{source_file}:p{page_num}:c{chunk_num}",
            ))

        start = end - overlap_chars
        if start >= len(full_text) - overlap_chars:
            break

    return chunks


def chunk_file(json_path: Path, min_length: int = 100, max_tokens: int = 512, overlap_tokens: int = 50) -> list[Chunk]:
    """Chunk a single extracted JSON file."""
    data = json.loads(json_path.read_text(encoding="utf-8"))

    if data["type"] == "pptx":
        return chunk_pptx(data, min_length=min_length)
    elif data["type"] == "pdf":
        return chunk_pdf(data, max_tokens=max_tokens, overlap_tokens=overlap_tokens)
    else:
        return []
