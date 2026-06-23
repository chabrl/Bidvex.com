# iter313 — P1 Production Verification Checklist

This document is a hand-off for the user to run on **production** (https://bidvex.com), since the agent only has access to the **preview** environment.

---

## 1. iter312 Data-Loss Reproduction Sanity Check

Run on **production** to confirm the AI-Review data-loss bug (hardcoded empty strings in flag-stub creation) is no longer regressing on real listings.

```bash
# SSH / pod shell on production
cd /app/backend
python -m pytest tests/test_iter312_ai_review_dataloss.py -v
```

Expected: **7/7 PASSED**.

If anything fails, copy the test output and tag the next agent.

---

## 2. Alex Boulanger Win-Email Repair

The user-reported missing win-email for buyer `alex.boulanger@example.com` (auction id from iter312 ticket).

```bash
# Dry-run first to inspect what would be emailed.
python /app/backend/scripts/repair_alex_boulanger_win_email.py --dry-run

# If the dry-run looks correct, re-run with --execute.
python /app/backend/scripts/repair_alex_boulanger_win_email.py --execute
```

Expected:
- Dry-run prints the auction id, the buyer email, and a preview of the templated message (no DB writes, no email sends).
- Execute mode logs `[OK] win email re-sent to alex.boulanger@example.com` and stamps `win_email_resent_at` on the auction document.

Verification: log in as the buyer (or check the SendGrid Activity feed) and confirm the email arrived.

---

## 3. iter309 D1 — Multi-Lot Category Backfill

This script restructures categories for any multi-lot vehicle auctions that pre-date the iter309 D1 category restructure.

```bash
# 1. Dry-run (read-only).
python /app/backend/scripts/iter309_d1_dryrun_multilot_categories.py

# 2. Inspect the dry-run output (which auctions would be touched + new category).
#    If satisfied, run the live backfill:
python /app/backend/scripts/iter309_d1_backfill_multilot_categories.py --execute
```

Expected:
- Dry-run prints `N auctions would be backfilled` and lists each old → new category mapping.
- Live run prints `OK backfilled N auctions` and stamps `category_backfilled_at` on each touched document.

Verification: open the **Lots Auction** marketplace tab on prod and confirm multi-lot vehicle auctions appear under their correct category filters (e.g. "Vehicles → Sedans" rather than the legacy "Multi-Lot" bucket).

---

## 4. SendGrid Delivery Verification

After steps 1–3, do a final SendGrid Activity feed check:

1. Open https://app.sendgrid.com/email_activity
2. Filter by `From: noreply@bidvex.com` and the last 24h.
3. Confirm:
   - `Delivered` count > 0.
   - `Bounces` < 1%.
   - `Spam Reports` < 0.1%.
   - The `Alex Boulanger` win-email has `Delivered` (not `Dropped` / `Bounced`).

---

## 5. iter313 P2 — Per-Campaign Auto-Pause Guardrail (NEW)

The new 5% guardrail is **passive** — it only triggers when SendGrid webhooks
report bounces/unsubscribes pushing a single campaign's negative ratio above
5%. There is nothing to verify proactively on production; the test suite
(`test_iter313_campaign_guardrail.py`, 9/9 passing) covers the logic.

To **manually test** the guardrail end-to-end on production:

1. Send a test campaign to a small (>=20-recipient) list.
2. After SendGrid reports the events back, check the admin banner at
   `https://bidvex.com/admin → Settings → External Campaigns`.
3. If any campaign is auto-paused, the banner appears at top with the ratio
   and a `Resume sending` button (which prompts for a free-text reason
   before flipping the campaign back to `sent` state).

The `auto_paused_at`, `auto_paused_ratio_pct`, `auto_paused_negative_count`,
and `auto_paused_attempted_count` fields are written onto the campaign
document for audit purposes. A row is also inserted into
`campaign_guardrail_events` on both pause and resume.

---

## Report-Back Format

Please paste the output of each command back to the next agent so they can
record the results in `/app/memory/CHANGELOG.md`. Use this template:

```
### iter313 P1 — Production Verification (run on bidvex.com, YYYY-MM-DD)

1. iter312 AI-review regression: ____/7 passed
2. Alex Boulanger repair: dry-run OK / execute OK
3. iter309 D1 backfill: N auctions backfilled
4. SendGrid Activity feed: Delivered=__, Bounces=__%, SpamReports=__%
5. iter313 P2 guardrail: no campaigns auto-paused / N campaigns auto-paused (list IDs)
```
