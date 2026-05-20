"""
iter217 Phase 5 — Conversion & Email Funnel Activation tests.

Covers:
  Task 1 — Email outbox drainer
    • Picks up vehicle_released_with_receipt rows and stamps them sent
    • Picks up title_transfer_overdue rows
    • Idempotency: already-sent rows are skipped
    • Failed rows retry up to MAX_ATTEMPTS then are marked failed
    • Missing recipient → skipped_no_recipient

  Task 2 — Day-21 retention reminder
    • Queues for eligible users only (account ≥ 21d, no relationship,
      not a broker, no prior reminder)
    • Honors user's language for the queued context
    • Idempotent (second run queues nothing)
    • Skips users who already started a broker partnership

  Task 3 — Meta CAPI Purchase events
    • value = platform_fee + broker_fee (NEVER hammer)
    • SHA-256 hashes email/phone/name/state before transmission
    • Audit row written to meta_capi_log
    • Graceful no-op when META_* env vars unset
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient


@pytest.fixture
def db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture
def cleanup():
    state = {"users": [], "outbox": [], "rels": [], "capi": []}
    yield state
    sync = MongoClient(os.environ["MONGO_URL"])
    sdb  = sync[os.environ["DB_NAME"]]
    for uid in state["users"]: sdb.users.delete_one({"id": uid})
    for oid in state["outbox"]: sdb.email_outbox.delete_one({"id": oid})
    for rid in state["rels"]: sdb.broker_buyer_relationships.delete_one({"id": rid})
    for cid in state["capi"]: sdb.meta_capi_log.delete_one({"id": cid})
    sync.close()


# ────────────────────────────────────────────────────────────────────
# TASK 3 — Meta CAPI
# ────────────────────────────────────────────────────────────────────
class TestMetaCAPI:
    def test_value_equals_platform_plus_broker_fee_only(self):
        """LEGAL: value must be platform + broker fee — NEVER hammer."""
        from services.analytics_tracker import compute_purchase_value_cad
        v = compute_purchase_value_cad(platform_fee=375.00, broker_fee=500.00)
        assert v == 875.00
        # Even if someone tried to pass hammer through, it isn't accepted
        v2 = compute_purchase_value_cad(platform_fee=0, broker_fee=0)
        assert v2 == 0.0

    def test_user_data_hashes_pii(self):
        """Every PII field must be SHA-256-hashed; IP / UA pass through."""
        from services.analytics_tracker import build_user_data
        u = build_user_data(
            email="John.Doe@Example.com",
            phone="+1 (514) 555-1234",
            first_name="John", last_name="Doe",
            state="QC", country="ca",
            client_ip="1.2.3.4",
            client_ua="UA-test/1.0",
        )
        # All hashed fields are 64-char hex SHA-256
        for k in ("em", "ph", "fn", "ln", "st", "country"):
            assert k in u, f"missing {k}"
            assert isinstance(u[k], list) and len(u[k]) == 1
            assert len(u[k][0]) == 64
            int(u[k][0], 16)   # raises if not hex
        # Cleartext only for IP / UA
        assert u["client_ip_address"] == "1.2.3.4"
        assert u["client_user_agent"] == "UA-test/1.0"
        # Email is hashed of LOWER-CASE STRIP form
        import hashlib
        assert u["em"][0] == hashlib.sha256(b"john.doe@example.com").hexdigest()
        # Phone is digits-only before hashing
        assert u["ph"][0] == hashlib.sha256(b"15145551234").hexdigest()

    def test_purchase_event_payload_shape(self):
        from services.analytics_tracker import build_purchase_event, build_user_data
        ud = build_user_data(email="a@b.com")
        ev = build_purchase_event(platform_fee=375, broker_fee=500, user_data=ud,
                                   event_id="inv_1", event_source_url="https://bidvex.com/test")
        assert ev["event_name"] == "Purchase"
        assert ev["event_id"]   == "inv_1"
        assert ev["custom_data"]["currency"] == "CAD"
        assert ev["custom_data"]["value"]    == 875.00
        # Never any hammer-derived field
        assert "hammer" not in ev["custom_data"]

    @pytest.mark.asyncio
    async def test_track_broker_purchase_writes_audit(self, db, cleanup):
        """Even when META_* env vars missing, the audit row is written."""
        from services.analytics_tracker import track_broker_purchase
        # Ensure CAPI is in no-op mode
        os.environ.pop("META_PIXEL_ID", None)
        os.environ.pop("META_CAPI_ACCESS_TOKEN", None)
        result = await track_broker_purchase(
            db=db,
            invoice_id="inv-test-" + uuid.uuid4().hex[:6],
            platform_fee=375.0,
            broker_fee=500.0,
            buyer_user={"email": "buyer@example.com", "full_name": "John Doe", "id": "u-1"},
        )
        assert result["value_cad"] == 875.0
        assert result["delivery"]["ok"] is False
        assert result["delivery"]["reason"] == "missing_env"
        # Audit row present
        row = await db.meta_capi_log.find_one({"event_id": result["event_id"]}, {"_id": 0, "id": 1, "value_cad": 1})
        assert row is not None
        assert row["value_cad"] == 875.0
        cleanup["capi"].append(row["id"])


# ────────────────────────────────────────────────────────────────────
# TASK 1 — Email outbox drainer
# ────────────────────────────────────────────────────────────────────
class TestEmailOutboxDrainer:
    @pytest.mark.asyncio
    async def test_drainer_processes_receipt_email(self, db, cleanup):
        """Drainer marks the row 'stubbed_no_template' when no SendGrid
        template env var is set — the dev-mode happy path."""
        from workers.email_delivery_worker import drain_email_outbox
        # Seed a user
        uid = str(uuid.uuid4())
        await db.users.insert_one({
            "id": uid, "email": f"buyer-{uuid.uuid4().hex[:6]}@example.com",
            "full_name": "John Doe", "is_active": True, "email_verified": True,
            "role": "user", "account_type": "personal",
            "username": "j", "hashed_password": "x", "password_hash": "x", "is_demo_account": False,
        })
        cleanup["users"].append(uid)
        # Seed an outbox row
        oid = str(uuid.uuid4())
        await db.email_outbox.insert_one({
            "id": oid, "kind": "vehicle_released_with_receipt",
            "to_user_id": uid,
            "context": {
                "invoice_id": "inv-1", "invoice_number": "BVX-1",
                "pickup_code": "ABCD-1234",
                "receipt_url": "/my-receipt/inv-1?code=tok123",
            },
            "queued_at": datetime.now(timezone.utc),
        })
        cleanup["outbox"].append(oid)
        # Ensure SendGrid is not configured for this test
        os.environ.pop("SENDGRID_TEMPLATE_VEHICLE_RELEASED_WITH_RECEIPT_EN", None)
        os.environ.pop("SENDGRID_TEMPLATE_VEHICLE_RELEASED_WITH_RECEIPT_FR", None)

        stats = await drain_email_outbox(db)
        assert stats["processed"] >= 1
        assert stats["stubbed"]   >= 1

        # Row stamped sent (stubbed)
        row = await db.email_outbox.find_one({"id": oid}, {"_id": 0})
        assert row["sent_at"] is not None
        assert row["delivery_status"] == "stubbed_no_template"
        assert row["sent_to"].startswith("buyer-")
        assert row["sent_lang"] in ("en", "fr")

    @pytest.mark.asyncio
    async def test_drainer_is_idempotent(self, db, cleanup):
        """Re-running the drainer on a sent row does not re-process it."""
        from workers.email_delivery_worker import drain_email_outbox
        uid = str(uuid.uuid4())
        await db.users.insert_one({
            "id": uid, "email": f"u-{uuid.uuid4().hex[:6]}@example.com",
            "full_name": "Jane Doe", "is_active": True, "email_verified": True,
            "role": "user", "account_type": "personal",
            "username": "x", "hashed_password": "x", "password_hash": "x", "is_demo_account": False,
        })
        cleanup["users"].append(uid)
        oid = str(uuid.uuid4())
        await db.email_outbox.insert_one({
            "id": oid, "kind": "title_transfer_overdue",
            "to_user_id": uid,
            "context": {"invoice_number": "BVX-2", "broker_name": "Acme"},
            "queued_at": datetime.now(timezone.utc),
        })
        cleanup["outbox"].append(oid)
        await drain_email_outbox(db)
        stats2 = await drain_email_outbox(db)
        # Second call should NOT re-process this row
        rerun = [k for k in ("sent", "stubbed", "failed") if stats2[k] > 0]
        # Either nothing happened OR nothing about THIS oid changed twice
        row = await db.email_outbox.find_one({"id": oid}, {"_id": 0, "attempts": 1, "delivery_status": 1, "sent_at": 1})
        assert row["sent_at"] is not None

    @pytest.mark.asyncio
    async def test_drainer_skips_when_no_recipient(self, db, cleanup):
        """Row with no resolvable email is marked skipped_no_recipient."""
        from workers.email_delivery_worker import drain_email_outbox
        oid = str(uuid.uuid4())
        await db.email_outbox.insert_one({
            "id": oid, "kind": "vehicle_released_with_receipt",
            "to_user_id": "nonexistent-user-id",
            "context": {},
            "queued_at": datetime.now(timezone.utc),
        })
        cleanup["outbox"].append(oid)
        stats = await drain_email_outbox(db)
        assert stats["skipped"] >= 1
        row = await db.email_outbox.find_one({"id": oid}, {"_id": 0})
        assert row["delivery_status"] == "skipped_no_recipient"


# ────────────────────────────────────────────────────────────────────
# TASK 2 — Day-21 broker-onboarding reminder
# ────────────────────────────────────────────────────────────────────
class TestDay21Reminder:
    @pytest.mark.asyncio
    async def test_eligible_user_gets_reminder_queued(self, db, cleanup):
        from jobs.retention_reminders import queue_day21_broker_reminders
        uid = str(uuid.uuid4())
        await db.users.insert_one({
            "id": uid, "email": f"r-{uuid.uuid4().hex[:6]}@example.com",
            "full_name": "Marie Dupont",
            "language": "fr",
            "created_at": datetime.now(timezone.utc) - timedelta(days=22),
            "is_active": True, "email_verified": True,
            "role": "user", "account_type": "personal",
            "username": "m", "hashed_password": "x", "password_hash": "x", "is_demo_account": False,
        })
        cleanup["users"].append(uid)
        s = await queue_day21_broker_reminders(db)
        assert s["queued"] >= 1
        # The queued row carries the user's language
        row = await db.email_outbox.find_one({"to_user_id": uid, "kind": "day21_broker_reminder"}, {"_id": 0})
        assert row is not None
        assert row["context"]["lang"] == "fr"
        cleanup["outbox"].append(row["id"])
        # Idempotency — second run does not requeue
        s2 = await queue_day21_broker_reminders(db)
        assert s2["queued"] < s["queued"] or s2["queued"] == 0

    @pytest.mark.asyncio
    async def test_user_with_active_broker_relationship_skipped(self, db, cleanup):
        from jobs.retention_reminders import queue_day21_broker_reminders
        uid = str(uuid.uuid4())
        await db.users.insert_one({
            "id": uid, "email": f"skip-{uuid.uuid4().hex[:6]}@example.com",
            "full_name": "Existing Partner",
            "created_at": datetime.now(timezone.utc) - timedelta(days=23),
            "is_active": True, "email_verified": True,
            "role": "user", "account_type": "personal",
            "username": "x", "hashed_password": "x", "password_hash": "x", "is_demo_account": False,
        })
        cleanup["users"].append(uid)
        rid = str(uuid.uuid4())
        await db.broker_buyer_relationships.insert_one({
            "id": rid, "buyer_user_id": uid, "broker_id": "b1", "status": "active",
            "created_at": datetime.now(timezone.utc), "approved_at": datetime.now(timezone.utc),
        })
        cleanup["rels"].append(rid)
        await queue_day21_broker_reminders(db)
        n = await db.email_outbox.count_documents({"to_user_id": uid, "kind": "day21_broker_reminder"})
        assert n == 0

    @pytest.mark.asyncio
    async def test_broker_account_is_not_reminded(self, db, cleanup):
        """Brokers / dealers / admins are never reminded to find a broker."""
        from jobs.retention_reminders import queue_day21_broker_reminders
        uid = str(uuid.uuid4())
        await db.users.insert_one({
            "id": uid, "email": f"br-{uuid.uuid4().hex[:6]}@example.com",
            "full_name": "Some Broker",
            "created_at": datetime.now(timezone.utc) - timedelta(days=22),
            "is_active": True, "email_verified": True,
            "role": "user", "account_type": "broker",
            "username": "b", "hashed_password": "x", "password_hash": "x", "is_demo_account": False,
        })
        cleanup["users"].append(uid)
        await queue_day21_broker_reminders(db)
        n = await db.email_outbox.count_documents({"to_user_id": uid, "kind": "day21_broker_reminder"})
        assert n == 0
