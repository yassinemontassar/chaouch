"""Embedding and reranking models, on CPU (spec 3.1.2). Loaded lazily, once per process."""

from __future__ import annotations

import functools
import gc
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from sentence_transformers import CrossEncoder, SentenceTransformer

from chaouch.config import SearchConfig

Vectors = NDArray[np.float32]
Rerank = Callable[[str, list[str]], list[float]]


@dataclass(frozen=True)
class Embedder:
    embed_docs: Callable[[list[str]], Vectors]
    embed_queries: Callable[[list[str]], Vectors]


@functools.cache
def _sentence_transformer(name: str, device: str) -> SentenceTransformer:
    return SentenceTransformer(name, device=device)


@functools.cache
def _cross_encoder(name: str, device: str, max_length: int) -> CrossEncoder:
    model: CrossEncoder = CrossEncoder(name, device=device, max_length=max_length)  # stub: Any
    return model


def load_embedder(cfg: SearchConfig, key: str) -> Embedder:
    ecfg = cfg.embedders[key]
    model = _sentence_transformer(ecfg.name, cfg.device)

    def encode(texts: list[str], prompt_name: str | None) -> Vectors:
        vectors = model.encode(
            texts,
            prompt_name=prompt_name,
            batch_size=cfg.embed_batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        out = np.asarray(vectors, dtype=np.float32)
        if out.shape != (len(texts), ecfg.dim):
            raise ValueError(f"{key}: expected {len(texts)} x {ecfg.dim} vectors, got {out.shape}")
        return out

    return Embedder(
        embed_docs=lambda texts: encode(texts, None),
        embed_queries=lambda texts: encode(texts, ecfg.query_prompt_name),
    )


def load_reranker(cfg: SearchConfig) -> Rerank:
    model = _cross_encoder(cfg.reranker_model, cfg.device, cfg.rerank_max_length)

    def rerank(query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        scores = model.predict([(query, t) for t in texts], batch_size=cfg.embed_batch_size)
        return [float(s) for s in np.asarray(scores).reshape(-1)]

    return rerank


def release_models() -> None:
    """Free every loaded model (each takes ~1-2 GB of RAM in fp32)."""
    _sentence_transformer.cache_clear()
    _cross_encoder.cache_clear()
    gc.collect()
