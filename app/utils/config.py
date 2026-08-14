"""Application configuration loaded from environment variables / .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    """Central configuration for Brain OS.

    All values can be overridden via environment variables or a `.env` file
    in the project root. Nothing here is a secret default -- API keys are
    left empty and features that depend on them degrade gracefully when
    unset (see services/executive_briefing.py and services/notification_service.py).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Brain OS Enterprise Workflow Platform"
    environment: str = "local"
    log_level: str = "INFO"

    # Risk engine
    auto_approve_threshold: float = 5000.0

    # SQLite
    database_path: str = str(DATA_DIR / "brain_os.db")
    checkpoint_db_path: str = str(DATA_DIR / "checkpoints.db")

    # ChromaDB
    chroma_persist_path: str = str(DATA_DIR / "chroma")
    chroma_collection_name: str = "invoice_memory"
    duplicate_similarity_threshold: float = 0.92

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"

    # Slack
    slack_bot_token: str = ""
    slack_approval_channel: str = ""

    # API authentication (Bearer token for all /brain-os/* endpoints).
    # Unlike the integration keys above, an empty value here does NOT mean
    # "feature disabled" -- it means "reject every request" (see
    # app/api/security.py). There is no default that opens the API.
    brain_os_api_token: str = ""

    # Rate limiting: max requests per caller (keyed by bearer token) within
    # a rolling window, enforced per process (see app/api/rate_limit.py).
    rate_limit_max_requests: int = 60
    rate_limit_window_seconds: float = 60.0

    # Reject any request whose Content-Length exceeds this before the body
    # is ever parsed (see app/api/middleware.py). 1 MiB is comfortably
    # larger than any real invoice text payload.
    max_request_body_bytes: int = 1_048_576

    def ensure_data_dir(self) -> None:
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.checkpoint_db_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.chroma_persist_path).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
