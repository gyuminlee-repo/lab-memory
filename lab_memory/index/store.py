"""ChromaDB vector store management."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings


def get_client(persist_dir: str | Path = "data/chroma_db") -> chromadb.ClientAPI:
    """Get or create a persistent ChromaDB client."""
    return chromadb.PersistentClient(
        path=str(persist_dir),
        settings=Settings(anonymized_telemetry=False),
    )


def get_or_create_collection(
    client: chromadb.ClientAPI,
    name: str = "lab_memory",
) -> chromadb.Collection:
    """Get or create the main collection."""
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def _sanitize_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Remove None values from metadata (ChromaDB rejects them)."""
    return {k: v for k, v in meta.items() if v is not None}


def add_chunks(
    collection: chromadb.Collection,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, Any]],
    batch_size: int = 1000,
) -> int:
    """Add chunks to collection in batches."""
    clean_metadatas = [_sanitize_metadata(m) for m in metadatas]
    total = len(ids)
    for i in range(0, total, batch_size):
        end = min(i + batch_size, total)
        collection.add(
            ids=ids[i:end],
            embeddings=embeddings[i:end],
            documents=documents[i:end],
            metadatas=clean_metadatas[i:end],
        )
    return total


def search(
    collection: chromadb.Collection,
    query_embedding: list[float],
    top_k: int = 10,
    where: dict | None = None,
) -> dict[str, Any]:
    """Search the collection."""
    kwargs: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    return collection.query(**kwargs)


def get_collection_stats(collection: chromadb.Collection) -> dict[str, Any]:
    """Get basic stats about the collection."""
    return {
        "name": collection.name,
        "count": collection.count(),
    }
