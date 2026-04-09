"""
Social Media Links Feature Tests - Iteration 124
Tests for GET /api/site-config/social-links (public) and PUT /api/admin/site-config/social-links (admin)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Admin123!"
NON_ADMIN_EMAIL = "starter@test.com"
NON_ADMIN_PASSWORD = "TestUser2026!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def non_admin_token():
    """Get non-admin user JWT token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": NON_ADMIN_EMAIL,
        "password": NON_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Non-admin login failed: {response.status_code} - {response.text}")


class TestPublicSocialLinksEndpoint:
    """Tests for GET /api/site-config/social-links (public endpoint)"""

    def test_get_social_links_returns_200(self):
        """Public endpoint should return 200 without auth"""
        response = requests.get(f"{BASE_URL}/api/site-config/social-links")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /api/site-config/social-links returns 200")

    def test_get_social_links_returns_correct_structure(self):
        """Response should have social_links object with all 5 platform keys"""
        response = requests.get(f"{BASE_URL}/api/site-config/social-links")
        assert response.status_code == 200
        data = response.json()
        
        assert "social_links" in data, "Response missing 'social_links' key"
        social_links = data["social_links"]
        
        expected_keys = {"x", "facebook", "instagram", "linkedin", "tiktok"}
        actual_keys = set(social_links.keys())
        
        assert expected_keys.issubset(actual_keys), f"Missing keys: {expected_keys - actual_keys}"
        print(f"✓ social_links contains all required keys: {expected_keys}")

    def test_get_social_links_values_are_strings(self):
        """All social link values should be strings"""
        response = requests.get(f"{BASE_URL}/api/site-config/social-links")
        assert response.status_code == 200
        social_links = response.json()["social_links"]
        
        for key, value in social_links.items():
            assert isinstance(value, str), f"{key} value is not a string: {type(value)}"
        print("✓ All social link values are strings")


class TestAdminSocialLinksEndpoint:
    """Tests for PUT /api/admin/site-config/social-links (admin-only endpoint)"""

    def test_update_social_links_no_auth_returns_401(self):
        """Unauthenticated request should return 401"""
        response = requests.put(
            f"{BASE_URL}/api/admin/site-config/social-links",
            json={"x": "https://x.com/test"}
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ PUT without auth returns 401/403")

    def test_update_social_links_non_admin_returns_403(self, non_admin_token):
        """Non-admin user should get 403 Forbidden"""
        response = requests.put(
            f"{BASE_URL}/api/admin/site-config/social-links",
            json={"x": "https://x.com/test"},
            headers={"Authorization": f"Bearer {non_admin_token}"}
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        print("✓ PUT with non-admin token returns 403")

    def test_update_social_links_admin_success(self, admin_token):
        """Admin should be able to update social links"""
        # First get current values to restore later
        get_response = requests.get(f"{BASE_URL}/api/site-config/social-links")
        original_links = get_response.json()["social_links"]
        
        # Update with test values
        test_data = {
            "x": "https://x.com/bidvex_test",
            "facebook": "https://facebook.com/bidvex_test",
            "instagram": "https://instagram.com/bidvex_test",
            "linkedin": "https://linkedin.com/company/bidvex_test",
            "tiktok": "https://tiktok.com/@bidvex_test"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/site-config/social-links",
            json=test_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "social_links" in data, "Response missing 'social_links'"
        updated_links = data["social_links"]
        
        for key, expected_value in test_data.items():
            assert updated_links.get(key) == expected_value, f"{key} not updated correctly"
        
        print("✓ Admin can update social links successfully")
        
        # Restore original values
        requests.put(
            f"{BASE_URL}/api/admin/site-config/social-links",
            json=original_links,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        print("✓ Original values restored")

    def test_update_social_links_persists_in_db(self, admin_token):
        """Updated values should persist and be returned by GET"""
        # Get original values
        get_response = requests.get(f"{BASE_URL}/api/site-config/social-links")
        original_links = get_response.json()["social_links"]
        
        # Update with unique test value
        test_value = "https://x.com/persistence_test_124"
        requests.put(
            f"{BASE_URL}/api/admin/site-config/social-links",
            json={"x": test_value},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Verify via GET
        verify_response = requests.get(f"{BASE_URL}/api/site-config/social-links")
        assert verify_response.status_code == 200
        assert verify_response.json()["social_links"]["x"] == test_value
        print("✓ Updated value persists in database")
        
        # Restore original
        requests.put(
            f"{BASE_URL}/api/admin/site-config/social-links",
            json={"x": original_links.get("x", "")},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

    def test_update_social_links_partial_update(self, admin_token):
        """Should allow partial updates (only some keys)"""
        # Get original values
        get_response = requests.get(f"{BASE_URL}/api/site-config/social-links")
        original_links = get_response.json()["social_links"]
        
        # Update only one field
        response = requests.put(
            f"{BASE_URL}/api/admin/site-config/social-links",
            json={"tiktok": "https://tiktok.com/@partial_test"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        updated = response.json()["social_links"]
        
        # Verify other fields unchanged
        assert updated["tiktok"] == "https://tiktok.com/@partial_test"
        # Other fields should remain unchanged (or at least exist)
        assert "x" in updated
        assert "facebook" in updated
        print("✓ Partial update works correctly")
        
        # Restore
        requests.put(
            f"{BASE_URL}/api/admin/site-config/social-links",
            json={"tiktok": original_links.get("tiktok", "")},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

    def test_update_social_links_empty_string_allowed(self, admin_token):
        """Empty strings should be allowed (to hide icons)"""
        # Get original
        get_response = requests.get(f"{BASE_URL}/api/site-config/social-links")
        original_links = get_response.json()["social_links"]
        
        response = requests.put(
            f"{BASE_URL}/api/admin/site-config/social-links",
            json={"facebook": ""},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        assert response.json()["social_links"]["facebook"] == ""
        print("✓ Empty string values allowed")
        
        # Restore
        requests.put(
            f"{BASE_URL}/api/admin/site-config/social-links",
            json={"facebook": original_links.get("facebook", "")},
            headers={"Authorization": f"Bearer {admin_token}"}
        )

    def test_update_social_links_invalid_type_rejected(self, admin_token):
        """Non-string values should be rejected"""
        response = requests.put(
            f"{BASE_URL}/api/admin/site-config/social-links",
            json={"x": 12345},  # Number instead of string
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid type, got {response.status_code}"
        print("✓ Non-string values rejected with 400")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
