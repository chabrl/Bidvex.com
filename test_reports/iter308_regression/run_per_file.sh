#!/usr/bin/env bash
# iter308 regression — run iter299→iter308 each in its own pytest process,
# with a 35s sleep between files to let the auth rate-limit reset.

set +e
OUT=/app/test_reports/iter308_regression/per_file.log
SUM=/app/test_reports/iter308_regression/summary.txt
: > "$OUT"
: > "$SUM"

FILES=(
  backend/tests/test_iter299_e2e_preview.py
  backend/tests/test_iter299_postlaunch.py
  backend/tests/test_iter300_features.py
  backend/tests/test_iter301_features.py
  backend/tests/test_iter301_review_request.py
  backend/tests/test_iter302_settlement.py
  backend/tests/test_iter304_extra.py
  backend/tests/test_iter304_lot_templates_and_badges.py
  backend/tests/test_iter305_audit.py
  backend/tests/test_iter306_bulk_import_and_errors.py
  backend/tests/test_iter306_e2e_public.py
  backend/tests/test_iter306_push_dispatcher.py
  backend/tests/test_iter307_features.py
  backend/tests/test_iter307_remediation.py
  backend/tests/test_iter307_supplement.py
  backend/tests/test_iter308_billing_and_verification.py
)

cd /app
for f in "${FILES[@]}"; do
  echo "═══ $f ═══" | tee -a "$OUT"
  pytest "$f" -v --tb=short --no-header 2>&1 | tee -a "$OUT" > /tmp/last_run.log
  LAST=$(tail -1 /tmp/last_run.log)
  echo "$f :: $LAST" >> "$SUM"
  sleep 35
done

echo "═══════════ SUMMARY ═══════════" | tee -a "$OUT"
cat "$SUM" | tee -a "$OUT"
