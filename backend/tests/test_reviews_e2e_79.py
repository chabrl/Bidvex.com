"""
BidVex Review System - Full E2E Tests with MongoDB Data Creation
Tests the complete review flow: create transaction -> create review -> verify reputation -> test edit window
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
MONGO_URL = os.environ.get('MONGO_URL')
DB_NAME = os.environ.get('DB_NAME', 'bazario_db')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"
ADMIN_USER_ID = "8940074d-da97-43ca-9a0b-c59d39411ed6"

# Unique test IDs for this run
RUN_ID = uuid.uuid4().hex[:8]
TEST_SELLER_ID = f"test-seller-e2e-{RUN_ID}"
TEST_AUCTION_ID = f"test-auction-e2e-{RUN_ID}"
TEST_TXN_ID_1 = f"test-txn-e2e-1-{RUN_ID}"
TEST_TXN_ID_2 = f"test-txn-e2e-2-{RUN_ID}"
TEST_TXN_ID_3 = f"test-txn-e2e-3-{RUN_ID}"
TEST_TXN_SELF = f"test-txn-self-{RUN_ID}"


@pytest.fixture(scope="module")
def mongo_client():
    """Get MongoDB client"""
    client = MongoClient(MONGO_URL)
    yield client
    client.close()


@pytest.fixture(scope="module")
def db(mongo_client):
    """Get database"""
    return mongo_client[DB_NAME]


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    data = response.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def setup_test_data(db):
    """Create test data in MongoDB for review testing"""
    now = datetime.now(timezone.utc)
    
    # Create a test seller user
    test_seller = {
        "id": TEST_SELLER_ID,
        "email": f"test-seller-{RUN_ID}@test.com",
        "name": "Test Seller E2E",
        "role": "user",
        "created_at": now.isoformat(),
    }
    db.users.update_one({"id": TEST_SELLER_ID}, {"$set": test_seller}, upsert=True)
    
    # Create a test multi_item_listing (auction)
    test_auction = {
        "id": TEST_AUCTION_ID,
        "title": "Test Auction for Reviews",
        "seller_id": TEST_SELLER_ID,
        "status": "ended",
        "lots": [{"lot_number": 1, "title": "Test Lot", "images": []}],
        "images": [],
        "created_at": now.isoformat(),
    }
    db.multi_item_listings.update_one({"id": TEST_AUCTION_ID}, {"$set": test_auction}, upsert=True)
    
    # Create buy_now_transactions for testing
    # Transaction 1: Valid paid transaction for admin user
    txn1 = {
        "id": TEST_TXN_ID_1,
        "auction_id": TEST_AUCTION_ID,
        "lot_number": 1,
        "buyer_id": ADMIN_USER_ID,
        "payment_status": "paid",
        "buyer_total": 100.00,
        "transaction_date": now.isoformat(),
        "created_at": now.isoformat(),
    }
    db.buy_now_transactions.update_one({"id": TEST_TXN_ID_1}, {"$set": txn1}, upsert=True)
    
    # Transaction 2: Another valid transaction for duplicate test
    txn2 = {
        "id": TEST_TXN_ID_2,
        "auction_id": TEST_AUCTION_ID,
        "lot_number": 1,
        "buyer_id": ADMIN_USER_ID,
        "payment_status": "paid",
        "buyer_total": 150.00,
        "transaction_date": now.isoformat(),
        "created_at": now.isoformat(),
    }
    db.buy_now_transactions.update_one({"id": TEST_TXN_ID_2}, {"$set": txn2}, upsert=True)
    
    # Transaction 3: For edit window test
    txn3 = {
        "id": TEST_TXN_ID_3,
        "auction_id": TEST_AUCTION_ID,
        "lot_number": 1,
        "buyer_id": ADMIN_USER_ID,
        "payment_status": "paid",
        "buyer_total": 200.00,
        "transaction_date": now.isoformat(),
        "created_at": now.isoformat(),
    }
    db.buy_now_transactions.update_one({"id": TEST_TXN_ID_3}, {"$set": txn3}, upsert=True)
    
    # Transaction for self-review test (buyer = seller)
    # Create auction where admin is the seller
    admin_auction_id = f"admin-auction-{RUN_ID}"
    admin_auction = {
        "id": admin_auction_id,
        "title": "Admin's Auction",
        "seller_id": ADMIN_USER_ID,  # Admin is the seller
        "status": "ended",
        "lots": [{"lot_number": 1, "title": "Admin Lot", "images": []}],
        "images": [],
        "created_at": now.isoformat(),
    }
    db.multi_item_listings.update_one({"id": admin_auction_id}, {"$set": admin_auction}, upsert=True)
    
    txn_self = {
        "id": TEST_TXN_SELF,
        "auction_id": admin_auction_id,
        "lot_number": 1,
        "buyer_id": ADMIN_USER_ID,  # Admin is also the buyer
        "payment_status": "paid",
        "buyer_total": 50.00,
        "transaction_date": now.isoformat(),
        "created_at": now.isoformat(),
    }
    db.buy_now_transactions.update_one({"id": TEST_TXN_SELF}, {"$set": txn_self}, upsert=True)
    
    yield {
        "seller_id": TEST_SELLER_ID,
        "auction_id": TEST_AUCTION_ID,
        "txn_id_1": TEST_TXN_ID_1,
        "txn_id_2": TEST_TXN_ID_2,
        "txn_id_3": TEST_TXN_ID_3,
        "txn_self": TEST_TXN_SELF,
        "admin_auction_id": admin_auction_id,
    }
    
    # Cleanup after tests
    db.users.delete_one({"id": TEST_SELLER_ID})
    db.multi_item_listings.delete_one({"id": TEST_AUCTION_ID})
    db.multi_item_listings.delete_one({"id": admin_auction_id})
    db.buy_now_transactions.delete_many({"id": {"$in": [TEST_TXN_ID_1, TEST_TXN_ID_2, TEST_TXN_ID_3, TEST_TXN_SELF]}})
    db.reviews.delete_many({"transaction_id": {"$in": [TEST_TXN_ID_1, TEST_TXN_ID_2, TEST_TXN_ID_3, TEST_TXN_SELF]}})
    db.seller_reputation.delete_one({"seller_id": TEST_SELLER_ID})


class TestE2EReviewCreation:
    """E2E tests for review creation with real data"""
    
    def test_01_create_review_success(self, admin_token, setup_test_data):
        """Test: Successfully create a review for a paid transaction"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "transaction_id": setup_test_data["txn_id_1"],
                "rating": 5,
                "item_accuracy": 5,
                "communication": 4,
                "shipping_speed": 5,
                "comment": "Excellent seller! Fast shipping and item exactly as described. Highly recommend!"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] is True
        assert "review" in data
        assert "reputation" in data
        
        review = data["review"]
        assert review["transaction_id"] == setup_test_data["txn_id_1"]
        assert review["rating"] == 5
        assert review["item_accuracy"] == 5
        assert review["communication"] == 4
        assert review["shipping_speed"] == 5
        assert review["status"] == "active"
        assert "editable_until" in review
        assert review["seller_id"] == setup_test_data["seller_id"]
        
        # Verify reputation was updated
        rep = data["reputation"]
        assert rep["total_reviews"] >= 1
        assert rep["seller_id"] == setup_test_data["seller_id"]
    
    def test_02_create_duplicate_review_rejected(self, admin_token, setup_test_data):
        """Test: Reject duplicate review for same transaction (409)"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "transaction_id": setup_test_data["txn_id_1"],
                "rating": 4
            }
        )
        assert response.status_code == 409, f"Expected 409 for duplicate, got {response.status_code}: {response.text}"
        assert "already reviewed" in response.json().get("detail", "").lower()
    
    def test_03_self_review_rejected(self, admin_token, setup_test_data):
        """Test: Reject self-review (buyer = seller returns 400)"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "transaction_id": setup_test_data["txn_self"],
                "rating": 5
            }
        )
        assert response.status_code == 400, f"Expected 400 for self-review, got {response.status_code}: {response.text}"
        assert "yourself" in response.json().get("detail", "").lower()
    
    def test_04_get_review_details(self, admin_token, setup_test_data):
        """Test: Get transaction details for review form"""
        response = requests.get(
            f"{BASE_URL}/api/reviews/details/{setup_test_data['txn_id_2']}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "item_title" in data
        assert "seller_name" in data
        assert "seller_id" in data
        assert data["seller_id"] == setup_test_data["seller_id"]


class TestE2EReputationCalculation:
    """E2E tests for reputation calculation"""
    
    def test_05_reputation_after_review(self, admin_token, setup_test_data):
        """Test: Verify reputation is correctly calculated after review"""
        response = requests.get(f"{BASE_URL}/api/reviews/reputation/{setup_test_data['seller_id']}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_reviews"] >= 1
        assert data["average_rating"] > 0
        # With < 3 reviews, score should be hidden
        if data["total_reviews"] < 3:
            assert data.get("average_rating_display") is None
            assert data["badge"] == "new_seller"
    
    def test_06_create_more_reviews_for_badge_test(self, admin_token, setup_test_data, db):
        """Test: Create additional reviews to test badge transitions"""
        # Create review for txn_id_2
        response = requests.post(
            f"{BASE_URL}/api/reviews/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "transaction_id": setup_test_data["txn_id_2"],
                "rating": 5,
                "comment": "Another great transaction with this seller. Very satisfied!"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Create review for txn_id_3
        response = requests.post(
            f"{BASE_URL}/api/reviews/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "transaction_id": setup_test_data["txn_id_3"],
                "rating": 4,
                "comment": "Good experience overall. Would buy from again."
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Now check reputation - should have 3 reviews and show score
        response = requests.get(f"{BASE_URL}/api/reviews/reputation/{setup_test_data['seller_id']}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_reviews"] >= 3, f"Expected >= 3 reviews, got {data['total_reviews']}"
        # With 3+ reviews, score should be visible
        assert data.get("average_rating_display") is not None, "Score should be visible with 3+ reviews"
        
        # Verify rating breakdown
        breakdown = data.get("rating_breakdown", {})
        assert breakdown.get("5", 0) >= 2, "Should have at least 2 five-star reviews"
        assert breakdown.get("4", 0) >= 1, "Should have at least 1 four-star review"


class TestE2EEditWindow:
    """E2E tests for 48h edit window"""
    
    def test_07_edit_review_within_window(self, admin_token, setup_test_data, db):
        """Test: Allow edit within 48h window"""
        # Get the review for txn_id_1
        review = db.reviews.find_one({"transaction_id": setup_test_data["txn_id_1"]})
        assert review is not None, "Review should exist"
        
        review_id = review["id"]
        
        # Update the review
        response = requests.put(
            f"{BASE_URL}/api/reviews/{review_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "rating": 4,
                "comment": "Updated review: Still a great seller but adjusting rating slightly."
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] is True
        assert data["review"]["rating"] == 4
    
    def test_08_edit_review_after_window_expired(self, admin_token, setup_test_data, db):
        """Test: Reject edit after 48h window expired"""
        # Get the review for txn_id_2
        review = db.reviews.find_one({"transaction_id": setup_test_data["txn_id_2"]})
        assert review is not None, "Review should exist"
        
        review_id = review["id"]
        
        # Manually set editable_until to past
        past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        db.reviews.update_one(
            {"id": review_id},
            {"$set": {"editable_until": past_time}}
        )
        
        # Try to update - should fail
        response = requests.put(
            f"{BASE_URL}/api/reviews/{review_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"rating": 3}
        )
        assert response.status_code == 400, f"Expected 400 for expired window, got {response.status_code}: {response.text}"
        assert "48h" in response.json().get("detail", "").lower() or "expired" in response.json().get("detail", "").lower()


class TestE2EAdminModeration:
    """E2E tests for admin moderation"""
    
    def test_09_admin_flag_review(self, admin_token, setup_test_data, db):
        """Test: Admin can flag a review"""
        review = db.reviews.find_one({"transaction_id": setup_test_data["txn_id_3"]})
        assert review is not None
        review_id = review["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/reviews/{review_id}/flag",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"reason": "Test flagging for moderation"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify review is flagged
        flagged_review = db.reviews.find_one({"id": review_id})
        assert flagged_review["status"] == "flagged"
        
        # Verify reputation was recalculated (flagged reviews excluded)
        response = requests.get(f"{BASE_URL}/api/reviews/reputation/{setup_test_data['seller_id']}")
        data = response.json()
        # Total should be reduced by 1 (flagged review excluded)
        assert data["total_reviews"] >= 2  # At least 2 active reviews remain
    
    def test_10_admin_unflag_review(self, admin_token, setup_test_data, db):
        """Test: Admin can unflag a review"""
        review = db.reviews.find_one({"transaction_id": setup_test_data["txn_id_3"]})
        review_id = review["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/reviews/{review_id}/unflag",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify review is active again
        unflagged_review = db.reviews.find_one({"id": review_id})
        assert unflagged_review["status"] == "active"
    
    def test_11_admin_delete_review(self, admin_token, setup_test_data, db):
        """Test: Admin can delete a review"""
        review = db.reviews.find_one({"transaction_id": setup_test_data["txn_id_3"]})
        review_id = review["id"]
        
        response = requests.delete(
            f"{BASE_URL}/api/reviews/{review_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify review is marked as removed
        removed_review = db.reviews.find_one({"id": review_id})
        assert removed_review["status"] == "removed"
    
    def test_12_moderation_pending_list(self, admin_token, setup_test_data, db):
        """Test: Admin can list flagged reviews"""
        # First flag a review
        review = db.reviews.find_one({"transaction_id": setup_test_data["txn_id_1"]})
        if review:
            db.reviews.update_one(
                {"id": review["id"]},
                {"$set": {"status": "flagged", "flagged_reason": "Test"}}
            )
        
        response = requests.get(
            f"{BASE_URL}/api/reviews/moderation/pending",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "reviews" in data
        assert "total" in data


class TestE2ESellerReviews:
    """E2E tests for seller reviews list"""
    
    def test_13_get_seller_reviews(self, setup_test_data):
        """Test: Get paginated reviews for seller"""
        response = requests.get(
            f"{BASE_URL}/api/reviews/seller/{setup_test_data['seller_id']}?page=1&limit=10"
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "reviews" in data
        assert "total" in data
        assert "page" in data
        assert data["page"] == 1
        
        # Verify only active reviews are returned
        for review in data["reviews"]:
            assert review["status"] == "active"


class TestE2ETransactionReview:
    """E2E tests for transaction review lookup"""
    
    def test_14_get_transaction_review(self, setup_test_data):
        """Test: Get review for specific transaction"""
        response = requests.get(
            f"{BASE_URL}/api/reviews/transaction/{setup_test_data['txn_id_2']}"
        )
        assert response.status_code == 200
        
        data = response.json()
        # Review exists for this transaction
        if data.get("review"):
            assert data["review"]["transaction_id"] == setup_test_data["txn_id_2"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
