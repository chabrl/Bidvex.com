"""
iter317 Directives 2+3 — Agreement & Email Hub unit tests.
Direct text-hash, signature-injection, and validator coverage.
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest

from legal.contractor_agreement_v2 import (
    AGREEMENT_TEXT_EN,
    AGREEMENT_TEXT_FR,
    AGREEMENT_TEXT_HASH,
    AGREEMENT_VERSION,
    compute_text_hash,
    get_agreement,
)
from services.contractor_email_hub import (
    BIDVEX_CDN_LOGO_URL,
    CONTRACTOR_SENDER_EMAIL,
    SIGNATURE_TOKEN,
    SUPPORT_PHONE,
    build_contractor_signature,
    inject_signature,
    validate_recipient_email,
)


# ─── Directive 2 — Agreement text guarantees ─────────────────────────────

class TestAgreementV2:
    def test_french_text_uses_latin_indépendante_not_arabic(self):
        # Arabic substitutes from previous garbled versions.
        assert "مستقل" not in AGREEMENT_TEXT_FR
        assert "أو" not in AGREEMENT_TEXT_FR
        # Garble-free required tokens.
        assert "indépendante" in AGREEMENT_TEXT_FR
        # The standalone French conjunction "ou" must appear.
        assert " ou " in AGREEMENT_TEXT_FR

    def test_french_text_has_no_arabic_characters_at_all(self):
        for ch in AGREEMENT_TEXT_FR:
            cp = ord(ch)
            # Arabic block 0x0600..0x06FF — must NOT appear anywhere.
            assert not (0x0600 <= cp <= 0x06FF), f"Arabic char {ch!r} (U+{cp:04X}) leaked into FR text"

    def test_english_text_contains_canonical_clauses(self):
        for clause in [
            "INDEPENDENT CONTRACTOR STATUS",
            "COMMISSION & PAYMENT",
            "Leaderboard Overlay",
            "20.0%",
            "5.0%",
            "ELECTRONIC ACCEPTANCE",
            "SHA-256",
        ]:
            assert clause in AGREEMENT_TEXT_EN

    def test_french_text_contains_canonical_clauses(self):
        for clause in [
            "STATUT DE CONTRACTANT INDÉPENDANT",
            "COMMISSION ET PAIEMENT",
            "Leaderboard Overlay",
            "+20,0 %",
            "5,0 %",
            "ACCEPTATION ÉLECTRONIQUE",
            "SHA-256",
        ]:
            assert clause in AGREEMENT_TEXT_FR

    def test_hash_is_deterministic(self):
        assert compute_text_hash() == AGREEMENT_TEXT_HASH
        assert len(AGREEMENT_TEXT_HASH) == 64

    def test_get_agreement_payload_shape(self):
        p = get_agreement()
        assert set(p.keys()) >= {
            "version", "title_en", "title_fr", "text_en", "text_fr", "text_hash",
        }
        assert p["version"] == AGREEMENT_VERSION
        assert p["text_hash"] == AGREEMENT_TEXT_HASH


# ─── Directive 3 — Signature builder & injector ──────────────────────────

class TestContractorSignature:
    def test_signature_uses_cdn_logo_not_assets(self):
        sig = build_contractor_signature(
            contractor_name="Jane", contractor_email="jane@bidvex.ca", locale="en",
        )
        # Canonical CDN URL must appear.
        assert BIDVEX_CDN_LOGO_URL in sig
        # NEVER use bidvex.com/assets path.
        assert "bidvex.com/assets" not in sig
        assert ".sendgrid.net" in sig  # implicit assertion on CDN host

    def test_signature_hardcodes_support_number(self):
        sig = build_contractor_signature(
            contractor_name="Jane", contractor_email="jane@bidvex.ca", locale="en",
        )
        assert SUPPORT_PHONE in sig
        assert "+1 450 634 3099" in sig
        assert "+14506343099" in sig  # tel link

    def test_signature_has_idempotency_token(self):
        sig = build_contractor_signature(
            contractor_name="A", contractor_email="a@b.com", locale="en",
        )
        assert SIGNATURE_TOKEN in sig

    def test_signature_bilingual(self):
        sig_en = build_contractor_signature(
            contractor_name="A", contractor_email="a@b.com", locale="en",
        )
        sig_fr = build_contractor_signature(
            contractor_name="A", contractor_email="a@b.com", locale="fr",
        )
        assert "Support:" in sig_en
        assert "All rights reserved" in sig_en
        assert "Soutien:" in sig_fr
        assert "Tous droits réservés" in sig_fr


class TestSignatureInjection:
    def test_injects_when_body_lacks_token(self):
        sig = build_contractor_signature(
            contractor_name="A", contractor_email="a@b.com", locale="en",
        )
        out = inject_signature("<p>Hello</p>", sig)
        assert SIGNATURE_TOKEN in out
        assert "<p>Hello</p>" in out

    def test_idempotent_when_token_already_present(self):
        sig = build_contractor_signature(
            contractor_name="A", contractor_email="a@b.com", locale="en",
        )
        once = inject_signature("<p>Hi</p>", sig)
        twice = inject_signature(once, sig)
        # No double-injection.
        assert twice.count(SIGNATURE_TOKEN) == 1

    def test_injects_before_closing_body_tag(self):
        sig = build_contractor_signature(
            contractor_name="A", contractor_email="a@b.com", locale="en",
        )
        out = inject_signature(
            "<html><body><p>X</p></body></html>", sig,
        )
        # The signature must appear BEFORE </body>.
        body_close = out.find("</body>")
        sig_start = out.find(SIGNATURE_TOKEN)
        assert 0 < sig_start < body_close

    def test_empty_body_returns_signature(self):
        sig = build_contractor_signature(
            contractor_name="A", contractor_email="a@b.com", locale="en",
        )
        assert inject_signature("", sig) == sig


class TestRecipientValidator:
    @pytest.mark.parametrize("e", [
        "x@y.com", "a.b+tag@example.co.uk", "user@bidvex.ca",
    ])
    def test_valid_emails(self, e):
        assert validate_recipient_email(e) is True

    @pytest.mark.parametrize("e", [
        "", "no-at-sign", "@nodom.com", "no@dom", "x@", " ", "a@b. c",
        "x" * 250 + "@y.com",
    ])
    def test_invalid_emails(self, e):
        assert validate_recipient_email(e) is False


# ─── Directive 3 — Sender enforcement is a constant, not a parameter ────

class TestSenderHardLock:
    def test_sender_is_info_bidvex_com(self):
        # iter323 sender restored to partners@bidvex.ca (per the original
        # iter317 spec) now that SendGrid is authenticated for
        # `reply.bidvex.ca`. Old iter318 assertion (info@bidvex.com)
        # superseded; see /app/memory/CHANGELOG.md.
        assert CONTRACTOR_SENDER_EMAIL == "partners@bidvex.ca"

    def test_support_phone_is_hardcoded_exactly(self):
        assert SUPPORT_PHONE == "+1 450 634 3099"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
