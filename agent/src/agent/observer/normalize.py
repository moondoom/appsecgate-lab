"""Normalization of asset URLs and keys.

Duplicates the ClickHouse UDFs from 05_functions.sql.
Tests must verify that Python and SQL produce the same results.
"""

from __future__ import annotations

import re


def extract_repo_url(args: str) -> str:
    """Extract a repository URL from git command arguments."""
    # git@github.com:org/repo.git
    m = re.search(r"(?:git@|https?://|ssh://)[\w@.:/~-]+", args)
    return m.group(0) if m else ""


def normalize_repo_url(url: str) -> str:
    """Bring a repository URL to a canonical form.

    Supports:
      git@github.com:org/repo.git  → https://github.com/org/repo
      ssh://git@github.com/org/repo → https://github.com/org/repo
      https://github.com/org/repo   → https://github.com/org/repo (unchanged)
    """
    # SCP style: git@github.com:org/repo.git
    m = re.match(r"git@([\w.-]+):(.+)", url)
    if m:
        host, path = m.group(1), m.group(2)
        url = f"https://{host}/{path}"

    # ssh://git@github.com/org/repo → https://github.com/org/repo
    url = re.sub(r"^ssh://[^@]+@", "https://", url)

    # Strip the .git suffix
    url = re.sub(r"\.git$", "", url)

    return url.lower().rstrip(".")


def extract_db_key(args: str) -> str:
    """Extract a database key from tool call arguments."""
    # JSON: {"host": "db-01.internal"} or {"host":"db-01"}
    json_pat = re.compile(r'(?i)"(?:host|server|endpoint)"\s*:\s*"([\w.-]+)"')
    m = json_pat.search(args)
    if m:
        return m.group(1)
    # Key-value: host=db-01 or host: db-01
    kv_pat = re.compile(r'(?i)(?:host|server|endpoint)[=:]\s*"?([\w.-]+)"?')
    m = kv_pat.search(args)
    return m.group(1) if m else ""


def make_asset_key(asset_type: str, *parts: str) -> str:
    """Build an asset_key in the '<type>:<...>' format."""
    return f"{asset_type}:{':'.join(parts)}"
