"""iter239 live HTTP regression — verifies the 4 backend missions hit by E1:
(1) /api/notifications/unread-count  (auth gating + shape)
(2) /api/promoted-listings           (new canonical shape)
(3) /api/chat/stream                 (still text/plain streaming + persistence)
(4) /api/chat/history*               (list + get + delete + mark-read)
"""
import os
import json
import time
import uuid
import requests
import pytest


BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
BUYER_EMAIL = "charbel911@gmail.com"
BUYER_PWD = "Anderosli123!@#"


def _login(email=BUYER_EMAIL, pwd=BUYER_PWD):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pwd}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Login failed ({r.status_code}): {r.text[:200]}")
    j = r.json()
    return j.get("access_token") or j.get("token")


@pytest.fixture(scope="module")
def buyer_token():
    return _login()


# ---------- 1. Unread count ----------
class TestUnreadCount:
    def test_anonymous_returns_401(self):
        r = requests.get(f"{BASE}/api/notifications/unread-count", timeout=10)
        assert r.status_code in (401, 403), r.text

    def test_authenticated_returns_shape(self, buyer_token):
        r = requests.get(
            f"{BASE}/api/notifications/unread-count",
            headers={"Authorization": f"Bearer {buyer_token}"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert "unread_count" in j
        assert "ai_unread_count" in j
        assert isinstance(j["unread_count"], int)
        assert isinstance(j["ai_unread_count"], int)


# ---------- 2. Promoted listings (new shape) ----------
class TestPromotedListings:
    def test_marketplace_section_shape(self):
        r = requests.get(f"{BASE}/api/promoted-listings?section=marketplace&limit=10", timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "items" in j and isinstance(j["items"], list)
        assert "total" in j
        assert j.get("section") == "marketplace"
        # legacy key MUST NOT be present
        assert "listings" not in j, "legacy marketplace.py shape leaked: 'listings' key present"

    def test_lots_section_shape(self):
        r = requests.get(f"{BASE}/api/promoted-listings?section=lots&limit=5", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j.get("section") == "lots"
        assert isinstance(j.get("items"), list)


# ---------- 3. Chat stream + persistence ----------
class TestChatStreamPersistence:
    def test_stream_still_text_plain_and_persists(self, buyer_token):
        session_id = f"qa-iter239-{uuid.uuid4().hex[:10]}"
        body = {
            "message": "Hi, what is BidVex?",
            "session_id": session_id,
        }
        r = requests.post(
            f"{BASE}/api/chat/stream",
            json=body,
            headers={
                "Authorization": f"Bearer {buyer_token}",
                "Content-Type": "application/json",
            },
            timeout=60,
            stream=True,
        )
        assert r.status_code == 200, r.text[:300]
        ctype = r.headers.get("Content-Type", "")
        assert ctype.startswith("text/plain"), f"expected text/plain, got {ctype}"
        # drain
        body_bytes = b""
        for chunk in r.iter_content(chunk_size=512):
            if chunk:
                body_bytes += chunk
            if len(body_bytes) > 4000:
                break
        assert len(body_bytes) > 0
        # allow persistence to flush
        time.sleep(2)
        # verify persisted via history listing
        h = requests.get(
            f"{BASE}/api/chat/history",
            headers={"Authorization": f"Bearer {buyer_token}"},
            timeout=15,
        )
        assert h.status_code == 200, h.text
        hj = h.json()
        assert "sessions" in hj and isinstance(hj["sessions"], list)
        assert "pagination" in hj
        ids = [s.get("session_id") for s in hj["sessions"]]
        assert session_id in ids, f"new session {session_id} not present in history (top {len(ids)})"
        return session_id

    def test_history_get_and_delete_flow(self, buyer_token):
        # create one
        sid = f"qa-iter239-del-{uuid.uuid4().hex[:8]}"
        requests.post(
            f"{BASE}/api/chat/stream",
            json={"message": "ping", "session_id": sid},
            headers={"Authorization": f"Bearer {buyer_token}"},
            timeout=60,
            stream=True,
        ).content  # drain
        time.sleep(2)

        # GET single
        g = requests.get(
            f"{BASE}/api/chat/history/{sid}",
            headers={"Authorization": f"Bearer {buyer_token}"},
            timeout=10,
        )
        assert g.status_code == 200, g.text
        assert "messages" in g.json() or "session" in g.json()

        # mark-read
        m = requests.post(
            f"{BASE}/api/chat/mark-read/{sid}",
            headers={"Authorization": f"Bearer {buyer_token}"},
            timeout=10,
        )
        assert m.status_code in (200, 204), m.text

        # DELETE
        d = requests.delete(
            f"{BASE}/api/chat/history/{sid}",
            headers={"Authorization": f"Bearer {buyer_token}"},
            timeout=10,
        )
        assert d.status_code in (200, 204), d.text

    def test_history_requires_auth(self):
        r = requests.get(f"{BASE}/api/chat/history", timeout=10)
        assert r.status_code in (401, 403)
