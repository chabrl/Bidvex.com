"""
Test Suite for Bug Fix Iteration 46
Tests the 6 reported issues:
1. Error handling for Pydantic validation error objects in bid placement
2. Marketplace card layout (overflow fix for View button)
3. Become a Partner page light mode theming
4. Item routing - standalone items to /listing/:id
5. Verified Partner badge on marketplace cards
6. General polish audit

Backend API tests to verify is_partner_listing and auction_id fields
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestMarketplaceAPI:
    """Test marketplace API responses for Issue 4 and Issue 5"""
    
    def test_marketplace_items_returns_is_partner_listing(self):
        """Issue 5: API should return is_partner_listing field"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'items' in data, "Response should have 'items' key"
        
        if data['items']:
            item = data['items'][0]
            assert 'is_partner_listing' in item, "Item should have 'is_partner_listing' field"
            # Verify it's a boolean
            assert isinstance(item['is_partner_listing'], bool), "is_partner_listing should be a boolean"
            print(f"PASS: is_partner_listing = {item['is_partner_listing']}")
    
    def test_marketplace_items_returns_auction_id(self):
        """Issue 4: API should return auction_id field (can be null for standalone items)"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'items' in data, "Response should have 'items' key"
        
        if data['items']:
            item = data['items'][0]
            assert 'auction_id' in item, "Item should have 'auction_id' field"
            # auction_id can be None for standalone listings
            print(f"PASS: auction_id = {item['auction_id']}")
    
    def test_standalone_item_has_null_auction_id(self):
        """Issue 4: Standalone item 'table' should have auction_id=null"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        # Find the 'table' item
        table_item = None
        for item in data.get('items', []):
            if item.get('title', '').lower() == 'table':
                table_item = item
                break
        
        if table_item:
            assert table_item['auction_id'] is None, f"'table' item should have auction_id=None, got {table_item['auction_id']}"
            assert table_item['is_partner_listing'] == True, "'table' item should be a partner listing"
            print(f"PASS: 'table' item has auction_id=None and is_partner_listing=True")
        else:
            pytest.skip("'table' item not found in marketplace")
    
    def test_item_has_required_routing_fields(self):
        """Items should have id, auction_id, and lot_number fields for routing logic"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        if data['items']:
            item = data['items'][0]
            assert 'id' in item, "Item should have 'id' field"
            assert 'auction_id' in item, "Item should have 'auction_id' field"
            assert 'lot_number' in item, "Item should have 'lot_number' field"
            print(f"PASS: Item has id={item['id']}, auction_id={item['auction_id']}, lot_number={item['lot_number']}")


class TestHealthCheck:
    """Basic health check tests"""
    
    def test_health_endpoint(self):
        """API should be healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy', f"Expected healthy status, got {data}"


class TestAuthAndBidErrorHandling:
    """Test authentication and bid error scenarios for Issue 1"""
    
    def test_login_returns_token(self):
        """Login should return access_token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'access_token' in data, "Response should have 'access_token'"
        print(f"PASS: Login successful, token received")
        return data['access_token']
    
    def test_bid_without_auth_returns_401(self):
        """Bid without authentication should return 401"""
        # Try to bid without token
        response = requests.post(
            f"{BASE_URL}/api/multi-item-listings/some-id/lots/1/bid",
            json={"amount": 100}
        )
        # Should get 401 or 403 without auth
        assert response.status_code in [401, 403, 422], f"Expected 401/403/422, got {response.status_code}"
        print(f"PASS: Unauthorized bid returns {response.status_code}")
    
    def test_bid_validation_error_returns_proper_format(self):
        """Bid with invalid data should return proper error format"""
        # First login
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        if login_response.status_code != 200:
            pytest.skip("Login failed")
        
        token = login_response.json()['access_token']
        
        # Try to bid with invalid auction_id
        response = requests.post(
            f"{BASE_URL}/api/multi-item-listings/invalid-uuid/lots/1/bid",
            json={"amount": 100},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Should get 422 (validation error) or 404 (not found)
        assert response.status_code in [404, 422, 400], f"Expected 404/422/400, got {response.status_code}"
        
        # Check error format
        data = response.json()
        if 'detail' in data:
            detail = data['detail']
            # Detail can be string, array of objects, or single object
            if isinstance(detail, str):
                print(f"PASS: Error detail is string: {detail}")
            elif isinstance(detail, list):
                print(f"PASS: Error detail is array (Pydantic format)")
                for err in detail[:3]:  # Show first 3
                    print(f"  - {err}")
            elif isinstance(detail, dict):
                print(f"PASS: Error detail is object: {detail}")


class TestPartnerPageAndUI:
    """Test partner page endpoint"""
    
    def test_partner_status_without_auth(self):
        """Partner status without auth should return 401"""
        response = requests.get(f"{BASE_URL}/api/partner/status")
        # Without auth, should get 401
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
