"""Does stripping Arabic diacritics from the question help dense retrieval? (ADR 0013)

For the Arabic-script in-scope questions: R@1 and MRR of each embedder on the full corpus, with the
question as written and with every Unicode combining mark removed (query side only; the stored chunk
vectors are unchanged). Same metric definitions as eval-retrieval.

Usage: uv run python -m scripts.query_diacritics_check   (after `uv run tasks.py index`)
"""

from __future__ import annotations

import sys
import unicodedata

import numpy as np

from chaouch.config import Settings, load_retrieval_config
from chaouch.retrieval.chunks import load_chunks
from chaouch.retrieval.models import load_embedder, release_models
from chaouch.retrieval.store import assert_fresh, chunk_vectors, connect
from evals.gold import load_gold
from evals.metrics.retrieval import recall_at_k, reciprocal_rank


def strip_marks(text: str) -> str:
    """Remove combining marks only (shadda, harakat, hamza/madda on alef); no other folding."""
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def main() -> int:
    cfg = load_retrieval_config().retrieval
    chunks, sha = load_chunks()
    doc_of = {c.chunk_id: c.doc_id for c in chunks}
    questions = [q for q in load_gold() if q.category == "in_scope" and q.script == "arabic"]
    with_marks = sum(strip_marks(q.question) != q.question for q in questions)
    print(f"{len(questions)} Arabic-script questions, {with_marks} with diacritics")

    with connect(Settings().database_dsn()) as conn:
        for key in cfg.embedders:
            assert_fresh(conn, key, sha)
            stored = chunk_vectors(conn, key)
            ids = list(stored)
            matrix = np.stack([stored[i] for i in ids])
            embedder = load_embedder(cfg, key)
            for label, prepare in (("as written", lambda t: t), ("no diacritics", strip_marks)):
                vectors = embedder.embed_queries([prepare(q.question) for q in questions])
                r1 = rr = 0.0
                for q, vector in zip(questions, vectors, strict=True):
                    docs = [
                        doc_of[ids[i]] for i in np.argsort(-(matrix @ vector))[: cfg.candidates]
                    ]
                    r1 += recall_at_k(docs, q.gold_doc_ids, 1)
                    rr += reciprocal_rank(docs, q.gold_doc_ids)
                n = len(questions)
                print(f"{key:15} {label:14} R@1 {r1 / n:.2f}  MRR {rr / n:.2f}")
            release_models()
    return 0


if __name__ == "__main__":
    sys.exit(main())
