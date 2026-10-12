from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"


class ConfigError(Exception):
    pass


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProviderConfig(StrictModel):
    base_url: str
    api_key_env: str | None
    rpm: int = Field(gt=0)
    rpd: int | None = Field(gt=0)
    timeout_s: float = Field(gt=0)
    max_retries: int = Field(ge=0)
    concurrency: int = Field(gt=0)


class ModelConfig(StrictModel):
    provider: str
    name: str
    params: dict[str, Any] = {}


class ModelsConfig(StrictModel):
    providers: dict[str, ProviderConfig]
    models: dict[str, ModelConfig]

    @model_validator(mode="after")
    def _models_use_known_providers(self) -> ModelsConfig:
        for key, model in self.models.items():
            if model.provider not in self.providers:
                raise ValueError(f"model {key!r} uses unknown provider {model.provider!r}")
        return self


class IngestionConfig(StrictModel):
    user_agent: str = Field(min_length=1)
    request_delay_s: float = Field(ge=0)
    timeout_s: float = Field(gt=0)


class ChunkingConfig(StrictModel):
    tokenizer: str
    target_tokens: int = Field(gt=0)
    max_tokens: int = Field(gt=0)
    overlap_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def _sizes_are_consistent(self) -> ChunkingConfig:
        if not self.overlap_tokens < self.target_tokens <= self.max_tokens:
            raise ValueError("need overlap_tokens < target_tokens <= max_tokens")
        return self


class EmbedderConfig(StrictModel):
    name: str  # Hugging Face model id
    dim: int = Field(gt=0)
    query_prompt_name: str | None  # the model's built-in query prompt, applied to queries only


class BM25Config(StrictModel):
    k1: float = Field(gt=0)
    b: float = Field(ge=0, le=1)


class SearchConfig(StrictModel):
    embedders: dict[str, EmbedderConfig]
    default_embedder: str
    reranker_model: str
    device: str
    embed_batch_size: int = Field(gt=0)
    rerank_max_length: int = Field(gt=0)
    bm25: BM25Config
    rrf_k: int = Field(gt=0)
    candidates: int = Field(gt=0)  # per retriever, before fusion
    rerank_candidates: int = Field(gt=0)
    top_k: int = Field(gt=0)

    @model_validator(mode="after")
    def _consistent(self) -> SearchConfig:
        if not self.top_k <= self.rerank_candidates <= self.candidates:
            raise ValueError("need top_k <= rerank_candidates <= candidates")
        if self.default_embedder not in self.embedders:
            raise ValueError(f"default_embedder {self.default_embedder!r} not in embedders")
        return self


class RetrievalConfig(StrictModel):
    ingestion: IngestionConfig
    chunking: ChunkingConfig
    retrieval: SearchConfig


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    database_url: SecretStr | None = None
    hf_token: SecretStr | None = None  # optional; faster, less throttled model downloads

    def _keys(self) -> dict[str, SecretStr | None]:
        return {"GEMINI_API_KEY": self.gemini_api_key, "GROQ_API_KEY": self.groq_api_key}

    def api_key(self, env_name: str) -> str:
        if env_name not in self._keys():
            raise ConfigError(f"unknown API key variable {env_name!r}; declare it in Settings")
        secret = self._keys()[env_name]
        if secret is None or not secret.get_secret_value():
            raise ConfigError(f"{env_name} is not set; add it to .env (see .env.example)")
        return secret.get_secret_value()

    def database_dsn(self) -> str:
        if self.database_url is None or not self.database_url.get_secret_value():
            raise ConfigError("DATABASE_URL is not set; add it to .env (see .env.example)")
        return self.database_url.get_secret_value()


def load_yaml[T: BaseModel](path: Path, model: type[T]) -> T:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return model.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise ConfigError(f"invalid config {path}: {exc}") from exc


def load_models_config(path: Path = CONFIG_DIR / "models.yaml") -> ModelsConfig:
    return load_yaml(path, ModelsConfig)


def load_retrieval_config(path: Path = CONFIG_DIR / "retrieval.yaml") -> RetrievalConfig:
    return load_yaml(path, RetrievalConfig)
