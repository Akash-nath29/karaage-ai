import logging
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

from app.config import settings
from app.core.tokens import estimate_tokens

EMBEDDING_DIM = 1536  # fixed by the pgvector column (docs/decisions.md Q1)
EMBED_BATCH = 100  # max inputs per request
MAX_RETRY_DELAY = 90.0

EmbedTask = Literal["document", "query"]
T = TypeVar("T")
log = logging.getLogger(__name__)


class ProviderError(Exception):
    """Permanent failure: bad key, bad request, unexpected response. Retrying won't help."""


class TransientProviderError(ProviderError):
    """Rate limit, server error or network failure. Worth retrying later."""


class Embedder(Protocol):
    provider: str
    model: str

    def embed(self, texts: list[str], task: EmbedTask) -> list[list[float]]: ...


@dataclass
class ChatResult:
    text: str
    input_tokens: int
    output_tokens: int  # includes thinking tokens: they're billed as output
    model: str  # the model that actually answered (fallbacks may have been used)


@dataclass
class StreamUsage:
    """Filled in as a stream runs: which model answered and, at the end, the token counts."""

    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


Message = tuple[str, str]  # (role: "user" | "assistant", text)


class ChatModel(Protocol):
    provider: str
    model: str

    def generate_json(
        self, system: str, prompt: str, schema: type[BaseModel], temperature: float = 0.2
    ) -> ChatResult:
        """JSON text constrained to `schema` (validation happens in app.ai.llm, not here)."""
        ...

    def stream_text(self, system: str, messages: list[Message]) -> tuple[Iterator[str], StreamUsage]:
        """Text chunks as they're generated. Overload/rate limits before the first chunk fall through to the
        next model; errors after it are raised from the iterator."""
        ...


def token_batches(texts: list[str]) -> list[list[int]]:
    """Group text indices into request-sized batches, capped by count and by estimated tokens.
    The token cap matters on rate-limited tiers: a request bigger than the per-minute quota can never succeed."""
    batches: list[list[int]] = []
    tokens = 0
    for i, text in enumerate(texts):
        size = estimate_tokens(text)
        if batches and len(batches[-1]) < EMBED_BATCH and tokens + size <= settings.embedding_batch_tokens:
            batches[-1].append(i)
            tokens += size
        else:
            batches.append([i])
            tokens = size
    return batches


def with_retries(
    call: Callable[[], T],
    is_transient: Callable[[Exception], bool],
    retry_after: Callable[[Exception], float | None] = lambda e: None,
    attempts: int = 6,
) -> T:
    """Retry transient failures in-process: wait as long as the provider asks (rate limits), else back off 2–32 s."""
    for attempt in range(attempts):
        try:
            return call()
        except Exception as e:
            if not is_transient(e):
                raise ProviderError(f"{type(e).__name__}: {e}") from e
            if attempt == attempts - 1:
                raise TransientProviderError(f"{type(e).__name__}: {e}") from e
            delay = min(MAX_RETRY_DELAY, retry_after(e) or 2 ** (attempt + 1))
            log.warning("provider call failed (%s), retrying in %.0fs", type(e).__name__, delay)
            time.sleep(delay)
    raise AssertionError("unreachable")


# Models whose quota is exhausted for a long time (e.g. a daily cap: "retry in 46000s"), skipped until then.
_cooldown_until: dict[str, float] = {}
LONG_COOLDOWN = 300.0  # seconds; shorter waits are ordinary rate limiting and are retried


def first_available(
    models: list[str],
    call: Callable[[str], T],
    is_transient: Callable[[Exception], bool],
    retry_after: Callable[[Exception], float | None] = lambda e: None,
) -> tuple[str, T]:
    """Try each model in order, moving on at once when one is overloaded or rate-limited. A model that asks to
    wait longer than LONG_COOLDOWN is skipped until then. Raises the last transient error when all fail, so
    `with_retries` backs off before the next full pass."""
    last: Exception | None = None
    now = time.monotonic()
    available = [m for m in models if _cooldown_until.get(m, 0) <= now] or models[-1:]
    for model in available:
        try:
            return model, call(model)
        except Exception as e:
            if not is_transient(e):
                raise
            wait = retry_after(e) or 0
            if wait > LONG_COOLDOWN:
                _cooldown_until[model] = time.monotonic() + wait
                log.warning("model %s exhausted for %.0f min, skipping it until then", model, wait / 60)
            else:
                log.info("model %s unavailable (%s), trying the next one", model, type(e).__name__)
            last = e
    assert last is not None
    raise last


def check_vectors(vectors: list[list[float]], expected: int) -> list[list[float]]:
    if len(vectors) != expected:
        raise ProviderError(f"provider returned {len(vectors)} embeddings for {expected} inputs")
    if any(len(v) != EMBEDDING_DIM for v in vectors):
        raise ProviderError(f"provider returned embeddings that are not {EMBEDDING_DIM}-dimensional")
    return vectors
