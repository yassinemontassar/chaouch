import math

import pytest

from chaouch.config import BM25Config
from chaouch.retrieval.bm25 import BM25

CFG = BM25Config(k1=1.2, b=0.75)
DOCS = [
    ["passeport", "timbre", "80", "dinars"],
    ["carte", "identite", "timbre", "3", "dinars"],
    ["bulletin", "3", "casier"],
]


def test_idf_stays_positive_for_a_term_in_every_doc() -> None:
    index = BM25.build([["a", "b"], ["a"], ["a", "c"]], CFG)
    assert index.idf["a"] == pytest.approx(math.log(1 + 0.5 / 3.5))
    assert index.idf["a"] > 0


def test_rank_orders_by_score_and_drops_zero_scores() -> None:
    index = BM25.build(DOCS, CFG)
    assert index.rank(["passeport"], 5) == [0]
    assert index.rank(["timbre", "carte"], 5) == [1, 0]
    assert index.rank(["introuvable"], 5) == []


def test_shorter_document_wins_on_equal_term_frequency() -> None:
    index = BM25.build([["x", "y", "z", "w"], ["x", "y"]], CFG)
    assert index.rank(["x"], 2) == [1, 0]


def test_ties_keep_document_order_and_n_is_honored() -> None:
    index = BM25.build([["a"], ["a"], ["a"]], CFG)
    assert index.rank(["a"], 2) == [0, 1]


def test_hand_computed_score() -> None:
    index = BM25.build(DOCS, CFG)
    avg = (4 + 5 + 3) / 3
    idf = math.log(1 + (3 - 1 + 0.5) / (1 + 0.5))
    expected = idf * 1 * 2.2 / (1 + 1.2 * (1 - 0.75 + 0.75 * 4 / avg))
    assert index.scores(["passeport"])[0] == pytest.approx(expected)
