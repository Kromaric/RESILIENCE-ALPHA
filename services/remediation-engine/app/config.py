from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REMEDIATION_")

    service_name: str = "remediation-engine"
    port: int = 8003
    log_level: str = "INFO"

    prometheus_url: str = "http://prometheus:9090"
    loki_url: str = "http://loki:3100"
    payment_url: str = "http://oorbe-payment-service:8002"
    blocklist_path: Path = Path("/etc/nginx/blocklist/blocklist.conf")
    docker_socket: str = "/var/run/docker.sock"

    waf_container: str = "waf"
    payment_container: str = "oorbe-payment-service"

    cooldown_seconds: int = 30
    whitelist_ips: list[str] = ["::1"]
