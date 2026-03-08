#!/bin/bash
# Aruvi Chapter Mapping — stable entry point
# Usage: bash run_mapping.sh --subject social_sciences --grade vii --chapters 1
# Usage: bash run_mapping.sh --subject mathematics --grade ix --all

SESSION_ROOT=$(dirname "$(realpath "$0")")
[ -f "$SESSION_ROOT/.env" ] && source "$SESSION_ROOT/.env"

# httpx can't use socks5h proxy; unset ALL_PROXY so it falls back to HTTP_PROXY
unset ALL_PROXY all_proxy

# Locate the skill dir (for bundled constitution files)
SKILL_DIR=$(find /sessions -type d -name "aruvi-chapter-mapping" -path "*/.skills/*" 2>/dev/null | head -1)

# Run from aruvi-scripts/ — writable copies of all skill scripts,
# including the patched call_mapping_api.py (verify=False + socks proxy fix)
python "$SESSION_ROOT/aruvi-scripts/run_mapping.py" \
  --config "$SESSION_ROOT/aruvi_config.json" \
  --skill-dir "$SKILL_DIR" \
  "$@"
