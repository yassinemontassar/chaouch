"""Real retrieval models on CPU. Downloads them on first run (~6 GB in the Hugging Face cache)."""

import numpy as np
import pytest

from chaouch.config import load_retrieval_config
from chaouch.retrieval.models import load_embedder, load_reranker, release_models

pytestmark = pytest.mark.integration

CFG = load_retrieval_config().retrieval
# A sanity check that each model loads and matches across languages, in MSA ("how much does the
# passport cost?"). Derja quality is measured by eval-retrieval, not here: bge-m3 ranks the Derja
# "قدّاش يكلّف الباسبور؟" closer to UNRELATED than to RELEVANT (ADR 0013).
QUERY = "كم تبلغ تكلفة جواز السفر؟"
RELEVANT = "Passeport : timbre fiscal de 80 dinars pour la délivrance ou le renouvellement."
UNRELATED = "Le compteur d'eau est déplacé à la demande de l'abonné."


@pytest.mark.parametrize("key", list(CFG.embedders))
def test_embedder_returns_unit_vectors_and_matches_across_languages(key: str) -> None:
    embedder = load_embedder(CFG, key)
    docs = embedder.embed_docs([RELEVANT, UNRELATED])
    (query,) = embedder.embed_queries([QUERY])
    release_models()
    assert docs.shape == (2, CFG.embedders[key].dim)
    assert np.allclose(np.linalg.norm(docs, axis=1), 1, atol=1e-3)
    assert query @ docs[0] > query @ docs[1]


def test_reranker_prefers_the_relevant_passage() -> None:
    relevant, unrelated = load_reranker(CFG)(QUERY, [RELEVANT, UNRELATED])
    release_models()
    assert relevant > unrelated
