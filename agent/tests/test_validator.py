"""Validator tests: the "safe SELECT only" policy."""

from pathlib import Path

import pytest

from agent.validator import extract_severity, validate_sql

RULES_DIR = Path(__file__).resolve().parents[2] / "rules" / "static"


class TestValidSql:
    def test_all_static_rules_are_valid(self) -> None:
        """Every static rule must pass validation."""
        for rule_file in sorted(RULES_DIR.glob("*.sql")):
            query = rule_file.read_text(encoding="utf-8")
            ok, reason = validate_sql(query)
            assert ok, f"{rule_file.name}: {reason}"

    def test_simple_select(self) -> None:
        ok, reason = validate_sql(
            "SELECT count() FROM security_logs.assets WHERE asset_type = 'host'"
        )
        assert ok, reason

    def test_system_table_allowed(self) -> None:
        ok, reason = validate_sql("SELECT name FROM system.tables WHERE database = 'security_logs'")
        assert ok, reason

    def test_subquery_is_allowed(self) -> None:
        ok, reason = validate_sql(
            """
            SELECT a.asset_key
            FROM security_logs.assets AS a
            WHERE NOT EXISTS (
                SELECT 1 FROM security_logs.assets AS d
                WHERE d.asset_key = a.asset_key
            )
            """
        )
        assert ok, reason

    def test_settings_clause_allowed(self) -> None:
        """LEFT JOIN rules use SETTINGS join_use_nulls = 1 (anti-join via IS NULL)."""
        ok, reason = validate_sql(
            """
            SELECT e.tool_name
            FROM security_logs.events_tool_calls AS e
            LEFT JOIN security_logs.mcp_tools AS m ON e.tool_name = m.tool_name
            WHERE e.timestamp >= now() - INTERVAL 10 MINUTE
              AND m.tool_id IS NULL
            GROUP BY e.tool_name
            SETTINGS join_use_nulls = 1
            """
        )
        assert ok, reason


class TestSeverityExtraction:
    def test_from_literal_alias(self) -> None:
        assert extract_severity("SELECT 'high' AS severity FROM security_logs.assets") == "high"

    def test_case_insensitive_alias(self) -> None:
        query = "SELECT 'CRITICAL' AS Severity FROM security_logs.assets"
        assert extract_severity(query) == "critical"

    def test_missing_severity_defaults_medium(self) -> None:
        assert extract_severity("SELECT asset_key FROM security_logs.assets") == "medium"

    def test_invalid_query_defaults_medium(self) -> None:
        assert extract_severity("NOT SQL AT ALL") == "medium"

    def test_low_value_accepted(self) -> None:
        assert extract_severity("SELECT 'low' AS severity FROM security_logs.assets") == "low"


class TestRejectedSql:
    def test_insert_rejected(self) -> None:
        ok, reason = validate_sql("INSERT INTO security_logs.assets (asset_key) VALUES ('x')")
        assert not ok
        assert reason.startswith("not_select")

    def test_create_rejected(self) -> None:
        ok, reason = validate_sql("CREATE TABLE security_logs.x (a UInt8)")
        assert not ok
        assert reason.startswith("not_select")

    def test_multi_statement_rejected(self) -> None:
        ok, reason = validate_sql(
            "SELECT 1 FROM security_logs.assets; SELECT 2 FROM security_logs.assets"
        )
        assert not ok
        assert reason == "multi_statement"

    def test_foreign_table_rejected(self) -> None:
        ok, reason = validate_sql("SELECT * FROM external.events")
        assert not ok
        assert reason == "table_not_allowed: external.events"

    def test_unqualified_table_rejected(self) -> None:
        ok, reason = validate_sql("SELECT * FROM assets")
        assert not ok
        assert reason == "table_not_allowed: assets"

    @pytest.mark.parametrize(
        "fn",
        [
            "file('/etc/passwd')",
            "url('http://evil')",
            "s3('https://bucket/x')",
            "remote('127.0.0.1:9000', 'db', 'u', 'p')",
            "mysql('host:3306', 'db', 'u', 'p')",
        ],
    )
    def test_blocked_functions_rejected(self, fn: str) -> None:
        ok, reason = validate_sql(
            f"SELECT {fn} FROM security_logs.assets WHERE asset_type = 'host'"
        )
        assert not ok
        assert reason == f"blocked_function: {fn.split('(')[0].lower()}"

    def test_bad_syntax_rejected(self) -> None:
        ok, reason = validate_sql("SELEC * FROM security_logs.assets")
        assert not ok
        assert reason.startswith("parse_error")
