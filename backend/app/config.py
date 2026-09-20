from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every setting comes from the environment (or backend/.env). None has a default in code, so a missing
    value stops the app at start-up, by name, instead of silently running on a guess."""

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    log_level: str
    # Comma-separated browser origins allowed to call the API (the frontend's own address).
    cors_origins: str

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]

    # extra="ignore": backend/.env also holds keys this class doesn't own (the SEED_*_PASSWORD values are read
    # by app.seed), and an unknown key must not stop the API from starting.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        # Names only: the error's own text would echo the values, which can be secrets.
        names = ", ".join(sorted({str(error["loc"][0]).upper() for error in exc.errors()}))
        raise SystemExit(
            f"Configuration error: missing or invalid environment variables: {names}\n"
            "Set them in the environment or in backend/.env (see backend/.env.example)."
        ) from None


settings = load_settings()
