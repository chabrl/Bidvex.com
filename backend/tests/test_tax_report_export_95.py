"""
Test Tax Report Export Endpoint - Iteration 95
Tests GET /api/admin/tax-report endpoint with:
- Period filters (Q1-2026, Q2-2026, full year 2026)
- Province filter
- JSON and CSV export formats
- Admin authentication requirement
- Invalid period handling
- Response structure validation
"""

import pytest
import requests
import os
import csv
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"

# Test transaction IDs from test_credentials.md
TEST_TRANSACTION_QC_1 = "5d5e4c3d-5939-4538-a5e2-739f5648bbdb"
TEST_TRANSACTION_QC_2 = "49e7251f-c69a-4ee3-90b4-6e16fbb57404"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth token"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


class TestTaxReportAuthentication:
    """Test authentication requirements for tax report endpoint"""

    def test_tax_report_requires_auth_401(self):
        """GET /api/admin/tax-report returns 401 without auth token"""
        response = requests.get(f"{BASE_URL}/api/admin/tax-report?period=Q2-2026")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("PASSED: Tax report returns 401 without auth")

    def test_tax_report_invalid_token_401(self):
        """GET /api/admin/tax-report returns 401 with invalid token"""
        headers = {"Authorization": "Bearer invalid_token_12345"}
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q2-2026",
            headers=headers
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASSED: Tax report returns 401 with invalid token")


class TestTaxReportPeriodValidation:
    """Test period parameter validation"""

    def test_tax_report_invalid_period_400(self, admin_headers):
        """GET /api/admin/tax-report?period=INVALID returns 400 with helpful error"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=INVALID",
            headers=admin_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data, "Error response should have 'detail' field"
        print(f"PASSED: Invalid period returns 400 with message: {data.get('detail')}")

    def test_tax_report_invalid_quarter_400(self, admin_headers):
        """GET /api/admin/tax-report?period=Q5-2026 returns 400"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q5-2026",
            headers=admin_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "Q1" in data.get("detail", "") or "Q4" in data.get("detail", ""), \
            "Error should mention valid quarters"
        print(f"PASSED: Invalid quarter Q5 returns 400: {data.get('detail')}")


class TestTaxReportJSONFormat:
    """Test JSON format responses"""

    def test_tax_report_q2_2026_json_structure(self, admin_headers):
        """GET /api/admin/tax-report?period=Q2-2026 returns JSON with correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q2-2026",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required top-level fields
        required_fields = ["period", "transaction_count", "totals", "transactions", "generated_by", "date_range"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify date_range structure
        assert "start" in data["date_range"], "date_range should have 'start'"
        assert "end" in data["date_range"], "date_range should have 'end'"
        
        # Verify Q2 date range (April 1 to July 1)
        assert "2026-04-01" in data["date_range"]["start"], f"Q2 should start April 1: {data['date_range']['start']}"
        assert "2026-07-01" in data["date_range"]["end"], f"Q2 should end July 1: {data['date_range']['end']}"
        
        # Verify generated_by is admin email
        assert data["generated_by"] == ADMIN_EMAIL, f"generated_by should be admin email: {data['generated_by']}"
        
        print(f"PASSED: Q2-2026 JSON structure valid. Transaction count: {data['transaction_count']}")

    def test_tax_report_totals_structure(self, admin_headers):
        """Verify totals object has all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q2-2026",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        totals = data.get("totals", {})
        
        required_totals = ["subtotal", "buyer_premium", "tax_gst", "tax_pst_qst", "tax_hst", "total"]
        for field in required_totals:
            assert field in totals, f"Missing totals field: {field}"
            assert isinstance(totals[field], (int, float)), f"totals.{field} should be numeric"
        
        print(f"PASSED: Totals structure valid: {totals}")

    def test_tax_report_transaction_row_structure(self, admin_headers):
        """Each transaction row has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q2-2026",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        transactions = data.get("transactions", [])
        
        if len(transactions) > 0:
            txn = transactions[0]
            required_fields = [
                "transaction_id", "date", "buyer_province", "subtotal",
                "buyer_premium", "tax_gst", "tax_pst_qst", "tax_hst",
                "total", "invoice_url"
            ]
            for field in required_fields:
                assert field in txn, f"Transaction missing field: {field}"
            print(f"PASSED: Transaction row structure valid. Sample: {txn['transaction_id']}")
        else:
            print("PASSED: Transaction structure check (no transactions in Q2-2026)")

    def test_tax_report_totals_sum_correctly(self, admin_headers):
        """Totals object sums all transaction amounts correctly"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q2-2026",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        transactions = data.get("transactions", [])
        totals = data.get("totals", {})
        
        if len(transactions) > 0:
            # Calculate expected totals from transactions
            calc_subtotal = sum(t.get("subtotal", 0) for t in transactions)
            calc_premium = sum(t.get("buyer_premium", 0) for t in transactions)
            calc_gst = sum(t.get("tax_gst", 0) for t in transactions)
            calc_pst_qst = sum(t.get("tax_pst_qst", 0) for t in transactions)
            calc_hst = sum(t.get("tax_hst", 0) for t in transactions)
            calc_total = sum(t.get("total", 0) for t in transactions)
            
            # Allow small floating point tolerance
            assert abs(totals["subtotal"] - calc_subtotal) < 0.01, \
                f"Subtotal mismatch: {totals['subtotal']} vs {calc_subtotal}"
            assert abs(totals["buyer_premium"] - calc_premium) < 0.01, \
                f"Buyer premium mismatch: {totals['buyer_premium']} vs {calc_premium}"
            assert abs(totals["tax_gst"] - calc_gst) < 0.01, \
                f"GST mismatch: {totals['tax_gst']} vs {calc_gst}"
            assert abs(totals["tax_pst_qst"] - calc_pst_qst) < 0.01, \
                f"PST/QST mismatch: {totals['tax_pst_qst']} vs {calc_pst_qst}"
            assert abs(totals["tax_hst"] - calc_hst) < 0.01, \
                f"HST mismatch: {totals['tax_hst']} vs {calc_hst}"
            assert abs(totals["total"] - calc_total) < 0.01, \
                f"Total mismatch: {totals['total']} vs {calc_total}"
            
            print(f"PASSED: Totals sum correctly. Total: ${totals['total']:.2f}")
        else:
            # With no transactions, all totals should be 0
            for key in ["subtotal", "buyer_premium", "tax_gst", "tax_pst_qst", "tax_hst", "total"]:
                assert totals[key] == 0, f"Empty report should have {key}=0"
            print("PASSED: Empty report has zero totals")


