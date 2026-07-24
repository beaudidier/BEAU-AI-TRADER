from functools import lru_cache

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # Allows public market endpoints to run before SaaS dependencies are installed.
    from pydantic import BaseModel
    import os

    class BaseSettings(BaseModel):
        def __init__(self, **values):
            values = {"supabase_url": os.getenv("SUPABASE_URL"), "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY"), "supabase_jwt_secret": os.getenv("SUPABASE_JWT_SECRET"), **values}
            super().__init__(**values)

    def SettingsConfigDict(**_kwargs): return {}


class Settings(BaseSettings):
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_jwt_secret: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
