"""
iter208 — Document URL migration (idempotent, dry-run-able).

Purges absolute hostnames from every document URL stored in MongoDB so that
the frontend is the SOLE authority on which environment (preview vs
production) the file is fetched from.

Touches three fields:
    * users.partner_neq_document            (str | None)
    * users.partner_certifications[]        (List[str])
    * dealer_licenses.document_url          (str | None)

For each value:
    "http://localhost:8001/api/uploads/foo.pdf"   →  "/api/uploads/foo.pdf"
    "https://www.bidvex.com/api/uploads/foo.pdf"  →  "/api/uploads/foo.pdf"
    "https://bidvex.com/api/uploads/foo.pdf"      →  "/api/uploads/foo.pdf"
    "https://prod-verify-2.preview.emergentagent.com/api/uploads/foo.pdf" → "/api/uploads/foo.pdf"
    "/api/uploads/foo.pdf"                        →  unchanged
    "https://example.com/external.pdf"            →  unchanged (left for manual audit)

USAGE:
    python3 -m scripts.migrate_doc_urls_to_relative                # apply
    python3 -m scripts.migrate_doc_urls_to_relative --dry-run      # report only
"""
import asyncio
import os
import re
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


# Any hostname whose path begins with `/api/uploads/...` is one of OUR backend
# serving routes — strip the scheme+host so we keep ONLY the path.
_PREFIX_RE = re.compile(r"^https?://[^/]+(/api/uploads/.+)$", re.IGNORECASE)


def _normalize_url(value: str | None) -> str | None:
    """Return relative path if `value` is a BidVex /api/uploads/... URL, else unchanged."""
    if not value or not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    match = _PREFIX_RE.match(stripped)
    if match:
        return match.group(1)
    # Already relative path → ensure leading slash
    if stripped.startswith("/api/uploads/"):
        return stripped
    # External URL (e.g. https://example.com/...) → leave for manual audit
    return value


async def _migrate(db, *, dry_run: bool) -> dict:
    summary = {
        "users_neq_changed": 0,
        "users_certs_changed": 0,
        "dealer_licenses_changed": 0,
        "external_kept": [],
    }

    # 1) users.partner_neq_document  +  users.partner_certifications[]
    cursor = db.users.find(
        {"$or": [
            {"partner_neq_document": {"$exists": True, "$ne": None}},
            {"partner_certifications": {"$exists": True, "$ne": []}},
        ]},
        {"_id": 0, "id": 1, "email": 1, "partner_neq_document": 1, "partner_certifications": 1},
    )
    async for u in cursor:
        updates: dict = {}

        # NEQ document
        old_neq = u.get("partner_neq_document")
        new_neq = _normalize_url(old_neq)
        if old_neq and old_neq != new_neq:
            updates["partner_neq_document"] = new_neq
            summary["users_neq_changed"] += 1
            print(f"  users[{u.get('email')}] neq: {old_neq}  →  {new_neq}")
        elif old_neq and not old_neq.startswith("/api/uploads/") and not _PREFIX_RE.match(old_neq):
            summary["external_kept"].append(("users.partner_neq_document", u.get("email"), old_neq))

        # Certifications array
        certs = u.get("partner_certifications") or []
        if certs:
            new_certs = [_normalize_url(c) for c in certs]
            if new_certs != certs:
                updates["partner_certifications"] = new_certs
                summary["users_certs_changed"] += 1
                for o, n in zip(certs, new_certs):
                    if o != n:
                        print(f"  users[{u.get('email')}] cert: {o}  →  {n}")
                    elif o and not o.startswith("/api/uploads/") and not _PREFIX_RE.match(o):
                        summary["external_kept"].append(("users.partner_certifications[]", u.get("email"), o))

        if updates and not dry_run:
            await db.users.update_one({"id": u["id"]}, {"$set": updates})

    # 2) dealer_licenses.document_url
    cursor2 = db.dealer_licenses.find(
        {"document_url": {"$exists": True, "$ne": None}},
        {"_id": 0, "id": 1, "user_id": 1, "document_url": 1},
    )
    async for d in cursor2:
        old = d.get("document_url")
        new = _normalize_url(old)
        if old and old != new:
            summary["dealer_licenses_changed"] += 1
            print(f"  dealer_licenses[{d['id']}] url: {old}  →  {new}")
            if not dry_run:
                await db.dealer_licenses.update_one({"id": d["id"]}, {"$set": {"document_url": new}})
        elif old and not old.startswith("/api/uploads/") and not _PREFIX_RE.match(old):
            summary["external_kept"].append(("dealer_licenses.document_url", d.get("user_id"), old))

    return summary


async def main():
    dry_run = "--dry-run" in sys.argv
    load_dotenv("/app/backend/.env")
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        raise SystemExit("Missing MONGO_URL or DB_NAME in environment")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print(f"\n=== iter208 URL Migration {'(DRY RUN)' if dry_run else ''} ===")
    print(f"DB: {db_name}\n")
    summary = await _migrate(db, dry_run=dry_run)

    print("\n=== Summary ===")
    print(f"users.partner_neq_document changed:   {summary['users_neq_changed']}")
    print(f"users.partner_certifications[] rows changed: {summary['users_certs_changed']}")
    print(f"dealer_licenses.document_url changed: {summary['dealer_licenses_changed']}")
    if summary["external_kept"]:
        print(f"\n[INFO] {len(summary['external_kept'])} external URLs left untouched for manual audit:")
        for field, who, val in summary["external_kept"][:10]:
            print(f"  {field}  {who}  {val}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
