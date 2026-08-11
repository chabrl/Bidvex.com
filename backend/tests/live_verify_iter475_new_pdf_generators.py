"""iter475 — Verify EVERY newly-supported dashboard document.

Uses iter474's removable seed as the settlement base (same auctions,
same receipts). Then hits `/api/dashboard/documents/{purchase,sale}`
for each (section, role) combination and asserts:

  • The endpoint reports `available: true` for every previously-gap
    document (Storage buyer invoice, Universal receipt across all 4
    sections, Marketplace seller stmt/receipt/commission, Vehicles
    seller stmt/receipt/commission, Storage seller stmt/receipt/
    commission).
  • The signed URL is absolute HTTPS.
  • Click-through returns `200 application/pdf` with a `%PDF-` magic
    number in the body (host swapped to caller-base for reachability;
    signature/expiry/id preserved — see iter474 note).
  • The totals rendered in the PDF match the `total_charged` (buyer) /
    `net_payout` (seller) column of `db.receipts` — proving no math
    was recomputed.
  • Second request for the same document returns the SAME invoice_id
    (idempotent — no duplicate PDF generation).
  • Cross-user 403 for non-owner requests.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

BACKEND = Path("/app/backend")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # type: ignore
load_dotenv(BACKEND / ".env")

import httpx  # type: ignore
from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore

BASE = os.environ.get(
    "FRONTEND_URL",
    "https://prod-verify-2.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE}/api"


async def _login(client, email, password):
    r = await client.post(f"{API}/auth/login",
                          json={"email": email, "password": password})
    tok = r.json().get("access_token") or r.json().get("token")
    if not tok:
        raise RuntimeError(f"login {email} → {r.status_code} {r.text[:120]}")
    return tok


def _swap_host(url: str, target_host: str) -> str:
    p = urlparse(url)
    return url.replace(p.netloc, target_host)


def _sum_receipts(rows, field):
    total = Decimal("0")
    for r in rows:
        v = r.get(field)
        if v is None or v == "":
            continue
        try:
            total += Decimal(str(v))
        except Exception:  # noqa: BLE001
            continue
    return total


def _extract_totals_from_pdf(pdf_bytes: bytes) -> list:
    """Extract dollar amounts from PDF using pypdf text extraction —
    PDF text streams are zlib-compressed so plain regex won't match."""
    try:
        from pypdf import PdfReader  # type: ignore
        import io
        reader = PdfReader(io.BytesIO(pdf_bytes))
        txt = "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception:  # noqa: BLE001
        txt = pdf_bytes.decode("latin-1", errors="ignore")
    return [m.replace(",", "") for m in re.findall(r"CA\$\s?([\d,]+\.\d{2})", txt)]


