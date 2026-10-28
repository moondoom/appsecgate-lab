"""Нормализация URL и ключей активов.

Дублирует ClickHouse UDF из 05_functions.sql.
Тесты должны проверять, что Python и SQL дают одинаковые результаты.
"""

from __future__ import annotations

import re


def extract_repo_url(args: str) -> str:
    """Извлечь URL репозитория из аргументов git-команды."""
    # git@github.com:org/repo.git
    m = re.search(r"(?:git@|https?://|ssh://)[\w@.:/~-]+", args)
    return m.group(0) if m else ""


def normalize_repo_url(url: str) -> str:
    """Привести URL репозитория к единому виду.

    Поддерживает:
      git@github.com:org/repo.git  → https://github.com/org/repo
      ssh://git@github.com/org/repo → https://github.com/org/repo
      https://github.com/org/repo   → https://github.com/org/repo (без изменений)
    """
    # SCP-стиль: git@github.com:org/repo.git
    m = re.match(r"git@([\w.-]+):(.+)", url)
    if m:
        host, path = m.group(1), m.group(2)
        url = f"https://{host}/{path}"

    # ssh://git@github.com/org/repo → https://github.com/org/repo
    url = re.sub(r"^ssh://[^@]+@", "https://", url)

    # Убрать .git суффикс
    url = re.sub(r"\.git$", "", url)

    return url.lower().rstrip(".")


def extract_db_key(args: str) -> str:
    """Извлечь ключ БД из аргументов tool call."""
    # JSON: {"host": "db-01.internal"} или {"host":"db-01"}
    json_pat = re.compile(r'(?i)"(?:host|server|endpoint)"\s*:\s*"([\w.-]+)"')
    m = json_pat.search(args)
    if m:
        return m.group(1)
    # Key-value: host=db-01 или host: db-01
    kv_pat = re.compile(r'(?i)(?:host|server|endpoint)[=:]\s*"?([\w.-]+)"?')
    m = kv_pat.search(args)
    return m.group(1) if m else ""


def make_asset_key(asset_type: str, *parts: str) -> str:
    """Сформировать asset_key в формате '<type>:<...>'."""
    return f"{asset_type}:{':'.join(parts)}"
