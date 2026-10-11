from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from chaouch.config import BM25Config


@dataclass(frozen=True)
class BM25:
    """Okapi BM25 with Lucene's idf, which stays positive for terms found in most documents
    (rank_bm25's Okapi idf goes negative there, a real case in a corpus of a few dozen chunks)."""

    term_freqs: list[Counter[str]]
    lengths: list[int]
    idf: dict[str, float]
    avg_length: float
    k1: float
    b: float

    @classmethod
    def build(cls, docs: Sequence[Sequence[str]], cfg: BM25Config) -> BM25:
        n = len(docs)
        doc_freq = Counter(term for doc in docs for term in set(doc))
        idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in doc_freq.items()}
        lengths = [len(doc) for doc in docs]
        avg = sum(lengths) / n if n else 0.0
        return cls([Counter(d) for d in docs], lengths, idf, avg or 1.0, cfg.k1, cfg.b)

    def scores(self, query: Sequence[str]) -> list[float]:
        out = []
        for tf, length in zip(self.term_freqs, self.lengths, strict=True):
            norm = self.k1 * (1 - self.b + self.b * length / self.avg_length)
            out.append(
                sum(self.idf[t] * tf[t] * (self.k1 + 1) / (tf[t] + norm) for t in query if t in tf)
            )
        return out

    def rank(self, query: Sequence[str], n: int) -> list[int]:
        """Indices of the top n documents with a positive score (ties: lower index first).
        A query sharing no term with the corpus returns []."""
        scores = self.scores(query)
        ranked = sorted((i for i, s in enumerate(scores) if s > 0), key=lambda i: (-scores[i], i))
        return ranked[:n]
