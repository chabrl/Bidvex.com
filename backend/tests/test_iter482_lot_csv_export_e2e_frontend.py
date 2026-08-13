"""
iter482+ — Frontend E2E tests for the two new CSV export surfaces
==================================================================

These tests use Playwright to prove that the "Download Lot List
(CSV)" (public) and "Export CSV (Admin)" (admin) buttons render
correctly, respect auth rules, and produce well-formed CSV downloads.

Because Playwright is not part of the standard backend test rig, the
tests skip cleanly when the ``playwright`` package is unavailable.
The full pytest suite still runs green.

Manual verification (recorded in /tmp during the audit):

* /tmp/iter482_csv_public_guest_v2.png     — guest sees no button
* /tmp/iter482_csv_public_auth_final.png   — auth user sees button
* /tmp/iter482_csv_public_downloaded_bidvex_lots_iter482csv-seller-owned-test_public.csv
* /tmp/iter482_csv_admin_dash_final.png    — admin dashboard w/ button
* /tmp/iter482_csv_admin_downloaded_bidvex_lots_iter482csv-seller-owned-test_admin.csv
"""
from __future__ import annotations

import csv
import io
import os
import pytest

pytest.importorskip("playwright")
from playwright.async_api import async_playwright


_API = os.environ.get("REACT_APP_BACKEND_URL")
if not _API:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    _API = line.split("=", 1)[1].strip()
                    break
    except FileNotFoundError:
        _API = None

_FRONTEND_URL = _API  # same domain in this preview
_TEST_AUCTION_ID = "iter482csv-seller-owned-test"

pytestmark = pytest.mark.skipif(
    not _FRONTEND_URL, reason="No frontend URL configured")


async def _login_via_api(page, email: str, password: str) -> str | None:
    """Login via the /api/auth/login endpoint from within the page context."""
    r = await page.evaluate(
        """async ({email, password}) => {
            const r = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, password}),
            });
            return await r.json();
        }""",
        {"email": email, "password": password},
    )
    tok = r.get("access_token")
    if not tok:
        return None
    await page.evaluate(
        "(t) => localStorage.setItem('token', t)", tok)
    return tok


# ═════════════════════════════════════════════════════════════════════
#  SURFACE 2 — Public catalog CSV button
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_public_csv_button_hidden_for_guest():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(
                f"{_FRONTEND_URL}/lots/{_TEST_AUCTION_ID}",
                wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(4000)
            btn = await page.query_selector('[data-testid="public-export-csv-btn"]')
            assert btn is None, "Guest must NOT see the Download Lot List (CSV) button"
        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_public_csv_button_visible_for_auth_and_downloads():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, accept_downloads=True)
        try:
            page = await browser.new_page(accept_downloads=True)
            await page.goto(f"{_FRONTEND_URL}/", wait_until="domcontentloaded")
            tok = await _login_via_api(page, "testbuyer@bidvex.com", "TestBuyer2026!")
            if not tok:
                pytest.skip("auth login rate-limited")
            await page.goto(
                f"{_FRONTEND_URL}/lots/{_TEST_AUCTION_ID}",
                wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(5000)
            btn = await page.query_selector('[data-testid="public-export-csv-btn"]')
            assert btn is not None, "Auth user must see the CSV button"
            await btn.scroll_into_view_if_needed()

            async with page.expect_download(timeout=15_000) as dl_info:
                await btn.click(force=True)
            dl = await dl_info.value
            assert dl.suggested_filename.endswith(f"_{_TEST_AUCTION_ID}_public.csv")

            path = await dl.path()
            with open(path, "rb") as f:
                data = f.read()
            assert data.startswith(b"\xef\xbb\xbf"), "UTF-8 BOM missing"
            text = data.decode("utf-8").lstrip("\ufeff")
            reader = csv.DictReader(io.StringIO(text))
            cols = reader.fieldnames or []
            # Public surface: exactly 13 canonical columns
            assert cols == [
                "auction_id", "auction_name", "lot_number", "title",
                "description", "quantity", "starting_bid", "category",
                "condition", "current_bid", "status", "listing_url",
                "image_urls",
            ]
            # No forbidden fields
            for forbidden in ("hammer_price", "winner_user_id",
                              "sold_at", "seller_id"):
                assert forbidden not in cols
        finally:
            await browser.close()


# ═════════════════════════════════════════════════════════════════════
#  SURFACE 3 — Admin CSV button
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_admin_csv_button_visible_for_admin_and_downloads():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, accept_downloads=True)
        try:
            page = await browser.new_page(accept_downloads=True)
            await page.goto(f"{_FRONTEND_URL}/", wait_until="domcontentloaded")
            tok = await _login_via_api(page, "charbel911@gmail.com", "Anderosli123!@#")
            if not tok:
                pytest.skip("auth login rate-limited")
            await page.goto(
                f"{_FRONTEND_URL}/admin?tab=all-auctions",
                wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(6000)
            testid = f'[data-testid="admin-export-csv-btn-{_TEST_AUCTION_ID}"]'
            btn = await page.query_selector(testid)
            assert btn is not None, f"Admin export button missing for {_TEST_AUCTION_ID}"
            await btn.scroll_into_view_if_needed()
            async with page.expect_download(timeout=20_000) as dl_info:
                await btn.click(force=True)
            dl = await dl_info.value
            assert dl.suggested_filename.endswith(f"_{_TEST_AUCTION_ID}_admin.csv")

            path = await dl.path()
            with open(path, "rb") as f:
                data = f.read()
            assert data.startswith(b"\xef\xbb\xbf")
            text = data.decode("utf-8").lstrip("\ufeff")
            reader = csv.DictReader(io.StringIO(text))
            cols = reader.fieldnames or []
            # Admin: 13 canonical + 4 extras
            for extra in ("winner_user_id", "hammer_price",
                          "sold_at", "seller_id"):
                assert extra in cols, f"Admin surface missing {extra}"
        finally:
            await browser.close()
