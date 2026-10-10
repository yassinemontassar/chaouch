"""Usage: uv run tasks.py fetch|clean|chunk|ingest [--force]"""

from __future__ import annotations

import argparse
import sys

import httpx2

from chaouch.config import ROOT, load_retrieval_config
from chaouch.ingestion.chunk import chunk_all
from chaouch.ingestion.clean import CleanError, clean_document
from chaouch.ingestion.fetch import Fetcher
from chaouch.ingestion.sources import load_sources
from chaouch.ingestion.tokens import hf_token_counter
from chaouch.log import setup_logging

RAW_DIR = ROOT / "data" / "documents" / "raw"
PROCESSED_DIR = ROOT / "data" / "documents" / "processed"


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest official documents.")
    parser.add_argument("stage", choices=["fetch", "clean", "chunk", "all"])
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    args = parser.parse_args()
    setup_logging()

    cfg = load_retrieval_config()
    sources = load_sources()
    if not sources:
        print("data/documents/sources.yaml has no sources yet ([HUMAN] task).")
        return 0
    failed = 0

    if args.stage in ("fetch", "all"):
        with httpx2.Client() as client:
            fetcher = Fetcher(cfg.ingestion, client)
            results = [fetcher.fetch(s, RAW_DIR, force=args.force) for s in sources]
        for r in results:
            print(f"fetch {r.doc_id}: {r.status} {r.detail}")
        failed += sum(r.status in ("blocked", "failed") for r in results)

    if args.stage in ("clean", "all"):
        for source in sources:
            try:
                out = clean_document(source, RAW_DIR, PROCESSED_DIR)
                print(f"clean {source.doc_id}: {out.name}")
            except (CleanError, FileNotFoundError) as exc:
                print(f"clean {source.doc_id}: FAILED {exc}")
                failed += 1

    if args.stage in ("chunk", "all"):
        count = hf_token_counter(cfg.chunking.tokenizer)
        out, missing = chunk_all(sources, PROCESSED_DIR, cfg.chunking, count)
        n = sum(1 for _ in out.open(encoding="utf-8"))
        print(f"chunk: {n} chunks -> {out.relative_to(ROOT)}")
        for doc_id in missing:
            print(f"chunk {doc_id}: MISSING (run clean first)")
        failed += len(missing)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
