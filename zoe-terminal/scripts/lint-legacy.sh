#!/usr/bin/env bash
# Detect legacy CSS patterns that violate the Sakura SNES theme.
# Exit non-zero if any violations found.
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1

ERRORS=0

check() {
  local pattern="$1" msg="$2"
  matches=$(grep -rn --include='*.tsx' --include='*.ts' "$pattern" src/ 2>/dev/null | grep -v node_modules || true)
  if [ -n "$matches" ]; then
    echo "❌ $msg"
    echo "$matches"
    echo ""
    ERRORS=$((ERRORS + 1))
  fi
}

echo "🌸 Sakura SNES Legacy Pattern Lint"
echo "==================================="
echo ""

check 'data-theme="paper"'     "Legacy paper theme attribute"
check 'noise-overlay'           "Legacy noise overlay class"
check 'trading-active-border'   "Legacy trading border class"
check 'useModeContext'          "Legacy mode context import"
check 'ModeProvider'            "Legacy ModeProvider"
check 'Starfield'               "Legacy Starfield component"

echo ""
if [ $ERRORS -eq 0 ]; then
  echo "✅ No legacy patterns found!"
  exit 0
else
  echo "⚠️  $ERRORS legacy pattern(s) detected"
  exit 1
fi
