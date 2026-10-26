from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    secret_key: str = "dev-secret"
    admin_email: str = "admin@cooperativa.com"
    admin_password: str = "CambiaEsta123"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    # Permite cualquier frontend de la red local (192.168.x.x, 10.x.x.x, localhost) en cualquier puerto
    cors_origin_regex: str = r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?"
    database_url: str = "sqlite:///./cooperativa.db"
    token_minutes: int = 480

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
