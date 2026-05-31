import json
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    REDIS_URL: str

    PAYSTACK_SECRET_KEY: str
    PAYSTACK_PUBLIC_KEY: str

    EMAIL_HOST: str
    EMAIL_PORT: int = 587
    EMAIL_USERNAME: str
    EMAIL_PASSWORD: str
    EMAIL_FROM: str

    # Set these in Render env vars to seed the first admin on startup.
    # Remove them after the account is created.
    ADMIN_EMAIL: Optional[str] = None
    ADMIN_USERNAME: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        # Render provides postgres:// or postgresql://, but asyncpg requires postgresql+asyncpg://
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        v = v.strip()
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return [o.strip() for o in v.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
