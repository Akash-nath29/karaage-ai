from functools import cache

from app.ai.providers.base import ChatModel, Embedder, ProviderError
from app.config import settings

# Imports are local so a deployment only loads the SDK it uses.


@cache
def get_embedder() -> Embedder:
    if settings.embedding_provider == "gemini":
        from app.ai.providers.gemini import GeminiEmbedder

        return GeminiEmbedder(settings.gemini_api_key, settings.embedding_model)
    if settings.embedding_provider == "openai":
        from app.ai.providers.openai import OpenAIEmbedder

        return OpenAIEmbedder(settings.openai_api_key, settings.openai_base_url, settings.embedding_model)
    raise ProviderError(f"unknown EMBEDDING_PROVIDER {settings.embedding_provider!r} (use 'gemini' or 'openai')")


def _models(setting: str) -> list[str]:
    models = [m.strip() for m in setting.split(",") if m.strip()]
    if not models:
        raise ProviderError("LLM_MODEL_FAST / LLM_MODEL_SMART is empty")
    return models


@cache
def get_chat_model(tier: str = "fast") -> ChatModel:
    """"fast": extraction, classification, planning. "smart": lesson generation (PRD §12.4–5)."""
    models = _models(settings.llm_model_smart if tier == "smart" else settings.llm_model_fast)
    if settings.llm_provider == "gemini":
        from app.ai.providers.gemini import GeminiChat

        return GeminiChat(settings.gemini_api_key, models)
    if settings.llm_provider == "openai":
        from app.ai.providers.openai import OpenAIChat

        return OpenAIChat(settings.openai_api_key, settings.openai_base_url, models)
    raise ProviderError(f"unknown LLM_PROVIDER {settings.llm_provider!r} (use 'gemini' or 'openai')")
