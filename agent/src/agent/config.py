"""Конфигурация агента из переменных окружения."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки агента."""

    clickhouse_host: str = "localhost"
    clickhouse_reader_user: str = "agent_reader"
    clickhouse_reader_pass: str = ""
    clickhouse_writer_user: str = "agent_writer"
    clickhouse_writer_pass: str = ""
    clickhouse_promoter_user: str = "agent_promoter"
    clickhouse_promoter_pass: str = ""

    litellm_base_url: str = "http://localhost:4000"
    litellm_api_key: str = ""

    agent_model: str = "gemma4:26b"

    observer_interval_sec: int = 300
    correlator_interval_sec: int = 60
    rule_engine_interval_sec: int = 3600

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
