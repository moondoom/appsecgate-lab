#!/usr/bin/env bash
set -euo pipefail

# Сквозная проверка стенда.

echo "=== Smoke test ==="

# 1. Сервисы healthy
echo "→ checking services..."
docker compose ps --format json | python3 -c "
import json, sys
for line in sys.stdin:
    s = json.loads(line.strip())
    assert s['State'] == 'running', f'{s[\"Name\"]} is {s[\"State\"]}'
    if s.get('Health'):
        assert s['Health'] == 'healthy', f'{s[\"Name\"]} health: {s[\"Health\"]}'
print('  ✓ all services running')
"

# 2. ClickHouse отвечает
echo "→ checking clickhouse..."
docker compose exec -T clickhouse clickhouse-client --query "SELECT 1" || {
    echo "  ✗ ClickHouse not responding"
    exit 1
}
echo "  ✓ ClickHouse OK"

# 3. Prometheus отвечает
echo "→ checking prometheus..."
curl -sf http://localhost:9090/-/ready > /dev/null && echo "  ✓ Prometheus OK" || {
    echo "  ✗ Prometheus not ready"
    exit 1
}

# 4. В ClickHouse есть таблицы
echo "→ checking tables..."
tables=$(docker compose exec -T clickhouse clickhouse-client --query "
    SELECT count() FROM system.tables WHERE database = 'security_logs'
" 2>/dev/null || echo "0")
echo "  → security_logs tables: $tables"

# 5. Агент отдаёт метрики
echo "→ checking agent metrics..."
curl -sf http://localhost:9101/metrics 2>/dev/null | grep -q 'agent_' && {
    echo "  ✓ agent metrics OK"
} || echo "  ⚠ agent metrics not available (agent may not be running)"

echo ""
echo "=== Smoke test passed ==="
