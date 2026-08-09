#!/usr/bin/env python3
"""Live focused verification for iter454 seller-dashboard status tabs.

Modes:
  seed-verify   Clear old iter454live data, seed edge-case listings/receipt,
                call the preview API in EN/FR, assert tab counts match filters,
                and leave seed data for a frontend Playwright pass.
  cleanup       Remove iter454live seed data.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PW = "Anderosli123!@#"
PREFIX = "iter454live-"
OUT = Path("/app/test_reports/iter454_live_api_state.json")

PENDING = {"pending_ai_review", "pending_admin_review", "pending_review"}
ENDED = {"sold", "ended", "expired", "completed", "ended_no_sale", "unsold"}


def lots(l: Dict[str, Any]) -> List[Dict[str, Any]]:
    return l.get("lots") if isinstance(l.get("lots"), list) else []


def has_any_won(l: Dict[str, Any]) -> bool:
    if l.get("winner_user_id") or l.get("winner_id") or l.get("highest_bidder_id"):
        return True
    for lot in lots(l):
        if lot.get("winner_user_id") or lot.get("winner_id") or lot.get("highest_bidder_id"):
            return True
        if int(lot.get("sold_quantity") or 0) > 0:
            return True
    return False


def has_any_payment_collected(l: Dict[str, Any]) -> bool:
    if l.get("payment_status") == "payment_collected":
        return True
    return any(lot.get("payment_status") == "payment_collected" for lot in lots(l))


def has_any_payment_failed(l: Dict[str, Any]) -> bool:
    if l.get("payment_status") in ("payment_failed", "payment_failed_final"):
        return True
    return any(lot.get("payment_status") in ("payment_failed", "payment_failed_final") for lot in lots(l))


def is_sold(l: Dict[str, Any]) -> bool:
    return l.get("status") == "sold" or (l.get("status") in ("ended", "expired", "completed") and has_any_won(l))


def is_no_sale(l: Dict[str, Any]) -> bool:
    return l.get("status") in ("ended_no_sale", "unsold") or (l.get("status") in ("ended", "expired") and not has_any_won(l))


def is_completed(l: Dict[str, Any]) -> bool:
    return l.get("status") == "completed" or (l.get("pickup_confirmed") is True and has_any_payment_collected(l))


def tab_filter(tab: str, all_listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if tab == "all":
        return list(all_listings)
    if tab == "active":
        return [l for l in all_listings if l.get("status") == "active"]
    if tab == "pending_review":
        return [l for l in all_listings if l.get("status") in PENDING]
    if tab == "draft":
        return [l for l in all_listings if l.get("status") == "draft"]
    if tab == "ended":
        return [l for l in all_listings if l.get("status") in ENDED]
    if tab == "sold":
        return [l for l in all_listings if is_sold(l)]
    if tab == "no_sale":
        return [l for l in tab_filter("ended", all_listings) if is_no_sale(l)]
    if tab == "payment_collected":
        return [l for l in tab_filter("sold", all_listings) if has_any_payment_collected(l)]
    if tab == "payment_failed":
        return [l for l in tab_filter("sold", all_listings) if has_any_payment_failed(l)]
    if tab == "completed":
        return [l for l in all_listings if is_completed(l)]
    raise ValueError(tab)


def count_key(tab: str) -> str:
    return {"all": "total", "no_sale": "ended_no_sale"}.get(tab, tab)


def single(seller_id: str, suffix: str, status: str, **kw: Any) -> Dict[str, Any]:
    d = {
        "id": f"{PREFIX}{suffix}",
        "seller_id": seller_id,
        "title": f"iter454 live {suffix}",
        "description": "focused status-tab test",
        "category": "other",
        "condition": "used",
        "location": "Montreal, QC",
        "city": "Montreal",
        "region": "QC",
        "starting_price": 10.0,
        "current_price": 10.0,
        "auction_start_date": "2026-07-01T00:00:00+00:00",
        "auction_end_date": "2026-07-02T00:00:00+00:00",
        "status": status,
        "images": [],
        "bid_count": 0,
        "views": 0,
    }
    d.update(kw)
    return d


def multi(seller_id: str, suffix: str, lots_: List[Dict[str, Any]], status: str = "ended", **kw: Any) -> Dict[str, Any]:
    d = {
        "id": f"{PREFIX}{suffix}",
        "seller_id": seller_id,
        "title": f"iter454 live {suffix}",
        "description": "focused lot-aware status-tab test",
        "city": "Montreal",
        "region": "QC",
        "location": "Montreal, QC",
        "auction_start_date": "2026-07-01T00:00:00+00:00",
        "auction_end_date": "2026-07-02T00:00:00+00:00",
        "listing_type": "multi_item",
        "buyer_premium_pct": 5.0,
        "commission_rate": 4.0,
        "tax_rate_gst": 5.0,
        "tax_rate_qst": 9.975,
        "currency": "CAD",
        "premium_percentage": 5.0,
        "status": status,
        "lots": lots_,
        "views": 0,
    }
    d.update(kw)
    return d


async def cleanup(db) -> None:
    await db.listings.delete_many({"id": {"$regex": f"^{PREFIX}"}})
    await db.multi_item_listings.delete_many({"id": {"$regex": f"^{PREFIX}"}})
    await db.receipts.delete_many({"id": {"$regex": f"^{PREFIX}"}})


async def login(http: httpx.AsyncClient) -> str:
    r = await http.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    r.raise_for_status()
    token = r.json().get("access_token") or r.json().get("token")
    assert token, "login returned no token"
    return token


async def seed_and_verify() -> None:
    db_client = AsyncIOMotorClient(MONGO_URL)
    db = db_client[DB_NAME]
    try:
        admin = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0, "id": 1})
        assert admin and admin.get("id"), "admin seller not found"
        seller_id = admin["id"]
        await cleanup(db)

        now = datetime.now(timezone.utc).isoformat()
        singles = [
            single(seller_id, "active", "active"),
            single(seller_id, "draft", "draft"),
            single(seller_id, "pending", "pending_admin_review"),
            single(seller_id, "nosale", "ended_no_sale"),
            single(seller_id, "sold-single", "sold", winner_user_id="iter454live-buyer", final_price=100.0),
            single(seller_id, "completed-single", "completed", winner_user_id="iter454live-buyer", payment_status="payment_collected", pickup_confirmed=True, final_price=120.0, completed_at=now),
        ]
        multis = [
            multi(seller_id, "multi-lot-winner", [{"lot_number": 1, "title": "lot winner", "quantity": 1, "sold_quantity": 0, "starting_price": 10, "current_price": 33, "winner_user_id": "iter454live-buyer", "payment_status": "pending_payment", "lot_status": "ended", "status": "sold"}]),
            multi(seller_id, "multi-payment-collected", [{"lot_number": 1, "title": "lot paid", "quantity": 1, "sold_quantity": 0, "starting_price": 10, "current_price": 44, "winner_user_id": "iter454live-buyer", "payment_status": "payment_collected", "lot_status": "ended", "status": "sold"}]),
            multi(seller_id, "multi-payment-failed", [{"lot_number": 1, "title": "lot failed", "quantity": 1, "sold_quantity": 0, "starting_price": 10, "current_price": 55, "winner_user_id": "iter454live-buyer", "payment_status": "payment_failed", "lot_status": "ended", "status": "sold"}]),
            multi(seller_id, "multi-buynow-soldqty", [{"lot_number": 1, "title": "lot buy now", "quantity": 5, "sold_quantity": 2, "available_quantity": 3, "starting_price": 10, "current_price": 10, "buy_now_enabled": True, "buy_now_price": 15, "lot_status": "partially_sold", "status": "ended"}]),
            multi(seller_id, "multi-nosale", [{"lot_number": 1, "title": "lot unsold", "quantity": 1, "sold_quantity": 0, "starting_price": 10, "current_price": 10, "lot_status": "ended", "status": "ended"}], status="ended_no_sale"),
        ]
        receipt = {
            "id": f"{PREFIX}receipt",
            "type": "seller_statement",
            "user_id": seller_id,
            "listing_id": f"{PREFIX}purged-receipt-listing",
            "listing_title": "iter454 live orphan receipt sale",
            "buyer_id": "iter454live-buyer",
            "hammer_price": 210.0,
            "total_charged": 220.5,
            "net_payout": 201.0,
            "created_at": now,
        }
        await db.listings.insert_many(singles)
        await db.multi_item_listings.insert_many(multis)
        await db.receipts.insert_one(receipt)

        async with httpx.AsyncClient(timeout=60.0, verify=True) as http:
            token = await login(http)
            auth = {"Authorization": f"Bearer {token}"}
            payloads = {}
            for lang in ("en", "fr"):
                r = await http.get(f"{BASE_URL}/api/dashboard/seller?lang={lang}", headers=auth)
                r.raise_for_status()
                payloads[lang] = r.json()

        assert payloads["en"]["counts"] == payloads["fr"]["counts"], "EN/FR counts differ"
        data = payloads["en"]
        counts = data["counts"]
        all_listings = data["all_listings"]
        report: Dict[str, Dict[str, int]] = {}
        for tab in ("all", "active", "pending_review", "draft", "ended", "sold", "no_sale", "payment_collected", "payment_failed", "completed"):
            filtered = tab_filter(tab, all_listings)
            count = int(counts[count_key(tab)])
            report[tab] = {"count": count, "filtered_cards": len(filtered)}
            assert count == len(filtered), f"{tab} mismatch: count={count}, filtered={len(filtered)}"

        ids = {l.get("id") for l in all_listings if str(l.get("id", "")).startswith(PREFIX)}
        assert f"{PREFIX}purged-receipt-listing" in ids, "orphan seller_statement was not materialized"
        sold_ids = {l.get("id") for l in tab_filter("sold", all_listings)}
        for suffix in ("sold-single", "completed-single", "multi-lot-winner", "multi-payment-collected", "multi-payment-failed", "multi-buynow-soldqty", "purged-receipt-listing"):
            assert f"{PREFIX}{suffix}" in sold_ids, f"{suffix} missing from Sold"
        assert f"{PREFIX}multi-payment-collected" in {l.get("id") for l in tab_filter("payment_collected", all_listings)}
        assert f"{PREFIX}multi-payment-failed" in {l.get("id") for l in tab_filter("payment_failed", all_listings)}
        assert f"{PREFIX}multi-nosale" in {l.get("id") for l in tab_filter("no_sale", all_listings)}

        result = {
            "base_url": BASE_URL,
            "seller_id": seller_id,
            "counts": counts,
            "tab_report": report,
            "seed_prefix": PREFIX,
            "seeded_ids_present": sorted(ids),
            "en_fr_counts_equal": True,
        }
        OUT.write_text(json.dumps(result, indent=2, sort_keys=True))
        print(json.dumps(result, indent=2, sort_keys=True))
    finally:
        db_client.close()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["seed-verify", "cleanup"])
    args = parser.parse_args()
    db_client = AsyncIOMotorClient(MONGO_URL)
    try:
        if args.mode == "cleanup":
            await cleanup(db_client[DB_NAME])
            print(f"cleaned {PREFIX} data")
        else:
            await seed_and_verify()
    finally:
        db_client.close()


if __name__ == "__main__":
    asyncio.run(main())