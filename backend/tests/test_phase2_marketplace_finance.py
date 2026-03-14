"""
BidVex Phase 2 - Marketplace Sidebar Filter & Admin Finance Dashboard Tests
Tests for:
- GET /api/marketplace/filter-counts (sidebar filters)
- GET /api/multi-item-listings with city/seller_id params
- GET /api/admin/finance/revenue-summary
- GET /api/admin/finance/transactions
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "charbeladmin@bidvex.com",
        "password": "Admin123!"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Admin authentication failed")


class TestMarketplaceFilterCounts:
    """Test /api/marketplace/filter-counts endpoint - Sidebar Filters"""
    
    def test_filter_counts_returns_200(self):
        """Filter counts endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/marketplace/filter-counts")
        assert response.status_code == 200
        print(f"✓ Filter counts endpoint returned 200")
    
    def test_filter_counts_response_structure(self):
        """Filter counts should return auctioneers, categories, locations arrays"""
        response = requests.get(f"{BASE_URL}/api/marketplace/filter-counts")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "auctioneers" in data, "Response should contain 'auctioneers'"
        assert "categories" in data, "Response should contain 'categories'"
        assert "locations" in data, "Response should contain 'locations'"
        assert "total_active_items" in data, "Response should contain 'total_active_items'"
        
        # Verify types
        assert isinstance(data["auctioneers"], list), "auctioneers should be a list"
        assert isinstance(data["categories"], list), "categories should be a list"
        assert isinstance(data["locations"], list), "locations should be a list"
        assert isinstance(data["total_active_items"], int), "total_active_items should be int"
        
        print(f"✓ Filter counts structure correct: auctioneers={len(data['auctioneers'])}, categories={len(data['categories'])}, locations={len(data['locations'])}, total={data['total_active_items']}")


