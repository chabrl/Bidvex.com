"""
BidVex Vehicle Auction - New Features Test Suite
Tests for: Scheduler, Stripe Payments, Document Upload, Admin Document Review

Test Coverage:
1. Scheduler Status API
2. Manual Job Execution API
3. Document Upload API
4. Get Required Documents API
5. Get My Documents API
6. Admin Pending Documents API
7. Stripe Invoice Checkout API
8. Stripe Deposit Checkout API
9. Payment Status Check API
"""

import pytest
import requests
import os
import io
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestSchedulerAPIs:
    """Test scheduler status and manual job execution"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token for scheduler tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        self.admin_token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.admin_token}"}
    
    def test_scheduler_status_endpoint(self):
        """Test GET /api/vehicle-admin/scheduler/status"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/scheduler/status",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Scheduler status failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "status" in data, "Missing 'status' field"
        assert data["status"] in ["running", "stopped", "not_initialized"], f"Unexpected status: {data['status']}"
        
        # If running, verify jobs list
        if data["status"] == "running":
            assert "jobs" in data, "Missing 'jobs' field when scheduler is running"
            jobs = data["jobs"]
            assert isinstance(jobs, list), "Jobs should be a list"
            
            # Verify expected jobs exist
            job_ids = [job["id"] for job in jobs]
            expected_jobs = [
                "process_ended_auctions",
                "activate_scheduled_auctions",
                "apply_late_penalties",
                "cleanup_expired_deposits",
                "cleanup_expired_sessions",
                "daily_summary"
            ]
            
            for expected_job in expected_jobs:
                assert expected_job in job_ids, f"Missing expected job: {expected_job}"
            
            # Verify job structure
            for job in jobs:
                assert "id" in job, "Job missing 'id'"
                assert "name" in job, "Job missing 'name'"
                assert "trigger" in job, "Job missing 'trigger'"
        
        print(f"✓ Scheduler status: {data['status']}")
        if "jobs" in data:
            print(f"✓ Found {len(data['jobs'])} scheduled jobs")
    
    def test_manual_job_execution_daily_summary(self):
        """Test POST /api/vehicle-admin/scheduler/run/{job_id} - daily_summary"""
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/scheduler/run/daily_summary",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Manual job execution failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "job_id" in data, "Missing 'job_id' in response"
        assert data["job_id"] == "daily_summary", f"Wrong job_id: {data['job_id']}"
        assert "executed_at" in data, "Missing 'executed_at'"
        assert "result" in data, "Missing 'result'"
        
        print(f"✓ Manual job execution successful: {data['job_id']}")
        print(f"✓ Executed at: {data['executed_at']}")
    
    def test_manual_job_execution_cleanup_deposits(self):
        """Test POST /api/vehicle-admin/scheduler/run/{job_id} - cleanup_expired_deposits"""
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/scheduler/run/cleanup_expired_deposits",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Manual job execution failed: {response.text}"
        data = response.json()
        
        assert "job_id" in data
        assert data["job_id"] == "cleanup_expired_deposits"
        
        print(f"✓ Cleanup deposits job executed successfully")
    
    def test_manual_job_execution_invalid_job(self):
        """Test POST /api/vehicle-admin/scheduler/run/{job_id} - invalid job"""
        response = requests.post(
            f"{BASE_URL}/api/vehicle-admin/scheduler/run/invalid_job_id",
            headers=self.headers
        )
        
        # Should return error for invalid job
        data = response.json()
        assert "error" in data or response.status_code != 200, "Should fail for invalid job"
        
        print(f"✓ Invalid job correctly rejected")
    
    def test_scheduler_requires_admin(self):
        """Test that scheduler endpoints require admin role"""
        # Try without auth
        response = requests.get(f"{BASE_URL}/api/vehicle-admin/scheduler/status")
        assert response.status_code == 401, "Should require authentication"
        
        print(f"✓ Scheduler endpoints correctly require admin auth")


