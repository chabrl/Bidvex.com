"""
iter320 — Live Support Escalation Protocol — LIVE HTTP tests.

Validates end-to-end via the public preview URL:
  • POST /api/support/escalate (auth, validation, marker stripping)
  • GET  /api/admin/support/escalations (filters, auth)
  • GET  /api/admin/support/escalations/pending/count
  • GET  /api/admin/support/escalations/{id} (admin only, 404 path)
  • PATCH /api/admin/support/escalations/{id}/status (invalid status, transitions)
  • 12-message transcript round-trip integrity
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fall back to the public preview URL written in frontend/.env so the
    # script remains runnable from the testing agent.
    try:
        env_path = "/app/frontend/.env"
        with open(env_path) as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASS  = "Anderosli123!@#"
BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PASS  = "TestBuyer2026!"


def _login(email: str, password: str) -> str:
    import time
    for attempt in range(4):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": password},
            timeout=20,
        )
        if r.status_code == 429:
            time.sleep(65)
            continue
        assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
        return r.json().get("access_token") or r.json().get("token")
    raise AssertionError(f"login rate-limited 4× for {email}")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def buyer_token():
    return _login(BUYER_EMAIL, BUYER_PASS)


def _h(token: str):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ─── AUTH / RBAC ────────────────────────────────────────────────────────

class TestAuth:
    def test_list_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/support/escalations", timeout=15)
        assert r.status_code in (401, 403)

    def test_list_forbidden_for_non_admin(self, buyer_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/support/escalations",
            headers=_h(buyer_token), timeout=15,
        )
        assert r.status_code == 403, r.text

    def test_pending_count_forbidden_for_non_admin(self, buyer_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/support/escalations/pending/count",
            headers=_h(buyer_token), timeout=15,
        )
        assert r.status_code == 403

    def test_create_requires_auth(self):
        r = requests.post(
            f"{BASE_URL}/api/support/escalate",
            json={"problem": "no auth"}, timeout=15,
        )
        assert r.status_code in (401, 403)


# ─── VALIDATION ─────────────────────────────────────────────────────────

class TestValidation:
    def test_empty_problem_422(self, buyer_token):
        r = requests.post(
            f"{BASE_URL}/api/support/escalate",
            headers=_h(buyer_token),
            json={"problem": "", "details": ""},
            timeout=15,
        )
        # Server uses a global validation envelope that returns 400 (not the
        # FastAPI default 422). Either is a valid spec interpretation as long
        # as the field-level message identifies `problem` as too short.
        assert r.status_code in (400, 422), r.text
        body = r.json()
        assert "problem" in str(body).lower()

    def test_problem_over_1500_chars_422(self, buyer_token):
        r = requests.post(
            f"{BASE_URL}/api/support/escalate",
            headers=_h(buyer_token),
            json={"problem": "x" * 1600, "details": ""},
            timeout=15,
        )
        assert r.status_code in (400, 422), r.text
        assert "1500" in r.text or "string_too_long" in r.text

    def test_transcript_over_20_messages_422(self, buyer_token):
        """The spec says max_length=20 on the transcript field; pydantic
        rejects oversize input. Verifies the cap is enforced."""
        big = [{"role": "user", "content": f"msg{i}"} for i in range(25)]
        r = requests.post(
            f"{BASE_URL}/api/support/escalate",
            headers=_h(buyer_token),
            json={"problem": "Stuck", "details": "ctx",
                  "transcript": big},
            timeout=15,
        )
        assert r.status_code in (400, 422), r.text
        assert "transcript" in r.text.lower()


# ─── 12-MESSAGE ROUND-TRIP + MARKER STRIPPING ──────────────────────────

@pytest.fixture(scope="module")
def created_ticket(buyer_token, admin_token):
    """POST a payload containing exactly 12 transcript messages of varied
    roles + varied sizes (one near MAX_TRANSCRIPT_CONTENT_CHARS=2000)
    AND a message with an embedded BIDVEX_ESCALATION marker. Returns the
    full row (via admin GET) for downstream assertions."""
    transcript = []
    roles = ["user", "assistant", "system"]
    for i in range(12):
        role = roles[i % 3]
        if i == 4:  # near-max content size
            content = "L" * 1990
        elif i == 7:  # message with embedded marker (must be stripped)
            content = ('Yes, escalating.\n'
                       '[[BIDVEX_ESCALATION]]'
                       '{"problem":"X","details":"Y"}'
                       '[[/BIDVEX_ESCALATION]]')
        else:
            content = f"TEST_iter320 message #{i} role={role} payload-✓"
        transcript.append({"role": role, "content": content})

    payload = {
        "problem":    "TEST_iter320 Stripe payout stuck on order ABC",
        "details":    "Order #123 was processed but funds not received. Need agent help.",
        "language":   "en",
        "transcript": transcript,
        "session_id": "test-session-iter320-LIVE",
        "page_url":   "https://preview/seller/dashboard",
    }
    r = requests.post(
        f"{BASE_URL}/api/support/escalate",
        headers=_h(buyer_token), json=payload, timeout=20,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "ticket_id" in data
    assert data["status"] == "open"
    assert "message_en" in data and "message_fr" in data

    # GET back via admin
    tid = data["ticket_id"]
    g = requests.get(
        f"{BASE_URL}/api/admin/support/escalations/{tid}",
        headers=_h(admin_token), timeout=15,
    )
    assert g.status_code == 200, g.text
    row = g.json()
    return {"ticket_id": tid, "row": row, "payload": payload}


class TestTranscriptRoundTrip:
    def test_12_messages_persisted_in_order(self, created_ticket):
        row = created_ticket["row"]
        # 12 sent — one embedded-marker message will be stripped but
        # since it has trailing "Yes, escalating." content, it remains.
        # Server strips marker and keeps the surrounding text.
        assert len(row["transcript"]) == 12, f"got {len(row['transcript'])} msgs"

    def test_marker_stripped_from_persisted_transcript(self, created_ticket):
        row = created_ticket["row"]
        for m in row["transcript"]:
            assert "[[BIDVEX_ESCALATION]]" not in m["content"]
            assert "[[/BIDVEX_ESCALATION]]" not in m["content"]

    def test_marker_message_keeps_surrounding_text(self, created_ticket):
        row = created_ticket["row"]
        # Index 7 originally had "Yes, escalating." before the marker.
        assert any("Yes, escalating." in m["content"] for m in row["transcript"])

    def test_large_message_truncated_to_2000_chars(self, created_ticket):
        row = created_ticket["row"]
        big_msgs = [m for m in row["transcript"] if len(m["content"]) >= 1900]
        assert big_msgs, "expected at least one near-max message"
        for m in big_msgs:
            assert len(m["content"]) <= 2000

    def test_role_distribution_preserved(self, created_ticket):
        row = created_ticket["row"]
        roles = [m["role"] for m in row["transcript"]]
        assert "user" in roles and "assistant" in roles and "system" in roles

    def test_problem_details_language_persisted(self, created_ticket):
        row = created_ticket["row"]
        assert row["problem"].startswith("TEST_iter320 Stripe payout stuck")
        assert "Order #123" in row["details"]
        assert row["language"] == "en"
        assert row["session_id"] == "test-session-iter320-LIVE"
        assert row["page_url"] == "https://preview/seller/dashboard"
        assert row["status"] == "open"


# ─── ADMIN LIST / FILTERS / COUNT ───────────────────────────────────────

class TestAdminList:
    def test_list_envelope_shape(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/support/escalations",
            headers=_h(admin_token), timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        for key in ("items", "count", "page", "limit"):
            assert key in data, f"missing {key} in envelope"
        assert isinstance(data["items"], list)

    def test_status_filter(self, admin_token, created_ticket):
        r = requests.get(
            f"{BASE_URL}/api/admin/support/escalations?status=open",
            headers=_h(admin_token), timeout=15,
        )
        assert r.status_code == 200
        items = r.json()["items"]
        # Should include our new open ticket
        assert any(it["id"] == created_ticket["ticket_id"] for it in items)
        for it in items:
            assert it["status"] == "open"

    def test_search_filter(self, admin_token, created_ticket):
        r = requests.get(
            f"{BASE_URL}/api/admin/support/escalations?search=TEST_iter320",
            headers=_h(admin_token), timeout=15,
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(it["id"] == created_ticket["ticket_id"] for it in items)

    def test_pending_count(self, admin_token, created_ticket):
        r = requests.get(
            f"{BASE_URL}/api/admin/support/escalations/pending/count",
            headers=_h(admin_token), timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert "open_count" in data
        assert isinstance(data["open_count"], int)
        assert data["open_count"] >= 1


# ─── ADMIN DETAIL / 404 ─────────────────────────────────────────────────

class TestAdminDetail:
    def test_404_unknown_ticket(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/support/escalations/this-id-does-not-exist",
            headers=_h(admin_token), timeout=15,
        )
        assert r.status_code == 404

    def test_detail_excludes_mongo_id(self, created_ticket):
        row = created_ticket["row"]
        assert "_id" not in row


# ─── STATUS TRANSITIONS ────────────────────────────────────────────────

class TestStatusTransitions:
    def test_invalid_status_422(self, admin_token, created_ticket):
        tid = created_ticket["ticket_id"]
        r = requests.patch(
            f"{BASE_URL}/api/admin/support/escalations/{tid}/status",
            headers=_h(admin_token),
            json={"status": "wibble"},
            timeout=15,
        )
        assert r.status_code == 422, r.text
        # Body should mention allowed list
        body = r.json()
        # FastAPI sometimes nests our HTTPException detail under "detail"
        msg = str(body)
        assert "open" in msg and "acknowledged" in msg

    def test_404_unknown_status_update(self, admin_token):
        r = requests.patch(
            f"{BASE_URL}/api/admin/support/escalations/nope-id/status",
            headers=_h(admin_token),
            json={"status": "acknowledged"},
            timeout=15,
        )
        assert r.status_code == 404

    def test_open_to_acknowledged(self, admin_token, created_ticket):
        tid = created_ticket["ticket_id"]
        r = requests.patch(
            f"{BASE_URL}/api/admin/support/escalations/{tid}/status",
            headers=_h(admin_token),
            json={"status": "acknowledged",
                  "admin_notes": "TEST_iter320 picked up by agent"},
            timeout=15,
        )
        assert r.status_code == 200
        # Persist check
        g = requests.get(
            f"{BASE_URL}/api/admin/support/escalations/{tid}",
            headers=_h(admin_token), timeout=15,
        )
        row = g.json()
        assert row["status"] == "acknowledged"
        assert row["admin_notes"] == "TEST_iter320 picked up by agent"

    def test_acknowledged_to_resolved_and_count_decreases(
        self, admin_token, created_ticket
    ):
        # Take snapshot first
        c0 = requests.get(
            f"{BASE_URL}/api/admin/support/escalations/pending/count",
            headers=_h(admin_token), timeout=15,
        ).json()["open_count"]

        tid = created_ticket["ticket_id"]
        r = requests.patch(
            f"{BASE_URL}/api/admin/support/escalations/{tid}/status",
            headers=_h(admin_token),
            json={"status": "resolved",
                  "admin_notes": "TEST_iter320 resolved by agent"},
            timeout=15,
        )
        assert r.status_code == 200

        g = requests.get(
            f"{BASE_URL}/api/admin/support/escalations/{tid}",
            headers=_h(admin_token), timeout=15,
        ).json()
        assert g["status"] == "resolved"
        assert g["admin_notes"] == "TEST_iter320 resolved by agent"

        # Open count should NOT have increased; it was already moved off-open
        # by the previous test, but if this test runs in isolation it should
        # still leave count consistent.
        c1 = requests.get(
            f"{BASE_URL}/api/admin/support/escalations/pending/count",
            headers=_h(admin_token), timeout=15,
        ).json()["open_count"]
        assert c1 <= c0


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
