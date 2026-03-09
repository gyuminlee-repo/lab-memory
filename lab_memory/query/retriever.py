"""Search retriever for lab memory."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lab_memory.index.embedder import embed_query
from lab_memory.index.store import get_client, get_or_create_collection, search


@dataclass
class SearchResult:
    text: str
    metadata: dict[str, Any]
    score: float
    chunk_id: str


def retrieve(
    query: str,
    chroma_dir: str | Path = "data/chroma_db",
    top_k: int = 10,
    date_from: str | None = None,
    date_to: str | None = None,
    file_type: str | None = None,
    score_threshold: float = 0.3,
) -> list[SearchResult]:
    """Search lab memory for relevant chunks.

    Args:
        query: Natural language search query
        chroma_dir: Path to ChromaDB directory
        top_k: Number of results to return
        date_from: Filter by start date (YYYY-MM-DD)
        date_to: Filter by end date (YYYY-MM-DD)
        file_type: Filter by type ("pptx" or "pdf")
        score_threshold: Minimum similarity score (cosine distance threshold)
    """
    query_emb = embed_query(query)

    client = get_client(chroma_dir)
    collection = get_or_create_collection(client)

    # Build where filter
    where_conditions = []
    if file_type:
        where_conditions.append({"type": {"$eq": file_type}})
    if date_from:
        where_conditions.append({"date": {"$gte": date_from}})
    if date_to:
        where_conditions.append({"date": {"$lte": date_to}})

    where = None
    if len(where_conditions) == 1:
        where = where_conditions[0]
    elif len(where_conditions) > 1:
        where = {"$and": where_conditions}

    raw = search(
        collection=collection,
        query_embedding=query_emb.tolist(),
        top_k=top_k,
        where=where,
    )

    results = []
    if raw["documents"] and raw["documents"][0]:
        for doc, meta, dist, id_ in zip(
            raw["documents"][0],
            raw["metadatas"][0],
            raw["distances"][0],
            raw["ids"][0],
        ):
            # ChromaDB returns cosine distance (0=identical, 2=opposite)
            # Convert to similarity score
            score = 1.0 - dist
            if score >= score_threshold:
                results.append(SearchResult(
                    text=doc,
                    metadata=meta,
                    score=score,
                    chunk_id=id_,
                ))

    return results


def format_results(results: list[SearchResult], max_length: int = 500) -> str:
    """Format search results for display."""
    if not results:
        return "검색 결과가 없습니다."

    parts = []
    for i, r in enumerate(results, 1):
        source = r.metadata.get("source_file", "unknown")
        date = r.metadata.get("date", "")
        slide = r.metadata.get("slide_number", "")

        location = source
        if date:
            location = f"{date} - {source}"
        if slide:
            location += f" (slide {slide})"

        text = r.text[:max_length] + "..." if len(r.text) > max_length else r.text

        parts.append(f"### [{i}] {location} (score: {r.score:.2f})\n{text}")

    return "\n\n---\n\n".join(parts)
