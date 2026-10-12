import pytest

from chaouch.retrieval.fusion import rrf


def test_item_in_both_rankings_wins() -> None:
    assert rrf([["a", "b", "c"], ["b", "d"]], k=60) == ["b", "a", "d", "c"]


def test_item_found_by_one_retriever_only_is_kept() -> None:
    assert rrf([["a"], []], k=60) == ["a"]
    assert rrf([[], ["z"]], k=60) == ["z"]


def test_ties_keep_first_seen_order() -> None:
    # a and x both sit at rank 1 in one list each: equal scores
    assert rrf([["a"], ["x"]], k=60) == ["a", "x"]


def test_hand_computed_scores_decide_order() -> None:
    # c: 1/(1+3) + 1/(1+1) = 0.75 ; a: 1/(1+1) = 0.5 ; b: 1/(1+2) + 1/(1+2) = 0.667
    assert rrf([["a", "b", "c"], ["c", "b"]], k=1) == ["c", "b", "a"]


@pytest.mark.parametrize("rankings", [[], [[], []]])
def test_empty(rankings: list[list[str]]) -> None:
    assert rrf(rankings, k=60) == []
