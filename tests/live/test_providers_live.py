"""Opt-in: `uv run tasks.py test-live`. One tiny real call per model in configs/models.yaml."""

import httpx2
import pytest

from chaouch.config import ConfigError, Settings, load_models_config
from chaouch.llm import LLMClient

CONFIG = load_models_config()


@pytest.mark.live
@pytest.mark.parametrize("model_key", sorted(CONFIG.models))
async def test_model_answers(model_key: str) -> None:
    provider = CONFIG.providers[CONFIG.models[model_key].provider]
    settings = Settings()
    if provider.api_key_env:
        try:
            settings.api_key(provider.api_key_env)
        except ConfigError:
            pytest.skip(f"{provider.api_key_env} not set")
    else:
        try:
            httpx2.get(provider.base_url.removesuffix("/v1"), timeout=2)
        except httpx2.HTTPError:
            pytest.skip(f"server not reachable at {provider.base_url}")

    result = await LLMClient(CONFIG, settings).complete(
        [{"role": "user", "content": "Reply with the single word: ok"}], model_key
    )
    assert result.text.strip()
    assert result.latency_ms > 0