class TestTaxReportProvinceFilter:
    """Test province filtering"""

    def test_tax_report_province_filter_qc(self, admin_headers):
        """GET /api/admin/tax-report?period=Q2-2026&province=QC filters by province"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q2-2026&province=QC",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify province filter is reflected in response
        assert data.get("province_filter") == "QC", f"Province filter should be QC: {data.get('province_filter')}"
        
        # All transactions should be from QC
        for txn in data.get("transactions", []):
            assert txn.get("buyer_province") == "QC", \
                f"Transaction {txn.get('transaction_id')} has province {txn.get('buyer_province')}, expected QC"
        
        print(f"PASSED: Province filter QC works. {data['transaction_count']} transactions")

    def test_tax_report_province_filter_on(self, admin_headers):
        """GET /api/admin/tax-report?period=Q2-2026&province=ON filters by Ontario"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q2-2026&province=ON",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("province_filter") == "ON"
        
        # All transactions should be from ON (may be empty)
        for txn in data.get("transactions", []):
            assert txn.get("buyer_province") == "ON"
        
        print(f"PASSED: Province filter ON works. {data['transaction_count']} transactions")


class TestTaxReportCSVFormat:
    """Test CSV export format"""

    def test_tax_report_csv_format(self, admin_headers):
        """GET /api/admin/tax-report?period=Q2-2026&format=csv returns CSV"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q2-2026&format=csv",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        
        print("PASSED: CSV format returns text/csv content type")

    def test_tax_report_csv_headers(self, admin_headers):
        """CSV has correct column headers"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q2-2026&format=csv",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        # Parse CSV
        csv_content = response.text
        reader = csv.reader(io.StringIO(csv_content))
        headers = next(reader)
        
        expected_headers = [
            "Transaction ID", "Date", "Province",
            "Subtotal", "Buyer Premium", "GST", "PST/QST", "HST", "Total",
            "Invoice URL"
        ]
        
        assert headers == expected_headers, f"CSV headers mismatch: {headers}"
        print(f"PASSED: CSV headers correct: {headers}")

    def test_tax_report_csv_totals_row(self, admin_headers):
        """CSV has TOTALS summary row at the bottom"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q2-2026&format=csv",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        # Parse CSV and find TOTALS row
        csv_content = response.text
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)
        
        # Find TOTALS row (should be last non-empty row)
        totals_row = None
        for row in reversed(rows):
            if row and row[0] == "TOTALS":
                totals_row = row
                break
        
        assert totals_row is not None, "CSV should have TOTALS row"
        assert totals_row[0] == "TOTALS", f"First column should be 'TOTALS': {totals_row[0]}"
        
        print(f"PASSED: CSV has TOTALS row: {totals_row}")

    def test_tax_report_csv_filename_contains_period(self, admin_headers):
        """CSV filename contains period and province suffix"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q2-2026&format=csv",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        content_disposition = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disposition, "Should be attachment download"
        assert "Q2-2026" in content_disposition, f"Filename should contain period: {content_disposition}"
        assert ".csv" in content_disposition, f"Filename should end with .csv: {content_disposition}"
        
        print(f"PASSED: CSV filename correct: {content_disposition}")

    def test_tax_report_csv_filename_with_province(self, admin_headers):
        """CSV filename contains province suffix when filtered"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q2-2026&province=QC&format=csv",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        content_disposition = response.headers.get("Content-Disposition", "")
        assert "_QC" in content_disposition, f"Filename should contain province suffix: {content_disposition}"
        
        print(f"PASSED: CSV filename with province: {content_disposition}")


class TestTaxReportFullYear:
    """Test full year period"""

    def test_tax_report_full_year_2026(self, admin_headers):
        """GET /api/admin/tax-report?period=2026 returns full year range"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=2026",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify full year date range (Jan 1 2026 to Jan 1 2027)
        assert "2026-01-01" in data["date_range"]["start"], \
            f"Full year should start Jan 1: {data['date_range']['start']}"
        assert "2027-01-01" in data["date_range"]["end"], \
            f"Full year should end Jan 1 next year: {data['date_range']['end']}"
        
        print(f"PASSED: Full year 2026 date range correct. Transactions: {data['transaction_count']}")


