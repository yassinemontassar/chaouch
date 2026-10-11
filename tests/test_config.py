from pathlib import Path

import pytest

from chaouch.config import (
    CONFIG_DIR,
    ConfigError,
    Settings,
    load_models_config,
    load_retrieval_config,
)

VALID = """
providers:
  local:
    base_url: http://localhost:11434/v1
    api_key_env: null
    rpm: 60
    rpd: null
    timeout_s: 30
    max_retries: 1
    concurrency: 1
models:
  m:
    provider: local
    name: some-model
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_repo_models_config_is_valid() -> None:
    cfg = load_models_config()
    assert cfg.providers["ollama"].concurrency == 1
    assert all(m.provider in cfg.providers for m in cfg.models.values())


def test_valid_config_loads(tmp_path: Path) -> None:
    cfg = load_models_config(write(tmp_path, VALID))
    assert cfg.models["m"].name == "some-model"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("provider: local", "provider: missing"),  # unknown provider
        ("rpm: 60", "rpm: 0"),  # non-positive limit
        ("rpm: 60", "rpm: 60\n    surprise: 1"),  # unknown key
    ],
)
def test_invalid_config_raises(tmp_path: Path, old: str, new: str) -> None:
    with pytest.raises(ConfigError):
        load_models_config(write(tmp_path, VALID.replace(old, new)))


def test_unparseable_yaml_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_models_config(write(tmp_path, "providers: [unclosed"))


def test_api_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "secret")
    assert Settings(_env_file=None).api_key("GROQ_API_KEY") == "secret"


@pytest.mark.parametrize("value", [None, ""])
def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    if value is not None:
        monkeypatch.setenv("GROQ_API_KEY", value)
    with pytest.raises(ConfigError, match="GROQ_API_KEY is not set"):
        Settings(_env_file=None).api_key("GROQ_API_KEY")


def test_unknown_api_key_name_raises() -> None:
    with pytest.raises(ConfigError, match="unknown API key"):
        Settings(_env_file=None).api_key("NOPE_API_KEY")


def test_repo_retrieval_config_is_valid() -> None:
    cfg = load_retrieval_config().retrieval
    assert cfg.top_k <= cfg.rerank_candidates <= cfg.candidates
    assert cfg.default_embedder in cfg.embedders


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("top_k: 5", "top_k: 50"),  # top_k > rerank_candidates
        ("default_embedder: bge_m3", "default_embedder: nope"),
    ],
)
def test_invalid_retrieval_config_raises(tmp_path: Path, old: str, new: str) -> None:
    text = (CONFIG_DIR / "retrieval.yaml").read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "retrieval.yaml"
    path.write_text(text.replace(old, new), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_retrieval_config(path)


def test_database_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    assert Settings(_env_file=None).database_dsn() == "postgresql://u:p@localhost/db"
    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(ConfigError, match="DATABASE_URL is not set"):
        Settings(_env_file=None).database_dsn()
