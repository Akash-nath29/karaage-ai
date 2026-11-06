import json

import httpx
import pytest

from app.ai.providers import base
from app.ai.providers.base import EMBEDDING_DIM, ProviderError, TransientProviderError, with_retries
from app.ai.providers.openai import OpenAIChat, OpenAIEmbedder


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base.time, "sleep", lambda s: None)


def embedder(handler) -> OpenAIEmbedder:  # type: ignore[no-untyped-def]
    return OpenAIEmbedder("sk-test", "https://example.test/v1", "text-embedding-3-small", httpx.MockTransport(handler))


def vector(x: float) -> list[float]:
    return [x] * EMBEDDING_DIM


def test_openai_compatible_request_and_order() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(url=str(request.url), auth=request.headers["authorization"], body=json.loads(request.content))
        # out of order on purpose: results are matched by index
        return httpx.Response(200, json={"data": [{"index": 1, "embedding": vector(2)}, {"index": 0, "embedding": vector(1)}]})

    out = embedder(handler).embed(["a", "b"], "document")
    assert [v[0] for v in out] == [1, 2]
    assert seen["url"] == "https://example.test/v1/embeddings"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"] == {"model": "text-embedding-3-small", "input": ["a", "b"], "dimensions": EMBEDDING_DIM}


def test_rate_limit_is_retried() -> None:
    responses = iter([httpx.Response(429), httpx.Response(200, json={"data": [{"index": 0, "embedding": vector(1)}]})])
    assert embedder(lambda r: next(responses)).embed(["a"], "query")[0][0] == 1


def test_permanent_and_exhausted_errors() -> None:
    with pytest.raises(ProviderError) as bad:
        embedder(lambda r: httpx.Response(400)).embed(["a"], "query")
    assert not isinstance(bad.value, TransientProviderError)
    with pytest.raises(TransientProviderError):
        embedder(lambda r: httpx.Response(503)).embed(["a"], "query")
    with pytest.raises(ProviderError, match="2 embeddings for 1 inputs"):
        embedder(lambda r: httpx.Response(200, json={"data": [{"index": 0, "embedding": vector(1)}, {"index": 1, "embedding": vector(1)}]})).embed(["a"], "query")
    with pytest.raises(ProviderError, match="1536"):
        embedder(lambda r: httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]})).embed(["a"], "query")


def test_with_retries_counts_attempts() -> None:
    calls = []

    def flaky() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ConnectError("dropped")
        return "ok"

    assert with_retries(flaky, lambda e: isinstance(e, httpx.TransportError)) == "ok"
    assert len(calls) == 3


def test_batches_capped_by_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base.settings, "embedding_batch_tokens", 20000)
    texts = ["x" * 8000] * 25  # ~2000 tokens each
    assert [len(b) for b in base.token_batches(texts)] == [10, 10, 5]
    assert base.token_batches(["x" * 200_000]) == [[0]]  # an oversized single input still gets its own batch
    assert [len(b) for b in base.token_batches(["a"] * 250)] == [100, 100, 50]  # count cap


def test_rate_limit_waits_as_long_as_the_provider_asks(monkeypatch: pytest.MonkeyPatch) -> None:
    from google.genai import errors

    from app.ai.providers.gemini import _retry_after

    quota = errors.ClientError(429, {"error": {"code": 429, "details": [
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "41s"}]}})
    assert _retry_after(quota) == 42
    assert _retry_after(errors.ServerError(503, {"error": {"code": 503}})) is None

    slept: list[float] = []
    monkeypatch.setattr(base.time, "sleep", slept.append)
    responses = iter([httpx.Response(429, headers={"retry-after": "7"}),
                      httpx.Response(200, json={"data": [{"index": 0, "embedding": vector(1)}]})])
    embedder(lambda r: next(responses)).embed(["a"], "query")
    assert slept == [7.0]


def test_chat_falls_back_to_the_next_model() -> None:
    from pydantic import BaseModel

    class Out(BaseModel):
        x: int

    asked: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        asked.append(model)
        if model == "big":
            return httpx.Response(503)  # overloaded: next model at once, no backoff
        body = {"choices": [{"message": {"content": "{\"x\": 1}"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}
        return httpx.Response(200, json=body)

    chat = OpenAIChat("k", "https://example.test/v1", ["big", "small"], httpx.MockTransport(handler))
    result = chat.generate_json("system", "prompt", Out)
    assert (result.text, result.model, result.input_tokens) == ("{\"x\": 1}", "small", 5)
    assert asked == ["big", "small"]

    bad = OpenAIChat("k", "https://example.test/v1", ["a", "b"], httpx.MockTransport(lambda r: httpx.Response(400)))
    with pytest.raises(ProviderError):  # a non-transient error doesn't fall through to other models
        bad.generate_json("s", "p", Out)


def test_stream_falls_back_and_reports_usage() -> None:
    asked: list[dict] = []  # type: ignore[type-arg]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        asked.append(body)
        if body["model"] == "big":
            return httpx.Response(429)  # rate-limited before the first chunk: next model
        events = [{"choices": [{"delta": {"content": text}}]} for text in ("Hel", "lo")]
        events.append({"choices": [], "usage": {"prompt_tokens": 9, "completion_tokens": 3}})
        lines = "".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"
        return httpx.Response(200, text=lines, headers={"content-type": "text/event-stream"})

    chat = OpenAIChat("k", "https://example.test/v1", ["big", "small"], httpx.MockTransport(handler))
    chunks, usage = chat.stream_text("be brief", [("user", "hi"), ("assistant", "yes?"), ("user", "greet me")])
    assert "".join(chunks) == "Hello"
    assert (usage.model, usage.input_tokens, usage.output_tokens) == ("small", 9, 3)
    assert [m["model"] for m in asked] == ["big", "small"]
    assert [m["role"] for m in asked[-1]["messages"]] == ["system", "user", "assistant", "user"]
