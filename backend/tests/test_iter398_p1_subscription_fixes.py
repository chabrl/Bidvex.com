#!/usr/bin/env python3
"""
Focused iter398 verification for three P1 subscription fixes:
1) dynamic Stripe Price ID -> tier resolution from subscription_plans
2) monthly billing_period acceptance + monthly price ID availability
3) legacy /api/subscription/status DB-sourced prices

This is intentionally a narrow live-preview QA script, not a full regression suite.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import string
import sys
import time
from pathlib import Path
from typing import Any, Dict

import requests
from dotenv import dotenv_values, load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient


BACKEND_DIR = Path("/app/backend")
FRONTEND_ENV = Path("/app/frontend/.env")
BACKEND_ENV = BACKEND_DIR / ".env"
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_ENV, override=False)
frontend_env = dotenv_values(FRONTEND_ENV)
API_BASE = (frontend_env.get("REACT_APP_BACKEND_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ.get("DB_NAME", "bazario_db")


def _unique(prefix: str) -> str:
    suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    return f"{prefix}_{int(time.time())}_{suffix}"


def register_user(email_prefix: str) -> Dict[str, Any]:
    email = f"{_unique(email_prefix)}@example.com"
    password = "Iter398Test!234"
    payload = {
        "email": email,
        "password": password,
        "name": "iter398 subscription tester",
        "account_type": "personal",
        "terms_agreed": True,
        "ai_disclosure_consent": True,
    }
    r = requests.post(f"{API_BASE}/api/auth/register", json=payload, timeout=40)
    assert r.status_code == 200, f"register failed {r.status_code}: {r.text}"
    data = r.json()
    assert data.get("access_token"), f"register response missing access token: {data}"
    return {"email": email, "password": password, "token": data["access_token"], "user": data.get("user", {})}


def authed_get(path: str, token: str) -> requests.Response:
    return requests.get(f"{API_BASE}{path}", headers={"Authorization": f"Bearer {token}"}, timeout=40)


def authed_post(path: str, token: str, body: Dict[str, Any]) -> requests.Response:
    return requests.post(
        f"{API_BASE}{path}",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )


async def main() -> Dict[str, Any]:
    sync_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10000)
    db = sync_client[DB_NAME]
    async_client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)
    adb = async_client[DB_NAME]

    created_emails: list[str] = []
    results: Dict[str, Any] = {
        "api_base": API_BASE,
        "checks": {},
        "failures": [],
        "created_emails": created_emails,
    }

    def record_failure(message: str) -> None:
        results.setdefault("failures", []).append(message)

    premium_original_yearly = None
    premium_had_yearly = False
    fake_price = f"price_iter398_test_admin_edit_{int(time.time())}"

    try:
        # Baseline public subscription catalog.
        public_r = requests.get(f"{API_BASE}/api/subscription-plans", timeout=40)
        if public_r.status_code != 200:
            raise AssertionError(f"GET subscription-plans failed {public_r.status_code}: {public_r.text}")
        public_plans = {p["plan_id"]: p for p in public_r.json().get("plans", [])}
        if "premium" not in public_plans or "vip" not in public_plans:
            raise AssertionError(f"missing premium/vip public plans: {public_plans.keys()}")
        results["checks"]["public_subscription_plans"] = {
            "premium_price_monthly": public_plans["premium"].get("price_monthly"),
            "premium_price_yearly": public_plans["premium"].get("price_yearly"),
            "vip_price_monthly": public_plans["vip"].get("price_monthly"),
            "vip_price_yearly": public_plans["vip"].get("price_yearly"),
            "premium_stripe_price_id_monthly": public_plans["premium"].get("stripe_price_id_monthly"),
            "premium_stripe_price_id_yearly": public_plans["premium"].get("stripe_price_id_yearly"),
        }

        # P1 #1: DB-aware async resolver + register_price_id.
        premium_doc = db.subscription_plans.find_one({"plan_id": "premium"}, {"_id": 0})
        assert premium_doc, "premium plan not found in subscription_plans"
        premium_had_yearly = "stripe_price_id_yearly" in premium_doc
        premium_original_yearly = premium_doc.get("stripe_price_id_yearly")

        db.subscription_plans.update_one({"plan_id": "premium"}, {"$set": {"stripe_price_id_yearly": fake_price}})
        from services.subscription_service import (
            PRICE_ID_TO_TIER,
            get_tier_from_price_id,
            get_tier_from_price_id_async,
            register_price_id,
        )

        PRICE_ID_TO_TIER.pop(fake_price, None)
        resolved = await get_tier_from_price_id_async(adb, fake_price)
        if resolved != "premium":
            record_failure(f"P1 #1: async DB resolver returned {resolved!r} for synthetic premium price, expected 'premium'")

        synth_price = f"price_iter398_synth_{int(time.time())}"
        register_price_id(synth_price, "vip")
        sync_resolved = get_tier_from_price_id(synth_price)
        if sync_resolved != "vip":
            record_failure(f"P1 #1: register_price_id/get_tier_from_price_id returned {sync_resolved!r}, expected 'vip'")
        results["checks"]["dynamic_price_id_to_tier"] = {
            "fake_price": fake_price,
            "async_resolved_tier": resolved,
            "registered_synth_price": synth_price,
            "sync_resolved_tier": sync_resolved,
        }

        # Restore immediately after P1 #1 so later HTTP checks see real pinned plan data.
        if premium_had_yearly:
            db.subscription_plans.update_one({"plan_id": "premium"}, {"$set": {"stripe_price_id_yearly": premium_original_yearly}})
        else:
            db.subscription_plans.update_one({"plan_id": "premium"}, {"$unset": {"stripe_price_id_yearly": ""}})

        # P1 #2: monthly billing_period is accepted and does not fail as missing Stripe price.
        monthly_user = register_user("iter398_monthly")
        created_emails.append(monthly_user["email"])
        create_r = authed_post(
            "/api/subscriptions/create",
            monthly_user["token"],
            {"plan_id": "premium", "billing_period": "monthly"},
        )
        create_detail = None
        try:
            create_detail = create_r.json().get("detail")
        except Exception:
            create_detail = create_r.text
        if create_r.status_code not in (200, 400):
            record_failure(f"P1 #2: unexpected subscriptions/create status {create_r.status_code}: {create_r.text}")
        if "Stripe price not configured" in str(create_detail):
            record_failure(f"P1 #2: monthly create still fails as missing Stripe price: {create_detail}")
        premium_after_create = db.subscription_plans.find_one({"plan_id": "premium"}, {"_id": 0, "stripe_price_id_monthly": 1, "stripe_price_id_yearly": 1}) or {}
        if not premium_after_create.get("stripe_price_id_monthly"):
            record_failure(f"P1 #2: premium stripe_price_id_monthly is still missing after monthly create attempt: {premium_after_create}")
        results["checks"]["monthly_billing_period_create"] = {
            "status_code": create_r.status_code,
            "detail": create_detail,
            "premium_stripe_price_id_monthly": premium_after_create.get("stripe_price_id_monthly"),
            "premium_stripe_price_id_yearly": premium_after_create.get("stripe_price_id_yearly"),
        }

        # P1 #3: legacy status endpoint uses DB prices and never returns old stubs or 500.
        status_user = register_user("iter398_status")
        created_emails.append(status_user["email"])
        uid = status_user["user"].get("id")
        if not uid:
            raise AssertionError(f"registered status user missing id: {status_user['user']}")

        free_r = authed_get("/api/subscription/status", status_user["token"])
        if free_r.status_code != 200:
            record_failure(f"P1 #3: free legacy status failed {free_r.status_code}: {free_r.text}")
            free_data = {}
        else:
            free_data = free_r.json()
            if "price" in free_data.get("features", {}):
                record_failure(f"P1 #3: free tier should not include features.price: {free_data}")

        db.users.update_one({"id": uid}, {"$set": {"subscription_tier": "premium", "subscription_status": "active"}})
        prem_r = authed_get("/api/subscription/status", status_user["token"])
        if prem_r.status_code != 200:
            record_failure(f"P1 #3: premium legacy status failed {prem_r.status_code}: {prem_r.text}")
            prem_data = {"features": {}}
        else:
            prem_data = prem_r.json()
        prem_features = prem_data.get("features", {})
        if prem_data.get("subscription_tier") != "premium":
            record_failure(f"P1 #3: premium status tier wrong: {prem_data}")
        if prem_features.get("price") != "$180.00 CAD/year":
            record_failure(f"P1 #3: premium price wrong: {prem_features}")
        if prem_features.get("price_yearly_cad") != 180:
            record_failure(f"P1 #3: premium yearly numeric wrong: {prem_features}")
        if prem_features.get("price_monthly_cad") != 15:
            record_failure(f"P1 #3: premium monthly numeric wrong: {prem_features}")
        if "$99.99" in json.dumps(prem_data):
            record_failure(f"P1 #3: legacy $99.99 stub still present: {prem_data}")

        db.users.update_one({"id": uid}, {"$set": {"subscription_tier": "vip", "subscription_status": "active"}})
        vip_r = authed_get("/api/subscription/status", status_user["token"])
        if vip_r.status_code != 200:
            record_failure(f"P1 #3: vip legacy status failed {vip_r.status_code}: {vip_r.text}")
            vip_data = {"features": {}}
        else:
            vip_data = vip_r.json()
        vip_features = vip_data.get("features", {})
        if vip_data.get("subscription_tier") != "vip":
            record_failure(f"P1 #3: vip status tier wrong: {vip_data}")
        if vip_features.get("price") != "$300.00 CAD/year":
            record_failure(f"P1 #3: vip price wrong: {vip_features}")
        if vip_features.get("price_yearly_cad") != 300:
            record_failure(f"P1 #3: vip yearly numeric wrong: {vip_features}")
        if vip_features.get("price_monthly_cad") != 25:
            record_failure(f"P1 #3: vip monthly numeric wrong: {vip_features}")
        if "$299.99" in json.dumps(vip_data):
            record_failure(f"P1 #3: legacy $299.99 stub still present: {vip_data}")
        results["checks"]["legacy_subscription_status"] = {
            "free_features": free_data.get("features", {}),
            "premium_features": prem_features,
            "vip_features": vip_features,
        }

        results["ok"] = not bool(results.get("failures"))
        return results

    finally:
        # Always restore the synthetic admin-price mutation.
        try:
            if premium_original_yearly is not None or premium_had_yearly:
                db.subscription_plans.update_one({"plan_id": "premium"}, {"$set": {"stripe_price_id_yearly": premium_original_yearly}})
            else:
                db.subscription_plans.update_one({"plan_id": "premium"}, {"$unset": {"stripe_price_id_yearly": ""}})
        except Exception as restore_err:  # pragma: no cover - report only
            results.setdefault("cleanup_errors", []).append(f"restore premium yearly price failed: {restore_err}")

        # Remove only fresh test users created by this script.
        try:
            if created_emails:
                db.users.delete_many({"email": {"$in": created_emails}})
        except Exception as cleanup_err:  # pragma: no cover - report only
            results.setdefault("cleanup_errors", []).append(f"test user cleanup failed: {cleanup_err}")

        async_client.close()
        sync_client.close()


if __name__ == "__main__":
    out_path = Path("/app/test_reports/iter398_backend_run.json")
    try:
        output = asyncio.run(main())
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(output, indent=2, sort_keys=True))
    except Exception as exc:
        failure = {"ok": False, "error": repr(exc)}
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(failure, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(failure, indent=2, sort_keys=True))
        raise