from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    secret_key: str = "dev-secret"
    admin_email: str = "admin.sostecoop@gmail.com"
    admin_password: str = "sostecoopltda"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    # Opcional (vacío = desactivado). Con cookies de sesión conviene listar los orígenes uno a uno en cors_origins.
    cors_origin_regex: str = ""
    # PostgreSQL local con la base "cooperativa" creada. Para otros datos de conexión, definir DATABASE_URL en el .env
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/cooperativa"
    token_minutes: int = 480
    # Fecha de creación (ISO 8601, p. ej. 2026-10-01T00:00:00+00:00) para las noticias antiguas que no la tienen.
    # Vacío = el momento en que se migran
    news_created_at_fallback: str = ""
    # "production" activa el atributo Secure de la cookie de sesión (requiere HTTPS)
    environment: str = "development"

    @property
    def origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cookie_secure(self) -> bool:
        return self.environment.strip().lower() == "production"


settings = Settings()
