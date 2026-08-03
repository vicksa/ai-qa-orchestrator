from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"

    database_url: str = "sqlite:///./aiqa.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_task_always_eager: bool = False

    browser_headless: bool = True
    max_agent_turns: int = 30


settings = Settings()