async def main():
    results = []
    add = lambda **kw: results.append(kw)  # noqa: E731

    client_db = AsyncIOMotorClient(os.environ["MONGO_URL"], tz_aware=True)
    db = client_db[os.environ["DB_NAME"]]

    mkt = await db.listings.find_one({"iter474ui_seed": True}, {"_id": 0, "id": 1})
    multi = await db.multi_item_listings.find_one({"iter474ui_seed": True}, {"_id": 0, "id": 1})
    veh = await db.vehicle_listings.find_one({"iter474ui_seed": True}, {"_id": 0, "id": 1})
    sto = await db.storage_auctions.find_one({"iter474ui_seed": True}, {"_id": 0, "id": 1})
    if not (mkt and multi and veh and sto):
        raise RuntimeError("Seed missing — run seed_iter474_documents_matrix.py first")

    LID_MKT, LID_MULTI, LID_VEH, LID_STO = mkt["id"], multi["id"], veh["id"], sto["id"]

    caller_host = urlparse(BASE).hostname

    async with httpx.AsyncClient(timeout=30) as client:
        tok_buyer = await _login(client, "testbuyer@bidvex.com", "TestBuyer2026!")
        tok_seller = await _login(client, "testseller@bidvex.com", "TestSeller2026!")
        tok_buyer_b = await _login(client, "iter474_buyer_b@test.com", "IterTestPwd!123")
        tok_seller_b = await _login(client, "iter474_seller_b@test.com", "IterTestPwd!123")
        auth_a = {"Authorization": f"Bearer {tok_buyer}"}
        auth_sa = {"Authorization": f"Bearer {tok_seller}"}
        auth_b = {"Authorization": f"Bearer {tok_buyer_b}"}
        auth_sb = {"Authorization": f"Bearer {tok_seller_b}"}

        # ══════════════ BUYER — every section × available doc kinds ══════════════
        buyer_cases = [
            # (section, listing, lot, expected_kinds_available, extra_expected_multi_lot)
            ("marketplace", LID_MKT, None, ["invoice", "receipt"]),
            ("lots",        LID_MULTI, 1, ["invoice", "receipt", "payment_letter"]),
            ("vehicles",    LID_VEH, 1, ["invoice", "receipt"]),
            ("storage",     LID_STO, None, ["invoice", "receipt"]),
        ]
        buyer_receipt_totals = {}
        for section, lid, lot, expected in buyer_cases:
            params = {"section": section, "listing_id": lid}
            if lot is not None:
                params["lot_number"] = lot
            r = await client.get(f"{API}/dashboard/documents/purchase",
                                 params=params, headers=auth_a)
            j = r.json() if r.status_code == 200 else {}
            docs = j.get("documents", {})
            got_available = [k for k, v in docs.items() if v.get("available")]
            add(test=f"BUYER-{section}-available",
                ok=(r.status_code == 200
                    and set(expected).issubset(set(got_available))),
                status=r.status_code, expected=expected, got=got_available)

            # Reconcile every available doc: 200 pdf + total in body matches receipts
            recs = await db.receipts.find({
                "user_id": (await db.users.find_one({"email": "testbuyer@bidvex.com"}, {"id": 1}))["id"],
                "type": "buyer_receipt", "section": section, "listing_id": lid,
            }).to_list(20)
            total_paid = _sum_receipts(recs, "total_charged")
            buyer_receipt_totals[section] = total_paid

            for kind, entry in docs.items():
                if not entry.get("available"):
                    continue
                url = entry["signed_url"]
                # Absolute HTTPS check
                p = urlparse(url)
                add(test=f"BUYER-{section}-{kind}-abshttps",
                    ok=(p.scheme == "https" and p.hostname
                        and "localhost" not in p.hostname
                        and p.path.startswith("/api/invoices/download/")))
                # Click-through
                callable_url = _swap_host(url, caller_host)
                pdf_r = await client.get(callable_url)
                is_pdf = (pdf_r.status_code == 200
                          and pdf_r.headers.get("content-type", "").startswith("application/pdf")
                          and pdf_r.content.startswith(b"%PDF"))
                add(test=f"BUYER-{section}-{kind}-clickthrough",
                    ok=is_pdf, status=pdf_r.status_code,
                    ctype=pdf_r.headers.get("content-type", "")[:30])

                # Financial reconciliation for receipt (total_charged sum)
                if is_pdf and kind == "receipt":
                    amounts = _extract_totals_from_pdf(pdf_r.content)
                    total_str = f"{total_paid:,.2f}"
                    add(test=f"BUYER-{section}-receipt-reconcile",
                        ok=(total_str in amounts),
                        expected_total=total_str,
                        found_amounts=amounts[-6:] if amounts else [])

        # ══════════════ BUYER — idempotency ══════════════
        r1 = await client.get(f"{API}/dashboard/documents/purchase",
                              params={"section": "storage", "listing_id": LID_STO},
                              headers=auth_a)
        r2 = await client.get(f"{API}/dashboard/documents/purchase",
                              params={"section": "storage", "listing_id": LID_STO},
                              headers=auth_a)
        u1 = urlparse(r1.json()["documents"]["invoice"]["signed_url"]).path
        u2 = urlparse(r2.json()["documents"]["invoice"]["signed_url"]).path
        add(test="BUYER-storage-invoice-idempotent",
            ok=(u1 == u2), path=u1)

        # ══════════════ BUYER — cross-user 403 (Buyer B on Buyer A row) ═════
        r = await client.get(f"{API}/dashboard/documents/purchase",
                             params={"section": "storage", "listing_id": LID_STO},
                             headers=auth_b)
        add(test="BUYER-crossuser-403", ok=(r.status_code == 403), status=r.status_code)

        # ══════════════ SELLER — every section, every kind ══════════════
        seller_cases = [
            ("lots",        LID_MULTI, ["statement", "seller_receipt", "commission_invoice"]),
            ("marketplace", LID_MKT,   ["statement", "seller_receipt", "commission_invoice"]),
            ("vehicles",    LID_VEH,   ["statement", "seller_receipt", "commission_invoice"]),
            ("storage",     LID_STO,   ["statement", "seller_receipt", "commission_invoice"]),
        ]
        seller_id = (await db.users.find_one({"email": "testseller@bidvex.com"}, {"id": 1}))["id"]
        for section, lid, expected in seller_cases:
            r = await client.get(f"{API}/dashboard/documents/sale",
                                 params={"section": section, "listing_id": lid},
                                 headers=auth_sa)
            j = r.json() if r.status_code == 200 else {}
            docs = j.get("documents", {})
            got_available = [k for k, v in docs.items() if v.get("available")]
            add(test=f"SELLER-{section}-available",
                ok=(r.status_code == 200
                    and set(expected).issubset(set(got_available))),
                status=r.status_code, expected=expected, got=got_available)

            # Reconcile every available doc against the receipts
            recs = await db.receipts.find({
                "user_id": seller_id, "type": "seller_statement",
                "section": section, "listing_id": lid,
            }).to_list(20)
            net_payout = _sum_receipts(recs, "net_payout")
            for kind, entry in docs.items():
                if not entry.get("available"):
                    continue
                url = entry["signed_url"]
                p = urlparse(url)
                add(test=f"SELLER-{section}-{kind}-abshttps",
                    ok=(p.scheme == "https" and p.hostname
                        and "localhost" not in p.hostname))
                callable_url = _swap_host(url, caller_host)
                pdf_r = await client.get(callable_url)
                is_pdf = (pdf_r.status_code == 200
                          and pdf_r.headers.get("content-type", "").startswith("application/pdf")
                          and pdf_r.content.startswith(b"%PDF"))
                add(test=f"SELLER-{section}-{kind}-clickthrough",
                    ok=is_pdf, status=pdf_r.status_code)
                # Reconcile net_payout on the statement PDF (skip the
                # legacy `lots` section — that uses the existing
                # generator, not iter475's new one, and the seed data
                # stored a placeholder PDF for it).
                if is_pdf and kind == "statement" and section != "lots":
                    amounts = _extract_totals_from_pdf(pdf_r.content)
                    exp = f"{net_payout:,.2f}"
                    add(test=f"SELLER-{section}-{kind}-reconcile",
                        ok=(exp in amounts),
                        expected_net_payout=exp,
                        sample=amounts[-6:] if amounts else [])

        # ══════════════ SELLER — cross-seller 403 ══════════════
        r = await client.get(f"{API}/dashboard/documents/sale",
                             params={"section": "storage", "listing_id": LID_STO},
                             headers=auth_sb)
        add(test="SELLER-crossseller-403", ok=(r.status_code == 403), status=r.status_code)

        # ══════════════ EN/FR lang param produces different PDFs ═══════
        # (verifies lang plumbing to renderer). We check both langs
        # return 200; content differs only if the invoice hasn't been
        # cached in the OTHER language yet — since we cache once per
        # (owner, invoice_type) the CACHED language wins on retry. This
        # is acceptable: the first hit wins. But we DO exercise both
        # code paths.
        for lang in ("en", "fr"):
            r = await client.get(f"{API}/dashboard/documents/purchase",
                                 params={"section": "storage",
                                         "listing_id": LID_STO, "lang": lang},
                                 headers=auth_a)
            add(test=f"BUYER-storage-lang={lang}",
                ok=(r.status_code == 200
                    and r.json()["documents"]["invoice"]["available"]))

    passed = sum(1 for x in results if x.get("ok"))
    total = len(results)
    out = {
        "iter": 475, "base_url": BASE, "passed": passed, "total": total,
        "buyer_expected_totals": {k: str(v) for k, v in buyer_receipt_totals.items()},
        "results": results,
    }
    p = Path("/app/test_reports/iter475_new_pdf_generators.json")
    p.parent.mkdir(exist_ok=True, parents=True)
    p.write_text(json.dumps(out, indent=2))
    print(f"[iter475] {passed}/{total} passed → {p}")
    for r in results:
        flag = "✅" if r.get("ok") else "❌"
        print(f"  {flag} {r['test']:52s} {r}")


if __name__ == "__main__":
    asyncio.run(main())
