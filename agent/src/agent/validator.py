"""SQL rule validator (safe SELECT).

Security policy for all SQL that ends up in ``alert_rules``
(static rules from ``rules/static/`` and Rule-Engine proposals):

* exactly one expression — no multi-statement (``;``);
* only ``SELECT`` — no INSERT/UPDATE/DELETE/CREATE/ALTER/DROP/GRANT;
* all tables are fully qualified and in the whitelist:
  ``security_logs.*`` and ``system.*``;
* functions accessing external sources are forbidden
  (``file``/``url``/``s3``/``remote`` and similar in ClickHouse).

No bypass: validation runs on the sqlglot AST (dialect=clickhouse),
not on the raw string.
"""

from __future__ import annotations

import sqlglot
from sqlglot import ErrorLevel, exp

ALLOWED_DATABASES: frozenset[str] = frozenset(("security_logs", "system"))

# ClickHouse functions that give access to external data sources.
BLOCKED_FUNCTIONS: frozenset[str] = frozenset(
    (
        # files, URLs, cloud/distributed storage
        "file",
        "url",
        "s3",
        "gcs",
        "azureblobstorage",
        "hdfs",
        "web",
        "remote",
        "remotesecure",
        # external DBMS and queues
        "mysql",
        "postgresql",
        "sqlite",
        "mongodb",
        "redis",
        "kafka",
        "jdbc",
        "odbc",
        # external dictionaries
        "dictget",
    )
)


def _func_name(func: exp.Func) -> str:
    """Function name in lowercase.

    Unknown sqlglot functions (which is exactly what all blocked
    ``file``/``url``/``s3``/... are in ClickHouse) come through as ``Anonymous``,
    for the rest we take the node key (``count``, ``now``, ``format``).
    """
    if isinstance(func, exp.Anonymous):
        this = func.this
        if isinstance(this, exp.Identifier):
            return this.name.lower()
        return str(this).lower() if this is not None else ""
    return func.key.lower()


_SEVERITIES = frozenset(("low", "medium", "high", "critical"))


def extract_severity(query: str) -> str:
    """Extract severity from ``SELECT ... AS severity`` in a rule query.

    Static rules carry severity inside the SELECT (``'high' AS severity``),
    while ``alert_rules.rule_proposals`` has no separate severity column — we
    take it from the AST. If not found — ``medium``.
    """
    try:
        stmt = sqlglot.parse_one(query, dialect="clickhouse", error_level=ErrorLevel.RAISE)
    except Exception:  # noqa: BLE001 — invalid SQL — default to medium
        return "medium"
    if not isinstance(stmt, exp.Select):
        return "medium"
    for alias in stmt.find_all(exp.Alias):
        if (alias.alias or "").lower() == "severity" and isinstance(alias.this, exp.Literal):
            value = alias.this.name.lower()
            if value in _SEVERITIES:
                return value
    return "medium"


def validate_sql(query: str) -> tuple[bool, str]:
    """Validate a rule SQL.

    Returns ``(ok, reason)``: ``reason`` is empty on success, otherwise a
    short rejection reason (``parse_error: ...``, ``multi_statement``,
    ``not_select: <key>``, ``table_not_allowed: <db>.<table>``,
    ``blocked_function: <name>``).
    """
    try:
        statements = sqlglot.parse(query, dialect="clickhouse", error_level=ErrorLevel.RAISE)
    except Exception as exc:  # noqa: BLE001 — sqlglot raises several exception types
        return False, f"parse_error: {exc}"

    if len(statements) != 1:
        return False, "multi_statement"

    stmt = statements[0]
    if not isinstance(stmt, exp.Select):
        return False, f"not_select: {type(stmt).__name__}"

    for table in stmt.find_all(exp.Table):
        db = (table.db or "").lower()
        if db not in ALLOWED_DATABASES:
            qualified = f"{db}.{table.name}" if db else table.name
            return False, f"table_not_allowed: {qualified}"

    for func in stmt.find_all(exp.Func):
        name = _func_name(func)
        if name in BLOCKED_FUNCTIONS:
            return False, f"blocked_function: {name}"

    return True, ""
