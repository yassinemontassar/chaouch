from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator

from chaouch.config import CONFIG_DIR, StrictModel, load_yaml


class GoldChecks(StrictModel):
    min_questions: int = Field(ge=0)
    script_share_min: float = Field(ge=0, le=1)
    script_share_max: float = Field(ge=0, le=1)
    not_in_scope_share_min: float = Field(ge=0, le=1)
    not_in_scope_share_max: float = Field(ge=0, le=1)


class SystemConfig(StrictModel):
    model: str
    use_oracle: bool


class EvalConfig(StrictModel):
    gold: GoldChecks
    cache_path: Path
    judge_model: str
    oracle_token_budget: int = Field(gt=0)
    smoke_size: int = Field(gt=0)
    smoke_systems: list[str]
    systems: dict[str, SystemConfig]

    @model_validator(mode="after")
    def _smoke_systems_exist(self) -> EvalConfig:
        unknown = [s for s in self.smoke_systems if s not in self.systems]
        if unknown:
            raise ValueError(f"smoke_systems not in systems: {', '.join(unknown)}")
        return self


def load_eval_config(path: Path = CONFIG_DIR / "eval.yaml") -> EvalConfig:
    return load_yaml(path, EvalConfig)
