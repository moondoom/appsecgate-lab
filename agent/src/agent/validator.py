"""Валидатор SQL-правил (безопасный SELECT).

Политика безопасности для всего SQL, который попадает в ``alert_rules``
(статика из ``rules/static/`` и предложения Rule-Engine):

* ровно одно выражение — никакого multi-statement (``;``);
* только ``SELECT`` — без INSERT/UPDATE/DELETE/CREATE/ALTER/DROP/GRANT;
* все таблицы полностью квалифицированы и лежат в whitelist:
  ``security_logs.*`` и ``system.*``;
* запрещены функции доступа к внешним источникам
  (``file``/``url``/``s3``/``remote`` и аналоги в ClickHouse).

Обхода нет: проверка выполняется по AST sqlglot (dialect=clickhouse),
а не по строке.
"""

from __future__ import annotations

import sqlglot
from sqlglot import ErrorLevel, exp

ALLOWED_DATABASES: frozenset[str] = frozenset(("security_logs", "system"))

# Функции ClickHouse, дающие доступ к внешним источникам данных.
BLOCKED_FUNCTIONS: frozenset[str] = frozenset(
    (
        # файлы, URL, облачные/распределённые хранилища
        "file",
        "url",
        "s3",
        "gcs",
        "azureblobstorage",
        "hdfs",
        "web",
        "remote",
        "remotesecure",
        # внешние СУБД и очереди
        "mysql",
        "postgresql",
        "sqlite",
        "mongodb",
        "redis",
        "kafka",
        "jdbc",
        "odbc",
        # внешние словари
        "dictget",
    )
)


def _func_name(func: exp.Func) -> str:
    """Имя функции в нижнем регистре.

    Неизвестные sqlglot функции (а именно к ним относятся все блокируемые
    ``file``/``url``/``s3``/... в ClickHouse) приходят как ``Anonymous``,
    у остальных берём ключ узла (``count``, ``now``, ``format``).
    """
    if isinstance(func, exp.Anonymous):
        this = func.this
        if isinstance(this, exp.Identifier):
            return this.name.lower()
        return str(this).lower() if this is not None else ""
    return func.key.lower()


_SEVERITIES = frozenset(("low", "medium", "high", "critical"))


def extract_severity(query: str) -> str:
    """Достать severity из ``SELECT ... AS severity`` в запросе правила.

    Статические правила несут severity внутри SELECT (``'high' AS severity``),
    а в ``alert_rules.rule_proposals`` отдельной колонки severity нет — берём
    из AST. Если не нашлось — ``medium``.
    """
    try:
        stmt = sqlglot.parse_one(query, dialect="clickhouse", error_level=ErrorLevel.RAISE)
    except Exception:  # noqa: BLE001 — невалидный SQL — медиум по умолчанию
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
    """Проверить SQL правила.

    Возвращает ``(ok, reason)``: ``reason`` пустой при успехе, иначе —
    короткая причина отклонения (``parse_error: ...``, ``multi_statement``,
    ``not_select: <key>``, ``table_not_allowed: <db>.<table>``,
    ``blocked_function: <name>``).
    """
    try:
        statements = sqlglot.parse(query, dialect="clickhouse", error_level=ErrorLevel.RAISE)
    except Exception as exc:  # noqa: BLE001 — sqlglot бросает несколько типов исключений
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