class TestMultiItemListingsFilters:
    """Test /api/multi-item-listings endpoint with sidebar filter params"""
    
    def test_multi_item_listings_basic(self):
        """Multi-item listings should return 200 with basic query"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Multi-item listings returned {len(data)} items")
    
    def test_multi_item_listings_city_filter(self):
        """Multi-item listings should accept city query param"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings?city=Montreal&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ City filter accepted, returned {len(data)} items")
    
    def test_multi_item_listings_seller_id_filter(self):
        """Multi-item listings should accept seller_id query param"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings?seller_id=test_seller&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Seller ID filter accepted, returned {len(data)} items")
    
    def test_multi_item_listings_multiple_seller_ids(self):
        """Multi-item listings should accept comma-separated seller_ids"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings?seller_id=seller1,seller2&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Multiple seller IDs filter accepted")
    
    def test_multi_item_listings_combined_filters(self):
        """Multi-item listings should accept combined filters"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings?city=Toronto&category=Furniture&search=chair&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Combined filters accepted")


class TestAdminFinanceRevenueSummary:
    """Test /api/admin/finance/revenue-summary endpoint"""
    
    def test_revenue_summary_requires_auth(self):
        """Revenue summary should require authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/finance/revenue-summary")
        assert response.status_code == 401, "Should require authentication"
        print(f"✓ Revenue summary requires auth (401)")
    
    def test_revenue_summary_returns_data(self, admin_token):
        """Revenue summary should return revenue breakdown for admin"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/revenue-summary",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Revenue summary returned 200")
        
    def test_revenue_summary_structure(self, admin_token):
        """Revenue summary should have correct structure with fee breakdown"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/revenue-summary",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check revenue section
        assert "revenue" in data, "Should have 'revenue' section"
        revenue = data["revenue"]
        assert "total_platform_fees" in revenue, "Should have total_platform_fees (3% Platform Fee)"
        assert "total_processing_fees" in revenue, "Should have total_processing_fees (Stripe Cost Recovery)"
        assert "subscription_revenue" in revenue, "Should have subscription_revenue"
        assert "total_hammer_volume" in revenue, "Should have total_hammer_volume"
        assert "total_buyer_premiums" in revenue, "Should have total_buyer_premiums"
        assert "total_transactions" in revenue, "Should have total_transactions"
        
        print(f"✓ Revenue section: platform_fees={revenue['total_platform_fees']}, processing_fees={revenue['total_processing_fees']}, subscriptions={revenue['subscription_revenue']}")
        
    def test_revenue_summary_partner_breakdown(self, admin_token):
        """Revenue summary should have partner revenue breakdown"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/revenue-summary",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "partner_revenue" in data, "Should have 'partner_revenue' section"
        pr = data["partner_revenue"]
        assert "hammer_volume" in pr, "Should have partner hammer_volume"
        assert "platform_fees_collected" in pr, "Should have 3% fees from partners"
        assert "buyer_premiums" in pr, "Should have partner buyer_premiums"
        assert "transaction_count" in pr, "Should have partner transaction_count"
        
        print(f"✓ Partner revenue breakdown: fees_collected={pr['platform_fees_collected']}, transactions={pr['transaction_count']}")
        
    def test_revenue_summary_user_counts(self, admin_token):
        """Revenue summary should include user account stats"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/revenue-summary",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "users" in data, "Should have 'users' section"
        users = data["users"]
        assert "total" in users, "Should have total users"
        assert "active_partners" in users, "Should have active_partners (Partners count)"
        assert "pending_partners" in users, "Should have pending_partners (Pending count)"
        
        print(f"✓ User accounts: total={users['total']}, partners={users['active_partners']}, pending={users['pending_partners']}")
        
    def test_revenue_summary_auction_stats(self, admin_token):
        """Revenue summary should include auction stats"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/revenue-summary",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "auctions" in data, "Should have 'auctions' section"
        auctions = data["auctions"]
        assert "active" in auctions, "Should have active auctions"
        assert "total" in auctions, "Should have total auctions"
        assert "partner_active" in auctions, "Should have partner_active"
        
        print(f"✓ Auctions: active={auctions['active']}, total={auctions['total']}, partner_active={auctions['partner_active']}")


class TestAdminFinanceTransactions:
    """Test /api/admin/finance/transactions endpoint"""
    
    def test_transactions_requires_auth(self):
        """Transactions log should require authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/finance/transactions")
        assert response.status_code == 401, "Should require authentication"
        print(f"✓ Transactions requires auth (401)")
    
    def test_transactions_returns_paginated(self, admin_token):
        """Transactions should return paginated results"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/transactions?page=1&limit=25",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "transactions" in data, "Should have 'transactions' list"
        assert "total" in data, "Should have 'total' count"
        assert "page" in data, "Should have 'page' number"
        assert "pages" in data, "Should have 'pages' total"
        
        print(f"✓ Transactions: total={data['total']}, page={data['page']}/{data['pages']}")
        
    def test_transactions_search_filter(self, admin_token):
        """Transactions should support search filter"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/transactions?search=test&page=1&limit=10",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "transactions" in data
        print(f"✓ Transaction search filter works")
        
    def test_transactions_partner_only_filter(self, admin_token):
        """Transactions should support partner_only filter"""
        response = requests.get(
            f"{BASE_URL}/api/admin/finance/transactions?partner_only=true&page=1&limit=10",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "transactions" in data
        print(f"✓ Partner-only filter works")


class TestAdminPartners:
    """Test /api/admin/partners endpoint"""
    
    def test_partners_list(self, admin_token):
        """Admin should be able to list partner applications"""
        response = requests.get(
            f"{BASE_URL}/api/admin/partners",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "applications" in data, "Should have 'applications' list"
        print(f"✓ Partner applications: {len(data['applications'])} found")
        
    def test_partners_filter_by_status(self, admin_token):
        """Admin should be able to filter partners by status"""
        for status in ["pending", "verified", "rejected"]:
            response = requests.get(
                f"{BASE_URL}/api/admin/partners?status={status}",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "applications" in data
            print(f"✓ Partner filter '{status}': {len(data['applications'])} found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
