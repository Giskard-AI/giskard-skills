#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Copy .env.example to .env and set OPENAI_API_KEY"
  exit 1
fi

uv sync
uv run python eval/test_sql_guardrails.py
echo ""
uv run python run_suite.py "$@"
