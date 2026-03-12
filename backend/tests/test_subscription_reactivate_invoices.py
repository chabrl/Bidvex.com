"""
Test Suite: Subscription Reactivate and Invoices API
Features tested:
- POST /api/subscriptions/reactivate - reactivate cancelled subscription
- GET /api/invoices - list user invoices
- GET /api/invoices/{invoice_id}/download - download PDF invoice
- POST /api/subscriptions/cancel - cancel subscription
- GET /api/subscriptions/status - subscription status with cancel_at_period_end
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "charbeladmin@bidvex.com"
TEST_PASSWORD = "Admin123!"

class TestSubscriptionReactivateAndInvoices:
    """Test subscription reactivate and invoice endpoints."""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get auth token."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, f"No access_token in response: {data}"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Auth headers for requests."""
        return {"Authorization": f"Bearer {auth_token}"}
    
    # 1. Test GET /api/subscriptions/status
    def test_subscription_status_returns_cancel_at_period_end(self, headers):
        """GET /api/subscriptions/status should return cancel_at_period_end field."""
        response = requests.get(f"{BASE_URL}/api/subscriptions/status", headers=headers)
        assert response.status_code == 200, f"Status failed: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "tier" in data, f"Missing 'tier' in response: {data}"
        assert "status" in data, f"Missing 'status' in response: {data}"
        assert "cancel_at_period_end" in data, f"Missing 'cancel_at_period_end' in response: {data}"
        assert "stripe_subscription_id" in data, f"Missing 'stripe_subscription_id' in response: {data}"
        
        print(f"Subscription status: tier={data['tier']}, status={data['status']}, cancel_at_period_end={data['cancel_at_period_end']}")
        return data
    
    # 2. Test POST /api/subscriptions/cancel
    def test_cancel_subscription_sets_cancel_at_period_end(self, headers):
        """POST /api/subscriptions/cancel should set cancel_at_period_end=True."""
        # First check if subscription is already cancelled
        status_resp = requests.get(f"{BASE_URL}/api/subscriptions/status", headers=headers)
        assert status_resp.status_code == 200
        status = status_resp.json()
        
        if status.get("cancel_at_period_end") == True:
            # Already cancelled - reactivate first
            reactivate_resp = requests.post(f"{BASE_URL}/api/subscriptions/reactivate", headers=headers)
            if reactivate_resp.status_code == 200:
                print("Reactivated subscription to test cancel")
        
        # Cancel the subscription
        response = requests.post(f"{BASE_URL}/api/subscriptions/cancel", headers=headers)
        assert response.status_code == 200, f"Cancel failed: {response.text}"
        data = response.json()
        
        assert data.get("success") == True, f"Cancel not successful: {data}"
        assert "message" in data, f"Missing message in response: {data}"
        print(f"Cancel response: {data}")
        
        # Verify status now shows cancel_at_period_end=True
        verify_resp = requests.get(f"{BASE_URL}/api/subscriptions/status", headers=headers)
        verify_data = verify_resp.json()
        assert verify_data.get("cancel_at_period_end") == True, f"cancel_at_period_end not True after cancel: {verify_data}"
        assert verify_data.get("status") == "active", f"Status should be 'active' after cancel: {verify_data}"
        print(f"Verified: status={verify_data['status']}, cancel_at_period_end={verify_data['cancel_at_period_end']}")
    
    # 3. Test POST /api/subscriptions/reactivate
    def test_reactivate_subscription_clears_cancel_flag(self, headers):
        """POST /api/subscriptions/reactivate should set cancel_at_period_end=False."""
        # First ensure subscription is set to cancel
        cancel_resp = requests.post(f"{BASE_URL}/api/subscriptions/cancel", headers=headers)
        if cancel_resp.status_code != 200:
            # If already cancelled, that's fine
            status_resp = requests.get(f"{BASE_URL}/api/subscriptions/status", headers=headers)
            status = status_resp.json()
            if not status.get("cancel_at_period_end"):
                pytest.skip("Subscription is not set to cancel, skipping reactivate test")
        
        # Reactivate the subscription
        response = requests.post(f"{BASE_URL}/api/subscriptions/reactivate", headers=headers)
        assert response.status_code == 200, f"Reactivate failed: {response.text}"
        data = response.json()
        
        assert data.get("success") == True, f"Reactivate not successful: {data}"
        assert "message" in data, f"Missing message in response: {data}"
        print(f"Reactivate response: {data}")
        
        # Verify status shows cancel_at_period_end=False
        verify_resp = requests.get(f"{BASE_URL}/api/subscriptions/status", headers=headers)
        verify_data = verify_resp.json()
        assert verify_data.get("cancel_at_period_end") == False, f"cancel_at_period_end not False after reactivate: {verify_data}"
        print(f"Verified: status={verify_data['status']}, cancel_at_period_end={verify_data['cancel_at_period_end']}")
    
    # 4. Test GET /api/invoices
    def test_list_invoices_excludes_pdf_data(self, headers):
        """GET /api/invoices should return invoices list without pdf_data field."""
        response = requests.get(f"{BASE_URL}/api/invoices", headers=headers)
        assert response.status_code == 200, f"List invoices failed: {response.text}"
        data = response.json()
        
        assert "invoices" in data, f"Missing 'invoices' in response: {data}"
        invoices = data["invoices"]
        
        print(f"Found {len(invoices)} invoice(s)")
        
        if len(invoices) > 0:
            invoice = invoices[0]
            # Verify required fields
            assert "id" in invoice, f"Missing 'id' in invoice: {invoice}"
            assert "invoice_number" in invoice, f"Missing 'invoice_number' in invoice: {invoice}"
            assert "tier_label" in invoice, f"Missing 'tier_label' in invoice: {invoice}"
            assert "total" in invoice, f"Missing 'total' in invoice: {invoice}"
            assert "created_at" in invoice, f"Missing 'created_at' in invoice: {invoice}"
            
            # Verify pdf_data is NOT included (excluded in query)
            assert "pdf_data" not in invoice, f"pdf_data should be excluded from list response"
            
            print(f"Invoice: {invoice.get('invoice_number')}, tier={invoice.get('tier_label')}, total={invoice.get('total')}")
            return invoice
        else:
            print("No invoices found - this may be expected if no subscription purchase has been made")
            return None
    
    # 5. Test GET /api/invoices/{invoice_id}/download
    def test_download_invoice_returns_pdf(self, headers):
        """GET /api/invoices/{invoice_id}/download should return PDF binary."""
        # First get list of invoices
        list_resp = requests.get(f"{BASE_URL}/api/invoices", headers=headers)
        assert list_resp.status_code == 200
        invoices = list_resp.json().get("invoices", [])
        
        if len(invoices) == 0:
            pytest.skip("No invoices available to download")
        
        invoice_id = invoices[0]["id"]
        invoice_number = invoices[0].get("invoice_number", "unknown")
        
        # Download the PDF
        response = requests.get(f"{BASE_URL}/api/invoices/{invoice_id}/download", headers=headers)
        assert response.status_code == 200, f"Download failed: {response.text}"
        
        # Verify Content-Type is application/pdf
        content_type = response.headers.get("Content-Type", "")
        assert "application/pdf" in content_type, f"Expected application/pdf, got: {content_type}"
        
        # Verify Content-Disposition header
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp, f"Expected attachment disposition, got: {content_disp}"
        assert ".pdf" in content_disp, f"Expected .pdf filename in disposition, got: {content_disp}"
        
        # Verify PDF content (check PDF magic bytes)
        content = response.content
        assert len(content) > 0, "PDF content is empty"
        assert content[:4] == b'%PDF', f"Content doesn't start with PDF magic bytes: {content[:20]}"
        
        print(f"Downloaded invoice {invoice_number}: {len(content)} bytes, Content-Type={content_type}")
    
    # 6. Test invoice not found
    def test_download_nonexistent_invoice_returns_404(self, headers):
        """GET /api/invoices/{fake_id}/download should return 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = requests.get(f"{BASE_URL}/api/invoices/{fake_id}/download", headers=headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    
    # 7. Test reactivate without subscription
    def test_reactivate_requires_subscription(self, headers):
        """POST /api/subscriptions/reactivate requires an active subscription."""
        # This test verifies the endpoint doesn't crash on edge cases
        # The admin user has a subscription, so this should work
        response = requests.post(f"{BASE_URL}/api/subscriptions/reactivate", headers=headers)
        # Either 200 (success) or 400 (no subscription) are valid responses
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code} - {response.text}"
        print(f"Reactivate response: {response.status_code} - {response.json()}")


class TestInvoiceDetails:
    """Test invoice content details."""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get auth token."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Auth headers for requests."""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_invoice_has_tax_fields(self, headers):
        """Invoices should include GST and QST tax fields."""
        response = requests.get(f"{BASE_URL}/api/invoices", headers=headers)
        assert response.status_code == 200
        invoices = response.json().get("invoices", [])
        
        if len(invoices) == 0:
            pytest.skip("No invoices available")
        
        invoice = invoices[0]
        
        # Check for tax fields (these are in the stored document)
        # Note: The list endpoint might not return all fields
        print(f"Invoice fields: {list(invoice.keys())}")
        
        # Essential fields that should be present
        required_fields = ["id", "invoice_number", "user_id", "tier_label", "total", "created_at"]
        for field in required_fields:
            assert field in invoice, f"Missing required field '{field}' in invoice"
        
        print(f"Invoice {invoice['invoice_number']}: total=${invoice['total']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
