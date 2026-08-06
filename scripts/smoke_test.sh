#!/usr/bin/env bash
set -euo pipefail

api_url="${API_URL:-http://localhost:8000}"
dashboard_url="${DASHBOARD_URL:-http://localhost:8501}"

curl --fail --silent --show-error "${api_url}/health" >/dev/null
curl --fail --silent --show-error "${api_url}/api/v1/summary" >/dev/null
curl --fail --silent --show-error "${api_url}/metrics" >/dev/null
curl --fail --silent --show-error "${dashboard_url}/_stcore/health" >/dev/null

echo "FinPulse smoke tests passed: API, warehouse serving, metrics, and dashboard are healthy."

