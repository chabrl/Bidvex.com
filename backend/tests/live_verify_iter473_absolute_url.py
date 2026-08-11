"""iter473 — Verify absolute HTTPS URL generation in emailed financial
document links across ALL paths.

Coverage:
  1. `services.cloud_storage.generate_signed_url` returns an absolute
     https:// URL for ALL callers by default (fixed at source).
  2. `services.final_document_delivery.deliver_final_documents` produces
     buyer + seller emails whose `<a href>` is absolute HTTPS with a
     valid host — for the same iter472 matrix (marketplace / lots /
     vehicles / storage · EN + FR).
  3. Clicking the link resolves to the correct signed PDF (200
     application/pdf).
  4. Expired signature (past `expires` timestamp) is rejected by the
     download route.
  5. Cross-user isolation: recipient A's signed URL cannot be replayed
     by recipient B — the URL points to A's invoice only.
  6. Env-fallback safety: setting all base URL vars empty returns a
     relative URL (existing behaviour) rather than a bad absolute one.
  7. Malformed host guard: `localhost`, `127.0.0.1`, and non-http(s)
     values are rejected by the resolver.

Guardrails:
  * No production data touched.
  * No changes to document contents, financial calculations, email
    recipients, payment logic, Stripe, escrow, or deployment settings.
  * Every recipient uses the `charbel911+iter473-*@gmail.com` alias
    → single QA inbox.
  * Removable data prefixed `iter473-*` and cleaned on exit.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path("/app/backend")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # type: ignore
load_dotenv(BACKEND / ".env")
load_dotenv(Path("/app/frontend/.env"), override=False)

import httpx  # type: ignore
from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL") or "https://prod-verify-2.preview.emergentagent.com"
API = f"{BACKEND_URL.rstrip('/')}/api"

QA_INBOX = "charbel911@gmail.com"
LOCAL, DOMAIN = QA_INBOX.split("@")
PREFIX = "iter473-"

PASS, FAIL = "✓", "✗"
report: Dict[str, Any] = {
    "backend_url": BACKEND_URL, "qa_inbox": QA_INBOX,
    "checks": [], "hrefs": [], "click_through": [],
    "cross_user_replay": [], "expiry_rejection": [],
    "resolver_precedence": {},
}


def _alias(tag: str) -> str:
    return f"{LOCAL}+iter473{tag}@{DOMAIN}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def check(name: str, ok: bool, detail: str = ""):
    print(f"  {PASS if ok else FAIL} {name}{(' — ' + detail) if detail else ''}")
    report["checks"].append({"name": name, "ok": ok, "detail": detail})


# ── Seed helpers (reuse iter472 shape) ──────────────────────────────

async def seed_user(db, *, role: str, tag: str, lang: str) -> Dict[str, Any]:
    email = _alias(f"-{role}-{tag}-{uuid.uuid4().hex[:4]}")
    uid = f"{PREFIX}{role}-{tag}-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": uid, "email": email, "name": f"iter473 {role} {tag}",
        "role": "user", "account_type": "individual",
        "preferred_language": lang, "phone_verified": True,
        "email_verified": True, "id_verified": True,
        "created_at": now_iso(), "iter473_seed": True,
    })
    return {"id": uid, "email": email, "name": f"iter473 {role} {tag}",
            "preferred_language": lang}


async def seed_invoice(db, *, invoice_type: str, auction_id: str, user_id: str,
                       amount: float, title: str) -> Dict[str, Any]:
    from services.cloud_storage import store_invoice_pdf, generate_signed_url
    invoice_id = str(uuid.uuid4())
    invoice_number = f"INV-{auction_id[:6].upper()}-{uuid.uuid4().hex[:4].upper()}"
    pdf = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj\n"
        b"4 0 obj<</Length 44>>stream\nBT /F1 24 Tf 100 700 Td (iter473 QA PDF) Tj ET\nendstream endobj\n"
        b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000053 00000 n\n"
        b"0000000098 00000 n\n0000000162 00000 n\ntrailer<</Size 5/Root 1 0 R>>\nstartxref\n245\n%%EOF"
    )
    storage_path = None
    try:
        storage_path = await store_invoice_pdf(invoice_id, pdf, subfolder="iter473_qa")
    except Exception:  # noqa: BLE001
        storage_path = f"bidvex/invoices/iter473_qa/{invoice_id}.pdf"
    doc = {
        "id": invoice_id, "invoice_number": invoice_number,
        "invoice_type": invoice_type, "user_id": user_id,
        "auction_id": auction_id, "listing_title": title,
        "amount_paid_display": f"${amount:.2f} CAD",
        "net_payout_display": f"${amount * 0.95:.2f} CAD",
        "storage_path": storage_path,
        "download_url": generate_signed_url(invoice_id),
        "generated_date": now_iso(), "status": "generated",
        "iter473_seed": True,
    }
    await db.invoices.insert_one(doc)
    return doc


HREF_RE = re.compile(r'href="([^"]+)"[^>]*data-testid="(buyer-final-invoice-link|seller-final-statement-link)"')


async def capture_email_hrefs(db, section: str, lang: str, tag: str) -> Dict[str, str]:
    """Trigger `deliver_final_documents` while intercepting the email
    body so we can inspect the actual `<a href>` — the very thing the
    email client renders."""
    from services import emails as _emails_pkg
    from services.emails import email_system
    from services.final_document_delivery import deliver_final_documents

    captured = {}
    orig_send = email_system._send_via_unified

    async def _cap(*, to_email, subject, html_content, **kw):
        for match in HREF_RE.finditer(html_content):
            href, kind = match.group(1), match.group(2)
            captured[kind] = {"href": href, "to_email": to_email,
                              "subject": subject}
        # Do NOT actually dispatch — QA is capturing hrefs only.
        return {"success": True, "captured": True}

    email_system._send_via_unified = _cap
    try:
        buyer = await seed_user(db, role="buyer", tag=tag, lang=lang)
        seller = await seed_user(db, role="seller", tag=tag, lang=lang)
        aid = f"{PREFIX}{section}-{tag}-{uuid.uuid4().hex[:8]}"
        title = f"iter473 {section.upper()} {lang.upper()} — {tag}"
        await seed_invoice(db, invoice_type="lots_won", auction_id=aid,
                          user_id=buyer["id"], amount=142.99, title=title)
        await seed_invoice(db, invoice_type="seller_statement", auction_id=aid,
                          user_id=seller["id"], amount=142.99, title=title)
        out = await deliver_final_documents(
            db, auction_id=aid, buyer_id=buyer["id"], seller_id=seller["id"],
            payment_method="stripe",
            buyer_charge={"stripe_pi": f"pi_iter473_{uuid.uuid4().hex[:6]}",
                          "amount": 142.99},
            listing_title=title,
        )
        return {"buyer": captured.get("buyer-final-invoice-link", {}),
                "seller": captured.get("seller-final-statement-link", {}),
                "buyer_id": buyer["id"], "seller_id": seller["id"],
                "auction_id": aid, "delivery_out": out}
    finally:
        email_system._send_via_unified = orig_send


async def cleanup(db):
    targets = [
        ("users", {"iter473_seed": True}),
        ("invoices", {"iter473_seed": True}),
        ("settlement_email_dispatches", {"auction_id": {"$regex": f"^{PREFIX}"}}),
    ]
    removed = {}
    for coll, q in targets:
        r = await db[coll].delete_many(q)
        removed[coll] = r.deleted_count
    return removed


# ── Tests ────────────────────────────────────────────────────────────

async def t1_env_resolver_precedence():
    print("[T1] Base-URL resolver precedence and safety")
    # Reload the module so env changes take effect.
    saved_env = {k: os.environ.get(k) for k in
                 ("PUBLIC_BASE_URL", "APP_URL", "FRONTEND_URL", "REACT_APP_BACKEND_URL")}

    def _reload_resolver():
        import importlib
        import services.cloud_storage as cs
        return importlib.reload(cs)

    # 1. Explicit PUBLIC_BASE_URL wins.
    os.environ["PUBLIC_BASE_URL"] = "https://qa.example.com"
    os.environ["APP_URL"] = "https://other.example.com"
    cs = _reload_resolver()
    r1 = cs._resolve_public_base_url()
    check("T1a: PUBLIC_BASE_URL wins over APP_URL", r1 == "https://qa.example.com", r1)

    # 2. Fallback chain to APP_URL when PUBLIC_BASE_URL unset.
    os.environ.pop("PUBLIC_BASE_URL", None)
    cs = _reload_resolver()
    r2 = cs._resolve_public_base_url()
    check("T1b: falls back to APP_URL", r2 == "https://other.example.com", r2)

    # 3. Skips localhost.
    os.environ["APP_URL"] = "http://localhost:8000"
    os.environ["FRONTEND_URL"] = "https://frontend.example.com"
    cs = _reload_resolver()
    r3 = cs._resolve_public_base_url()
    check("T1c: skips localhost -> uses FRONTEND_URL", r3 == "https://frontend.example.com", r3)

    # 4. Skips 127.0.0.1.
    os.environ["APP_URL"] = "https://127.0.0.1:9000"
    cs = _reload_resolver()
    r4 = cs._resolve_public_base_url()
    check("T1d: skips 127.0.0.1", r4 == "https://frontend.example.com", r4)

    # 5. Skips schemeless / invalid.
    os.environ["APP_URL"] = "ftp://example.com"
    cs = _reload_resolver()
    r5 = cs._resolve_public_base_url()
    check("T1e: skips non-http(s) scheme", r5 == "https://frontend.example.com", r5)

    # 6. No env set → warns, returns "".
    for k in ("PUBLIC_BASE_URL", "APP_URL", "FRONTEND_URL", "REACT_APP_BACKEND_URL"):
        os.environ.pop(k, None)
    cs = _reload_resolver()
    r6 = cs._resolve_public_base_url()
    check("T1f: returns empty when no host configured", r6 == "", r6)

    # Restore prod env
    for k, v in saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    _reload_resolver()
    report["resolver_precedence"] = {"r1": r1, "r2": r2, "r3": r3, "r4": r4, "r5": r5, "r6": r6}


async def t2_signed_url_absolute():
    print("[T2] generate_signed_url returns absolute HTTPS by default")
    import importlib, services.cloud_storage as cs
    cs = importlib.reload(cs)
    u = cs.generate_signed_url("test-abc")
    check("T2a: starts with https://", u.startswith("https://"), u[:80])
    check("T2b: no `http:///` empty host", "http:///" not in u, u[:80])
    check("T2c: no localhost", "localhost" not in u, u[:80])
    check("T2d: includes /api/invoices/download/test-abc",
          "/api/invoices/download/test-abc" in u, u)
    check("T2e: has expires + sig query", "expires=" in u and "sig=" in u, u)


async def t3_email_hrefs_absolute(db):
    print("[T3] Email `<a href>` links are absolute HTTPS across matrix")
    scenarios = [
        ("lots", "en", "L-EN"), ("lots", "fr", "L-FR"),
        ("marketplace", "en", "M-EN"), ("marketplace", "fr", "M-FR"),
        ("vehicles", "en", "V-EN"), ("vehicles", "fr", "V-FR"),
        ("storage", "en", "S-EN"), ("storage", "fr", "S-FR"),
    ]
    for section, lang, tag in scenarios:
        cap = await capture_email_hrefs(db, section, lang, tag)
        for role in ("buyer", "seller"):
            info = cap.get(role, {})
            href = info.get("href", "")
            report["hrefs"].append({
                "section": section, "lang": lang, "role": role,
                "href": href, "to_email": info.get("to_email", ""),
                "subject": info.get("subject", ""),
            })
            label = f"[{section}][{lang}][{role}]"
            check(f"T3a {label}: href present", bool(href))
            check(f"T3b {label}: absolute HTTPS", href.startswith("https://"), href[:80])
            check(f"T3c {label}: no http:///", "http:///" not in href)
            check(f"T3d {label}: no localhost/127.0.0.1",
                  "localhost" not in href and "127.0.0.1" not in href)
            check(f"T3e {label}: has /api/invoices/download/",
                  "/api/invoices/download/" in href)
            check(f"T3f {label}: has expires + sig",
                  "expires=" in href and "sig=" in href)


async def t4_click_through(db):
    print("[T4] Click-through — every captured href resolves to signed PDF")
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as http:
        for entry in report["hrefs"]:
            href = entry["href"]
            if not href.startswith("https://"):
                continue
            try:
                r = await http.get(href)
                ok = r.status_code == 200
                content_type = r.headers.get("content-type", "")
                report["click_through"].append({
                    **entry, "status": r.status_code,
                    "content_type": content_type, "ok": ok,
                })
                check(f"T4 [{entry['section']}][{entry['lang']}][{entry['role']}] "
                      f"click → 200 PDF",
                      ok and "application/pdf" in content_type,
                      f"status={r.status_code} type={content_type}")
            except Exception as e:  # noqa: BLE001
                report["click_through"].append({**entry, "err": str(e), "ok": False})
                check(f"T4 [{entry['section']}][{entry['lang']}][{entry['role']}]",
                      False, str(e))


async def t5_expired_signature_rejected():
    """iter473 — an expired signature must be rejected (401/403/410)."""
    print("[T5] Expired signature rejected")
    from services.cloud_storage import _sign
    fake_id = str(uuid.uuid4())
    expires = int(time.time()) - 60  # 1 min ago
    payload = f"{fake_id}:{expires}"
    sig = _sign(payload)
    url = f"{BACKEND_URL.rstrip('/')}/api/invoices/download/{fake_id}?expires={expires}&sig={sig}"
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.get(url)
    report["expiry_rejection"].append({"status": r.status_code, "body": r.text[:200]})
    check("T5a: expired signature returns 401/403/410",
          r.status_code in (401, 403, 410, 400),
          f"got {r.status_code}")
    check("T5b: expired signature does NOT return 200",
          r.status_code != 200, f"got {r.status_code}")


async def t6_cross_user_replay(db):
    """iter473 — recipient B cannot open recipient A's document."""
    print("[T6] Cross-user isolation — B can't replay A's link")
    if not report["hrefs"]:
        check("T6: hrefs available", False, "no hrefs captured")
        return
    # Pick the first two DIFFERENT buyer hrefs across different auctions
    buyer_hrefs = [h for h in report["hrefs"] if h["role"] == "buyer"]
    if len(buyer_hrefs) < 2:
        check("T6: two distinct buyer hrefs", False)
        return
    href_a, href_b = buyer_hrefs[0]["href"], buyer_hrefs[1]["href"]
    # Each URL carries its own invoice_id. The signature is bound to
    # that specific invoice_id — a valid signature for URL A cannot be
    # transplanted onto URL B and vice versa.
    # Test: swap the invoice IDs while keeping signatures.
    match_a = re.search(r"/api/invoices/download/([^?]+)\?expires=(\d+)&sig=([a-f0-9]+)", href_a)
    match_b = re.search(r"/api/invoices/download/([^?]+)\?expires=(\d+)&sig=([a-f0-9]+)", href_b)
    if not (match_a and match_b):
        check("T6: url shape parseable", False)
        return
    id_a, exp_a, sig_a = match_a.group(1), match_a.group(2), match_a.group(3)
    id_b, _, _ = match_b.group(1), match_b.group(2), match_b.group(3)
    # Substitute B's invoice id but keep A's signature → forgery attempt.
    host = BACKEND_URL.rstrip("/")
    forged = f"{host}/api/invoices/download/{id_b}?expires={exp_a}&sig={sig_a}"
    async with httpx.AsyncClient(timeout=10) as http:
        r = await http.get(forged)
    report["cross_user_replay"].append({
        "original_A": href_a[:80], "forged": forged[:80],
        "status": r.status_code,
    })
    check("T6a: forged signature (A's sig on B's id) rejected",
          r.status_code in (401, 403, 400, 404),
          f"got {r.status_code}")
    check("T6b: forged does NOT return 200",
          r.status_code != 200, f"got {r.status_code}")


