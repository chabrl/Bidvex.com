"""
iter283-smoke — Continuous self-healing smoke test pipeline.

Runs every 6 hours via the APScheduler that already powers
auction-end / deposit-cleanup / daily-summary jobs. Each pass:

  1. Hits `GET /api/vehicles` end-to-end through the public ingress
     URL (so we exercise the same path real buyers hit, not the
     in-process FastAPI route).
  2. Computes a fee breakdown for a Quebec buyer payload via
     `services/fee_calculator` and asserts the returned tax-string
     shape includes the QC GST + QST values.
  3. Pings MongoDB (`ping` command) and Stripe (a lightweight
     `Balance.retrieve()` call — same auth path payment flows use).

On success: a single-line `[SMOKE_TEST_PASS] ...` log entry.
On failure: structured CRITICAL log + appends to
`db.smoke_test_alerts` so the admin dashboard can surface a banner.

Decoupling guarantees:
  • The smoke runner is wrapped in a top-level try/except. ANY
    failure inside the runner bubbles up only as a log entry + DB
    write — it NEVER crashes the scheduler, never disrupts other
    jobs, and never touches buyer-session websockets.
  • Stripe + ingress probes have hard 10s timeouts so a hung
    upstream can't tie up the scheduler thread.
  • The smoke runner takes NO locks and writes to ONE collection
    (`smoke_test_alerts`) on failure only — zero blast radius.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("bidvex.smoke")

_HTTP_TIMEOUT = 10.0  # seconds
_SMOKE_USER_AGENT = "bidvex-smoke-runner/1.0"


# ── Individual checks ────────────────────────────────────────────────


async def _check_vehicles_endpoint(base_url: str) -> Dict[str, Any]:
    """Endpoint Check 1 — GET /api/vehicles must return 200 + dict
    payload with `vehicles` + `total` keys (the contract the
    frontend listing page consumes)."""
    started = time.monotonic()
    url = f"{base_url.rstrip('/')}/api/vehicles?limit=1"
    try:
        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            headers={"User-Agent": _SMOKE_USER_AGENT},
        ) as client:
            resp = await client.get(url)
        elapsed = round((time.monotonic() - started) * 1000)
        if resp.status_code != 200:
            return {
                "ok": False, "check": "vehicles_endpoint",
                "elapsed_ms": elapsed,
                "error": f"unexpected status {resp.status_code}",
                "body_sample": resp.text[:200],
            }
        body = resp.json()
        if not isinstance(body, dict) or "vehicles" not in body or "total" not in body:
            return {
                "ok": False, "check": "vehicles_endpoint",
                "elapsed_ms": elapsed,
                "error": "response shape missing 'vehicles' or 'total'",
                "body_sample": str(body)[:200],
            }
        return {"ok": True, "check": "vehicles_endpoint",
                "elapsed_ms": elapsed,
                "total_vehicles": int(body.get("total") or 0)}
    except httpx.TimeoutException:
        return {"ok": False, "check": "vehicles_endpoint",
                "error": "timeout (>10s)"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "check": "vehicles_endpoint",
                "error": f"{type(exc).__name__}: {exc}"}


def _check_qc_tax_calculation() -> Dict[str, Any]:
    """Endpoint Check 2 — Quebec fee + tax calculation. Synchronous
    in-process call (no HTTP) so we cover the math layer separately
    from the routing layer."""
    started = time.monotonic()
    try:
        from services.fee_calculator import calculate_fee
        fee = calculate_fee(
            hammer_price=1000.0,
            auction_type="vehicle",
            seller_account_type="vehicle_dealer",
            buyer_account_type="individual",
            buyer_tier="standard",
            payment_method="stripe",
            seller_province="QC",
        )
        elapsed = round((time.monotonic() - started) * 1000)
        # Expected math for vehicle_dealer @ $1000 hammer:
        #   buyer_premium (Platform Fee 2.5%) = $25
        #   QC tax on the fee (GST 5% + QST 9.975%) → ~$3.74
        bp = float(fee.get("buyer_premium") or 0)
        if abs(bp - 25.0) > 0.05:
            return {"ok": False, "check": "qc_tax_calculation",
                    "elapsed_ms": elapsed,
                    "error": f"buyer_premium={bp!r} (expected ~25.0)"}
        gst = float(fee.get("buyer_gst") or 0)
        qst = float(fee.get("buyer_qst") or 0)
        if gst <= 0 or qst <= 0:
            return {"ok": False, "check": "qc_tax_calculation",
                    "elapsed_ms": elapsed,
                    "error": f"QC fee returned no GST/QST (gst={gst}, qst={qst})"}
        return {"ok": True, "check": "qc_tax_calculation",
                "elapsed_ms": elapsed,
                "buyer_premium": bp,
                "buyer_gst": gst,
                "buyer_qst": qst}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "check": "qc_tax_calculation",
                "error": f"{type(exc).__name__}: {exc}"}


async def _check_mongo_health(db) -> Dict[str, Any]:
    """Endpoint Check 3a — MongoDB ping."""
    started = time.monotonic()
    try:
        # `ping` is the canonical Mongo health command.
        await db.command("ping")
        elapsed = round((time.monotonic() - started) * 1000)
        return {"ok": True, "check": "mongo_ping", "elapsed_ms": elapsed}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "check": "mongo_ping",
                "error": f"{type(exc).__name__}: {exc}"}


def _check_stripe_health() -> Dict[str, Any]:
    """Endpoint Check 3b — Stripe API reachability via Balance.retrieve.

    Same auth path payment flows use. Read-only call (no side effects).
    Skips cleanly when the runtime has no Stripe key configured
    (preview/test sandboxes)."""
    started = time.monotonic()
    try:
        import stripe
        # Read key from env every call so a late env update is picked up.
        configured_key = os.environ.get("STRIPE_API_KEY") or getattr(stripe, "api_key", None)
        if not configured_key:
            return {"ok": True, "check": "stripe_health",
                    "skipped": "no STRIPE_API_KEY configured",
                    "elapsed_ms": 0}
        # The Emergent preview pod injects `sk_test_emergent` as a
        # placeholder sentinel. The real production key (`sk_live_*`
        # or `sk_test_*` with the actual account suffix) is set at
        # deploy time. Skip the API hit on the sentinel rather than
        # raising a false-positive AuthenticationError every 6h.
        if configured_key in ("sk_test_emergent", "sk_test_emergent_placeholder"):
            return {"ok": True, "check": "stripe_health",
                    "skipped": "preview-sandbox sentinel key (sk_test_emergent)",
                    "elapsed_ms": 0}
        # The Stripe SDK module-level attr may have been cleared by a
        # different import path. Set it explicitly for this call.
        stripe.api_key = configured_key
        # Keep the call cheap — Balance object is constant-size.
        stripe.Balance.retrieve(api_key=configured_key, timeout=_HTTP_TIMEOUT)
        elapsed = round((time.monotonic() - started) * 1000)
        return {"ok": True, "check": "stripe_health", "elapsed_ms": elapsed}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "check": "stripe_health",
                "error": f"{type(exc).__name__}: {exc}"}


# ── Orchestrator ─────────────────────────────────────────────────────


async def run_smoke_test(db, *, base_url: Optional[str] = None) -> Dict[str, Any]:
    """Run all four checks. Returns a structured result envelope.

    Never raises — every failure is captured in the result. The
    caller (scheduler hook or admin endpoint) decides whether to
    alert.
    """
    base_url = base_url or os.environ.get("PUBLIC_BACKEND_URL") or _detect_base_url()
    started_at = datetime.now(timezone.utc)

    # Run the three async-capable checks concurrently; tax check is sync.
    vehicles_result, mongo_result = await asyncio.gather(
        _check_vehicles_endpoint(base_url),
        _check_mongo_health(db),
        return_exceptions=False,
    )
    tax_result = _check_qc_tax_calculation()
    stripe_result = _check_stripe_health()

    checks = [vehicles_result, tax_result, mongo_result, stripe_result]
    all_ok = all(c.get("ok") for c in checks)

    result = {
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "all_ok": all_ok,
        "checks": checks,
    }

    if all_ok:
        logger.info(
            f"[SMOKE_TEST_PASS] All core routes healthy at "
            f"{result['finished_at']} (vehicles={vehicles_result.get('elapsed_ms')}ms "
            f"mongo={mongo_result.get('elapsed_ms')}ms)"
        )
    else:
        failed = [c for c in checks if not c.get("ok")]
        logger.critical(
            f"[SMOKE_TEST_FAIL] {len(failed)} check(s) failed at "
            f"{result['finished_at']}: {failed}"
        )
        # Append to admin-visible alert ledger. Non-fatal if it fails.
        try:
            await db.smoke_test_alerts.insert_one({
                "created_at": result["finished_at"],
                "all_ok": False,
                "failed_count": len(failed),
                "checks": checks,
                "base_url": base_url,
                "acknowledged": False,
            })
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[SMOKE_TEST] alert write failed: {exc}")
    return result


def _detect_base_url() -> str:
    """Best-effort base URL detection.

    Preference: `PUBLIC_BACKEND_URL` env var > local internal port.
    Production should set `PUBLIC_BACKEND_URL=https://bidvex.com`.
    """
    return "http://localhost:8001"


# ── Scheduler hook ───────────────────────────────────────────────────


async def smoke_test_job():
    """APScheduler entry-point — wraps `run_smoke_test` so the
    scheduler thread never sees an unhandled exception."""
    try:
        from deps import get_db
        db = get_db()
        await run_smoke_test(db)
    except Exception as exc:  # noqa: BLE001
        # NEVER let the smoke test bring down the scheduler.
        logger.critical(f"[SMOKE_TEST] runner crashed: {exc}")


__all__ = [
    "run_smoke_test",
    "smoke_test_job",
    "_check_vehicles_endpoint",
    "_check_qc_tax_calculation",
    "_check_mongo_health",
    "_check_stripe_health",
]
