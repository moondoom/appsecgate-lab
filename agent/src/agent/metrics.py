"""Prometheus metrics for the agent.

Metric descriptions are in English (the Prometheus UI and dashboards are
consumed by the whole team).
"""

from prometheus_client import Counter, Gauge, Histogram

# Observer
observer_runs = Counter("agent_observer_runs_total", "Observer runs")
observer_assets_created = Counter("agent_observer_assets_created_total", "New assets")
observer_mcp_tools_created = Counter("agent_observer_mcp_tools_created_total", "New MCP tools")

# Correlator
correlator_incidents = Counter(
    "agent_correlator_incidents_total",
    "Incidents by severity",
    ["severity"],
)

# Rule-Engine
rule_engine_proposals = Counter(
    "agent_rule_engine_proposals_total",
    "Proposals by status",
    ["status"],
)
rule_engine_llm_latency = Histogram(
    "agent_rule_engine_llm_latency_seconds",
    "LLM call latency",
)

# Validator
validator_rejections = Counter(
    "agent_validator_rejections_total",
    "Rejections by reason",
    ["reason"],
)

# Promoter
promoted_rules = Counter("agent_promoted_rules_total", "Promoted rules")
promoted_assets = Counter("agent_promoted_assets_total", "Promoted assets")

# Gauges
active_rules = Gauge("agent_active_rules", "Active rules", ["severity"])
incidents_fp_ratio = Gauge("agent_incidents_fp_ratio", "FP ratio (target: < 20%)")
assets_observed = Gauge("agent_assets_observed_total", "Observed assets", ["type"])
assets_declared = Gauge("agent_assets_declared_total", "Declared assets", ["type"])
gap_total = Gauge("agent_gap_total", "Gap (observed − declared)", ["type"])
tools_without_declaration = Gauge(
    "agent_tools_without_declaration_total", "Calls without declaration"
)