class TestDocumentUploadAPIs:
    """Test document upload and retrieval APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get seller token for document tests"""
        # Login as admin (who is also a seller)
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_required_documents(self):
        """Test GET /api/vehicle-documents/required"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-documents/required",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Get required docs failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "required_documents" in data, "Missing 'required_documents'"
        required_docs = data["required_documents"]
        assert isinstance(required_docs, list), "required_documents should be a list"
        
        # Verify document structure
        for doc in required_docs:
            assert "type" in doc, "Document missing 'type'"
            assert "name" in doc, "Document missing 'name'"
            assert "required" in doc, "Document missing 'required'"
            assert "description" in doc, "Document missing 'description'"
        
        print(f"✓ Found {len(required_docs)} required document types")
        for doc in required_docs:
            print(f"  - {doc['type']}: {doc['name']}")
    
    def test_get_my_documents(self):
        """Test GET /api/vehicle-documents/my"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-documents/my",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Get my docs failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "documents" in data, "Missing 'documents'"
        assert "verification_status" in data, "Missing 'verification_status'"
        
        documents = data["documents"]
        assert isinstance(documents, list), "documents should be a list"
        
        verification = data["verification_status"]
        assert "seller_id" in verification or "status" in verification, "Invalid verification_status"
        
        print(f"✓ Found {len(documents)} uploaded documents")
        print(f"✓ Verification status retrieved")
    
    def test_document_upload_endpoint(self):
        """Test POST /api/vehicle-documents/upload"""
        # Create a test PDF file
        test_content = b"%PDF-1.4 test document content"
        files = {
            'file': ('test_document.pdf', io.BytesIO(test_content), 'application/pdf')
        }
        data = {
            'document_type': 'identity_front',
            'description': 'Test document upload'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/vehicle-documents/upload",
            headers=self.headers,
            files=files,
            data=data
        )
        
        # Should succeed or fail with validation error (not 500)
        assert response.status_code in [200, 201, 400, 403], f"Unexpected status: {response.status_code}, {response.text}"
        
        if response.status_code in [200, 201]:
            result = response.json()
            assert "document" in result or "message" in result, "Missing response data"
            print(f"✓ Document upload successful")
        else:
            print(f"✓ Document upload endpoint working (validation: {response.json().get('detail', 'N/A')})")
    
    def test_document_upload_invalid_type(self):
        """Test document upload with invalid document type"""
        test_content = b"%PDF-1.4 test document content"
        files = {
            'file': ('test.pdf', io.BytesIO(test_content), 'application/pdf')
        }
        data = {
            'document_type': 'invalid_type_xyz',
            'description': 'Test'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/vehicle-documents/upload",
            headers=self.headers,
            files=files,
            data=data
        )
        
        # Should return 400 for invalid document type
        assert response.status_code == 400, f"Should reject invalid document type: {response.status_code}"
        
        print(f"✓ Invalid document type correctly rejected")


