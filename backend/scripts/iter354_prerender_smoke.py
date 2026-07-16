#!/usr/bin/env python3
"""
iter354 — SSR prerender smoke script.

Curls every prerender-eligible route as Googlebot AND validates:
  • HTTP 200
  • Has <title>, meta description, canonical, hreflang
  • Has JSON-LD Organization block
  • JSON-LD parses as valid JSON
  • Auction detail pages have Product + Event blocks
  • Homepage has WebSite block

Usage:
    python -m scripts.iter354_prerender_smoke                       # preview
    python -m scripts.iter354_prerender_smoke --base https://...    # remote
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple
from urllib.request import Request, urlopen

# ─── Test matrix ──────────────────────────────────────────────────────
STATIC_ROUTES = [
    ("/", ["Organization", "WebSite"]),
    ("/marketplace", ["Organization", "BreadcrumbList"]),
    ("/vehicle-auctions", ["Organization", "BreadcrumbList"]),
    ("/storage-auctions", ["Organization", "BreadcrumbList"]),
    ("/lots-marketplace", ["Organization", "BreadcrumbList"]),
    ("/broker-directory", ["Organization", "BreadcrumbList"]),
    ("/faq", ["Organization", "BreadcrumbList", "FAQPage"]),
    ("/how-it-works", ["Organization", "BreadcrumbList", "FAQPage"]),
    ("/about", ["Organization", "BreadcrumbList"]),
    ("/contact", ["Organization", "BreadcrumbList"]),
    ("/legal/terms", ["Organization", "BreadcrumbList"]),
    ("/legal/privacy", ["Organization", "BreadcrumbList"]),
    ("/legal/refunds", ["Organization", "BreadcrumbList"]),
    ("/terms", ["Organization", "BreadcrumbList"]),
    ("/privacy-policy", ["Organization", "BreadcrumbList"]),
]

# Common assertions on every prerender output
REQUIRED_TAGS = [
    r'<title>[^<]+</title>',
    r'<meta name="description" content="[^"]+"\s*/?>',
    r'<link rel="canonical" href="https://www\.bidvex\.com[^"]*"\s*/?>',
    r'<link rel="alternate" hreflang="en-CA"',
    r'<link rel="alternate" hreflang="fr-CA"',
    r'<meta property="og:title"',
    r'<meta property="og:image"',
    r'<meta property="og:url"',
    r'<div id="root">\s*</div>',   # SPA hydration entry must survive
]

USER_AGENT = "Googlebot/2.1 (+http://www.google.com/bot.html)"


def _fetch(base: str, path: str) -> Tuple[int, str]:
    url = base.rstrip("/") + "/api/prerender" + path
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        resp = urlopen(req, timeout=15)
        return resp.status, resp.read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return 0, f"FETCH_ERROR: {e}"


def _extract_jsonld_blocks(html: str) -> List[Dict[str, Any]]:
    blocks = re.findall(
        r'<script type="application/ld\+json">(.+?)</script>',
        html, flags=re.DOTALL,
    )
    parsed: List[Dict[str, Any]] = []
    for b in blocks:
        try:
            parsed.append(json.loads(b))
        except json.JSONDecodeError as e:
            parsed.append({"@type": "INVALID_JSON", "_error": str(e), "_body": b[:200]})
    return parsed


def _check_route(base: str, path: str, expected_types: List[str]) -> Dict[str, Any]:
    status, body = _fetch(base, path)
    result: Dict[str, Any] = {
        "path": path,
        "status": status,
        "size": len(body),
        "missing_tags": [],
        "missing_jsonld": [],
        "invalid_jsonld": False,
        "ok": False,
    }
    if status != 200:
        result["error"] = body[:200]
        return result

    for pat in REQUIRED_TAGS:
        if not re.search(pat, body):
            result["missing_tags"].append(pat)

    blocks = _extract_jsonld_blocks(body)
    types = set()
    for b in blocks:
        if b.get("@type") == "INVALID_JSON":
            result["invalid_jsonld"] = True
        else:
            types.add(b.get("@type"))
    for want in expected_types:
        if want not in types:
            result["missing_jsonld"].append(want)
    result["found_jsonld_types"] = sorted(types)
    result["ok"] = (
        not result["missing_tags"]
        and not result["missing_jsonld"]
        and not result["invalid_jsonld"]
    )
    return result


def _try_auction_route(base: str) -> Dict[str, Any] | None:
    """Best-effort: probe a real auction ID from /api/marketplace/live for a
    dynamic-route smoke test. If nothing's live we skip."""
    try:
        req = Request(f"{base.rstrip('/')}/api/marketplace/live?limit=1",
                      headers={"User-Agent": "Mozilla/5.0"})
        resp = urlopen(req, timeout=10)
        data = json.loads(resp.read())
        items = data.get("items", []) if isinstance(data, dict) else []
        if not items:
            return None
        first = items[0]
        aid = first.get("id")
        kind = first.get("_kind") or first.get("type") or "listing"
        prefix = {"vehicle": "/vehicles/", "storage": "/storage/",
                  "multi_item": "/multi-item-auctions/",
                  "listing": "/auctions/"}.get(kind, "/auctions/")
        return _check_route(base, prefix + aid,
                            ["Organization", "Product", "Event", "BreadcrumbList"])
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.environ.get(
        "SMOKE_BASE_URL",
        "http://localhost:8001"),
        help="Base URL (no trailing slash)")
    args = parser.parse_args()

    print(f"[iter354 smoke] base={args.base}\n")
    print(f"{'PATH':50}  STATUS  SIZE  RESULT")
    print("-" * 90)

    results: List[Dict[str, Any]] = []
    for path, expected in STATIC_ROUTES:
        r = _check_route(args.base, path, expected)
        results.append(r)
        icon = "✅" if r["ok"] else "❌"
        detail = ""
        if not r["ok"]:
            if r["missing_tags"]:    detail += f" missing_tags={len(r['missing_tags'])}"
            if r["missing_jsonld"]:  detail += f" missing_jsonld={r['missing_jsonld']}"
            if r["invalid_jsonld"]:  detail += " invalid_jsonld"
            if r.get("error"):       detail += f" err={r['error'][:60]}"
        print(f"{path:50}  {r['status']:^6}  {r['size']:>5}  {icon}{detail}")

    # Auction-detail smoke (dynamic route)
    print()
    print("=== Dynamic auction route (best-effort) ===")
    dyn = _try_auction_route(args.base)
    if dyn is None:
        print("SKIP — no live auction found on preview")
    else:
        results.append(dyn)
        icon = "✅" if dyn["ok"] else "❌"
        detail = ""
        if not dyn["ok"]:
            if dyn["missing_tags"]:   detail += f" missing_tags={len(dyn['missing_tags'])}"
            if dyn["missing_jsonld"]: detail += f" missing_jsonld={dyn['missing_jsonld']}"
        print(f"{dyn['path']:50}  {dyn['status']:^6}  {dyn['size']:>5}  {icon}{detail}")
        print(f"  JSON-LD types found: {dyn['found_jsonld_types']}")

    n_ok = sum(1 for r in results if r["ok"])
    n_total = len(results)
    print()
    print(f"=== Summary: {n_ok}/{n_total} routes PASS ===")

    # Also test the bot-UA middleware (curl any SPA route with Googlebot UA)
    print()
    print("=== Bot-UA middleware test (informational) ===")
    try:
        req = Request(args.base.rstrip("/") + "/how-it-works",
                      headers={"User-Agent": USER_AGENT})
        resp = urlopen(req, timeout=10)
        hdr = resp.headers.get("X-Prerender-Version") or resp.headers.get("x-prerender-version")
        if hdr:
            print(f"✅ Middleware routed bot to prerender (X-Prerender-Version={hdr})")
        else:
            print("ℹ️  Middleware did NOT intercept — SPA served.")
            print("    This is EXPECTED when the base URL is the frontend ingress (Kubernetes /")
            print("    Cloudflare route). Middleware only fires when FastAPI is the direct entry.")
            print("    In production, the Cloudflare Worker (see docs/CLOUDFLARE_BOT_WORKER.md)")
            print("    handles this at the edge — no middleware role.")
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "404" in msg:
            print("ℹ️  /how-it-works returns 404 at this ingress — expected on a preview URL that")
            print("    doesn't have the frontend build present. Not a prerender regression.")
        else:
            print(f"❌ middleware test error: {e}")

    return 0 if n_ok == n_total else 1


if __name__ == "__main__":
    sys.exit(main())
