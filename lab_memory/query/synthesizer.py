"""Answer synthesis using Claude API."""
from __future__ import annotations

import os

from anthropic import Anthropic

from lab_memory.query.retriever import SearchResult


def synthesize_answer(
    query: str,
    results: list[SearchResult],
    mode: str = "search",
) -> str:
    """Synthesize an answer from search results using Claude API.

    Args:
        query: Original user query
        results: Retrieved search results
        mode: "search" for specific facts, "summarize" for topic overview
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Fall back to just returning formatted results
        from lab_memory.query.retriever import format_results
        return format_results(results)

    client = Anthropic(api_key=api_key)

    # Build context from results
    context_parts = []
    for i, r in enumerate(results, 1):
        source = r.metadata.get("source_file", "unknown")
        date = r.metadata.get("date", "")
        header = f"[Source {i}: {source}"
        if date:
            header += f", {date}"
        header += f", score={r.score:.2f}]"
        context_parts.append(f"{header}\n{r.text}")

    context = "\n\n---\n\n".join(context_parts)

    if mode == "summarize":
        system_prompt = (
            "You are a research assistant helping to summarize lab knowledge. "
            "Based on the provided lab report excerpts, create a comprehensive "
            "summary of the topic. Include specific experimental conditions, "
            "results, and key findings. Cite sources using [Source N] format. "
            "Respond in the same language as the query."
        )
    else:
        system_prompt = (
            "You are a research assistant helping to find specific information "
            "from lab reports. Based on the provided excerpts, answer the "
            "question precisely. Cite sources using [Source N] format. "
            "If the information is not found in the excerpts, say so clearly. "
            "Respond in the same language as the query."
        )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": f"## Question\n{query}\n\n## Lab Report Excerpts\n{context}",
        }],
    )

    return response.content[0].text
