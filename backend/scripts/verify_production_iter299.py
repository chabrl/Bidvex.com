"""
verify_production_iter299.py — Post-deploy production verification
==================================================================

Runs 5 read-mostly checks against the PRODUCTION deployment and prints a
human-readable ✅/❌ report with the actual response values.

CHECKS
------
  1. POST /api/auth/register with NO phone            → expect 200/201
  2. GET  /api/admin/analytics/advanced (admin)       → expect 200 + non-empty `gmv`
  3. GET  /api/marketplace/items?ending_soon=true     → every item ends within 24h
  4. GET  /api/dashboard/seller (test seller)         → `counts.sold` / `counts.ended` present
  5. GET  /api/notifications (test user)              → every notification has non-empty
                                                        title+message in BOTH EN and FR

HOW TO RUN (after deploy)
-------------------------
  cd /app/backend
  python scripts/verify_production_iter299.py \
      --base-url https://bidvex.com \
      --admin-email charbel911@gmail.com --admin-password '<admin password>' \
      --seller-email charbel911@gmail.com --seller-password '<password>'

  • --base-url defaults to https://bidvex.com
  • Credentials can also come from env vars: PROD_ADMIN_EMAIL,
    PROD_ADMIN_PASSWORD, PROD_SELLER_EMAIL, PROD_SELLER_PASSWORD.
  • The seller account defaults to the admin account when not provided
    (the admin owns the seed listings).
  • Check 1 creates ONE throwaway user per run, clearly tagged
    `iter299.verify+<timestamp>@example.com` so it is easy to clean up.

Exit code: 0 when all checks pass, 1 otherwise.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

RESULTS = []


def report(name: str, ok: bool, value: str, warn: bool = False):
    if warn:
        icon, color = "⚠️ ", YELLOW
    else:
        icon, color = ("✅", GREEN) if ok else ("❌", RED)
    print(f"{color}{icon} {name}{RESET}\n     → {value}\n")
    RESULTS.append((name, ok))


def login(base: str, email: str, password: str) -> str | None:
    try:
        r = requests.post(f"{base}/api/auth/login", json={"email": email, "password": password}, timeout=30)
        if r.status_code == 200:
            d = r.json()
            return d.get("access_token") or d.get("token")
        print(f"{RED}   login failed for {email}: HTTP {r.status_code} {r.text[:160]}{RESET}")
    except Exception as e:  # noqa: BLE001
        print(f"{RED}   login error for {email}: {e}{RESET}")
    return None


def parse_dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default=os.environ.get("PROD_BASE_URL", "https://bidvex.com"))
    p.add_argument("--admin-email", default=os.environ.get("PROD_ADMIN_EMAIL", "charbel911@gmail.com"))
    p.add_argument("--admin-password", default=os.environ.get("PROD_ADMIN_PASSWORD", ""))
    p.add_argument("--seller-email", default=os.environ.get("PROD_SELLER_EMAIL", ""))
    p.add_argument("--seller-password", default=os.environ.get("PROD_SELLER_PASSWORD", ""))
    args = p.parse_args()
    base = args.base_url.rstrip("/")
    seller_email = args.seller_email or args.admin_email
    seller_password = args.seller_password or args.admin_password

    print(f"\n🔍 BidVex iter299 production verification — {base}\n{'=' * 64}\n")

    # ── CHECK 1: register with NO phone ──
    test_email = f"iter299.verify+{int(time.time())}@example.com"
    try:
        r = requests.post(f"{base}/api/auth/register", json={
            "email": test_email, "password": "Iter299Verify!x", "name": "Iter299 Verify Bot",
            "terms_agreed": True, "ai_disclosure_consent": True,
        }, timeout=30)
        ok = r.status_code in (200, 201)
        report("1. Register with no phone → 200", ok,
               f"HTTP {r.status_code} for {test_email}" + ("" if ok else f" — {r.text[:200]}"))
    except Exception as e:  # noqa: BLE001
        report("1. Register with no phone → 200", False, f"request error: {e}")

    # ── CHECK 2: admin advanced analytics ──
    admin_token = login(base, args.admin_email, args.admin_password) if args.admin_password else None
    if not admin_token:
        report("2. GET /api/admin/analytics/advanced", False,
               "no admin token — pass --admin-password or set PROD_ADMIN_PASSWORD")
    else:
        try:
            r = requests.get(f"{base}/api/admin/analytics/advanced",
                             headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
            gmv = (r.json() or {}).get("gmv") if r.status_code == 200 else None
            ok = r.status_code == 200 and isinstance(gmv, dict) and "all_time" in gmv
            report("2. GET /api/admin/analytics/advanced → 200 + gmv", ok,
                   f"HTTP {r.status_code} — gmv={json.dumps(gmv)}" if gmv is not None
                   else f"HTTP {r.status_code} — {r.text[:200]}")
        except Exception as e:  # noqa: BLE001
            report("2. GET /api/admin/analytics/advanced → 200 + gmv", False, f"request error: {e}")

    # ── CHECK 3: marketplace ending-soon filter (dynamic ≤ 24h) ──
    try:
        r = requests.get(f"{base}/api/marketplace/items", params={"ending_soon": "true", "limit": 50}, timeout=60)
        body = r.json() if r.status_code == 200 else {}
        items = body.get("items") if isinstance(body, dict) else body
        items = items or []
        now = datetime.now(timezone.utc)
        horizon = now + timedelta(hours=24)
        bad = []
        for it in items:
            end = parse_dt(it.get("auction_end_date") or it.get("auction_end_time") or it.get("end_time"))
            if end and (end > horizon or end < now):
                bad.append(f"{it.get('id', '?')[:8]} ends {end.isoformat()}")
        ok = r.status_code == 200 and not bad
        report("3. Ending-soon filter → all items end within 24h", ok,
               f"HTTP {r.status_code} — {len(items)} item(s); "
               + ("all within 24h window" if not bad else f"OUT OF WINDOW: {bad[:3]}"))
    except Exception as e:  # noqa: BLE001
        report("3. Ending-soon filter → all items end within 24h", False, f"request error: {e}")

    # ── CHECK 4: seller dashboard counts ──
    seller_token = login(base, seller_email, seller_password) if seller_password else None
    if not seller_token:
        report("4. GET /api/dashboard/seller counts", False,
               "no seller token — pass --seller-password / PROD_SELLER_PASSWORD")
    else:
        try:
            r = requests.get(f"{base}/api/dashboard/seller",
                             headers={"Authorization": f"Bearer {seller_token}"}, timeout=60)
            d = r.json() if r.status_code == 200 else {}
            counts = d.get("counts") or {}
            sold = counts.get("sold")
            ended = counts.get("ended")
            ok = r.status_code == 200 and sold is not None and ended is not None
            zero_note = "" if (sold or ended) else " (both 0 — fine only if this seller has no history)"
            report("4. Seller dashboard sold/ended counts", ok,
                   f"HTTP {r.status_code} — counts.sold={sold}, counts.ended={ended}{zero_note}",
                   warn=ok and not (sold or ended))
        except Exception as e:  # noqa: BLE001
            report("4. Seller dashboard sold/ended counts", False, f"request error: {e}")

    # ── CHECK 5: notifications bilingual EN + FR ──
    token5 = seller_token or admin_token
    if not token5:
        report("5. Notifications bilingual EN/FR", False, "no auth token available")
    else:
        try:
            r = requests.get(f"{base}/api/notifications", params={"limit": 25},
                             headers={"Authorization": f"Bearer {token5}"}, timeout=60)
            notifs = (r.json() or {}).get("notifications", []) if r.status_code == 200 else []
            missing = []
            for n in notifs:
                t_en = (n.get("title_en") or n.get("title") or "").strip()
                m_en = (n.get("message_en") or n.get("message") or "").strip()
                t_fr = (n.get("title_fr") or "").strip()
                m_fr = (n.get("message_fr") or "").strip()
                if not (t_en and m_en and t_fr and m_fr):
                    missing.append(f"{n.get('type', '?')}#{str(n.get('id', ''))[:8]}")
            ok = r.status_code == 200 and not missing
            if not notifs:
                report("5. Notifications bilingual EN/FR", r.status_code == 200,
                       f"HTTP {r.status_code} — user has 0 notifications (nothing to validate)", warn=True)
            else:
                report("5. Notifications bilingual EN/FR", ok,
                       f"HTTP {r.status_code} — {len(notifs)} notification(s); "
                       + ("all have EN+FR title & message" if not missing
                          else f"MISSING bilingual copy on: {missing[:5]}"))
        except Exception as e:  # noqa: BLE001
            report("5. Notifications bilingual EN/FR", False, f"request error: {e}")

    passed = sum(1 for _, ok in RESULTS if ok)
    total = len(RESULTS)
    color = GREEN if passed == total else RED
    print(f"{'=' * 64}\n{color}RESULT: {passed}/{total} checks passed{RESET}\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
