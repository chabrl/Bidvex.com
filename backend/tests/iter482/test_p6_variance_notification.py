"""
iter482 P6 — Variance notification idempotency + rendering tests.

Covers:
  • CA + INT card jurisdiction paths through the variance email renderer
  • Idempotency guard (SENDING/SENT/PENDING transitions)
  • FR accent + terminology correctness
  • Recipients resolution (admin users + BILLING_ALERT_EMAIL env override
    + ADMIN_EMAIL fallback, deduped)

These tests exercise pure functions and an in-memory fake DB — no
network, no SendGrid round-trip, no P7 golden-snapshot impact.
"""
from __future__ import annotations
import asyncio
import os
from typing import Any, Dict, List, Optional

import pytest


# ─── in-memory fake Motor collection ────────────────────────────
class _FakeCol:
    def __init__(self) -> None:
        self.docs: List[Dict[str, Any]] = []

    async def find_one(self, query, projection=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                return dict(d)
        return None

    async def find_one_and_update(self, query, update, return_document=False):
        for d in self.docs:
            match = True
            for k, v in query.items():
                if k == "$or":
                    ok = False
                    for cond in v:
                        if all(_match_scalar(d, kk, vv) for kk, vv in cond.items()):
                            ok = True
                            break
                    if not ok:
                        match = False
                        break
                    continue
                if not _match_scalar(d, k, v):
                    match = False
                    break
            if match:
                if "$set" in update:
                    d.update(update["$set"])
                return dict(d)
        return None

    async def update_one(self, query, update, upsert=False):
        target = None
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                target = d
                break
        if not target and upsert:
            target = dict(query)
            if "$setOnInsert" in update:
                target.update(update["$setOnInsert"])
            self.docs.append(target)
        if target is not None and "$set" in update:
            target.update(update["$set"])

    def find(self, query, projection=None):
        matched = [dict(d) for d in self.docs if all(d.get(k) == v for k, v in query.items() if not isinstance(v, dict))]
        return _FakeCursor(matched)


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs
        self._limit = None

    def limit(self, n):
        self._limit = n
        return self

    def __aiter__(self):
        docs = self._docs[: self._limit] if self._limit else self._docs
        return _AsyncListIter(docs)


class _AsyncListIter:
    def __init__(self, docs):
        self._docs = list(docs)
        self._i = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._i >= len(self._docs):
            raise StopAsyncIteration
        d = self._docs[self._i]
        self._i += 1
        return d


def _match_scalar(d, key, val):
    if isinstance(val, dict):
        if "$exists" in val:
            has = key in d
            return has if val["$exists"] else (not has)
        if "$ne" in val:
            return d.get(key) != val["$ne"]
        return True
    return d.get(key) == val


class _FakeDB:
    def __init__(self):
        self.payment_processing_reconciliation = _FakeCol()
        self.users = _FakeCol()


# ─── unit tests ─────────────────────────────────────────────────
class TestVarianceEmailRendering:
    """The FR body MUST use the finalized P6 vocabulary — this test
    prevents any silent revert to older strings like 'Frais Stripe'."""

    def test_en_body_uses_canonical_labels(self):
        from services.variance_notification_service import _render_html
        doc = {
            "payment_intent_id": "pi_test_1",
            "reconciliation_status": "SHORTFALL",
            "estimated_cents": 320,
            "recovery_cents":  330,
            "actual_cents":    420,
            "variance_cents":  -90,
            "currency": "CAD",
            "payer_role": "buyer",
            "resolved_jurisdiction": "international",
            "card_country": "US",
            "updated_at": "2026-02-14T18:00:00+00:00",
        }
        html = _render_html(doc, "en")
        assert "Payment Processing Fee Variance Detected" in html
        assert "Actual Stripe Processing Fee" in html
        assert "Payment Processing Fee Recovery" in html
        assert "Estimated Payment Processing Fee" in html
        # Shortfall label (not variance) because variance_cents < 0.
        assert "Processing Fee Shortfall" in html
        # Values must appear formatted correctly.
        assert "$4.20 CAD" in html   # actual
        assert "$3.30 CAD" in html   # recovery
        assert "-$0.90 CAD" in html  # variance (signed)
        assert "International" in html

    def test_fr_body_uses_finalized_p6_vocabulary(self):
        from services.variance_notification_service import _render_html
        doc = {
            "payment_intent_id": "pi_test_1",
            "reconciliation_status": "SHORTFALL",
            "estimated_cents": 320,
            "recovery_cents":  330,
            "actual_cents":    420,
            "variance_cents":  -90,
            "currency": "CAD",
            "payer_role": "buyer",
            "resolved_jurisdiction": "international",
            "card_country": "US",
            "updated_at": "2026-02-14T18:00:00+00:00",
        }
        html = _render_html(doc, "fr")
        # Finalized P6 canonical strings — accents MUST be preserved.
        assert "Frais de traitement du paiement estimés" in html
        assert "Récupération des frais de traitement du paiement" in html
        assert "Frais de traitement Stripe réels" in html
        assert "Manque à récupérer sur les frais de traitement" in html
        assert "Écart détecté" in html
        # Guardrail — the discouraged variants must NOT appear.
        assert "Frais Stripe" not in html or "Frais Stripe réels" not in html
        # (We tolerate "Frais Stripe réels" nowhere — only "Frais de
        # traitement Stripe réels" is the finalized wording.)
        assert "Frais Stripe réels" not in html

    def test_domestic_body_uses_canada_label(self):
        from services.variance_notification_service import _render_html
        doc = {
            "payment_intent_id": "pi_test_ca",
            "reconciliation_status": "SHORTFALL",
            "estimated_cents": 320,
            "recovery_cents":  320,
            "actual_cents":    325,
            "variance_cents":  -5,
            "currency": "CAD",
            "resolved_jurisdiction": "domestic",
            "card_country": "CA",
            "updated_at": "2026-02-14T18:00:00+00:00",
        }
        html_en = _render_html(doc, "en")
        html_fr = _render_html(doc, "fr")
        assert "Canada" in html_en
        assert "Canada" in html_fr


class TestVarianceEmailIdempotency:
    """Locks the atomic claim/dispatch contract — a webhook retry must
    NEVER produce a second SendGrid call for the same PaymentIntent."""

    @pytest.fixture
    def db(self):
        return _FakeDB()

    def _seed(self, db, *, status="SHORTFALL", notif_status=None):
        d = {
            "payment_intent_id": "pi_test_dedup",
            "reconciliation_status": status,
            "estimated_cents": 320,
            "recovery_cents":  320,
            "actual_cents":    420,
            "variance_cents":  -100,
            "currency": "CAD",
            "resolved_jurisdiction": "international",
            "card_country": "US",
            "payer_role": "buyer",
            "updated_at": "2026-02-14T18:00:00+00:00",
        }
        if notif_status is not None:
            d["variance_notification_status"] = notif_status
        db.payment_processing_reconciliation.docs.append(d)
        db.users.docs.append({"role": "admin", "email": "admin@bidvex.test"})
        return d

    def test_first_call_claims_and_marks_sent(self, db, monkeypatch):
        from services.variance_notification_service import dispatch_variance_notification
        doc = self._seed(db)

        async def fake_send(**kwargs):
            return {"status": "sent"}

        # Monkey-patch canonical dispatcher import inside the service.
        import services.emails._email_core as _core
        monkeypatch.setattr(_core, "send_email", fake_send)

        res = asyncio.get_event_loop().run_until_complete(
            dispatch_variance_notification(db, doc)
        )
        assert res["status"] == "sent"
        # The seeded admin must be present. Additional recipients may
        # be present when a prior test loaded backend/.env into the
        # process (e.g. ADMIN_EMAIL / BILLING_ALERT_EMAIL); those are
        # intentional fallback recipients and don't break idempotency.
        assert "admin@bidvex.test" in res["recipients"]
        assert res["sent_at"] is not None
        # Persisted state should reflect SENT.
        stored = db.payment_processing_reconciliation.docs[0]
        assert stored["variance_notification_status"] == "SENT"
        assert stored["variance_notification_sent_at"]

    def test_second_call_is_a_noop_after_sent(self, db, monkeypatch):
        from services.variance_notification_service import dispatch_variance_notification
        doc = self._seed(db, notif_status="SENT")

        call_count = {"n": 0}

        async def fake_send(**kwargs):
            call_count["n"] += 1
            return {"status": "sent"}

        import services.emails._email_core as _core
        monkeypatch.setattr(_core, "send_email", fake_send)

        res = asyncio.get_event_loop().run_until_complete(
            dispatch_variance_notification(db, doc)
        )
        assert res["status"] == "skipped"
        assert res.get("reason") == "already_dispatched"
        assert call_count["n"] == 0  # SendGrid never called

    def test_reconciled_status_never_sends(self, db, monkeypatch):
        from services.variance_notification_service import dispatch_variance_notification
        doc = self._seed(db, status="COVERED")

        called = {"yes": False}

        async def fake_send(**kwargs):
            called["yes"] = True
            return {"status": "sent"}

        import services.emails._email_core as _core
        monkeypatch.setattr(_core, "send_email", fake_send)

        res = asyncio.get_event_loop().run_until_complete(
            dispatch_variance_notification(db, doc)
        )
        assert res["status"] == "not_shortfall"
        assert called["yes"] is False


class TestReconciliationStatusVocabulary:
    """Locks the P6-canonical public status vocabulary."""

    def test_public_status_map(self):
        from services.stripe_reconciliation_service import public_status
        assert public_status("COVERED")   == "RECONCILED"
        assert public_status("SHORTFALL") == "SHORTFALL"
        assert public_status("UNKNOWN")   == "PENDING"
        assert public_status("ERROR")     == "ERROR"
        assert public_status(None)        == "PENDING"

    def test_public_status_is_case_insensitive(self):
        from services.stripe_reconciliation_service import public_status
        assert public_status("covered") == "RECONCILED"
        assert public_status("Shortfall") == "SHORTFALL"


class TestRecipientResolution:
    """Recipients MUST combine admin users + BILLING_ALERT_EMAIL env
    override + ADMIN_EMAIL fallback, deduped, ordered."""

    def test_deduped_and_ordered(self, monkeypatch):
        from services.variance_notification_service import _resolve_recipients
        db = _FakeDB()
        db.users.docs.extend([
            {"role": "admin",       "email": "a@bidvex.test"},
            {"role": "super_admin", "email": "b@bidvex.test"},
            {"role": "admin",       "email": "a@bidvex.test"},  # duplicate
        ])
        monkeypatch.setenv("BILLING_ALERT_EMAIL", "billing@bidvex.test")
        monkeypatch.setenv("ADMIN_EMAIL",         "a@bidvex.test")  # dupe of above

        result = asyncio.get_event_loop().run_until_complete(
            _resolve_recipients(db)
        )
        # Deduped: admins first, then unique env override; ADMIN_EMAIL
        # already present, so not appended twice.
        assert result[0] == "a@bidvex.test"
        assert "b@bidvex.test" in result
        assert "billing@bidvex.test" in result
        assert len(result) == len(set(result))
