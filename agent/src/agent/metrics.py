"""Prometheus-метрики агента."""

from prometheus_client import Counter, Gauge, Histogram

# Observer
observer_runs = Counter("agent_observer_runs_total", "Запуски Observer")
observer_assets_created = Counter("agent_observer_assets_created_total", "Новые активы")
observer_mcp_tools_created = Counter(
    "agent_observer_mcp_tools_created_total", "Новые MCP-инструменты"
)

# Correlator
correlator_incidents = Counter(
    "agent_correlator_incidents_total",
    "Инциденты по severity",
    ["severity"],
)

# Rule-Engine
rule_engine_proposals = Counter(
    "agent_rule_engine_proposals_total",
    "Предложения по статусу",
    ["status"],
)
rule_engine_llm_latency = Histogram(
    "agent_rule_engine_llm_latency_seconds",
    "Latency LLM-вызова",
)

# Validator
validator_rejections = Counter(
    "agent_validator_rejections_total",
    "Отклонения по причине",
    ["reason"],
)

# Promoter
promoted_rules = Counter("agent_promoted_rules_total", "Промоутированные правила")
promoted_assets = Counter("agent_promoted_assets_total", "Промоутированные активы")

# Gauges
active_rules = Gauge("agent_active_rules", "Активные правила", ["severity"])
incidents_fp_ratio = Gauge("agent_incidents_fp_ratio", "Доля FP (цель: < 20%)")
assets_observed = Gauge("agent_assets_observed_total", "Наблюдаемые активы", ["type"])
assets_declared = Gauge("agent_assets_declared_total", "Декларированные активы", ["type"])
gap_total = Gauge("agent_gap_total", "Gap (observed − declared)", ["type"])
tools_without_declaration = Gauge("agent_tools_without_declaration_total", "Вызовы без декларации")
