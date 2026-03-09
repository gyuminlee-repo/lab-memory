"""MCP server for Lab Memory integration with Claude Code."""
from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from lab_memory.query.retriever import retrieve, format_results
from lab_memory.index.store import get_client, get_or_create_collection


def _resolve_home() -> Path:
    """Resolve LAB_MEMORY_HOME (env var > project root)."""
    env = os.environ.get("LAB_MEMORY_HOME")
    if env:
        return Path(env)
    return Path(__file__).parent.parent


PROJECT_ROOT = _resolve_home()
CHROMA_DIR = PROJECT_ROOT / "data" / "chroma_db"
EXTRACTED_DIR = PROJECT_ROOT / "data" / "extracted"

server = Server("lab-memory")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_lab_notes",
            description="Search through lab weekly reports and papers. Supports Korean and English queries. Use for finding specific experiments, conditions, results, or protocols.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (Korean or English)"},
                    "top_k": {"type": "integer", "description": "Number of results (default: 10)", "default": 10},
                    "date_from": {"type": "string", "description": "Start date filter (YYYY-MM-DD)"},
                    "date_to": {"type": "string", "description": "End date filter (YYYY-MM-DD)"},
                    "file_type": {"type": "string", "enum": ["pptx", "pdf"], "description": "Filter by file type"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_slide",
            description="Get the full content of a specific slide from a lab report.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_file": {"type": "string", "description": "Source filename (e.g., '2024-01-15.json')"},
                    "slide_number": {"type": "integer", "description": "Slide number (1-based)"},
                },
                "required": ["source_file", "slide_number"],
            },
        ),
        Tool(
            name="summarize_topic",
            description="Search lab memory broadly for a research topic and return all relevant excerpts. Claude Code will synthesize the summary from the returned sources.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Research topic to summarize"},
                    "top_k": {"type": "integer", "description": "Number of sources to retrieve (default: 15)", "default": 15},
                },
                "required": ["topic"],
            },
        ),
        Tool(
            name="list_reports",
            description="List available extracted lab reports with dates and metadata.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                    "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                },
            },
        ),
        Tool(
            name="get_report_summary",
            description="Get a brief summary of a specific report file showing all slide titles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "JSON filename in extracted dir (e.g., '2024-01-15.json')"},
                },
                "required": ["filename"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "search_lab_notes":
        results = retrieve(
            query=arguments["query"],
            chroma_dir=str(CHROMA_DIR),
            top_k=arguments.get("top_k", 10),
            date_from=arguments.get("date_from"),
            date_to=arguments.get("date_to"),
            file_type=arguments.get("file_type"),
        )
        formatted = format_results(results)
        return [TextContent(type="text", text=formatted)]

    elif name == "get_slide":
        source = arguments["source_file"]
        slide_num = arguments["slide_number"]

        # Find the extracted JSON
        json_path = EXTRACTED_DIR / source
        if not json_path.suffix:
            json_path = json_path.with_suffix(".json")
        # Also try matching by stem
        if not json_path.exists():
            candidates = list(EXTRACTED_DIR.glob(f"*{source}*"))
            if candidates:
                json_path = candidates[0]

        if not json_path.exists():
            return [TextContent(type="text", text=f"Report not found: {source}")]

        data = json.loads(json_path.read_text(encoding="utf-8"))
        for slide in data.get("slides", []):
            if slide["slide_number"] == slide_num:
                parts = []
                if slide["title"]:
                    parts.append(f"# {slide['title']}")
                if slide["body"]:
                    parts.append(slide["body"])
                for table in slide.get("tables", []):
                    parts.append(table)
                if slide["notes"]:
                    parts.append(f"\n**Notes:** {slide['notes']}")
                return [TextContent(type="text", text="\n\n".join(parts) or "(empty slide)")]

        return [TextContent(type="text", text=f"Slide {slide_num} not found in {source}")]

    elif name == "summarize_topic":
        results = retrieve(
            query=arguments["topic"],
            chroma_dir=str(CHROMA_DIR),
            top_k=arguments.get("top_k", 15),
        )
        if not results:
            return [TextContent(type="text", text="해당 주제에 대한 자료를 찾을 수 없습니다.")]

        formatted = format_results(results, max_length=1000)
        header = f"## Topic: {arguments['topic']}\n\nFound {len(results)} relevant sources.\n\n"
        return [TextContent(type="text", text=header + formatted)]

    elif name == "list_reports":
        if not EXTRACTED_DIR.exists():
            return [TextContent(type="text", text="No extracted reports found. Run 'lab-memory ingest' first.")]

        reports = []
        for json_file in sorted(EXTRACTED_DIR.glob("*.json")):
            data = json.loads(json_file.read_text(encoding="utf-8"))
            date = data.get("date", "unknown")
            src = data.get("source_file", json_file.name)
            total = data.get("total_slides") or data.get("total_pages", 0)
            doc_type = data.get("type", "unknown")

            # Apply date filters
            date_from = arguments.get("date_from")
            date_to = arguments.get("date_to")
            if date and date != "unknown":
                if date_from and date < date_from:
                    continue
                if date_to and date > date_to:
                    continue

            reports.append(f"- {date} | {src} | {doc_type} | {total} slides/pages")

        if not reports:
            return [TextContent(type="text", text="No reports found matching the criteria.")]

        header = f"Found {len(reports)} reports:\n\n"
        return [TextContent(type="text", text=header + "\n".join(reports))]

    elif name == "get_report_summary":
        filename = arguments["filename"]
        json_path = EXTRACTED_DIR / filename
        if not json_path.exists():
            return [TextContent(type="text", text=f"Report not found: {filename}")]

        data = json.loads(json_path.read_text(encoding="utf-8"))
        parts = [f"# {data.get('source_file', filename)}"]
        if data.get("date"):
            parts.append(f"Date: {data['date']}")
        parts.append(f"Type: {data.get('type', 'unknown')}")

        if data.get("type") == "pptx":
            parts.append(f"\n## Slides ({data.get('total_slides', 0)} total)")
            for slide in data.get("slides", []):
                title = slide.get("title", "(no title)")
                has_table = "\U0001f4ca" if slide.get("tables") else ""
                has_notes = "\U0001f4dd" if slide.get("notes") else ""
                parts.append(f"  {slide['slide_number']}. {title} {has_table}{has_notes}")
        elif data.get("type") == "pdf":
            parts.append(f"\nTotal pages: {data.get('total_pages', 0)}")

        return [TextContent(type="text", text="\n".join(parts))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
