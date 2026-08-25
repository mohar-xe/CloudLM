"""Runtime configuration for the fabric server (env prefix FABRIC_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class FabricSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FABRIC_", env_file=".env", extra="ignore")

    provider: str = "synthetic"
    seed: int = 42
    page_size: int = 500
    max_page_size: int = 1000
    host: str = "127.0.0.1"
    port: int = 9000
    billing_days: int = 30
    metrics_window_days: int = 14
    degraded_domains: str = ""
    aws_region: str = "us-east-1"

    @property
    def degraded_domain_list(self) -> list[str]:
        return [d.strip() for d in self.degraded_domains.split(",") if d.strip()]
