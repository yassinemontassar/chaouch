"""Opt-in: `uv run tasks.py test-live`. One tiny real call per model in configs/models.yaml."""

import httpx2
import pytest

from chaouch.config import ConfigError, Settings, load_models_config
from chaouch.llm import LLMClient

CONFIG = load_models_config()


def skip_reason(model_key: str, settings: Settings) -> str | None:
    model = CONFIG.models[model_key]
    provider = CONFIG.providers[model.provider]
    if provider.api_key_env:
        try:
            settings.api_key(provider.api_key_env)
        except ConfigError:
            return f"{provider.api_key_env} not set"
        return None
    try:  # local Ollama: the server must run and the model must be pulled
        tags = httpx2.get(provider.base_url.removesuffix("/v1") + "/api/tags", timeout=2).json()
    except httpx2.HTTPError:
        return f"server not reachable at {provider.base_url}"
    if model.name not in {m["name"] for m in tags.get("models", [])}:
        return f"run `ollama pull {model.name}` first"
    return None


@pytest.mark.live
@pytest.mark.parametrize("model_key", sorted(CONFIG.models))
async def test_model_answers(model_key: str) -> None:
    settings = Settings()
    if reason := skip_reason(model_key, settings):
        pytest.skip(reason)
    result = await LLMClient(CONFIG, settings).complete(
        [{"role": "user", "content": "Reply with the single word: ok"}], model_key
    )
    assert result.text.strip()
    assert result.latency_ms > 0
