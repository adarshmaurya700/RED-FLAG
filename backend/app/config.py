from functools import lru_cache
from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")
    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./suraksha.db"
    redis_url: str = "redis://localhost:6379/0"
    task_mode: str = "local"
    seed_demo: bool = True
    initialize_database: bool = True
    internal_api_key: str = Field(default="", repr=False)
    tinyfish_api_key: str = Field(default="", repr=False)
    brightdata_api_key: str = Field(default="", repr=False)
    brightdata_dataset_ids: str = "{}"
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = "gemini-2.5-flash"
    sarvam_api_key: str = Field(default="", repr=False)
    bhashini_api_key: str = Field(default="", repr=False)
    bhashini_user_id: str = ""
    bhashini_pipeline_id: str = "64392f96daac500b55c543cd"
    reddit_access_token: str = Field(default="", repr=False)
    nlp_mode: str = "rules"
    graph_backend: str = "networkx"
    hf_hinglish_model: str = "l3cube-pune/hing-roberta"
    hf_indic_model: str = "ai4bharat/IndicBERTv2-MLM-only"
    comet_model: str = ""
    scan_timeout_seconds: int = 20
    max_scan_items: int = 30
    max_concurrent_scans: int = 3
    data_directory: Path = Path(__file__).resolve().parents[2] / "data"

    @model_validator(mode="after")
    def production_contract(self):
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace(
                "postgres://", "postgresql+asyncpg://", 1
            )
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        if self.app_env == "production":
            if not self.database_url.startswith("postgresql+asyncpg://"):
                raise ValueError("Production requires PostgreSQL")
            if len(self.internal_api_key) < 32:
                raise ValueError(
                    "Production requires INTERNAL_API_KEY of at least 32 characters"
                )
            if self.task_mode != "celery":
                raise ValueError("Production requires TASK_MODE=celery")
        if self.task_mode not in {"local", "celery"}:
            raise ValueError("TASK_MODE must be local or celery")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
