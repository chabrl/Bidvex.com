"""iter321 — Live HTTP/SSE tests against the preview env.

Covers:
  • GET /api/admin/support/escalations/realtime/stream — 401 no token,
    403 non-admin, 200+`event: ready` with admin token (via ?token=).
  • Broker fan-out: 3 concurrent SSE subscribers all receive the
    `new_ticket` event when 1 ticket is POSTed to /api/support/escalate.
  • iter320 regression: POST /api/support/escalate works; admin
    GET /api/admin/support/escalations lists tickets.
"""
from __future__ import annotations

import asyncio
import json
import os
import time

import httpx
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
# fall back if env not loaded
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

ADMIN = {"email": "charbel911@gmail.com", "password": "Anderosli123!@#"}
BUYER = {"email": "testbuyer@bidvex.com", "password": "TestBuyer2026!"}


def _login(creds, retries=2):
    last = None
    for i in range(retries + 1):
        r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
        if r.status_code == 200:
            return r.json().get("access_token") or r.json().get("token")
        if r.status_code == 429:
            time.sleep(65)
            continue
        last = r
    pytest.skip(f"login failed for {creds['email']}: {last.status_code if last else 'N/A'} {last.text[:120] if last else ''}")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def buyer_token():
    return _login(BUYER)


# ─── SSE auth tests ─────────────────────────────────────────────────────


class TestSSEAuth:
    def test_stream_no_token_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/admin/support/escalations/realtime/stream", timeout=10)
        assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text[:200]}"

    def test_stream_buyer_token_returns_403(self, buyer_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/support/escalations/realtime/stream",
            params={"token": buyer_token},
            timeout=10,
        )
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"

    def test_stream_admin_token_returns_ready_event(self, admin_token):
        """Verify `event: ready` lands within ~3s using stream=True."""
        with requests.get(
            f"{BASE_URL}/api/admin/support/escalations/realtime/stream",
            params={"token": admin_token},
            stream=True,
            timeout=10,
        ) as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers.get("content-type", "")
            # Read first chunk
            buf = ""
            start = time.time()
            for chunk in r.iter_content(chunk_size=1024, decode_unicode=True):
                if chunk:
                    buf += chunk
                if "event: ready" in buf and "open_count" in buf:
                    break
                if time.time() - start > 5:
                    break
            assert "event: ready" in buf, f"no ready event in: {buf[:300]}"
            assert "open_count" in buf
            # The ready data payload must be valid JSON
            for line in buf.split("\n"):
                if line.startswith("data: "):
                    payload = json.loads(line[6:].strip())
                    assert "open_count" in payload
                    assert isinstance(payload["open_count"], int)
                    break


# ─── Broker fan-out E2E (SSE × 3 + POST escalate) ───────────────────────


async def _open_sse_and_wait_for_new_ticket(client: httpx.AsyncClient, token: str, timeout: float):
    """Open SSE stream, read until we see a `event: new_ticket` line.
    Returns the parsed data dict or None on timeout."""
    url = f"{BASE_URL}/api/admin/support/escalations/realtime/stream?token={token}"
    async with client.stream("GET", url, timeout=timeout) as resp:
        assert resp.status_code == 200
        buf = ""
        got_ready = False
        start = time.time()
        async for chunk in resp.aiter_text():
            buf += chunk
            if not got_ready and "event: ready" in buf:
                got_ready = True
            # SSE events are separated by blank lines (\n\n). Only parse
            # once we've received a full event block to avoid splitting
            # JSON mid-chunk.
            if "event: new_ticket" in buf and "\n\n" in buf:
                # Walk through completed event blocks
                blocks = buf.split("\n\n")
                for block in blocks:
                    lines = block.split("\n")
                    ev = None
                    data_line = None
                    for ln in lines:
                        if ln.startswith("event: "):
                            ev = ln[7:].strip()
                        elif ln.startswith("data: "):
                            data_line = ln[6:].strip()
                    if ev == "new_ticket" and data_line:
                        try:
                            return json.loads(data_line)
                        except json.JSONDecodeError:
                            continue
            if time.time() - start > timeout:
                return None
    return None


class TestBrokerFanOut:
    @pytest.mark.asyncio
    async def test_three_admins_all_receive_new_ticket(self, admin_token, buyer_token):
        """Open 3 admin SSE connections → POST 1 escalation as buyer →
        verify all 3 SSE clients received the new_ticket event."""

        async with httpx.AsyncClient() as client:
            # Kick off 3 concurrent SSE listeners
            tasks = [
                asyncio.create_task(_open_sse_and_wait_for_new_ticket(client, admin_token, 12.0))
                for _ in range(3)
            ]
            # Give SSE connections ~1.5s to fully open and register with broker
            await asyncio.sleep(1.5)

            # POST an escalation as the buyer (synchronously is fine)
            payload = {
                "problem": "TEST_iter321 broker fan-out probe",
                "details": "Automated test — should fan out to all 3 subscribers",
                "language": "en",
                "transcript": [],
            }
            r = requests.post(
                f"{BASE_URL}/api/support/escalate",
                json=payload,
                headers={"Authorization": f"Bearer {buyer_token}"},
                timeout=15,
            )
            assert r.status_code == 200, f"escalate failed: {r.status_code} {r.text[:200]}"
            ticket_id = r.json()["ticket_id"]

            results = await asyncio.gather(*tasks, return_exceptions=True)

        received_ids = []
        for res in results:
            assert not isinstance(res, Exception), f"SSE listener raised: {res}"
            assert res is not None, "SSE listener timed out without new_ticket"
            received_ids.append(res.get("id"))

        # All 3 subscribers should have received the SAME ticket_id
        assert all(rid == ticket_id for rid in received_ids), (
            f"fan-out mismatch: expected {ticket_id}, got {received_ids}"
        )


# ─── iter320 regression (must still work) ───────────────────────────────


class TestIter320Regression:
    def test_post_escalate_still_works(self, buyer_token):
        r = requests.post(
            f"{BASE_URL}/api/support/escalate",
            json={"problem": "TEST_iter321 regression probe", "details": "ok", "language": "en", "transcript": []},
            headers={"Authorization": f"Bearer {buyer_token}"},
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert "ticket_id" in data
        assert data["status"] == "open"

    def test_admin_list_escalations(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/support/escalations",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"limit": 5},
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "count" in data

    def test_admin_pending_count(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/support/escalations/pending/count",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200
        assert "open_count" in r.json()
        assert isinstance(r.json()["open_count"], int)


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
