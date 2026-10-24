#!/bin/sh
set -eu

if [ -z "${DOCS_HARNESS_ROOT:-}" ]; then
    echo "docs-harness router: DOCS_HARNESS_ROOT is required" >&2
    exit 0
fi

PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import sys" >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "docs-harness router: python not found" >&2
    exit 0
fi

exec "$PYTHON" "$DOCS_HARNESS_ROOT/routing/hosts/qoder/route_hook.py"
