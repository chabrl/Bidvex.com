"""
Iteration 159 — Pre-launch P3/P2 fixes
Tests:
  1. GET /api/site-config/legal-pages → 200 (en/fr/no-lang) — never 500
  2. GET /api/stats/public → 200 with {active_auctions: int}
  3. services/invoice_generator generate_vehicle_invoice_pdf bilingual labels
  4. services/invoice_generator generate_general_invoice_pdf bilingual labels
"""
import io
import os
import sys
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

# Make /app/backend importable for direct service tests
sys.path.insert(0, "/app/backend")


# ── 1. Legal-pages public endpoint ────────────────────────────────────
class TestLegalPagesPublic:
    def test_legal_pages_default(self):
        r = requests.get(f"{API}/site-config/legal-pages", timeout=15)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        # Either success=true with pages, or success=false with empty pages — never 500
        assert "success" in data
        assert "pages" in data or "message" in data

    def test_legal_pages_en(self):
        r = requests.get(f"{API}/site-config/legal-pages?language=en", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "success" in data

    def test_legal_pages_fr(self):
        r = requests.get(f"{API}/site-config/legal-pages?language=fr", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "success" in data

    def test_legal_pages_invalid_lang(self):
        # Should still return 200 (treated as 'no language filter')
        r = requests.get(f"{API}/site-config/legal-pages?language=xx", timeout=15)
        assert r.status_code == 200


# ── 2. Public stats counter ───────────────────────────────────────────
class TestPublicStats:
    def test_stats_public_shape(self):
        r = requests.get(f"{API}/stats/public", timeout=15)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert "active_auctions" in data
        assert isinstance(data["active_auctions"], int)
        assert data["active_auctions"] >= 0


# ── 3 & 4. Bilingual invoice PDF generation ─────────────────────────
@pytest.fixture(scope="module")
def pypdf_extract():
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover
        pytest.skip("pypdf not installed")

    def _extract(pdf_bytes: bytes) -> str:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    return _extract


@pytest.fixture(scope="module")
def vehicle_pdf_bytes():
    from services.tax_engine import calculate_vehicle_payment
    from services.invoice_generator import generate_vehicle_invoice_pdf

    payment = calculate_vehicle_payment(hammer_price=25000.0, buyer_tier="basic")
    pdf = generate_vehicle_invoice_pdf(
        payment_result=payment,
        buyer_info={"name": "Jean Tremblay", "email": "jean@example.com",
                    "address": "123 rue Test", "phone": "514-555-0100"},
        seller_info={"name": "Auto QC Inc.", "email": "ventes@autoqc.ca",
                     "address": "456 boul Sherbrooke", "phone": "514-555-0200",
                     "gst_number": "123456789RT0001", "qst_number": "1234567890TQ0001"},
        auction_info={"vehicle_title": "2020 Toyota Corolla", "auction_id": "A-TEST-V",
                      "vin": "1HGBH41JXMN000001", "year": 2020, "make": "Toyota", "model": "Corolla"},
        invoice_number="BV-TEST-VEHICLE",
    )
    assert isinstance(pdf, (bytes, bytearray)) and len(pdf) > 1000
    return bytes(pdf)


@pytest.fixture(scope="module")
def general_pdf_bytes():
    from services.tax_engine import calculate_general_payment
    from services.invoice_generator import generate_general_invoice_pdf

    payment = calculate_general_payment(
        hammer_price=2500.0,
        buyer_tier="basic",
        seller_tier="basic",
        seller_is_business=True,
    )
    pdf = generate_general_invoice_pdf(
        payment_result=payment,
        buyer_info={"name": "Marie Dubois", "email": "marie@example.com",
                    "address": "789 rue Saint-Denis", "phone": "514-555-0300"},
        seller_info={"name": "Equip Plus", "email": "info@equipplus.ca",
                     "address": "321 rue Industrial", "phone": "514-555-0400",
                     "gst_number": "987654321RT0001", "qst_number": "9876543210TQ0001"},
        auction_info={"item_title": "Industrial Generator", "auction_id": "A-TEST-G"},
        invoice_number="BV-TEST-GENERAL",
    )
    assert isinstance(pdf, (bytes, bytearray)) and len(pdf) > 1000
    return bytes(pdf)


def _has(haystack: str, needles: list) -> list:
    """Return any needle that is NOT in haystack."""
    h = haystack
    return [n for n in needles if n not in h]


class TestVehicleInvoicePDF:
    def test_vehicle_pdf_bilingual_labels(self, vehicle_pdf_bytes, pypdf_extract):
        text = pypdf_extract(vehicle_pdf_bytes)
        # Must-have bilingual content
        required = [
            "FACTURE",                  # FR title
            "Numéro de facture",        # FR invoice-number label
            "ACHETEUR",                 # FR buyer
            "VENDEUR",                  # FR seller
            "TPS",                      # GST FR
            "TVQ",                      # QST FR
            "INSTRUCTIONS DE PAIEMENT", # FR payment instructions
            "Étape 1",                  # FR step-1
            "traite bancaire",          # FR bank draft
        ]
        missing = _has(text, required)
        # 14.975% combined line — accept either decimal style
        if "14.975" not in text and "14,975" not in text:
            missing.append("14.975/14,975")
        assert not missing, f"Vehicle PDF missing bilingual labels: {missing}\n--- extracted ---\n{text[:1500]}"


class TestGeneralInvoicePDF:
    def test_general_pdf_bilingual_labels(self, general_pdf_bytes, pypdf_extract):
        text = pypdf_extract(general_pdf_bytes)
        required = [
            "FACTURE",
            "Numéro de facture",
            "ACHETEUR",
            "VENDEUR",
            "TPS",
            "TVQ",
            "INSTRUCTIONS DE PAIEMENT",
            "TVQ sur la prime",          # QST on buyer premium FR
            "TOTAL GÉNÉRAL",             # GRAND TOTAL FR
        ]
        missing = _has(text, required)
        if "14.975" not in text and "14,975" not in text:
            missing.append("14.975/14,975")
        assert not missing, f"General PDF missing bilingual labels: {missing}\n--- extracted ---\n{text[:1500]}"
