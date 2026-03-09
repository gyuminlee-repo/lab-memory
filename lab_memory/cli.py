"""CLI for Lab Memory system."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click
import yaml


def _get_home(ctx: click.Context | None = None) -> Path:
    """Resolve lab-memory home directory.

    Priority: --home flag > LAB_MEMORY_HOME env var > package root.
    """
    if ctx and ctx.obj and ctx.obj.get("home"):
        return Path(ctx.obj["home"])
    env = os.environ.get("LAB_MEMORY_HOME")
    if env:
        return Path(env)
    return Path(__file__).parent.parent


def _load_config(home: Path) -> dict:
    """Load settings from configs/settings.yaml."""
    config_path = home / "configs" / "settings.yaml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    # Fallback to package bundled config
    pkg_config = Path(__file__).parent.parent / "configs" / "settings.yaml"
    if pkg_config.exists():
        with open(pkg_config, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def _resolve_path(home: Path, config: dict, key: str, default: str) -> Path:
    """Resolve a path from config relative to home directory."""
    path_str = config.get("paths", {}).get(key, default)
    return home / path_str


@click.group()
@click.option("--home", envvar="LAB_MEMORY_HOME", default=None,
              type=click.Path(), help="Lab Memory home directory (default: package root or LAB_MEMORY_HOME)")
@click.pass_context
def cli(ctx, home):
    """Lab Memory - Local RAG system for lab reports."""
    ctx.ensure_object(dict)
    ctx.obj["home"] = home


@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
@click.option("--output-dir", "-o", type=click.Path(), default=None, help="Output directory for extracted JSON")
@click.option("--workers", "-w", type=int, default=None, help="Number of parallel workers")
@click.option("--exclude", "-x", multiple=True, help="Exclude paths containing this pattern (case-insensitive)")
@click.pass_context
def extract(ctx, input_dir: str, output_dir: str | None, workers: int | None, exclude: tuple[str, ...]):
    """Extract text from PPTX/PDF files."""
    home = _get_home(ctx)
    config = _load_config(home)
    out = Path(output_dir) if output_dir else _resolve_path(home, config, "extracted_dir", "data/extracted")
    in_path = Path(input_dir)
    exclude_list = list(exclude)

    click.echo(f"Home: {home}")
    click.echo(f"Extracting from: {in_path}")
    click.echo(f"Output to: {out}")
    if exclude_list:
        click.echo(f"Excluding: {exclude_list}")

    # Extract PPTX files
    from lab_memory.extract.pptx_extractor import extract_all as extract_pptx_all
    pptx_results = extract_pptx_all(in_path, out, workers=workers, exclude_patterns=exclude_list)

    pptx_ok = [r for r in pptx_results if not r.startswith("ERROR:")]
    pptx_err = [r for r in pptx_results if r.startswith("ERROR:")]
    click.echo(f"PPTX: {len(pptx_ok)} extracted, {len(pptx_err)} errors")
    for err in pptx_err:
        click.echo(f"  {err}", err=True)

    # Extract PDF files
    from lab_memory.extract.pdf_extractor import extract_pdf_to_json
    exclude_lower = [p.lower() for p in exclude_list]
    pdf_files = sorted(
        Path(os.path.join(root, f))
        for root, _, files in os.walk(in_path, followlinks=True)
        if not any(ex in root.lower() for ex in exclude_lower)
        for f in files
        if f.lower().endswith(".pdf")
    )
    pdf_ok, pdf_err = 0, 0
    for pdf_path in pdf_files:
        try:
            extract_pdf_to_json(pdf_path, out)
            pdf_ok += 1
        except Exception as e:
            click.echo(f"  ERROR:{pdf_path}:{e}", err=True)
            pdf_err += 1

    click.echo(f"PDF: {pdf_ok} extracted, {pdf_err} errors")
    click.echo(f"Total: {len(pptx_ok) + pdf_ok} files extracted")


@cli.command()
@click.option("--extracted-dir", "-e", type=click.Path(), default=None)
@click.option("--chroma-dir", "-c", type=click.Path(), default=None)
@click.option("--batch-size", "-b", type=int, default=64)
@click.pass_context
def index(ctx, extracted_dir: str | None, chroma_dir: str | None, batch_size: int):
    """Index extracted JSON files into ChromaDB."""
    home = _get_home(ctx)
    config = _load_config(home)
    ext_dir = Path(extracted_dir) if extracted_dir else _resolve_path(home, config, "extracted_dir", "data/extracted")
    chr_dir = Path(chroma_dir) if chroma_dir else _resolve_path(home, config, "chroma_dir", "data/chroma_db")

    model_name = config.get("embedding", {}).get("model_name", "intfloat/multilingual-e5-large")
    min_length = config.get("chunking", {}).get("min_chunk_length", 100)
    max_tokens = config.get("chunking", {}).get("max_chunk_tokens", 512)
    overlap = config.get("chunking", {}).get("overlap_tokens", 50)

    # Chunk all files
    from lab_memory.index.chunker import chunk_file
    json_files = sorted(ext_dir.glob("*.json"))

    if not json_files:
        click.echo("No extracted JSON files found.")
        return

    click.echo(f"Chunking {len(json_files)} files...")
    all_chunks = []
    for jf in json_files:
        chunks = chunk_file(jf, min_length=min_length, max_tokens=max_tokens, overlap_tokens=overlap)
        all_chunks.extend(chunks)

    click.echo(f"Generated {len(all_chunks)} chunks")

    if not all_chunks:
        click.echo("No chunks generated.")
        return

    # Embed
    click.echo(f"Embedding with {model_name} (batch_size={batch_size})...")
    from lab_memory.index.embedder import embed_texts
    texts = [c.text for c in all_chunks]
    embeddings = embed_texts(texts, model_name=model_name, batch_size=batch_size)

    # Store
    click.echo(f"Storing in ChromaDB at {chr_dir}...")
    from lab_memory.index.store import get_client, get_or_create_collection, add_chunks
    client = get_client(chr_dir)
    collection = get_or_create_collection(client)

    ids = [c.chunk_id for c in all_chunks]
    metadatas = [c.metadata for c in all_chunks]

    count = add_chunks(
        collection,
        ids=ids,
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=metadatas,
    )
    click.echo(f"Indexed {count} chunks into ChromaDB")


@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
@click.option("--workers", "-w", type=int, default=None)
@click.option("--batch-size", "-b", type=int, default=64)
@click.option("--exclude", "-x", multiple=True, help="Exclude paths containing this pattern (case-insensitive)")
@click.pass_context
def ingest(ctx, input_dir: str, workers: int | None, batch_size: int, exclude: tuple[str, ...]):
    """Extract and index in one step."""
    home = _get_home(ctx)
    config = _load_config(home)
    ext_dir = _resolve_path(home, config, "extracted_dir", "data/extracted")
    chr_dir = _resolve_path(home, config, "chroma_dir", "data/chroma_db")
    exclude_list = list(exclude)

    # Step 1: Extract
    click.echo(f"Home: {home}")
    click.echo("=== Phase 1: Extraction ===")
    if exclude_list:
        click.echo(f"Excluding: {exclude_list}")
    in_path = Path(input_dir)

    from lab_memory.extract.pptx_extractor import extract_all as extract_pptx_all
    from lab_memory.extract.pdf_extractor import extract_pdf_to_json

    pptx_results = extract_pptx_all(in_path, ext_dir, workers=workers, exclude_patterns=exclude_list)
    pptx_ok = [r for r in pptx_results if not r.startswith("ERROR:")]
    pptx_err = [r for r in pptx_results if r.startswith("ERROR:")]
    click.echo(f"PPTX: {len(pptx_ok)} extracted, {len(pptx_err)} errors")

    exclude_lower = [p.lower() for p in exclude_list]
    pdf_files = sorted(
        Path(os.path.join(root, f))
        for root, _, files in os.walk(in_path, followlinks=True)
        if not any(ex in root.lower() for ex in exclude_lower)
        for f in files
        if f.lower().endswith(".pdf")
    )
    pdf_ok = 0
    for pdf_path in pdf_files:
        try:
            extract_pdf_to_json(pdf_path, ext_dir)
            pdf_ok += 1
        except Exception as e:
            click.echo(f"  ERROR:{pdf_path}:{e}", err=True)
    click.echo(f"PDF: {pdf_ok} extracted")

    # Step 2: Index
    click.echo("\n=== Phase 2: Indexing ===")
    model_name = config.get("embedding", {}).get("model_name", "intfloat/multilingual-e5-large")
    min_length = config.get("chunking", {}).get("min_chunk_length", 100)
    max_tokens = config.get("chunking", {}).get("max_chunk_tokens", 512)
    overlap = config.get("chunking", {}).get("overlap_tokens", 50)

    from lab_memory.index.chunker import chunk_file
    from lab_memory.index.embedder import embed_texts
    from lab_memory.index.store import get_client, get_or_create_collection, add_chunks

    json_files = sorted(ext_dir.glob("*.json"))
    all_chunks = []
    for jf in json_files:
        all_chunks.extend(chunk_file(jf, min_length=min_length, max_tokens=max_tokens, overlap_tokens=overlap))

    click.echo(f"Generated {len(all_chunks)} chunks")

    if not all_chunks:
        return

    texts = [c.text for c in all_chunks]
    click.echo(f"Embedding {len(texts)} chunks...")
    embeddings = embed_texts(texts, model_name=model_name, batch_size=batch_size)

    client = get_client(chr_dir)
    collection = get_or_create_collection(client)
    count = add_chunks(
        collection,
        ids=[c.chunk_id for c in all_chunks],
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=[c.metadata for c in all_chunks],
    )
    click.echo(f"Indexed {count} chunks into ChromaDB")


@cli.command()
@click.argument("query")
@click.option("--top-k", "-k", type=int, default=10)
@click.option("--date-from", type=str, default=None)
@click.option("--date-to", type=str, default=None)
@click.option("--type", "file_type", type=click.Choice(["pptx", "pdf"]), default=None)
@click.option("--synthesize/--no-synthesize", default=False, help="Use Claude API to synthesize answer (requires ANTHROPIC_API_KEY)")
@click.pass_context
def search(ctx, query: str, top_k: int, date_from: str | None, date_to: str | None, file_type: str | None, synthesize: bool):
    """Search lab memory."""
    home = _get_home(ctx)
    config = _load_config(home)
    chroma_dir = _resolve_path(home, config, "chroma_dir", "data/chroma_db")
    threshold = config.get("search", {}).get("score_threshold", 0.3)

    from lab_memory.query.retriever import retrieve, format_results

    results = retrieve(
        query=query,
        chroma_dir=str(chroma_dir),
        top_k=top_k,
        date_from=date_from,
        date_to=date_to,
        file_type=file_type,
        score_threshold=threshold,
    )

    if synthesize and results:
        from lab_memory.query.synthesizer import synthesize_answer
        answer = synthesize_answer(query, results, mode="search")
        click.echo(answer)
        click.echo(f"\n---\nBased on {len(results)} sources")
    else:
        click.echo(format_results(results))


@cli.command()
@click.pass_context
def stats(ctx):
    """Show index statistics."""
    home = _get_home(ctx)
    config = _load_config(home)
    chroma_dir = _resolve_path(home, config, "chroma_dir", "data/chroma_db")
    ext_dir = _resolve_path(home, config, "extracted_dir", "data/extracted")

    click.echo(f"Home: {home}")

    # Extracted files
    json_files = list(ext_dir.glob("*.json")) if ext_dir.exists() else []
    click.echo(f"Extracted files: {len(json_files)}")

    # ChromaDB stats
    if chroma_dir.exists():
        from lab_memory.index.store import get_client, get_or_create_collection, get_collection_stats
        client = get_client(chroma_dir)
        collection = get_or_create_collection(client)
        s = get_collection_stats(collection)
        click.echo(f"ChromaDB collection '{s['name']}': {s['count']} chunks")
    else:
        click.echo("ChromaDB: not initialized")


@cli.command()
@click.pass_context
def serve(ctx):
    """Start MCP server."""
    import asyncio
    from lab_memory.mcp_server import main
    asyncio.run(main())


@cli.command()
@click.argument("target_dir", type=click.Path())
@click.pass_context
def init(ctx, target_dir: str):
    """Initialize a new lab-memory workspace with default config."""
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    # Create directory structure
    (target / "data" / "raw").mkdir(parents=True, exist_ok=True)
    (target / "data" / "extracted").mkdir(parents=True, exist_ok=True)
    (target / "data" / "chroma_db").mkdir(parents=True, exist_ok=True)
    (target / "configs").mkdir(parents=True, exist_ok=True)

    # Copy default config
    pkg_config = Path(__file__).parent.parent / "configs" / "settings.yaml"
    dest_config = target / "configs" / "settings.yaml"
    if not dest_config.exists() and pkg_config.exists():
        dest_config.write_text(pkg_config.read_text(encoding="utf-8"), encoding="utf-8")

    click.echo(f"Initialized lab-memory workspace at: {target}")
    click.echo(f"  data/raw/         ← put your PPT/PDF files here")
    click.echo(f"  data/extracted/   ← extracted JSON (auto-generated)")
    click.echo(f"  data/chroma_db/   ← vector DB (auto-generated)")
    click.echo(f"  configs/          ← settings.yaml")
    click.echo(f"\nUsage:")
    click.echo(f"  lab-memory --home {target} ingest {target / 'data' / 'raw'}")
    click.echo(f"  lab-memory --home {target} search \"query\"")


if __name__ == "__main__":
    cli()
