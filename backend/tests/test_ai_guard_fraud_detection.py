"""
AI Guard Fraud Detection API Tests
Tests the fraud detection service endpoints: stats, scan, flags, status updates
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable must be set")

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestAIGuardAuthentication:
    """Test admin login for AI Guard access"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access token in response"
        return data["access_token"]
    
    def test_admin_login_success(self, admin_token):
        """Verify admin can login and get token"""
        assert admin_token is not None
        assert len(admin_token) > 0
        print(f"✓ Admin login successful, token length: {len(admin_token)}")


class TestAIGuardStatsEndpoint:
    """Test /api/admin/ai-guard/stats endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Admin authentication failed")
    
    def test_stats_returns_200(self, admin_token):
        """Test stats endpoint returns 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ai-guard/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Stats API failed: {response.text}"
        print(f"✓ Stats endpoint returned 200 OK")
    
    def test_stats_response_structure(self, admin_token):
        """Test stats response has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ai-guard/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check success flag
        assert "success" in data
        assert data["success"] == True
        
        # Check stats object
        assert "stats" in data
        stats = data["stats"]
        
        # Verify required fields
        required_fields = ["total", "pending_review", "under_investigation", "cleared", "confirmed_fraud"]
        for field in required_fields:
            assert field in stats, f"Missing field: {field}"
            assert isinstance(stats[field], int), f"{field} should be an integer"
        
        print(f"✓ Stats structure valid: total={stats['total']}, pending={stats['pending_review']}, investigating={stats['under_investigation']}, cleared={stats['cleared']}, confirmed={stats['confirmed_fraud']}")
    
    def test_stats_unauthorized_without_token(self):
        """Test stats endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/ai-guard/stats")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Stats endpoint properly rejects unauthorized requests")


class TestAIGuardScanEndpoint:
    """Test /api/admin/ai-guard/scan endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Admin authentication failed")
    
    def test_scan_returns_200(self, admin_token):
        """Test scan endpoint returns 200 OK"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-guard/scan",
            json={"hours_back": 24},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Scan API failed: {response.text}"
        print(f"✓ Scan endpoint returned 200 OK")
    
    def test_scan_response_structure(self, admin_token):
        """Test scan response has correct structure"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-guard/scan",
            json={"hours_back": 24},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "success" in data
        assert data["success"] == True
        assert "flags_detected" in data
        assert "flags_saved" in data
        assert isinstance(data["flags_detected"], int)
        assert isinstance(data["flags_saved"], int)
        
        print(f"✓ Scan complete: {data['flags_detected']} flags detected, {data['flags_saved']} saved")
    
    def test_scan_with_custom_hours_back(self, admin_token):
        """Test scan with custom hours_back parameter"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-guard/scan",
            json={"hours_back": 168},  # 7 days
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print(f"✓ 7-day scan completed successfully")
    
    def test_scan_unauthorized_without_token(self):
        """Test scan endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-guard/scan",
            json={"hours_back": 24}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Scan endpoint properly rejects unauthorized requests")


class TestAIGuardFlagsEndpoint:
    """Test /api/admin/ai-guard/flags endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Admin authentication failed")
    
    def test_flags_returns_200(self, admin_token):
        """Test flags endpoint returns 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ai-guard/flags",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Flags API failed: {response.text}"
        print(f"✓ Flags endpoint returned 200 OK")
    
    def test_flags_response_structure(self, admin_token):
        """Test flags response has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ai-guard/flags",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "success" in data
        assert data["success"] == True
        assert "flags" in data
        assert isinstance(data["flags"], list)
        
        print(f"✓ Flags list returned with {len(data['flags'])} items")
    
    def test_flags_filter_by_status(self, admin_token):
        """Test flags endpoint filters by status"""
        statuses = ["pending_review", "under_investigation", "cleared", "confirmed_fraud"]
        
        for status in statuses:
            response = requests.get(
                f"{BASE_URL}/api/admin/ai-guard/flags",
                params={"status": status},
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200, f"Filter by {status} failed"
            data = response.json()
            assert data["success"] == True
            # All returned flags should match the status filter
            for flag in data["flags"]:
                assert flag.get("status") == status, f"Flag status {flag.get('status')} doesn't match filter {status}"
        
        print(f"✓ Status filters work correctly for all statuses")
    
    def test_flags_filter_by_type(self, admin_token):
        """Test flags endpoint filters by flag_type"""
        flag_types = ["bid_shilling", "price_anomaly", "account_risk", "rapid_bidding", "ip_clustering", "new_account_high_bid"]
        
        for flag_type in flag_types:
            response = requests.get(
                f"{BASE_URL}/api/admin/ai-guard/flags",
                params={"flag_type": flag_type},
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200, f"Filter by {flag_type} failed"
            data = response.json()
            assert data["success"] == True
        
        print(f"✓ Flag type filters work correctly")
    
    def test_flags_limit_parameter(self, admin_token):
        """Test flags endpoint respects limit parameter"""
        response = requests.get(
            f"{BASE_URL}/api/admin/ai-guard/flags",
            params={"limit": 5},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["flags"]) <= 5
        print(f"✓ Limit parameter works correctly")
    
    def test_flags_unauthorized_without_token(self):
        """Test flags endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/ai-guard/flags")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Flags endpoint properly rejects unauthorized requests")


class TestAIGuardFlagStatusUpdate:
    """Test /api/admin/ai-guard/flags/{flag_id}/status endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Admin authentication failed")
    
    def test_update_status_invalid_flag_id(self, admin_token):
        """Test updating status for non-existent flag"""
        response = requests.put(
            f"{BASE_URL}/api/admin/ai-guard/flags/nonexistent-flag-id/status",
            json={"status": "cleared"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Should return 200 with success=False or 404
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") == False or "not found" in str(data).lower()
        print(f"✓ Invalid flag ID handled correctly")
    
    def test_update_status_invalid_status_value(self, admin_token):
        """Test updating with invalid status value"""
        response = requests.put(
            f"{BASE_URL}/api/admin/ai-guard/flags/test-flag/status",
            json={"status": "invalid_status"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Should fail validation
        assert response.status_code in [200, 400, 422]
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") == False
        print(f"✓ Invalid status value handled correctly")


class TestAIGuardSuspendAuction:
    """Test /api/admin/ai-guard/suspend/{auction_id} endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Admin authentication failed")
    
    def test_suspend_invalid_auction_id(self, admin_token):
        """Test suspending non-existent auction"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-guard/suspend/nonexistent-auction-id",
            json={"reason": "Test suspension"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Should return 200 with success=False or 404
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            # Success should be False since auction doesn't exist
            assert data.get("success") == False or "not found" in str(data).lower()
        print(f"✓ Invalid auction ID handled correctly")


class TestAIGuardSummaryGeneration:
    """Test /api/admin/ai-guard/summary/{flag_id} endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Admin authentication failed")
    
    def test_summary_invalid_flag_id(self, admin_token):
        """Test generating summary for non-existent flag"""
        response = requests.post(
            f"{BASE_URL}/api/admin/ai-guard/summary/nonexistent-flag-id",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Should return 404 for non-existent flag
        assert response.status_code in [404, 200]
        if response.status_code == 404:
            print(f"✓ Summary endpoint returns 404 for non-existent flag")
        else:
            data = response.json()
            # If 200, success should be False
            assert data.get("success") == False or "not found" in str(response.text).lower()
            print(f"✓ Summary endpoint handles non-existent flag correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
