"""
Test cases for BidVex Bug Fixes - Iteration 47
Testing:
1. POST /api/ratings endpoint - auction_type field requirement
2. Backend validation and error messages
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"

# Test listing ID (the 'table' item)
TEST_LISTING_ID = "9b20dc8a-3d68-4cc7-934c-e01ee48fadb5"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for test user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed: {response.text}")


@pytest.fixture
def authenticated_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestRatingsAPIValidation:
    """Test POST /api/ratings endpoint validation"""
    
    def test_ratings_requires_auction_type(self, authenticated_client):
        """Test that auction_type field is required"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/ratings",
            json={
                "auction_id": TEST_LISTING_ID,
                "target_user_id": "some-user-id",
                "rating": 5
            }
        )
        
        # Should return 400 Bad Request
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        # Check error message mentions missing auction_type
        data = response.json()
        assert "detail" in data
        assert "auction_type" in data["detail"].lower(), f"Error should mention auction_type: {data}"
        print(f"✓ Missing auction_type returns 400: {data['detail']}")
    
    def test_ratings_validates_auction_type(self, authenticated_client):
        """Test that auction_type must be 'single' or 'multi'"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/ratings",
            json={
                "auction_id": TEST_LISTING_ID,
                "auction_type": "invalid_type",
                "target_user_id": "some-user-id",
                "rating": 5
            }
        )
        
        # Should return 400 Bad Request
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        # Check error message
        data = response.json()
        assert "detail" in data
        assert "single" in data["detail"].lower() or "multi" in data["detail"].lower()
        print(f"✓ Invalid auction_type returns 400: {data['detail']}")
    
    def test_ratings_requires_participation(self, authenticated_client):
        """Test that user must participate in auction to rate"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/ratings",
            json={
                "auction_id": TEST_LISTING_ID,
                "auction_type": "single",
                "target_user_id": "nonexistent-user-id",
                "rating": 5
            }
        )
        
        # Should return 403 Forbidden (user hasn't participated)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        
        # Check error message mentions participation
        data = response.json()
        assert "detail" in data
        assert "participate" in data["detail"].lower() or "rate" in data["detail"].lower()
        print(f"✓ Non-participant returns 403: {data['detail']}")
    
    def test_ratings_validates_rating_range(self, authenticated_client):
        """Test that rating must be 1-5"""
        # Test rating = 0 (too low)
        response = authenticated_client.post(
            f"{BASE_URL}/api/ratings",
            json={
                "auction_id": TEST_LISTING_ID,
                "auction_type": "single",
                "target_user_id": "some-user-id",
                "rating": 0
            }
        )
        assert response.status_code == 400, f"Expected 400 for rating=0, got {response.status_code}"
        print(f"✓ Rating=0 returns 400")
        
        # Test rating = 6 (too high)
        response = authenticated_client.post(
            f"{BASE_URL}/api/ratings",
            json={
                "auction_id": TEST_LISTING_ID,
                "auction_type": "single",
                "target_user_id": "some-user-id",
                "rating": 6
            }
        )
        assert response.status_code == 400, f"Expected 400 for rating=6, got {response.status_code}"
        print(f"✓ Rating=6 returns 400")


class TestHomepageAPIEndpoints:
    """Test homepage data endpoints are returning valid data"""
    
    def test_hot_items_endpoint(self):
        """Test /api/stats/hot-items returns valid response"""
        response = requests.get(f"{BASE_URL}/api/stats/hot-items?limit=6")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Hot items endpoint returns {len(data)} items")
    
    def test_new_listings_endpoint(self):
        """Test /api/carousel/new-listings returns valid response"""
        response = requests.get(f"{BASE_URL}/api/carousel/new-listings?limit=12")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ New listings endpoint returns {len(data)} items")
    
    def test_featured_endpoint(self):
        """Test /api/carousel/featured returns valid response"""
        response = requests.get(f"{BASE_URL}/api/carousel/featured?limit=12")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Featured endpoint returns {len(data)} items")
    
    def test_top_sellers_endpoint(self):
        """Test /api/stats/top-sellers returns valid response"""
        response = requests.get(f"{BASE_URL}/api/stats/top-sellers?limit=8")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Top sellers endpoint returns {len(data)} sellers")


class TestListingDetailPage:
    """Test listing detail page API"""
    
    def test_listing_detail_endpoint(self):
        """Test /api/listings/{id} returns valid listing"""
        response = requests.get(f"{BASE_URL}/api/listings/{TEST_LISTING_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "id" in data
        assert "title" in data
        assert "seller_id" in data
        assert data["id"] == TEST_LISTING_ID
        print(f"✓ Listing detail returns: {data['title']}")
    
    def test_listing_bids_endpoint(self):
        """Test /api/bids/listing/{id} returns bids array"""
        response = requests.get(f"{BASE_URL}/api/bids/listing/{TEST_LISTING_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listing bids returns {len(data)} bids")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
