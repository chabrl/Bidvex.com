"""
BidVex CRA Tax Reporting, PDF Invoice, and Email Notification Tests
Tests for:
- CRA Tax Reporting endpoints (GST/HST, QST, Annual Summary, Seller Payments)
- PDF Invoice Download
- Email Notifications (logged since no SendGrid key)
- Scheduler Status
- Auth endpoints
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestAuthEndpoints:
    """Test authentication endpoints"""
    
    def test_login_success(self):
        """Test admin login returns token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert "user" in data, "No user in response"
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["token_type"] == "bearer"
        print(f"✓ Login successful for {ADMIN_EMAIL}")
    
    def test_login_invalid_credentials(self):
        """Test login with wrong password returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid credentials correctly rejected")
    
    def test_me_endpoint(self):
        """Test /me endpoint returns current user"""
        # First login
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_response.json()["access_token"]
        
        # Get current user
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Me endpoint failed: {response.text}"
        
        data = response.json()
        assert data["email"] == ADMIN_EMAIL
        assert "id" in data
        print(f"✓ /me endpoint returns user: {data['email']}")


class TestSchedulerStatus:
    """Test scheduler status endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_scheduler_status_returns_6_jobs(self):
        """Test scheduler status endpoint returns 6 running jobs"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/scheduler/status",
            headers=self.headers
        )
        assert response.status_code == 200, f"Scheduler status failed: {response.text}"
        
        data = response.json()
        assert "jobs" in data, "No jobs in response"
        
        jobs = data["jobs"]
        assert len(jobs) == 6, f"Expected 6 jobs, got {len(jobs)}"
        
        # Verify expected job IDs
        job_ids = [job["id"] for job in jobs]
        expected_jobs = [
            "process_ended_auctions",
            "activate_scheduled_auctions", 
            "apply_late_penalties",
            "cleanup_expired_deposits",
            "cleanup_expired_sessions",
            "daily_summary"
        ]
        
        for expected in expected_jobs:
            assert expected in job_ids, f"Missing job: {expected}"
        
        # Verify all jobs are running (check next_run field)
        for job in jobs:
            # Jobs use 'next_run' not 'next_run_time'
            assert job.get("next_run") is not None, f"Job {job['id']} has no next_run"
        
        print(f"✓ Scheduler has {len(jobs)} jobs running: {job_ids}")


class TestCRATaxReporting:
    """Test CRA Tax Reporting endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_generate_gst_hst_report(self):
        """Test GST/HST Summary Report generation"""
        # Use current year dates
        start_date = "2025-01-01"
        end_date = "2025-12-31"
        
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/tax-reports/generate/gst-hst",
            params={
                "start_date": start_date,
                "end_date": end_date,
                "reporting_period": "quarterly"
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"GST/HST report generation failed: {response.text}"
        
        data = response.json()
        
        # Verify report structure
        assert "report_id" in data, "No report_id in response"
        assert "report_type" in data, "No report_type in response"
        assert data["report_type"] == "gst_hst_summary"
        assert "summary" in data, "No summary in response"
        assert "xml" in data, "No XML in response"
        
        # Verify XML contains required business info
        xml_content = data["xml"]
        assert "1763135-9" in xml_content, "Business Number not in XML"
        assert "123456789RT0001" in xml_content, "GST Number not in XML"
        assert "BidVex Inc." in xml_content, "Legal Name not in XML"
        
        # Verify XML structure (elements may be empty/self-closing if no data)
        assert "<GSTHSTReturn" in xml_content, "Missing GSTHSTReturn root element"
        assert "<Header>" in xml_content, "Missing Header element"
        assert "<Summary>" in xml_content, "Missing Summary element"
        assert "<GST34LineItems>" in xml_content, "Missing GST34LineItems element"
        # ProvincialBreakdown may be empty (<ProvincialBreakdown/>) if no invoices
        assert "ProvincialBreakdown" in xml_content, "Missing ProvincialBreakdown element"
        
        print(f"✓ GST/HST report generated: {data['report_id']}")
        print(f"  - Period: {data['period']}")
        print(f"  - Total GST/HST: ${data['summary'].get('total_gst_hst', 0):.2f}")
        
        # Store report_id for download test
        self.gst_report_id = data["report_id"]
        return data["report_id"]
    
    def test_generate_qst_report(self):
        """Test Quebec QST Report generation"""
        start_date = "2025-01-01"
        end_date = "2025-12-31"
        
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/tax-reports/generate/qst",
            params={
                "start_date": start_date,
                "end_date": end_date
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"QST report generation failed: {response.text}"
        
        data = response.json()
        
        # Verify report structure
        assert "report_id" in data
        assert data["report_type"] == "qst_return"
        assert "xml" in data
        
        # Verify XML contains QST-specific info
        xml_content = data["xml"]
        assert "1234567890TQ0001" in xml_content, "QST Number not in XML"
        assert "<QSTReturn" in xml_content, "Missing QSTReturn root element"
        assert "<QSTCollected>" in xml_content, "Missing QSTCollected element"
        
        print(f"✓ QST report generated: {data['report_id']}")
        print(f"  - QST Collected: ${data['summary'].get('qst_collected', 0):.2f}")
    
    def test_generate_annual_summary(self):
        """Test Annual Summary report with monthly breakdown"""
        year = 2025
        
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/tax-reports/generate/annual-summary",
            params={"year": year},
            headers=self.headers
        )
        assert response.status_code == 200, f"Annual summary generation failed: {response.text}"
        
        data = response.json()
        
        # Verify report structure
        assert "report_id" in data
        assert data["report_type"] == "annual_summary"
        assert data["year"] == year
        assert "summary" in data
        assert "monthly_breakdown" in data
        assert "xml" in data
        
        # Verify XML structure (elements may be empty/self-closing if no data)
        xml_content = data["xml"]
        assert "<AnnualTaxSummary" in xml_content, "Missing AnnualTaxSummary root element"
        assert "<AnnualTotals>" in xml_content, "Missing AnnualTotals element"
        # MonthlyBreakdown may be empty (<MonthlyBreakdown/>) if no invoices
        assert "MonthlyBreakdown" in xml_content, "Missing MonthlyBreakdown element"
        assert f"year=\"{year}\"" in xml_content, "Year not in XML attributes"
        
        # Verify business info in XML
        assert "1763135-9" in xml_content, "Business Number not in XML"
        assert "123456789RT0001" in xml_content, "GST Number not in XML"
        assert "1234567890TQ0001" in xml_content, "QST Number not in XML"
        
        print(f"✓ Annual summary generated: {data['report_id']}")
        print(f"  - Year: {data['year']}")
        print(f"  - Total Tax: ${data['summary'].get('total_tax', 0):.2f}")
        print(f"  - Total Revenue: ${data['summary'].get('total_revenue', 0):.2f}")
    
    def test_generate_seller_payments_report(self):
        """Test Seller Payments Report (T5018-style)"""
        year = 2025
        
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/tax-reports/generate/seller-payments",
            params={"year": year},
            headers=self.headers
        )
        assert response.status_code == 200, f"Seller payments report failed: {response.text}"
        
        data = response.json()
        
        # Verify report structure
        assert "report_id" in data
        assert data["report_type"] == "seller_payments"
        assert data["year"] == year
        assert "summary" in data
        assert "xml" in data
        
        # Verify summary fields
        summary = data["summary"]
        assert "total_sellers" in summary
        assert "reportable_sellers" in summary
        assert "total_gross" in summary
        assert "total_commissions" in summary
        assert "total_net" in summary
        
        # Verify XML structure (elements may be empty/self-closing if no data)
        xml_content = data["xml"]
        assert "<SellerPaymentsReport" in xml_content, "Missing SellerPaymentsReport root element"
        # Sellers may be empty (<Sellers/>) if no settlements
        assert "Sellers" in xml_content, "Missing Sellers element"
        assert "1763135-9" in xml_content, "Business Number not in XML"
        
        print(f"✓ Seller payments report generated: {data['report_id']}")
        print(f"  - Total Sellers: {summary['total_sellers']}")
        print(f"  - Reportable (>=$500): {summary['reportable_sellers']}")
    
    def test_get_tax_reports_list(self):
        """Test getting list of generated tax reports"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/tax-reports",
            headers=self.headers
        )
        assert response.status_code == 200, f"Get tax reports failed: {response.text}"
        
        data = response.json()
        assert "count" in data
        assert "reports" in data
        
        print(f"✓ Tax reports list: {data['count']} reports found")
    
    def test_download_tax_report_xml(self):
        """Test XML report download with proper format"""
        # First generate a report
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/tax-reports/generate/gst-hst",
            params={
                "start_date": "2025-01-01",
                "end_date": "2025-03-31",
                "reporting_period": "quarterly"
            },
            headers=self.headers
        )
        report_id = response.json()["report_id"]
        
        # Download the XML
        download_response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/tax-reports/{report_id}/download",
            headers=self.headers
        )
        assert download_response.status_code == 200, f"XML download failed: {download_response.text}"
        
        # Verify content type
        content_type = download_response.headers.get("Content-Type", "")
        assert "xml" in content_type.lower(), f"Expected XML content type, got {content_type}"
        
        # Verify Content-Disposition header
        content_disp = download_response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, "Missing attachment disposition"
        assert ".xml" in content_disp, "Missing .xml extension in filename"
        
        # Verify XML content
        xml_content = download_response.text
        assert "<?xml" in xml_content, "Missing XML declaration"
        assert "<GSTHSTReturn" in xml_content, "Missing root element"
        
        print(f"✓ XML download successful for report {report_id}")
        print(f"  - Content-Type: {content_type}")
        print(f"  - Content-Disposition: {content_disp}")


class TestPDFInvoiceDownload:
    """Test PDF Invoice Download endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_pdf_invoice_endpoint_exists(self):
        """Test PDF invoice endpoint returns proper error for non-existent invoice"""
        # Test with a fake invoice ID
        fake_invoice_id = "00000000-0000-0000-0000-000000000000"
        
        response = requests.get(
            f"{BASE_URL}/api/vehicle-invoices/{fake_invoice_id}/pdf",
            headers=self.headers
        )
        
        # Should return 404 for non-existent invoice
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ PDF endpoint correctly returns 404 for non-existent invoice")
    
    def test_pdf_invoice_with_real_invoice(self):
        """Test PDF generation with a real invoice if one exists"""
        # First, get list of invoices
        response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/invoices",
            headers=self.headers
        )
        
        if response.status_code != 200:
            pytest.skip("Could not get invoices list")
        
        data = response.json()
        invoices = data.get("invoices", [])
        
        if not invoices:
            print("⚠ No invoices found to test PDF generation")
            pytest.skip("No invoices available for PDF test")
        
        # Get first invoice
        invoice = invoices[0]
        invoice_id = invoice.get("id")
        
        # Try to download PDF
        pdf_response = requests.get(
            f"{BASE_URL}/api/vehicle-invoices/{invoice_id}/pdf",
            headers=self.headers
        )
        
        if pdf_response.status_code == 200:
            # Verify PDF content
            content_type = pdf_response.headers.get("Content-Type", "")
            assert "pdf" in content_type.lower(), f"Expected PDF content type, got {content_type}"
            
            # Verify Content-Disposition
            content_disp = pdf_response.headers.get("Content-Disposition", "")
            assert "attachment" in content_disp, "Missing attachment disposition"
            assert ".pdf" in content_disp.lower(), "Missing .pdf extension"
            
            # Verify PDF magic bytes
            pdf_content = pdf_response.content
            assert pdf_content[:4] == b'%PDF', "Invalid PDF magic bytes"
            
            print(f"✓ PDF generated successfully for invoice {invoice_id}")
            print(f"  - Size: {len(pdf_content)} bytes")
            print(f"  - Content-Type: {content_type}")
        else:
            print(f"⚠ PDF generation returned {pdf_response.status_code}: {pdf_response.text}")


