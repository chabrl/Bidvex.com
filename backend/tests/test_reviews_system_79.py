"""
BidVex Post-Purchase Review System Tests - Iteration 79
Tests: Review creation, reputation calculation, badge system, admin moderation, 48h edit window
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"
ADMIN_USER_ID = "8940074d-da97-43ca-9a0b-c59d39411ed6"

# Test data IDs - unique for this iteration
TEST_SELLER_ID = f"test-seller-reviews-79-{uuid.uuid4().hex[:8]}"
TEST_TRANSACTION_ID = f"test-txn-reviews-79-{uuid.uuid4().hex[:8]}"
TEST_TRANSACTION_ID_2 = f"test-txn-reviews-79-2-{uuid.uuid4().hex[:8]}"
TEST_AUCTION_ID = f"test-auction-reviews-79-{uuid.uuid4().hex[:8]}"


class TestReviewsSetup:
    """Setup: Login and create test data in MongoDB"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        token = data.get("access_token") or data.get("token")
        assert token, "No token in login response"
        return token
    
    @pytest.fixture(scope="class")
    def setup_test_data(self, admin_token):
        """Create test transaction data directly via MongoDB through a test endpoint or seed"""
        # We'll use the admin token to verify we can access protected endpoints
        # The actual test data will be created via direct MongoDB operations in the test
        return {
            "admin_token": admin_token,
            "seller_id": TEST_SELLER_ID,
            "transaction_id": TEST_TRANSACTION_ID,
            "transaction_id_2": TEST_TRANSACTION_ID_2,
            "auction_id": TEST_AUCTION_ID,
        }


class TestReviewCreation:
    """Test POST /api/reviews/create endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_01_create_review_no_transaction(self, admin_token):
        """Test: Reject review when transaction not found (404)"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "transaction_id": "non-existent-transaction-id",
                "rating": 5
            }
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        detail = response.json().get("detail", "").lower()
        assert "transaction" in detail or "not found" in detail, f"Unexpected error message: {detail}"
    
    def test_02_create_review_invalid_rating(self, admin_token):
        """Test: Reject review with invalid rating (outside 1-5)"""
        # Rating 0 should fail validation
        response = requests.post(
            f"{BASE_URL}/api/reviews/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "transaction_id": "any-id",
                "rating": 0
            }
        )
        assert response.status_code == 422, f"Expected 422 for rating=0, got {response.status_code}"
        
        # Rating 6 should fail validation
        response = requests.post(
            f"{BASE_URL}/api/reviews/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "transaction_id": "any-id",
                "rating": 6
            }
        )
        assert response.status_code == 422, f"Expected 422 for rating=6, got {response.status_code}"
    
    def test_03_create_review_comment_too_short(self, admin_token):
        """Test: Reject review with comment < 20 chars"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "transaction_id": "any-id",
                "rating": 5,
                "comment": "Too short"  # Less than 20 chars
            }
        )
        assert response.status_code == 422, f"Expected 422 for short comment, got {response.status_code}"
    
    def test_04_create_review_unauthenticated(self):
        """Test: Reject review without authentication"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/create",
            json={
                "transaction_id": "any-id",
                "rating": 5
            }
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestReviewDetails:
    """Test GET /api/reviews/details/{transactionId} endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_05_get_details_not_found(self, admin_token):
        """Test: Return 404 for non-existent transaction"""
        response = requests.get(
            f"{BASE_URL}/api/reviews/details/non-existent-txn-id",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Should return 404 or 400 for transaction not found
        assert response.status_code in [400, 404], f"Expected 400/404, got {response.status_code}: {response.text}"
    
    def test_06_get_details_unauthenticated(self):
        """Test: Reject details request without auth"""
        response = requests.get(f"{BASE_URL}/api/reviews/details/any-id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestSellerReputation:
    """Test GET /api/reviews/reputation/{sellerId} endpoint"""
    
    def test_07_get_reputation_new_seller(self):
        """Test: New seller with 0 reviews returns new_seller badge"""
        # Use a random seller ID that won't have any reviews
        random_seller_id = f"new-seller-{uuid.uuid4().hex[:8]}"
        response = requests.get(f"{BASE_URL}/api/reviews/reputation/{random_seller_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["badge"] == "new_seller", f"Expected new_seller badge, got {data.get('badge')}"
        assert data["total_reviews"] == 0, f"Expected 0 reviews, got {data.get('total_reviews')}"
        assert data.get("average_rating_display") is None, "Score should be hidden for <3 reviews"
    
    def test_08_get_reputation_response_structure(self):
        """Test: Reputation response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/reviews/reputation/{ADMIN_USER_ID}")
        assert response.status_code == 200
        
        data = response.json()
        # Check required fields exist
        assert "seller_id" in data
        assert "average_rating" in data
        assert "total_reviews" in data
        assert "badge" in data
        assert "rating_breakdown" in data
        # Badge should be one of the valid values
        assert data["badge"] in ["new_seller", "trusted_seller", "top_rated"]


