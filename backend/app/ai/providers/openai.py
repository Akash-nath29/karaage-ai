"""OpenAI, or any OpenAI-compatible endpoint (Ollama, vLLM, LM Studio) via OPENAI_BASE_URL. Plain HTTP, no SDK."""

import json
from collections.abc import Iterator
from typing import Any

import httpx
from pydantic import BaseModel

from app.ai.providers.base import (
    EMBEDDING_DIM,
    ChatResult,
    EmbedTask,
    Message,
    StreamUsage,
    check_vectors,
    first_available,
    token_batches,
    with_retries,
)


def _transient(e: Exception) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code == 429 or e.response.status_code >= 500
    return isinstance(e, httpx.TransportError)


def _retry_after(e: Exception) -> float | None:
    if isinstance(e, httpx.HTTPStatusError):
        try:
            return float(e.response.headers.get("retry-after", ""))
        except ValueError:
            return None
    return None


class _Client:
    def __init__(self, api_key: str, base_url: str, model: str, transport: httpx.BaseTransport | None = None) -> None:
        self.model = model
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.Client(base_url=base_url, headers=headers, timeout=180, transport=transport)

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        def call() -> dict[str, Any]:
            res = self._http.post(path, json=body)
            res.raise_for_status()
            return res.json()

        return with_retries(call, _transient, _retry_after)


class OpenAIEmbedder(_Client):
    provider = "openai"

    def embed(self, texts: list[str], task: EmbedTask) -> list[list[float]]:
        vectors: list[list[float]] = []
        for batch_ids in token_batches(texts):
            batch = [texts[i] for i in batch_ids]
            data = self._post("/embeddings", {"model": self.model, "input": batch, "dimensions": EMBEDDING_DIM})["data"]
            vectors += check_vectors([d["embedding"] for d in sorted(data, key=lambda d: d["index"])], len(batch))
        return vectors


class OpenAIChat(_Client):
    provider = "openai"

    def __init__(
        self, api_key: str, base_url: str, models: list[str], transport: httpx.BaseTransport | None = None
    ) -> None:
        super().__init__(api_key, base_url, models[0], transport)
        self.models = models

    def _complete(self, model: str, body: dict[str, Any]) -> dict[str, Any]:
        res = self._http.post("/chat/completions", json={**body, "model": model})
        res.raise_for_status()
        return res.json()

    def generate_json(
        self, system: str, prompt: str, schema: type[BaseModel], temperature: float = 0.2
    ) -> ChatResult:
        body = {
            "temperature": temperature,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            # Non-strict: strict mode rejects common schema features; app.ai.llm validates anyway.
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()},
            },
        }
        model, data = with_retries(
            lambda: first_available(self.models, lambda m: self._complete(m, body), _transient, _retry_after),
            _transient,
            _retry_after,
        )
        usage = data.get("usage") or {}
        return ChatResult(
            text=data["choices"][0]["message"].get("content") or "",
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=model,
        )

    def stream_text(self, system: str, messages: list[Message]) -> tuple[Iterator[str], StreamUsage]:
        body = {
            "temperature": 0.4,
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [{"role": "system", "content": system}, *({"role": r, "content": t} for r, t in messages)],
        }
        usage = StreamUsage()

        def start(model: str):  # type: ignore[no-untyped-def]
            context = self._http.stream("POST", "/chat/completions", json={**body, "model": model})
            response = context.__enter__()
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                response.read()
                context.__exit__(None, None, None)
                raise
            return context, response.iter_lines()

        usage.model, (context, lines) = with_retries(
            lambda: first_available(self.models, start, _transient, _retry_after), _transient, _retry_after
        )

        def chunks() -> Iterator[str]:
            try:
                for line in lines:
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    data = json.loads(line[6:])
                    if data.get("usage"):
                        usage.input_tokens = data["usage"].get("prompt_tokens", 0)
                        usage.output_tokens = data["usage"].get("completion_tokens", 0)
                    for choice in data.get("choices") or []:
                        if text := (choice.get("delta") or {}).get("content"):
                            yield text
            finally:
                context.__exit__(None, None, None)

        return chunks(), usage