class TestTaxReportQuarters:
    """Test all quarter periods"""

    def test_tax_report_q1_2026(self, admin_headers):
        """Q1-2026 returns Jan 1 to Apr 1 range"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q1-2026",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "2026-01-01" in data["date_range"]["start"]
        assert "2026-04-01" in data["date_range"]["end"]
        print(f"PASSED: Q1-2026 date range correct")

    def test_tax_report_q3_2026(self, admin_headers):
        """Q3-2026 returns Jul 1 to Oct 1 range"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q3-2026",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "2026-07-01" in data["date_range"]["start"]
        assert "2026-10-01" in data["date_range"]["end"]
        print(f"PASSED: Q3-2026 date range correct")

    def test_tax_report_q4_2026(self, admin_headers):
        """Q4-2026 returns Oct 1 to Jan 1 next year range"""
        response = requests.get(
            f"{BASE_URL}/api/admin/tax-report?period=Q4-2026",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "2026-10-01" in data["date_range"]["start"]
        assert "2027-01-01" in data["date_range"]["end"]
        print(f"PASSED: Q4-2026 date range correct")


class TestPreviousEndpointsRegression:
    """Verify previous endpoints still work"""

    def test_invoice_generate_endpoint_exists(self, admin_headers):
        """POST /api/invoices/generate/{id} endpoint still works"""
        # Use a known transaction ID
        response = requests.post(
            f"{BASE_URL}/api/invoices/generate/{TEST_TRANSACTION_QC_2}",
            headers=admin_headers
        )
        # Should return 200 or 404 (if transaction not found), not 500 or 405
        assert response.status_code in [200, 201, 404], \
            f"Invoice generate endpoint error: {response.status_code} - {response.text}"
        print(f"PASSED: Invoice generate endpoint works (status: {response.status_code})")

    def test_partner_stats_endpoint_exists(self, admin_headers):
        """GET /api/partner/stats endpoint still works"""
        response = requests.get(
            f"{BASE_URL}/api/partner/stats",
            headers=admin_headers
        )
        # Should return 200 or 403 (if not partner), not 500 or 404
        assert response.status_code in [200, 403], \
            f"Partner stats endpoint error: {response.status_code} - {response.text}"
        print(f"PASSED: Partner stats endpoint works (status: {response.status_code})")

    def test_cookie_policy_endpoint_exists(self):
        """GET /api/legal/cookie-policy endpoint still works (no auth required)"""
        response = requests.get(f"{BASE_URL}/api/legal/cookie-policy")
        assert response.status_code == 200, \
            f"Cookie policy endpoint error: {response.status_code} - {response.text}"
        
        data = response.json()
        # Categories are nested inside consent object
        assert "consent" in data, "Cookie policy should have consent object"
        assert "categories" in data.get("consent", {}), "Cookie policy consent should have categories"
        print("PASSED: Cookie policy endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
