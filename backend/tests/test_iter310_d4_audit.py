"""iter310 — D4 backward-compat: legacy /api/external/unsubscribe must still
work AND write an unsubscribe_events audit row with source='external_campaign',
token_type='jwt'."""
from __future__ import annotations
import os, sys, uuid
import requests
import pytest
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")
from pymongo import MongoClient  # noqa: E402

BASE_URL = None
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL"):
            BASE_URL = line.split("=", 1)[1].strip()
            break


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


def test_d4_legacy_unsub_writes_audit_row(db):
    # Generate a valid JWT external_unsub token via the existing helper.
    from services.external_email import make_unsubscribe_token
    email = f"iter310-d4-{uuid.uuid4().hex[:8]}@test.example"
    campaign_id = f"iter310-camp-{uuid.uuid4().hex[:6]}"
    try:
        token = make_unsubscribe_token(email=email, campaign_id=campaign_id, lang="en")
        # Hit the legacy public endpoint.
        r = requests.get(f"{BASE_URL}/api/external/unsubscribe", params={"token": token}, timeout=15)
        assert r.status_code == 200, r.text
        assert "successfully" in r.text.lower() or "désabonné" in r.text.lower() or "unsubscribed" in r.text.lower()
        # Verify audit row.
        row = db.unsubscribe_events.find_one({"email": email}, {"_id": 0})
        assert row is not None, "audit row not written by legacy /api/external/unsubscribe"
        assert row["source"] == "external_campaign"
        assert row["token_type"] == "jwt"
        assert row["event"] == "unsubscribed"
    finally:
        db.users.delete_many({"email": email})
        db.email_suppressions.delete_many({"email": email})
        db.external_email_suppressions.delete_many({"email": email})
        db.unsubscribe_events.delete_many({"email": email})
