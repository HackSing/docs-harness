#!/bin/sh
set -eu

[ -n "${QODER_PROJECT_DIR:-}" ] || exit 0
[ -f "$QODER_PROJECT_DIR/routing/registry.json" ] || exit 0

exec /usr/bin/python3 "${DOCS_HARNESS_ROOT:?DOCS_HARNESS_ROOT is required}/routing/hosts/qoder/route_hook.py"
