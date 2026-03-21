"""
Test Suite for Seller Reputation Features - Iteration 80
Tests SellerRatingInline component APIs and reputation endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://subscription-grid-ui.preview.emergentagent.com')

class TestReputationAPIs:
    """Test reputation API endpoints"""
    
    def test_single_reputation_endpoint_returns_correct_structure(self):
        """GET /api/reviews/reputation/{sellerId} returns correct structure"""
        # Use a known seller ID from the database
        seller_id = "8940074d-da97-43ca-9a0b-c59d39411ed6"
        response = requests.get(f"{BASE_URL}/api/reviews/reputation/{seller_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields exist
        assert "seller_id" in data
        assert "average_rating" in data
        assert "total_reviews" in data
        assert "rating_breakdown" in data
        assert "badge" in data
        assert "average_rating_display" in data
        
        # Verify badge is one of expected values
        assert data["badge"] in ["new_seller", "trusted_seller", "top_rated"]
        
        # Verify rating_breakdown has all star levels
        breakdown = data["rating_breakdown"]
        assert "1" in breakdown
        assert "2" in breakdown
        assert "3" in breakdown
        assert "4" in breakdown
        assert "5" in breakdown
    
    def test_single_reputation_hides_score_for_new_seller(self):
        """GET /api/reviews/reputation/{sellerId} hides score when < 3 reviews"""
        # Use a seller with no reviews
        seller_id = "test-new-seller-no-reviews"
        response = requests.get(f"{BASE_URL}/api/reviews/reputation/{seller_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # New seller should have badge = "new_seller" and average_rating_display = null
        assert data["badge"] == "new_seller"
        assert data["average_rating_display"] is None
        assert data["total_reviews"] == 0
    
    def test_batch_reputation_endpoint_returns_multiple_reputations(self):
        """POST /api/reviews/reputation/batch returns reputations for multiple sellers"""
        seller_ids = [
            "8940074d-da97-43ca-9a0b-c59d39411ed6",
            "test-seller-1",
            "test-seller-2"
        ]
        
        response = requests.post(
            f"{BASE_URL}/api/reviews/reputation/batch",
            json={"seller_ids": seller_ids}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify reputations object exists
        assert "reputations" in data
        reputations = data["reputations"]
        
        # Verify all requested seller IDs are in response
        for seller_id in seller_ids:
            assert seller_id in reputations
            rep = reputations[seller_id]
            assert "seller_id" in rep
            assert "badge" in rep
            assert "total_reviews" in rep
    
    def test_batch_reputation_rejects_empty_list(self):
        """POST /api/reviews/reputation/batch rejects empty seller_ids list"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/reputation/batch",
            json={"seller_ids": []}
        )
        
        assert response.status_code == 400
    
    def test_batch_reputation_rejects_too_many_ids(self):
        """POST /api/reviews/reputation/batch rejects > 50 seller IDs"""
        seller_ids = [f"seller-{i}" for i in range(51)]
        
        response = requests.post(
            f"{BASE_URL}/api/reviews/reputation/batch",
            json={"seller_ids": seller_ids}
        )
        
        assert response.status_code == 400
    
    def test_batch_reputation_fills_missing_with_defaults(self):
        """POST /api/reviews/reputation/batch fills missing sellers with defaults"""
        seller_ids = ["nonexistent-seller-xyz-123"]
        
        response = requests.post(
            f"{BASE_URL}/api/reviews/reputation/batch",
            json={"seller_ids": seller_ids}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        rep = data["reputations"]["nonexistent-seller-xyz-123"]
        assert rep["badge"] == "new_seller"
        assert rep["total_reviews"] == 0
        assert rep["average_rating_display"] is None


class TestListingsAPI:
    """Test that listings API returns seller_id for reputation lookup"""
    
    def test_listings_include_seller_id(self):
        """GET /api/listings returns seller_id for each listing"""
        response = requests.get(f"{BASE_URL}/api/listings?limit=5")
        
        assert response.status_code == 200
        listings = response.json()
        
        if len(listings) > 0:
            for listing in listings:
                assert "seller_id" in listing
                assert listing["seller_id"] is not None


class TestStorefrontAPI:
    """Test storefront API for seller reputation display"""
    
    def test_storefront_returns_seller_info(self):
        """GET /api/storefronts/{userId} returns seller info"""
        # Use known seller ID
        seller_id = "8940074d-da97-43ca-9a0b-c59d39411ed6"
        response = requests.get(f"{BASE_URL}/api/storefronts/{seller_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify seller info exists
        assert "seller" in data
        assert "listings" in data


class TestSellerReviewsAPI:
    """Test seller reviews endpoint for SellerReviewsList component"""
    
    def test_seller_reviews_returns_paginated_reviews(self):
        """GET /api/reviews/seller/{sellerId} returns paginated reviews"""
        seller_id = "8940074d-da97-43ca-9a0b-c59d39411ed6"
        response = requests.get(f"{BASE_URL}/api/reviews/seller/{seller_id}?page=1&limit=5")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify pagination structure
        assert "reviews" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert "total_pages" in data
        
        # Verify reviews is a list
        assert isinstance(data["reviews"], list)


class TestI18nKeys:
    """Test that i18n keys exist in locale files"""
    
    def test_en_locale_has_seller_reputation_keys(self):
        """EN locale file has sellerReputation keys"""
        import json
        with open('/app/frontend/src/locales/en.json', 'r') as f:
            en_locale = json.load(f)
        
        assert "sellerReputation" in en_locale
        sr = en_locale["sellerReputation"]
        
        # Verify required keys
        assert "newSeller" in sr
        assert "topRated" in sr
        assert "trustedSeller" in sr
        assert "buyerReviews" in sr
        assert "basedOnReviews" in sr
        assert "noReviewsYet" in sr
        assert "moreReviewsNeeded" in sr
        assert "viewAllReviews" in sr
        assert "rateSeller" in sr
        assert "sellerInformation" in sr
        assert "itemAccuracy" in sr
        assert "communication" in sr
        assert "shippingSpeed" in sr
    
    def test_fr_locale_has_seller_reputation_keys(self):
        """FR locale file has sellerReputation keys"""
        import json
        with open('/app/frontend/src/locales/fr.json', 'r') as f:
            fr_locale = json.load(f)
        
        assert "sellerReputation" in fr_locale
        sr = fr_locale["sellerReputation"]
        
        # Verify required keys
        assert "newSeller" in sr
        assert "topRated" in sr
        assert "trustedSeller" in sr
        assert "buyerReviews" in sr
        assert "basedOnReviews" in sr
        assert "noReviewsYet" in sr
        assert "moreReviewsNeeded" in sr
        assert "viewAllReviews" in sr
        assert "rateSeller" in sr
        assert "sellerInformation" in sr
        assert "itemAccuracy" in sr
        assert "communication" in sr
        assert "shippingSpeed" in sr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
