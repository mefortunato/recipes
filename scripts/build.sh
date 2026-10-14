#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== Building Svelte Frontend to Static Assets ==="
cd "${ROOT_DIR}/frontend"
npm run build

echo "=== Running Backend Pytest Test Suite with uv ==="
cd "${ROOT_DIR}/backend"
uv run pytest tests/

echo "=== Build & Verification Complete! ==="
