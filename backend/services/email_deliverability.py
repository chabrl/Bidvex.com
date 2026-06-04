"""
iter270 — Email deliverability instrumentation.

Two cheap startup probes that surface deliverability misconfigurations
before they cause production spam-folder routing:

  • `validate_email_config()` — loud check that the required env vars
    are present and that the canonical FROM address resolves to the
    .com domain (not .ca).
  • `verify_sendgrid_domain()` — best-effort DNS probe for the
    SendGrid CNAME chain (`em`, `s1._domainkey`, `s2._domainkey`).
    Logs ✅ / ❌ per record so ops can spot a broken DKIM rotation in
    the backend logs without leaving the terminal.

Both helpers are non-fatal: a failing DNS lookup must never prevent
the API from booting. The caller in `server.py` wraps them in a
try/except for that reason.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List

logger = logging.getLogger(__name__)


# ─── Canonical config ────────────────────────────────────────────────


CANONICAL_FROM_EMAIL = "noreply@bidvex.com"
CANONICAL_FROM_DOMAIN = "bidvex.com"

REQUIRED_ENV_VARS: List[str] = [
    "SENDGRID_API_KEY",
    "SENDGRID_FROM_EMAIL",
]

# DNS records that SendGrid creates when you authenticate a domain.
# The user-prefix varies per account so we only validate the labels
# under the sending domain.
SENDGRID_DNS_RECORDS: Dict[str, str] = {
    "em.bidvex.com":            "CNAME",
    "s1._domainkey.bidvex.com": "CNAME",
    "s2._domainkey.bidvex.com": "CNAME",
}


def validate_email_config() -> Dict[str, bool]:
    """Log ✅/❌ for each required env var + canonical FROM address.
    Returns a dict {var_name: present} for programmatic callers."""
    status: Dict[str, bool] = {}
    for var in REQUIRED_ENV_VARS:
        val = os.environ.get(var, "")
        ok = bool(val) and val != "SG.your-actual-sendgrid-key-here"
        status[var] = ok
        if ok:
            logger.info(f"✅ Email config OK: {var}")
        else:
            logger.error(f"❌ Email config missing: {var}")

    # Loud check that the canonical FROM is on .com.
    from_email = (os.environ.get("SENDGRID_FROM_EMAIL", "") or "").strip().lower()
    if from_email.endswith("@bidvex.com"):
        logger.info(f"✅ FROM address aligned: {from_email}")
        status["FROM_DOMAIN_OK"] = True
    elif from_email.endswith("@bidvex.ca"):
        logger.error(
            "❌ FROM address still on bidvex.ca — flip SENDGRID_FROM_EMAIL "
            "to noreply@bidvex.com to fix spam classification."
        )
        status["FROM_DOMAIN_OK"] = False
    else:
        logger.warning(f"⚠️  FROM address is unusual: {from_email!r}")
        status["FROM_DOMAIN_OK"] = False
    return status


async def verify_sendgrid_domain() -> Dict[str, bool]:
    """Best-effort DNS probe for the SendGrid CNAME chain.
    Uses `dnspython` if available; otherwise logs a single skipped
    line. Never raises — caller wraps in try/except for safety."""
    results: Dict[str, bool] = {}
    try:
        import dns.resolver  # type: ignore  # noqa: WPS433
    except ImportError:
        logger.info("[deliverability] dns.resolver unavailable — skipping DNS check.")
        return results

    for record, rtype in SENDGRID_DNS_RECORDS.items():
        try:
            answer = dns.resolver.resolve(record, rtype, lifetime=4.0)
            first = str(answer[0]).rstrip(".") if answer else ""
            results[record] = True
            logger.info(f"✅ DNS {rtype} {record} → {first}")
        except Exception as exc:  # noqa: BLE001
            results[record] = False
            logger.error(f"❌ DNS {rtype} {record} MISSING ({exc.__class__.__name__})")
    return results


__all__ = [
    "validate_email_config",
    "verify_sendgrid_domain",
    "CANONICAL_FROM_EMAIL",
    "CANONICAL_FROM_DOMAIN",
    "SENDGRID_DNS_RECORDS",
]
