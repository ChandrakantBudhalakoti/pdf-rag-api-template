"""Command-line interface.

    python -m rag_pipeline.cli status            # database / pgvector / index check (no OpenAI needed)
    python -m rag_pipeline.cli ingest            # PDFs -> chunks -> embeddings -> pgvector
    python -m rag_pipeline.cli search "query"    # show retrieved chunks only (no LLM)
    python -m rag_pipeline.cli ask "question"    # full RAG answer with sources
    python -m rag_pipeline.cli chat              # ask repeatedly; type 'exit' to quit
"""

from __future__ import annotations

import argparse
import logging
import sys
import warnings

from rag_pipeline.config import ConfigError, Settings
from rag_pipeline.ingestion import IngestionError
from rag_pipeline.pipeline import LLMError, RagAnswer, RagPipeline, ingest
from rag_pipeline.vectorstore import DatabaseError, get_status

# Third-party libraries emit Python 3.14 deprecation noise that is irrelevant to users.
warnings.filterwarnings("ignore", category=DeprecationWarning)


def _print_answer(result: RagAnswer, show_chunks: bool) -> None:
    print(f"\nAnswer: {result.answer}")
    if result.references:
        print("Sources:")
        for ref in result.references:
            print(f"  - {ref}")
    elif result.found:
        print("Sources: (the model did not cite specific excerpts)")
    if show_chunks:
        print("\nRetrieved chunks (closest first, cosine distance):")
        for i, c in enumerate(result.retrieved, start=1):
            preview = " ".join(c.document.page_content.split())[:160]
            print(f"  [{i}] {c.reference}  d={c.distance:.3f}  {preview}...")


def cmd_status(settings: Settings, _args: argparse.Namespace) -> int:
    print(f"AI provider:      {settings.provider}")
    print(f"Collection:       {settings.collection_name}")
    print(f"Embedding model:  {settings.embedding_model}")
    print(f"LLM model:        {settings.llm_model}")
    print(f"Chunk size/overlap: {settings.chunk_size}/{settings.chunk_overlap}   top_k: {settings.top_k}")
    print(f"{settings.provider} API key: {'set' if settings.has_api_key else 'NOT SET'}")
    status = get_status(settings)
    print(f"PostgreSQL:       {status.server_version} (connected)")
    print(f"pgvector:         {status.pgvector_version or 'NOT ENABLED (runs automatically on ingest)'}")
    if not status.collection_exists:
        print("Index:            empty - run: python -m rag_pipeline.cli ingest")
        return 0
    meta = status.collection_metadata or {}
    print(f"Indexed with:     {meta.get('embedding_model')} "
          f"({meta.get('embedding_dimensions')} dims), chunk {meta.get('chunk_size')}/{meta.get('chunk_overlap')}")
    print(f"Stored chunks:    {sum(status.chunk_counts.values())}")
    for source, count in status.chunk_counts.items():
        print(f"  - {source}: {count} chunks")
    return 0


def cmd_ingest(settings: Settings, args: argparse.Namespace) -> int:
    print(f"Ingesting PDFs from {settings.pdf_dir}")
    print(f"  chunk_size={settings.chunk_size} chunk_overlap={settings.chunk_overlap} "
          f"embedding_model={settings.embedding_model}")
    result = ingest(settings, min_documents=args.min_docs)
    print(f"Done: {len(result.files)} files, {result.pages} pages, {result.chunks} chunks "
          f"stored in collection '{settings.collection_name}'.")
    for name in result.files:
        print(f"  - {name}")
    return 0


def cmd_search(settings: Settings, args: argparse.Namespace) -> int:
    pipeline = RagPipeline(settings)
    for i, c in enumerate(pipeline.search(args.query, args.k), start=1):
        print(f"\n[{i}] {c.reference}  (cosine distance {c.distance:.3f})")
        print(c.document.page_content)
    return 0


def cmd_ask(settings: Settings, args: argparse.Namespace) -> int:
    pipeline = RagPipeline(settings)
    _print_answer(pipeline.ask(args.question, args.k), args.show_chunks)
    return 0


def cmd_chat(settings: Settings, args: argparse.Namespace) -> int:
    pipeline = RagPipeline(settings)
    print("Ask questions about the ingested documents. Type 'exit' to quit.")
    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if question.lower() in {"exit", "quit"}:
            return 0
        if not question:
            continue
        try:
            _print_answer(pipeline.ask(question, args.k), args.show_chunks)
        except (LLMError, DatabaseError) as exc:
            print(f"Error: {exc}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m rag_pipeline.cli", description="RAG Pipeline as a Service (CLI)")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="check database, pgvector and the index")

    p = sub.add_parser("ingest", help="load PDFs, chunk, embed and store in pgvector")
    p.add_argument("--min-docs", type=int, default=3, help="minimum number of PDFs required (default 3)")

    p = sub.add_parser("search", help="similarity search only (no LLM)")
    p.add_argument("query")
    p.add_argument("-k", type=int, default=None, help="number of chunks (default TOP_K)")

    for name, help_text in (("ask", "answer one question"), ("chat", "interactive question loop")):
        p = sub.add_parser(name, help=help_text)
        if name == "ask":
            p.add_argument("question")
        p.add_argument("-k", type=int, default=None, help="number of chunks to retrieve (default TOP_K)")
        p.add_argument("--show-chunks", action="store_true", help="also print the retrieved chunks")
    return parser


COMMANDS = {"status": cmd_status, "ingest": cmd_ingest, "search": cmd_search, "ask": cmd_ask, "chat": cmd_chat}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    try:
        settings = Settings.from_env()
        return COMMANDS[args.command](settings, args)
    except (ConfigError, IngestionError, DatabaseError, LLMError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
