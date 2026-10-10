from __future__ import annotations

from pathlib import Path

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


class RetrievalConfig(StrictModel):
    ingestion: IngestionConfig
    chunking: ChunkingConfig


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    gemini_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None

    def _keys(self) -> dict[str, SecretStr | None]:
        return {"GEMINI_API_KEY": self.gemini_api_key, "GROQ_API_KEY": self.groq_api_key}

    def api_key(self, env_name: str) -> str:
        if env_name not in self._keys():
            raise ConfigError(f"unknown API key variable {env_name!r}; declare it in Settings")
        secret = self._keys()[env_name]
        if secret is None or not secret.get_secret_value():
            raise ConfigError(f"{env_name} is not set; add it to .env (see .env.example)")
        return secret.get_secret_value()


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