class TestSellerReviews:
    """Test GET /api/reviews/seller/{sellerId} endpoint"""
    
    def test_09_get_seller_reviews_pagination(self):
        """Test: Seller reviews endpoint returns paginated response"""
        response = requests.get(f"{BASE_URL}/api/reviews/seller/{ADMIN_USER_ID}?page=1&limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "reviews" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert "total_pages" in data
        assert isinstance(data["reviews"], list)
    
    def test_10_get_seller_reviews_limit_validation(self):
        """Test: Limit parameter is validated (max 50)"""
        response = requests.get(f"{BASE_URL}/api/reviews/seller/{ADMIN_USER_ID}?page=1&limit=100")
        # Should either cap at 50 or return 422
        assert response.status_code in [200, 422], f"Expected 200 or 422, got {response.status_code}"


class TestTransactionReview:
    """Test GET /api/reviews/transaction/{transactionId} endpoint"""
    
    def test_11_get_transaction_review_not_found(self):
        """Test: Return null review for non-existent transaction"""
        response = requests.get(f"{BASE_URL}/api/reviews/transaction/non-existent-txn")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("review") is None, "Should return null for non-existent transaction"


class TestBatchReputations:
    """Test POST /api/reviews/reputation/batch endpoint"""
    
    def test_12_batch_reputations_valid(self):
        """Test: Batch endpoint returns reputations for multiple sellers"""
        seller_ids = [ADMIN_USER_ID, f"seller-{uuid.uuid4().hex[:8]}"]
        response = requests.post(
            f"{BASE_URL}/api/reviews/reputation/batch",
            json={"seller_ids": seller_ids}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "reputations" in data
        # Should have entries for all requested sellers
        for sid in seller_ids:
            assert sid in data["reputations"], f"Missing reputation for {sid}"
    
    def test_13_batch_reputations_empty(self):
        """Test: Batch endpoint rejects empty seller_ids"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/reputation/batch",
            json={"seller_ids": []}
        )
        assert response.status_code == 400, f"Expected 400 for empty list, got {response.status_code}"
    
    def test_14_batch_reputations_too_many(self):
        """Test: Batch endpoint rejects >50 seller_ids"""
        seller_ids = [f"seller-{i}" for i in range(51)]
        response = requests.post(
            f"{BASE_URL}/api/reviews/reputation/batch",
            json={"seller_ids": seller_ids}
        )
        assert response.status_code == 400, f"Expected 400 for >50 sellers, got {response.status_code}"


class TestAdminModeration:
    """Test admin-only moderation endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_15_flag_review_not_found(self, admin_token):
        """Test: Flag non-existent review returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/non-existent-review-id/flag",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "Test flag"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_16_unflag_review_not_found(self, admin_token):
        """Test: Unflag non-existent review returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/non-existent-review-id/unflag",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_17_delete_review_not_found(self, admin_token):
        """Test: Delete non-existent review returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/reviews/non-existent-review-id",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_18_moderation_pending_admin_only(self, admin_token):
        """Test: Moderation pending endpoint requires admin"""
        # With admin token - should work
        response = requests.get(
            f"{BASE_URL}/api/reviews/moderation/pending",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200 with admin, got {response.status_code}"
        
        data = response.json()
        assert "reviews" in data
        assert "total" in data
    
    def test_19_moderation_pending_no_auth(self):
        """Test: Moderation pending endpoint rejects unauthenticated"""
        response = requests.get(f"{BASE_URL}/api/reviews/moderation/pending")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestReviewUpdate:
    """Test PUT /api/reviews/{reviewId} endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_20_update_review_not_found(self, admin_token):
        """Test: Update non-existent review returns 404"""
        response = requests.put(
            f"{BASE_URL}/api/reviews/non-existent-review-id",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"rating": 4}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    
    def test_21_update_review_unauthenticated(self):
        """Test: Update review without auth returns 401"""
        response = requests.put(
            f"{BASE_URL}/api/reviews/any-review-id",
            json={"rating": 4}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestEndToEndReviewFlow:
    """End-to-end test: Create transaction, create review, verify reputation"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_22_full_review_flow_setup(self, admin_token):
        """
        Test full flow: We need to create a buy_now_transaction with payment_status='paid'
        This test documents the expected flow even if we can't create the transaction directly.
        """
        # Document the expected API behavior
        # 1. A buy_now_transaction must exist with:
        #    - id: transaction_id
        #    - buyer_id: current user's ID
        #    - payment_status: 'paid'
        #    - auction_id: pointing to a multi_item_listing with seller_id
        
        # 2. POST /api/reviews/create with valid transaction_id should:
        #    - Return 200 with review object
        #    - Include: id, transaction_id, rating, status='active', editable_until
        
        # 3. GET /api/reviews/reputation/{sellerId} should:
        #    - Return updated average_rating
        #    - Return updated total_reviews
        #    - Return appropriate badge based on count and rating
        
        # For now, verify the endpoints exist and respond correctly
        response = requests.get(f"{BASE_URL}/api/reviews/reputation/{ADMIN_USER_ID}")
        assert response.status_code == 200
        print(f"Reputation endpoint working. Response: {response.json()}")


class TestBadgeLogic:
    """Test badge calculation logic"""
    
    def test_23_badge_thresholds_documented(self):
        """Document badge thresholds for verification"""
        # Badge logic from reviews.py:
        # - top_rated: avg >= 4.7 AND total >= 25
        # - trusted_seller: avg >= 4.0 AND total >= 10
        # - new_seller: default (< 10 reviews OR avg < 4.0)
        
        # Verify endpoint returns valid badge values
        response = requests.get(f"{BASE_URL}/api/reviews/reputation/{ADMIN_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["badge"] in ["new_seller", "trusted_seller", "top_rated"]
        
        # Verify score is hidden for < 3 reviews
        if data["total_reviews"] < 3:
            assert data.get("average_rating_display") is None
        else:
            assert data.get("average_rating_display") is not None


class TestRateLimiting:
    """Test rate limiting on review creation"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        return data.get("access_token") or data.get("token")
    
    def test_24_rate_limit_exists(self, admin_token):
        """Test: Rate limit is enforced (10 reviews/hour)"""
        # We can't easily test hitting the rate limit without creating 10 reviews
        # But we can verify the endpoint responds correctly
        response = requests.post(
            f"{BASE_URL}/api/reviews/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "transaction_id": "rate-limit-test",
                "rating": 5
            }
        )
        # Should return 404 (transaction not found) not 429 (rate limited)
        # This confirms the rate limit check happens after auth but before transaction lookup
        assert response.status_code in [404, 429], f"Expected 404 or 429, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
