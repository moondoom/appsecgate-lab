"""Конфигурация агента из переменных окружения."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки агента."""

    clickhouse_host: str = "localhost"
    clickhouse_reader_user: str = "agent_reader"
    clickhouse_reader_pass: str = Field("", alias="AGENT_READER_PASS")
    clickhouse_writer_user: str = "agent_writer"
    clickhouse_writer_pass: str = Field("", alias="AGENT_WRITER_PASS")
    clickhouse_promoter_user: str = "agent_promoter"
    clickhouse_promoter_pass: str = Field("", alias="AGENT_PROMOTER_PASS")
    clickhouse_asset_promoter_user: str = "agent_asset_promoter"
    clickhouse_asset_promoter_pass: str = Field("", alias="AGENT_ASSET_PROMOTER_PASS")

    # Автопромоут активов: proposals с confidence >= порога переносятся в assets
    # сразу (без ручного approved); ниже порога — ждут ручного одобрения.
    asset_auto_promote_threshold: float = 0.9

    litellm_base_url: str = "http://localhost:4000"
    litellm_api_key: str = ""

    agent_model: str = "gemma4:26b"

    metrics_port: int = 9101

    observer_interval_sec: int = 300
    correlator_interval_sec: int = 60
    rule_engine_interval_sec: int = 3600

    # .env лежит в корне репозитория; Makefile запускает агента из корня,
    # но поддерживаем и запуск из agent/ («../.env»).
    model_config = {
        "env_prefix": "",
        "case_sensitive": False,
        "env_file": (".env", "../.env"),
        "extra": "ignore",
    }


settings = Settings()
