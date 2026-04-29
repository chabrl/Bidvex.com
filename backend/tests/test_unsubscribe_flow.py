"""Tests for Custom Unsubscribe Flow — iteration 161"""
import os, sys, asyncio, uuid, time
import pytest, requests
from unittest.mock import patch, MagicMock, AsyncMock

with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from routes.unsubscribe import generate_unsubscribe_token, build_unsubscribe_urls
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
import deps

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def _run_async(coro_factory):
    """Run a fresh coroutine with motor bound to a fresh loop's DB."""
    async def wrapper():
        deps.set_db(AsyncIOMotorClient(MONGO_URL)[DB_NAME])
        return await coro_factory()
    return asyncio.run(wrapper())


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s

@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]

@pytest.fixture
def test_email():
    return f"TEST_unsub_{uuid.uuid4().hex[:8]}@example.com"


# 1. /verify
class TestVerifyEndpoint:
    def test_verify_missing_token(self, session):
        r = session.get(f"{BASE_URL}/api/unsubscribe/verify")
        assert r.status_code == 400
        assert r.json()["detail"] == "token_missing"

    def test_verify_garbage_token(self, session):
        r = session.get(f"{BASE_URL}/api/unsubscribe/verify?token=garbage123")
        assert r.status_code == 400
        assert r.json()["detail"] == "token_invalid"

    def test_verify_valid_token(self, session, test_email):
        token = generate_unsubscribe_token(test_email)
        r = session.get(f"{BASE_URL}/api/unsubscribe/verify?token={token}")
        assert r.status_code == 200
        data = r.json()
        assert "@example.com" in data["email_masked"]
        assert data["already_unsubscribed"] is False


# 2. /confirm
class TestConfirmEndpoint:
    def test_confirm_garbage_token(self, session):
        r = session.post(f"{BASE_URL}/api/unsubscribe/confirm", json={"token": "garbage"})
        assert r.status_code == 400
        assert r.json()["detail"] == "token_invalid"

    def test_confirm_valid_then_already_done(self, session, db, test_email):
        email_l = test_email.lower()
        token = generate_unsubscribe_token(test_email)
        try:
            r1 = session.post(f"{BASE_URL}/api/unsubscribe/confirm", json={"token": token})
            assert r1.status_code == 200, r1.text
            assert r1.json()["status"] == "success"

            user = db.users.find_one({"email": email_l})
            assert user and user.get("marketing_unsubscribed") is True
            supp = db.email_suppressions.find_one({"email": email_l})
            assert supp and supp.get("source") == "link"

            r2 = session.post(f"{BASE_URL}/api/unsubscribe/confirm", json={"token": token})
            assert r2.status_code == 200
            assert r2.json()["status"] == "already_done"
        finally:
            db.users.delete_one({"email": email_l})
            db.email_suppressions.delete_one({"email": email_l})


# 3. build_unsubscribe_urls
class TestBuildUrls:
    def test_structure(self):
        urls = build_unsubscribe_urls("user@x.com")
        assert "/unsubscribe?token=" in urls["en"] and "lang=en" in urls["en"]
        assert "/desabonnement?token=" in urls["fr"] and "lang=fr" in urls["fr"]
        assert urls["en"].startswith("https://bidvex.com")
        assert urls["fr"].startswith("https://bidvex.com")


# 4. send_template_email suppression + injection
class TestSuppressionGuard:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_marketing_suppressed_blocks_send(self):
        from services import email_service
        async def go():
            with patch("routes.unsubscribe.is_marketing_suppressed", AsyncMock(return_value=True)):
                with patch.object(email_service, "_get_sg") as mock_sg:
                    mock_client = MagicMock()
                    mock_sg.return_value = mock_client
                    result = await email_service.send_template_email(
                        to_email="x@y.com", to_name="X", template_id="d-t",
                        dynamic_data={}, is_marketing=True)
                    assert result is False
                    mock_client.send.assert_not_called()
        _run_async(go)

    def test_transactional_bypasses_suppression(self):
        from services import email_service
        async def go():
            with patch("routes.unsubscribe.is_marketing_suppressed", AsyncMock(return_value=True)) as guard:
                with patch.object(email_service, "_get_sg") as mock_sg:
                    mock_client = MagicMock()
                    resp = MagicMock(); resp.status_code = 202; resp.headers = {"X-Message-Id": "abc"}
                    mock_client.send.return_value = resp
                    mock_sg.return_value = mock_client
                    result = await email_service.send_template_email(
                        to_email="x@y.com", to_name="X", template_id="d-t",
                        dynamic_data={}, is_marketing=False)
                    assert result is True
                    guard.assert_not_called()
                    mock_client.send.assert_called_once()
        _run_async(go)

    def test_marketing_injects_bilingual_urls(self):
        from services import email_service
        data = {}
        async def go():
            with patch("routes.unsubscribe.is_marketing_suppressed", AsyncMock(return_value=False)):
                with patch.object(email_service, "_get_sg") as mock_sg:
                    mock_client = MagicMock()
                    resp = MagicMock(); resp.status_code = 202; resp.headers = {"X-Message-Id": "abc"}
                    mock_client.send.return_value = resp
                    mock_sg.return_value = mock_client
                    r = await email_service.send_template_email(
                        to_email="user@example.com", to_name="U", template_id="d-t",
                        dynamic_data=data, is_marketing=True)
                    assert r is True
        _run_async(go)
        # dynamic_data is mutated via setdefault() in email_service
        assert "/unsubscribe?token=" in data["unsubscribe_url_en"]
        assert "lang=en" in data["unsubscribe_url_en"]
        assert "/desabonnement?token=" in data["unsubscribe_url_fr"]
        assert "lang=fr" in data["unsubscribe_url_fr"]


