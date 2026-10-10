"""Typed view of `configs/eval.yaml`."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from chaouch.config import CONFIG_DIR, load_yaml


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GoldChecks(_Strict):
    """Distribution targets from spec 7.2; violations are warnings, not errors."""

    min_questions: int = Field(ge=0)
    script_share_min: float = Field(ge=0, le=1)
    script_share_max: float = Field(ge=0, le=1)
    not_in_scope_share_min: float = Field(ge=0, le=1)
    not_in_scope_share_max: float = Field(ge=0, le=1)


class EvalConfig(_Strict):
    gold: GoldChecks


def load_eval_config(path: Path = CONFIG_DIR / "eval.yaml") -> EvalConfig:
    return load_yaml(path, EvalConfig)
