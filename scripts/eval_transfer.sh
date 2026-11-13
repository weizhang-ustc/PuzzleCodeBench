#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  echo "usage: bash scripts/eval_transfer.sh <ref|model_name> [extra args...]"
  exit 2
fi
shift || true
python "$ROOT/scripts/eval_transfer.py" "$TARGET" "$@"
