.PHONY: regression-fast regression-full

# 90-second monetization + listing-pipeline guard
# Covers: footer link, annual fee Stripe checkout, webhook fields,
# admin tier override, verification push+email side-effects, and the
# iter309 bulletproof listing pipeline (single, multi-lot, storage,
# bilingual 400 validator).
#
# Targets the iter308 + iter309 files explicitly because some other
# test files in /app/backend/tests do `assert ENV_VAR` or `sys.exit()`
# at module-load and would break a marker-only collection.
regression-fast:
	pytest backend/tests/test_iter308_billing_and_verification.py \
	       backend/tests/test_iter309_bulletproof_listing.py \
	       backend/tests/test_iter310_bulk_delete_cascade.py \
	       backend/tests/test_iter310_bill96_compliance.py \
	       -v --tb=short

# Full iter299→iter309 regression (~17 min, per-file with 35s rate-limit spacing).
regression-full:
	bash /app/test_reports/iter308_regression/run_per_file.sh