# ── Runner ──────────────────────────────────────────────────────────

async def main():
    print(f"[iter473] backend: {BACKEND_URL}")
    print(f"[iter473] db: {DB_NAME}")
    print(f"[iter473] QA inbox: {QA_INBOX}\n")

    await t1_env_resolver_precedence()
    print()
    await t2_signed_url_absolute()
    print()

    client = AsyncIOMotorClient(MONGO_URL, tz_aware=True)
    db = client[DB_NAME]
    try:
        await t3_email_hrefs_absolute(db)
        print()
        await t4_click_through(db)
        print()
        await t5_expired_signature_rejected()
        print()
        await t6_cross_user_replay(db)
    finally:
        report_path = Path("/app/test_reports/iter473_absolute_url_qa.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, default=str))
        print(f"\n[iter473] report saved → {report_path}")
        removed = await cleanup(db)
        print(f"[iter473] cleanup: {removed}")

    total = len(report["checks"])
    ok = sum(1 for c in report["checks"] if c["ok"])
    print("\n═════════════════════════════════════════════")
    print(f"[iter473] RESULT: {ok}/{total} checks PASS")
    print("═════════════════════════════════════════════")
    failed = [c for c in report["checks"] if not c["ok"]]
    if failed:
        for c in failed:
            print(f"  {FAIL} {c['name']} — {c['detail']}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
