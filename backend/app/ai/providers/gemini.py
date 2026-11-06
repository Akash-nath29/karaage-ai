from collections.abc import Iterator
from functools import cache
from itertools import chain

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.ai.providers.base import (
    EMBEDDING_DIM,
    ChatResult,
    EmbedTask,
    Message,
    ProviderError,
    StreamUsage,
    check_vectors,
    first_available,
    token_batches,
    with_retries,
)

_TASK = {"document": "RETRIEVAL_DOCUMENT", "query": "RETRIEVAL_QUERY"}


def _transient(e: Exception) -> bool:
    if isinstance(e, errors.APIError):
        return e.code == 429 or e.code >= 500  # 503 "high demand" happens; it passes
    return isinstance(e, httpx.TransportError)  # includes dropped connections and timeouts


def _retry_after(e: Exception) -> float | None:
    """Rate-limit errors carry RetryInfo, e.g. {"retryDelay": "41s"}."""
    if not isinstance(e, errors.APIError) or not isinstance(e.details, dict):
        return None
    for detail in e.details.get("error", {}).get("details", []):
        delay = str(detail.get("retryDelay", ""))
        if delay.endswith("s"):
            try:
                return float(delay[:-1]) + 1
            except ValueError:
                return None
    return None


@cache
def _client(api_key: str) -> genai.Client:
    if not api_key:
        raise ProviderError("GEMINI_API_KEY is not set")
    # One client per process: keep-alive matters on high-latency links.
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=180_000))


class GeminiEmbedder:
    provider = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self._client = _client(api_key)

    def embed(self, texts: list[str], task: EmbedTask) -> list[list[float]]:
        # Needs a model that embeds each input separately; gemini-embedding-2 merges a list into one vector.
        config = types.EmbedContentConfig(task_type=_TASK[task], output_dimensionality=EMBEDDING_DIM)
        vectors: list[list[float]] = []
        for batch_ids in token_batches(texts):
            batch = [texts[i] for i in batch_ids]
            result = with_retries(
                lambda batch=batch: self._client.models.embed_content(model=self.model, contents=batch, config=config),
                _transient,
                _retry_after,
            )
            vectors += check_vectors([list(e.values or []) for e in result.embeddings or []], len(batch))
        return vectors


class GeminiChat:
    provider = "gemini"

    def __init__(self, api_key: str, models: list[str], max_output_tokens: int | None = None) -> None:
        self.models, self.model = models, models[0]
        self._max_output = max_output_tokens
        self._client = _client(api_key)

    def generate_json(
        self, system: str, prompt: str, schema: type[BaseModel], temperature: float = 0.2
    ) -> ChatResult:
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
            max_output_tokens=self._max_output,
        )
        model, response = with_retries(
            lambda: first_available(
                self.models,
                lambda m: self._client.models.generate_content(model=m, contents=prompt, config=config),
                _transient,
                _retry_after,
            ),
            _transient,
            _retry_after,
        )
        usage = response.usage_metadata
        return ChatResult(
            text=response.text or "",
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)) if usage else 0,
            model=model,
        )

    def stream_text(self, system: str, messages: list[Message]) -> tuple[Iterator[str], StreamUsage]:
        contents = [types.Content(role="model" if role == "assistant" else "user", parts=[types.Part(text=text)])
                    for role, text in messages]
        config = types.GenerateContentConfig(system_instruction=system, temperature=0.4)
        usage = StreamUsage()

        def start(model: str):  # type: ignore[no-untyped-def]  # pull the first chunk so quota errors surface here
            stream = iter(self._client.models.generate_content_stream(model=model, contents=contents, config=config))
            return next(stream, None), stream

        usage.model, (first, rest) = with_retries(
            lambda: first_available(self.models, start, _transient, _retry_after), _transient, _retry_after
        )

        def chunks() -> Iterator[str]:
            for chunk in chain([first] if first is not None else [], rest):
                if chunk.usage_metadata:
                    meta = chunk.usage_metadata
                    usage.input_tokens = meta.prompt_token_count or 0
                    usage.output_tokens = (meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0)
                if chunk.text:
                    yield chunk.text

        return chunks(), usage
