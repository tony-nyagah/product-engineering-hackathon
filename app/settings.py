from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://pos:pos@postgres:5432/posdb"
    redis_url: str = "redis://redis:6379"

    model_config = {"env_file": ".env"}


settings = Settings()
