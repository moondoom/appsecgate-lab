"""ClickHouse клиенты (reader / writer / promoter)."""

from __future__ import annotations

import clickhouse_connect

from agent.config import settings


def get_reader() -> clickhouse_connect.driver.Client:
    """Read-only клиент для исследования логов."""
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        user=settings.clickhouse_reader_user,
        password=settings.clickhouse_reader_pass,
        database="security_logs",
    )


def get_writer() -> clickhouse_connect.driver.Client:
    """Клиент для записи в proposals и memory."""
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        user=settings.clickhouse_writer_user,
        password=settings.clickhouse_writer_pass,
        database="security_logs",
    )


def get_promoter() -> clickhouse_connect.driver.Client:
    """Клиент для промоушена правил."""
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        user=settings.clickhouse_promoter_user,
        password=settings.clickhouse_promoter_pass,
        database="security_logs",
    )


def get_asset_promoter() -> clickhouse_connect.driver.Client:
    """Клиент для промоушена активов (INSERT только в assets)."""
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        user=settings.clickhouse_asset_promoter_user,
        password=settings.clickhouse_asset_promoter_pass,
        database="security_logs",
    )
