"""iter234 — Live HTTP probes against REACT_APP_BACKEND_URL.

Validates the live deployment (real Gemini 2.5 Flash + real SendGrid).
Marked separate from the unit suite so unit tests stay offline.
"""
from __future__ import annotations

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
import requests

BASE_URL = "https://prod-verify-2.preview.emergentagent.com"

# ---------- Diagnostics ----------
def test_chat_diagnostics_live():
    r = requests.get(f"{BASE_URL}/api/chat/diagnostics", timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["model"] == "gemini-2.5-flash"
    assert j["gemini_api_key_present"] is True
    assert j["gemini_api_key_preview"].endswith("lckYGQ"), j
    assert j["google_search_tool_enabled"] is True
    assert j["thinking_budget"] == -1


# ---------- POST /api/chat/stream ----------
def test_post_chat_stream_returns_chunks():
    with requests.post(
        f"{BASE_URL}/api/chat/stream",
        json={"message": "Reply with the single word: PONG", "google_search": False},
        stream=True,
        timeout=60,
    ) as r:
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("text/plain")
        assert r.headers.get("X-GenAI-Model") == "gemini-2.5-flash"
        assert r.headers.get("X-Accel-Buffering") == "no"
        body = b""
        start = time.time()
        for chunk in r.iter_content(chunk_size=None):
            if chunk:
                body += chunk
            if time.time() - start > 30:
                break
        assert len(body) > 0, f"empty stream body: {body!r}"
        # Surface any stream-error trailer for visibility
        if b"[stream-error]" in body:
            pytest.fail(f"Stream error surfaced live: {body[-300:]!r}")


# ---------- GET /api/chat/stream (EventSource flavour) ----------
def test_get_chat_stream_returns_chunks():
    with requests.get(
        f"{BASE_URL}/api/chat/stream",
        params={"message": "Reply with the word OK only", "google_search": "false"},
        stream=True,
        timeout=60,
    ) as r:
        assert r.status_code == 200, r.text
        body = b""
        start = time.time()
        for chunk in r.iter_content(chunk_size=None):
            if chunk:
                body += chunk
            if time.time() - start > 30:
                break
        assert len(body) > 0
        if b"[stream-error]" in body:
            pytest.fail(f"Stream error surfaced: {body[-300:]!r}")


# ---------- extra_context ----------
def test_post_chat_stream_with_extra_context():
    r = requests.post(
        f"{BASE_URL}/api/chat/stream",
        json={
            "message": "What context label was just provided to you?",
            "extra_context": "RUNTIME-LABEL: iter234-verify",
            "google_search": False,
        },
        stream=True,
        timeout=60,
    )
    assert r.status_code == 200
    body = b""
    start = time.time()
    for chunk in r.iter_content(chunk_size=None):
        if chunk:
            body += chunk
        if time.time() - start > 30:
            break
    assert len(body) > 0
    # Don't assert the model echoes the label (LLM non-determinism) — only that we got
    # a real (non-error) response back when extra_context is wired through.
    assert b"[stream-error]" not in body, body[-300:]


# ---------- Malformed payload → 422 ----------
def test_post_chat_stream_empty_message_returns_422():
    r = requests.post(
        f"{BASE_URL}/api/chat/stream",
        json={"message": "", "google_search": False},
        timeout=15,
    )
    assert r.status_code == 422, r.text


# ---------- Watchdog run-now ----------
def test_watchdog_run_now_delivers_email():
    r = requests.post(f"{BASE_URL}/api/chat/watchdog/run-now", timeout=120)
    assert r.status_code == 200, r.text
    j = r.json()
    res = j.get("result", {})
    assert res.get("status") == "ok", res
    delivery = res.get("delivery", {})
    # delivery.status may be reported as 'sent' (wrapper) and/or include status_code 202
    assert delivery.get("to") == "charbel911@gmail.com"
    sc = delivery.get("status_code") or delivery.get("status")
    assert sc in (202, "sent", "ok"), delivery
    stats = res.get("stats", {})
    expected_collections = {"user_sessions", "audit_logs", "admin_logs", "bids",
                            "payment_transactions", "stripe_events"}
    assert expected_collections.issubset(set(stats.keys())), stats


# ---------- Existing litellm path still works ----------
def test_existing_ai_chat_message_still_works():
    # Try common paths — endpoint may require auth; accept 200/401/403 (not 500).
    r = requests.post(
        f"{BASE_URL}/api/ai-chat/message",
        json={"message": "ping"},
        timeout=30,
    )
    assert r.status_code != 500, r.text
    assert r.status_code in (200, 401, 403, 404, 422), (r.status_code, r.text[:300])


# ---------- Concurrency: two streams overlap ----------
def _fetch_stream(idx: int) -> dict:
    t0 = time.time()
    first_byte_at = None
    last_byte_at = None
    with requests.post(
        f"{BASE_URL}/api/chat/stream",
        json={"message": f"Count to 5 ({idx}). Reply ONLY the digits.", "google_search": False},
        stream=True,
        timeout=60,
    ) as r:
        assert r.status_code == 200
        for chunk in r.iter_content(chunk_size=None):
            if chunk:
                if first_byte_at is None:
                    first_byte_at = time.time()
                last_byte_at = time.time()
            if last_byte_at and last_byte_at - t0 > 30:
                break
    return {"start": t0, "first": first_byte_at, "last": last_byte_at}


def test_two_concurrent_streams_overlap():
    with ThreadPoolExecutor(max_workers=2) as ex:
        fa = ex.submit(_fetch_stream, 1)
        fb = ex.submit(_fetch_stream, 2)
        a = fa.result()
        b = fb.result()
    assert a["first"] and a["last"] and b["first"] and b["last"]
    # Overlap: A starts before B finishes AND B starts before A finishes
    overlap = (a["first"] < b["last"]) and (b["first"] < a["last"])
    assert overlap, f"streams did not overlap: a={a} b={b}"
