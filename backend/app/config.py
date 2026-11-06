import re
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore")

    # 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first and stalls against Docker.
    database_url: str = "postgresql+psycopg://semsaviour:semsaviour@127.0.0.1:5432/semsaviour"
    redis_url: str = "redis://127.0.0.1:6380/0"
    log_level: str = "INFO"
    sentry_dsn: str = ""  # empty = Sentry off (D33)

    # S3-compatible object storage (MinIO in dev, R2/S3 in prod)
    s3_endpoint_url: str = "http://127.0.0.1:9000"
    s3_bucket: str = "semsaviour"
    s3_access_key: str = "semsaviour"
    s3_secret_key: str = "semsaviour-secret"
    s3_region: str = "us-east-1"

    max_upload_mb: int = 100

    # Auth (docs/decisions.md D25). SECRET_KEY signs access tokens: set it in .env (empty = random per process,
    # which logs everyone out on every restart).
    secret_key: str = ""
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = False  # True behind HTTPS (production)
    rate_limit_enabled: bool = True
    app_url: str = "http://127.0.0.1:5173"  # links in emails

    # Email (A19, D34): Mailpit in development (docker compose), any SMTP server in production.
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False
    smtp_from: str = "Karaage <no-reply@karaage.local>"

    # Embeddings: provider is "gemini" or "openai" (OpenAI or any OpenAI-compatible local endpoint).
    # Dimension is fixed at 1536 by the database column (docs/decisions.md Q1).
    embedding_provider: str = "gemini"
    embedding_model: str = "gemini-embedding-001"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    # Max estimated tokens per embedding request. Gemini's free tier allows 30k embedding tokens/minute,
    # so one request above that can never succeed. Raise it on paid tiers for fewer round trips.
    embedding_batch_tokens: int = 20000

    # Chat models (PRD §12.4–5). "fast" = extraction, classification, planning. Pinned, not "-latest":
    # the model id is recorded with every output. Comma-separated = preference order: on overload (503) or a
    # rate limit (429, quotas are per model) the next model answers instead (docs/decisions.md D11).
    llm_provider: str = "gemini"  # gemini | openai
    llm_model_fast: str = "gemini-3.8-flash,gemini-3.5-flash,gemini-3.1-flash-lite"
    # "smart" = lesson generation (PRD §12.5). Pro models aren't on Gemini's free tier; the list falls through
    # to flash-lite there and uses pro automatically on a paid key.
    llm_model_smart: str = (
        "gemini-3.1-pro-preview,gemini-3.8-flash,gemini-3.5-flash,gemini-3.1-flash-lite,gemini-3.5-flash-lite"
    )

    # Workspace AI budget per calendar month (A18). 0 = unlimited. Jobs stop with a clear message when reached.
    workspace_monthly_tokens: int = 3_000_000  # chat tokens, input + output
    workspace_monthly_searches: int = 500  # web searches
    user_monthly_tokens: int = 1_500_000  # per person across all workspaces (§12.6, D30)

    # Lessons (Phase 4)
    lesson_default_depth: str = "detailed"  # depth for the batch queued when a syllabus is confirmed (Q3)

    # Web research (PRD E4 budget)
    tavily_api_key: str = ""
    research_max_queries: int = 4
    research_results_per_query: int = 5
    research_max_sources: int = 8
    research_passages_per_source: int = 3
    research_reuse_days: int = 7  # PRD §12.2: reuse recent research unless refreshed

    # Chunk → topic mapping: minimum cosine similarity between a chunk and a topic's description
    topic_match_threshold: float = 0.6

    # Chunking (PRD D4), in estimated tokens
    chunk_max_tokens: int = 800
    chunk_min_tokens: int = 300  # a heading starts a new chunk only once the current one is this big
    chunk_overlap_tokens: int = 100

    # Retrieval (PRD D6)
    retrieval_candidates: int = 30
    retrieval_top_k: int = 8
    # Keyword ranking's weight in fusion (vector = 1). 0 = vector only. Benchmark: docs/decisions.md D9.
    retrieval_keyword_weight: float = 0.3

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, url: str) -> str:
        # Hosted Postgres (Neon, Render) hands out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver.
        return re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", url)


settings = Settings()