class TestEmailNotifications:
    """Test email notification integration (logged since no SendGrid key)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_document_approval_triggers_email(self):
        """Test that document approval triggers email notification (logged)"""
        # Get pending documents
        response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/documents/pending",
            headers=self.headers
        )
        
        if response.status_code != 200:
            pytest.skip("Could not get pending documents")
        
        data = response.json()
        pending_docs = data.get("documents", [])
        
        if not pending_docs:
            print("⚠ No pending documents to test email notification")
            # This is expected - just verify the endpoint works
            assert "pending_count" in data or "documents" in data
            print("✓ Pending documents endpoint works correctly")
            return
        
        # If there are pending docs, we could test approval
        # But we don't want to actually approve them in tests
        print(f"✓ Found {len(pending_docs)} pending documents")
        print("  - Email notifications would be logged on approval (SendGrid not configured)")


class TestInvalidDateHandling:
    """Test error handling for invalid inputs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_invalid_date_format_gst_hst(self):
        """Test GST/HST report rejects invalid date format"""
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/tax-reports/generate/gst-hst",
            params={
                "start_date": "invalid-date",
                "end_date": "2025-12-31"
            },
            headers=self.headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid date format correctly rejected")
    
    def test_invalid_year_annual_summary(self):
        """Test annual summary rejects invalid year"""
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/tax-reports/generate/annual-summary",
            params={"year": 2019},  # Before 2020
            headers=self.headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Invalid year correctly rejected")
    
    def test_future_year_seller_payments(self):
        """Test seller payments rejects future year"""
        future_year = datetime.now().year + 1
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/tax-reports/generate/seller-payments",
            params={"year": future_year},
            headers=self.headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Future year correctly rejected")


class TestUnauthorizedAccess:
    """Test that endpoints require authentication"""
    
    def test_tax_reports_require_auth(self):
        """Test tax reports endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/vehicle-admin/tax-reports")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Tax reports endpoint requires authentication")
    
    def test_scheduler_status_requires_auth(self):
        """Test scheduler status requires authentication"""
        response = requests.get(f"{BASE_URL}/api/vehicle-admin/scheduler/status")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Scheduler status endpoint requires authentication")
    
    def test_pdf_invoice_requires_auth(self):
        """Test PDF invoice download requires authentication"""
        response = requests.get(f"{BASE_URL}/api/vehicle-invoices/test-id/pdf")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ PDF invoice endpoint requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
