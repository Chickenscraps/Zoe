#!/usr/bin/env bash
# Brand enforcement check — fails CI if legacy/disallowed patterns are found.
# Run: bash scripts/check-brand-enforcement.sh

set -euo pipefail

SRC_DIR="src"
ERRORS=0

echo "=== Brand Enforcement Check ==="
echo ""

# 1. Check for NaN rendering in format helpers
echo "Checking for unguarded NaN in format helpers..."
if grep -rn '\$NaN\|NaN\$\|\.toFixed\b' "$SRC_DIR/lib/utils.ts" | grep -v 'isFinite\|isNaN\|guard'; then
  echo "  WARNING: Format helpers may produce NaN (check utils.ts)"
fi

# 2. Check for legacy Robinhood references
echo "Checking for legacy Robinhood references..."
LEGACY_HITS=$(grep -rni 'robinhood\|rh_cash\|rh_holdings\|robinhood_api' "$SRC_DIR" --include='*.tsx' --include='*.ts' || true)
if [ -n "$LEGACY_HITS" ]; then
  echo "  FAIL: Found Robinhood references:"
  echo "$LEGACY_HITS"
  ERRORS=$((ERRORS + 1))
fi

# 3. Check for blur shadows (should be pixel shadows only)
echo "Checking for blur shadows..."
BLUR_HITS=$(grep -rn 'shadow-soft\|shadow-lg\|shadow-xl\|shadow-2xl' "$SRC_DIR" --include='*.tsx' --include='*.ts' --include='*.css' | grep -v '\.output\|node_modules\|dist' || true)
if [ -n "$BLUR_HITS" ]; then
  echo "  WARNING: Found blur shadow classes (should use pixel shadows):"
  echo "$BLUR_HITS"
fi

# 4. Check for backdrop-blur (modern, not pixel)
echo "Checking for backdrop-blur..."
BACKDROP_HITS=$(grep -rn 'backdrop-blur' "$SRC_DIR" --include='*.tsx' --include='*.ts' --include='*.css' | grep -v 'node_modules\|dist' || true)
if [ -n "$BACKDROP_HITS" ]; then
  echo "  WARNING: Found backdrop-blur classes (not pixel aesthetic):"
  echo "$BACKDROP_HITS"
fi

# 5. Check for old rounded-modern classes
echo "Checking for non-pixel border-radius..."
ROUND_HITS=$(grep -rn 'rounded-lg\|rounded-xl\|rounded-2xl\|rounded-3xl\|rounded-full' "$SRC_DIR" --include='*.tsx' --include='*.ts' | grep -v 'petal\|animate\|SakuraPetals\|live-dot\|node_modules\|dist' || true)
if [ -n "$ROUND_HITS" ]; then
  echo "  WARNING: Found modern rounded classes (should be pixel corners):"
  echo "$ROUND_HITS"
fi

echo ""
if [ "$ERRORS" -gt 0 ]; then
  echo "FAIL: $ERRORS critical brand violations found."
  exit 1
else
  echo "PASS: No critical brand violations."
  exit 0
fi
