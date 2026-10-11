"""Pre-check for distractor documents (ADR 0013): could a distractor answer a gold question?

For every in-scope question, the reranker scores (question + required facts) against every chunk
of the question's gold documents and every distractor chunk. A distractor chunk scoring at least as
high as the best gold chunk is flagged for a human read. This screens; it does not decide.

Usage: uv run python -m scripts.distractor_check   (after `uv run tasks.py ingest`)
"""

from __future__ import annotations

import sys

from chaouch.config import load_retrieval_config
from chaouch.retrieval.chunks import indexed_text, load_chunks
from chaouch.retrieval.models import load_reranker
from evals.gold import load_gold

TOP = 3


def main() -> int:
    cfg = load_retrieval_config().retrieval
    chunks, _ = load_chunks()
    distractors = [c for c in chunks if c.role == "distractor"]
    if not distractors:
        print("no distractor chunks in chunks.jsonl")
        return 0
    rerank = load_reranker(cfg)
    flagged = []
    for q in (q for q in load_gold() if q.category == "in_scope"):
        query = f"{q.question}\n" + "; ".join(q.required_facts)
        gold = [c for c in chunks if c.doc_id in q.gold_doc_ids]
        scores = rerank(query, [indexed_text(c) for c in [*gold, *distractors]])
        best_gold = max(scores[: len(gold)])
        ranked = sorted(zip(scores[len(gold) :], distractors, strict=True), key=lambda p: -p[0])
        top = ", ".join(f"{c.chunk_id} {s:+.2f}" for s, c in ranked[:TOP])
        hits = [(s, c) for s, c in ranked if s >= best_gold]
        mark = "FLAG" if hits else "ok  "
        print(f"{mark} {q.id:10} best gold {best_gold:+.2f} | top distractors: {top}")
        flagged += [(q.id, c.chunk_id, s, best_gold) for s, c in hits]
    print(f"\n{len(flagged)} flagged (question, distractor chunk) pairs")
    for qid, chunk_id, score, best in flagged:
        print(f"  {qid}: {chunk_id} {score:+.2f} >= best gold {best:+.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