class TestAdminDocumentAPIs:
    """Test admin document review APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.admin_token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.admin_token}"}
    
    def test_get_pending_documents(self):
        """Test GET /api/vehicle-admin/documents/pending"""
        response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/documents/pending",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Get pending docs failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "documents" in data, "Missing 'documents'"
        documents = data["documents"]
        assert isinstance(documents, list), "documents should be a list"
        
        # Verify document structure if any exist
        for doc in documents:
            assert "id" in doc, "Document missing 'id'"
            assert "document_type" in doc, "Document missing 'document_type'"
            assert "status" in doc, "Document missing 'status'"
            assert doc["status"] == "pending", f"Non-pending document in list: {doc['status']}"
        
        print(f"✓ Found {len(documents)} pending documents for review")
    
    def test_pending_documents_requires_admin(self):
        """Test that pending documents endpoint requires admin role"""
        response = requests.get(f"{BASE_URL}/api/vehicle-admin/documents/pending")
        assert response.status_code == 401, "Should require authentication"
        
        print(f"✓ Admin documents endpoint correctly requires admin auth")


class TestStripePaymentAPIs:
    """Test Stripe payment integration APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get user token for payment tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_invoice_checkout_endpoint_exists(self):
        """Test POST /api/vehicle-payments/invoice/{invoice_id}/checkout endpoint exists"""
        # Use a fake invoice ID - should return 400 (not found) not 404 (route not found)
        response = requests.post(
            f"{BASE_URL}/api/vehicle-payments/invoice/fake-invoice-id/checkout",
            headers=self.headers
        )
        
        # Should return 400 (invoice not found) or 404, not 500 or route error
        assert response.status_code in [400, 404], f"Unexpected status: {response.status_code}, {response.text}"
        
        data = response.json()
        assert "detail" in data, "Should return error detail"
        
        print(f"✓ Invoice checkout endpoint exists and validates input")
    
    def test_deposit_checkout_endpoint_exists(self):
        """Test POST /api/vehicle-payments/deposit/{vehicle_id}/checkout endpoint exists"""
        # Use a fake vehicle ID
        response = requests.post(
            f"{BASE_URL}/api/vehicle-payments/deposit/fake-vehicle-id/checkout",
            headers=self.headers
        )
        
        # Should return 400 or 404 (vehicle not found), not 500
        assert response.status_code in [400, 404], f"Unexpected status: {response.status_code}, {response.text}"
        
        data = response.json()
        assert "detail" in data, "Should return error detail"
        
        print(f"✓ Deposit checkout endpoint exists and validates input")
    
    def test_payment_status_endpoint_exists(self):
        """Test GET /api/vehicle-payments/status/{session_id} endpoint exists"""
        # Use a fake session ID
        response = requests.get(
            f"{BASE_URL}/api/vehicle-payments/status/fake-session-id",
            headers=self.headers
        )
        
        # Should return 404 (transaction not found), not 500
        assert response.status_code in [400, 404], f"Unexpected status: {response.status_code}, {response.text}"
        
        data = response.json()
        assert "detail" in data, "Should return error detail"
        
        print(f"✓ Payment status endpoint exists and validates input")
    
    def test_payment_endpoints_require_auth(self):
        """Test that payment endpoints require authentication"""
        # Invoice checkout without auth
        response = requests.post(f"{BASE_URL}/api/vehicle-payments/invoice/test/checkout")
        assert response.status_code == 401, "Invoice checkout should require auth"
        
        # Deposit checkout without auth
        response = requests.post(f"{BASE_URL}/api/vehicle-payments/deposit/test/checkout")
        assert response.status_code == 401, "Deposit checkout should require auth"
        
        print(f"✓ Payment endpoints correctly require authentication")


class TestIntegrationScenarios:
    """Integration tests for complete workflows"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for integration tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_scheduler_and_job_execution_flow(self):
        """Test complete scheduler workflow"""
        # 1. Check scheduler status
        status_response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/scheduler/status",
            headers=self.headers
        )
        assert status_response.status_code == 200
        status = status_response.json()
        
        print(f"✓ Scheduler status: {status.get('status')}")
        
        # 2. Run a manual job
        if status.get("status") == "running":
            job_response = requests.post(
                f"{BASE_URL}/api/vehicle-admin/scheduler/run/daily_summary",
                headers=self.headers
            )
            assert job_response.status_code == 200
            job_result = job_response.json()
            
            print(f"✓ Manual job executed: {job_result.get('job_id')}")
            print(f"✓ Result: {job_result.get('result')}")
    
    def test_document_verification_flow(self):
        """Test document upload and verification workflow"""
        # 1. Get required documents
        required_response = requests.get(
            f"{BASE_URL}/api/vehicle-documents/required",
            headers=self.headers
        )
        assert required_response.status_code == 200
        required = required_response.json()
        
        print(f"✓ Required documents: {len(required.get('required_documents', []))}")
        
        # 2. Get my documents
        my_docs_response = requests.get(
            f"{BASE_URL}/api/vehicle-documents/my",
            headers=self.headers
        )
        assert my_docs_response.status_code == 200
        my_docs = my_docs_response.json()
        
        print(f"✓ My documents: {len(my_docs.get('documents', []))}")
        print(f"✓ Verification status: {my_docs.get('verification_status', {})}")
        
        # 3. Check admin pending documents
        pending_response = requests.get(
            f"{BASE_URL}/api/vehicle-admin/documents/pending",
            headers=self.headers
        )
        assert pending_response.status_code == 200
        pending = pending_response.json()
        
        print(f"✓ Pending documents for admin review: {len(pending.get('documents', []))}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