# 5. SendGrid webhook handlers (call directly; live endpoint rejects unsigned)
class TestWebhookHandlers:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_unsubscribe_event_writes_suppression(self, db, test_email):
        from routes.sendgrid_webhook import _process_events, UNSUBSCRIBE_EVENTS
        assert "unsubscribe" in UNSUBSCRIBE_EVENTS
        email_l = test_email.lower()
        try:
            _run_async(lambda: _process_events([{
                "event": "unsubscribe", "email": test_email,
                "sg_event_id": f"evt_{uuid.uuid4().hex}",
                "timestamp": 1700000000,
            }]))
            time.sleep(0.5)
            supp = db.email_suppressions.find_one({"email": email_l})
            assert supp is not None, "unsubscribe event must write to email_suppressions"
            # user doc only updated if one exists (handler doesn't upsert)
        finally:
            db.users.delete_one({"email": email_l})
            db.email_suppressions.delete_one({"email": email_l})

    def test_spamreport_is_in_unsubscribe_events(self, db, test_email):
        from routes.sendgrid_webhook import _process_events, UNSUBSCRIBE_EVENTS, DELIVERABILITY_KILL_EVENTS
        assert "spamreport" in UNSUBSCRIBE_EVENTS
        assert "spamreport" not in DELIVERABILITY_KILL_EVENTS
        email_l = test_email.lower()
        try:
            _run_async(lambda: _process_events([{
                "event": "spamreport", "email": test_email,
                "sg_event_id": f"evt_{uuid.uuid4().hex}",
                "timestamp": 1700000000,
            }]))
            time.sleep(0.5)
            supp = db.email_suppressions.find_one({"email": email_l})
            assert supp is not None, "spamreport must write to email_suppressions (now in UNSUBSCRIBE_EVENTS)"
        finally:
            db.users.delete_one({"email": email_l})
            db.email_suppressions.delete_one({"email": email_l})


# 6. End-to-end lifecycle
class TestLifecycle:
    def test_register_unsubscribe_resend_flow(self, session, db, test_email):
        """Register contact → send marketing (allowed) → unsubscribe → send marketing (blocked) → send transactional (allowed)"""
        from services import email_service
        email_l = test_email.lower()
        async def run():
            # Pre-unsubscribe: send marketing → SendGrid called
            with patch.object(email_service, "_get_sg") as mock_sg:
                mock_client = MagicMock()
                resp = MagicMock(); resp.status_code = 202; resp.headers = {"X-Message-Id": "a"}
                mock_client.send.return_value = resp
                mock_sg.return_value = mock_client
                r1 = await email_service.send_template_email(
                    to_email=test_email, to_name="T", template_id="d-t",
                    dynamic_data={}, is_marketing=True)
                assert r1 is True
                assert mock_client.send.call_count == 1

            # Unsubscribe via API
            token = generate_unsubscribe_token(test_email)
            r = session.post(f"{BASE_URL}/api/unsubscribe/confirm", json={"token": token})
            assert r.status_code == 200

            # Post-unsubscribe: marketing blocked
            with patch.object(email_service, "_get_sg") as mock_sg:
                mock_client = MagicMock(); mock_sg.return_value = mock_client
                r2 = await email_service.send_template_email(
                    to_email=test_email, to_name="T", template_id="d-t",
                    dynamic_data={}, is_marketing=True)
                assert r2 is False
                mock_client.send.assert_not_called()

            # Transactional still sends
            with patch.object(email_service, "_get_sg") as mock_sg:
                mock_client = MagicMock()
                resp = MagicMock(); resp.status_code = 202; resp.headers = {"X-Message-Id": "b"}
                mock_client.send.return_value = resp
                mock_sg.return_value = mock_client
                r3 = await email_service.send_template_email(
                    to_email=test_email, to_name="T", template_id="d-t",
                    dynamic_data={}, is_marketing=False)
                assert r3 is True
                mock_client.send.assert_called_once()
        try:
            _run_async(run)
        finally:
            db.users.delete_one({"email": email_l})
            db.email_suppressions.delete_one({"email": email_l})
