"""
iter315 — One-shot patcher for in-flight legacy-logo email rows.

Background
----------
iter314 introduced the canonical BidVex logo URL and a server-side
header injection at every send dispatcher. However, any row already
sitting in `email_outbox` or `external_email_campaigns` BEFORE iter314
shipped could carry the older logo URL (or no logo at all) in its
serialised HTML payload — and those rows can still be drained or sent
manually by an admin after iter314 deploy.

This script closes that gap.

What it does
------------
Scans both collections for `status ∈ {scheduled, draft, pending_send,
pending, queued, sending}` rows whose HTML body references the **legacy**
BidVex logo URL token (or has no canonical logo at all) and rewrites
them in-place using the exact same idempotent helpers iter314 ships
(`inject_bidvex_logo_header()` for outbox rows, `wrap_external_campaign_body()`
for external campaigns — so the admin-authored body always lands inside
the standard BidVex shell with header + CASL footer).

Usage
-----
    # 1. Dry-run (no writes). Prints affected count + 3 before/after diffs.
    python /app/backend/scripts/iter315_patch_legacy_logo.py

    # 2. Live patch.
    python /app/backend/scripts/iter315_patch_legacy_logo.py --execute

Optional flags
--------------
    --only outbox          patch only email_outbox
    --only campaigns       patch only external_email_campaigns
    --include-sent         also patch rows in terminal states (default: skip
                           sent/cancelled/failed — those have already been
                           delivered and there's no point rewriting history)
    --sample N             show N before/after diffs in dry-run (default 3)

Idempotency
-----------
Running the script twice in a row is a no-op: the second run's match
count is zero because the first run already injected the canonical logo
token. The same helpers used at runtime by `send_email()` are used here.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import List

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.emails._email_core import (  # noqa: E402
    BIDVEX_LOGO_URL,
    BIDVEX_LOGO_ID_TOKEN,
    inject_bidvex_logo_header,
)
from services.external_email import wrap_external_campaign_body  # noqa: E402

LEGACY_LOGO_TOKEN_1 = "31636d5f-c160-446b-b715-bcf542e9607e"  # email_templates.py legacy
LEGACY_LOGO_TOKEN_2 = "9dc6a7c3-8237-4a66-b82b-0d9abc165b44"  # email_service.py legacy

OUTBOX_STATUSES_DEFAULT = {"scheduled", "draft", "pending_send",
                           "pending", "queued", "sending", "retry"}
CAMPAIGN_STATUSES_DEFAULT = {"scheduled", "draft", "pending_send",
                             "pending", "queued", "sending"}


def _needs_patch(html: str) -> bool:
    """A row needs patching iff its HTML is non-empty and DOES NOT
    already contain the canonical logo id-token. (Rows with a legacy
    URL OR no logo at all both qualify.)"""
    if not html or not isinstance(html, str):
        return False
    if BIDVEX_LOGO_ID_TOKEN in html:
        return False
    return True


def _diff_summary(before: str, after: str) -> str:
    """Tiny human-readable diff."""
    if before == after:
        return "(no change)"
    return (f"  before: {len(before):>6} chars, canonical-URL count = {before.count(BIDVEX_LOGO_URL)}, "
            f"legacy1={before.count(LEGACY_LOGO_TOKEN_1)}, legacy2={before.count(LEGACY_LOGO_TOKEN_2)}\n"
            f"  after:  {len(after):>6} chars, canonical-URL count = {after.count(BIDVEX_LOGO_URL)}, "
            f"legacy1={after.count(LEGACY_LOGO_TOKEN_1)}, legacy2={after.count(LEGACY_LOGO_TOKEN_2)}")


async def patch_email_outbox(db, *, execute: bool, statuses: set,
                              sample_n: int) -> dict:
    """email_outbox stores transactional drains (html_content)."""
    q = {"status": {"$in": list(statuses)}}
    cursor = db.email_outbox.find(q, {"_id": 0, "id": 1, "html_content": 1, "status": 1, "subject": 1})
    rows = await cursor.to_list(length=20000)
    affected, samples = [], []
    for row in rows:
        before = row.get("html_content") or ""
        if not _needs_patch(before):
            continue
        after = inject_bidvex_logo_header(before)
        if after == before:
            continue
        affected.append({"id": row.get("id"), "status": row.get("status"),
                         "subject": (row.get("subject") or "")[:60]})
        if len(samples) < sample_n:
            samples.append({
                "id": row.get("id"), "subject": (row.get("subject") or "")[:80],
                "status": row.get("status"),
                "diff": _diff_summary(before, after),
            })
        if execute:
            await db.email_outbox.update_one(
                {"id": row.get("id")},
                {"$set": {
                    "html_content": after,
                    "iter315_patched_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
    return {
        "collection": "email_outbox",
        "scanned": len(rows),
        "affected": len(affected),
        "samples": samples,
    }


async def patch_external_campaigns(db, *, execute: bool, statuses: set,
                                    sample_n: int) -> dict:
    """external_email_campaigns stores per-language admin-authored HTML
    in `body_html_en` and `body_html_fr`. We wrap (logo+CASL) using the
    same `wrap_external_campaign_body()` helper used at live send."""
    q = {"status": {"$in": list(statuses)}}
    cursor = db.external_email_campaigns.find(
        q, {"_id": 0, "id": 1, "name": 1, "status": 1,
            "body_html_en": 1, "body_html_fr": 1},
    )
    rows = await cursor.to_list(length=5000)
    affected, samples = [], []
    # NB: at send-time the campaign payload is wrapped per-recipient with
    # a personalised {unsubscribe_url}. Here, since we don't know each
    # recipient's URL, we wrap with the literal token "{unsubscribe_url}"
    # so the templating logic at send time still kicks in correctly.
    PLACEHOLDER_UNSUB = "{unsubscribe_url}"
    for row in rows:
        any_change = False
        update = {}
        for field in ("body_html_en", "body_html_fr"):
            before = row.get(field) or ""
            if not before:
                continue
            if not _needs_patch(before):
                continue
            after = wrap_external_campaign_body(before, PLACEHOLDER_UNSUB)
            if after == before:
                continue
            update[field] = after
            any_change = True
            if len(samples) < sample_n:
                samples.append({
                    "id": row.get("id"), "name": row.get("name"),
                    "status": row.get("status"), "field": field,
                    "diff": _diff_summary(before, after),
                })
        if not any_change:
            continue
        affected.append({"id": row.get("id"), "name": row.get("name"),
                         "status": row.get("status"),
                         "fields_patched": list(update.keys())})
        if execute:
            update["iter315_patched_at"] = datetime.now(timezone.utc).isoformat()
            await db.external_email_campaigns.update_one(
                {"id": row.get("id")}, {"$set": update},
            )
    return {
        "collection": "external_email_campaigns",
        "scanned": len(rows),
        "affected": len(affected),
        "samples": samples,
    }


def _print_report(report: dict) -> None:
    print(f"\n— {report['collection']} —")
    print(f"  scanned : {report['scanned']}")
    print(f"  affected: {report['affected']}")
    for i, s in enumerate(report["samples"], 1):
        print(f"\n  sample [{i}]")
        for k, v in s.items():
            if k == "diff":
                print(f"    {k}:\n{v}")
            else:
                print(f"    {k}: {v}")


async def amain(args) -> int:
    mongo_url = os.environ["MONGO_URL"]
    db_name   = os.environ["DB_NAME"]
    client    = AsyncIOMotorClient(mongo_url)
    db        = client[db_name]

    statuses_out  = OUTBOX_STATUSES_DEFAULT
    statuses_camp = CAMPAIGN_STATUSES_DEFAULT
    if args.include_sent:
        statuses_out  = statuses_out  | {"sent", "failed", "cancelled"}
        statuses_camp = statuses_camp | {"sent", "auto_paused", "cancelled"}

    print("\niter315 — Legacy-logo patcher")
    print("=" * 60)
    print(f"DB:        {db_name}")
    print(f"Mode:      {'EXECUTE (writes will happen)' if args.execute else 'DRY-RUN (no writes)'}")
    print(f"Scope:     {args.only or 'both collections'}")
    print(f"Statuses:  outbox={sorted(statuses_out)}  campaigns={sorted(statuses_camp)}")
    print(f"Canonical: {BIDVEX_LOGO_URL}")
    print()

    reports: List[dict] = []
    if args.only in (None, "outbox"):
        reports.append(await patch_email_outbox(
            db, execute=args.execute, statuses=statuses_out, sample_n=args.sample))
    if args.only in (None, "campaigns"):
        reports.append(await patch_external_campaigns(
            db, execute=args.execute, statuses=statuses_camp, sample_n=args.sample))

    for r in reports:
        _print_report(r)

    total_affected = sum(r["affected"] for r in reports)
    print(f"\nTotal documents {'PATCHED' if args.execute else 'WOULD BE PATCHED'}: {total_affected}")

    if not args.execute and total_affected > 0:
        print("\n→ Re-run with --execute to apply.")
    elif args.execute and total_affected > 0:
        print("\n→ All affected rows now carry the canonical BidVex logo.")
    elif total_affected == 0:
        print("\n✓ Nothing to patch — every in-flight row already carries the canonical logo.")

    client.close()
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="iter315 legacy-logo patcher")
    p.add_argument("--execute", action="store_true",
                   help="Actually write changes (default: dry-run)")
    p.add_argument("--only", choices=("outbox", "campaigns"), default=None,
                   help="Restrict to one collection")
    p.add_argument("--include-sent", action="store_true",
                   help="Include terminal-state rows (sent/cancelled/failed). "
                        "Not recommended — those emails already left the platform.")
    p.add_argument("--sample", type=int, default=3,
                   help="Number of before/after diff samples to print (default 3)")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(amain(parse_args())))
