from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "bindu-edge-gateway"
    ENV: str = "dev"
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    # Phase 2 settings
    MAX_WS_PAYLOAD_BYTES: int = 64 * 1024  # 64KB
    REQUEST_TIMEOUT_SECONDS: int = 30
    WS_PING_INTERVAL_SECONDS: int = 10
    WS_PONG_TIMEOUT_SECONDS: int = 5
    # Phase 3 settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None
    TUNNEL_REGISTRY_TTL: int = 300  # 5 minutes
    # Phase 4 settings
    CONTROL_PLANE_URL: str = "http://localhost:8000"
    SLUG_CACHE_TTL: int = 60  # 60 seconds

    class Config:
        env_file = ".env"


settings = Settings()
