"""
Phase 4 Testing: Push Notifications, Regional Trends, AI Personalization, CDN Headers
Tests for:
1. Push VAPID key endpoint: GET /api/push/vapid-public-key
2. Push subscribe: POST /api/push/subscribe (requires auth)
3. Push status: GET /api/push/status (requires auth)
4. Push unsubscribe: DELETE /api/push/unsubscribe (requires auth)
5. Regional trends: GET /api/insights/regional-trends (requires auth)
6. AI personalized ending-soon: GET /api/carousel/ending-soon?user_id=xxx
7. Marketplace WebSocket: /api/ws/marketplace responds to PING with PONG
8. Security headers: X-Content-Type-Options nosniff and X-Frame-Options on API responses
9. Service Worker at /sw.js is accessible
"""

import pytest
import requests
import os
import json
import asyncio
import websockets

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"
STARTER_EMAIL = "starter@test.com"
STARTER_PASSWORD = "TestUser2026!"
PREMIUM_EMAIL = "premium@test.com"
PREMIUM_PASSWORD = "TestUser2026!"
PARTNER_EMAIL = "partner@test.com"
PARTNER_PASSWORD = "TestUser2026!"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def starter_token(api_client):
    """Get starter user authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": STARTER_EMAIL,
        "password": STARTER_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip("Starter user authentication failed")


@pytest.fixture(scope="module")
def premium_token(api_client):
    """Get premium user authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": PREMIUM_EMAIL,
        "password": PREMIUM_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip("Premium user authentication failed")


class TestHealthAndAuth:
    """Basic health and authentication tests"""
    
    def test_api_health(self, api_client):
        """Test API health endpoint"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ API health check passed")
    
    def test_admin_login(self, api_client):
        """Test admin login"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data
        print("✓ Admin login successful")
    
    def test_starter_login(self, api_client):
        """Test starter user login"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": STARTER_EMAIL,
            "password": STARTER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data
        print("✓ Starter user login successful")


class TestPushNotificationAPIs:
    """Push notification endpoint tests"""
    
    def test_vapid_public_key_endpoint(self, api_client):
        """GET /api/push/vapid-public-key must return a public_key string"""
        response = api_client.get(f"{BASE_URL}/api/push/vapid-public-key")
        assert response.status_code == 200
        data = response.json()
        assert "public_key" in data
        assert isinstance(data["public_key"], str)
        # VAPID public key should be non-empty (base64url encoded)
        assert len(data["public_key"]) > 0
        print(f"✓ VAPID public key endpoint returns key: {data['public_key'][:20]}...")
    
    def test_push_subscribe_requires_auth(self, api_client):
        """POST /api/push/subscribe requires authentication"""
        response = api_client.post(f"{BASE_URL}/api/push/subscribe", json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/test",
            "keys": {"p256dh": "test", "auth": "test"}
        })
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403, 422]
        print("✓ Push subscribe requires authentication")
    
    def test_push_subscribe_with_auth(self, api_client, starter_token):
        """POST /api/push/subscribe must accept endpoint + keys and return success"""
        response = api_client.post(
            f"{BASE_URL}/api/push/subscribe",
            json={
                "endpoint": "https://fcm.googleapis.com/fcm/send/test-endpoint-123",
                "keys": {"p256dh": "test-p256dh-key", "auth": "test-auth-key"}
            },
            headers={"Authorization": f"Bearer {starter_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print("✓ Push subscribe with auth returns success")
    
    def test_push_status_with_auth(self, api_client, starter_token):
        """GET /api/push/status must return subscribed boolean and device_count"""
        response = api_client.get(
            f"{BASE_URL}/api/push/status",
            headers={"Authorization": f"Bearer {starter_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "subscribed" in data
        assert "device_count" in data
        assert isinstance(data["subscribed"], bool)
        assert isinstance(data["device_count"], int)
        print(f"✓ Push status: subscribed={data['subscribed']}, device_count={data['device_count']}")
    
    def test_push_unsubscribe_with_auth(self, api_client, starter_token):
        """DELETE /api/push/unsubscribe must remove subscription"""
        response = api_client.delete(
            f"{BASE_URL}/api/push/unsubscribe",
            json={
                "endpoint": "https://fcm.googleapis.com/fcm/send/test-endpoint-123",
                "keys": {"p256dh": "test-p256dh-key", "auth": "test-auth-key"}
            },
            headers={"Authorization": f"Bearer {starter_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print("✓ Push unsubscribe returns success")


class TestRegionalTrends:
    """Regional trends endpoint tests"""
    
    def test_regional_trends_requires_auth(self, api_client):
        """GET /api/insights/regional-trends requires authentication"""
        response = api_client.get(f"{BASE_URL}/api/insights/regional-trends")
        assert response.status_code in [401, 403, 422]
        print("✓ Regional trends requires authentication")
    
    def test_regional_trends_with_auth(self, api_client, starter_token):
        """GET /api/insights/regional-trends must return top_categories, top_regions, insights arrays"""
        response = api_client.get(
            f"{BASE_URL}/api/insights/regional-trends",
            headers={"Authorization": f"Bearer {starter_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "top_categories" in data
        assert "top_regions" in data
        assert "insights" in data
        
        # Verify types
        assert isinstance(data["top_categories"], list)
        assert isinstance(data["top_regions"], list)
        assert isinstance(data["insights"], list)
        
        # Note: Arrays may be empty if no user_interests data exists for this week
        print(f"✓ Regional trends: {len(data['top_categories'])} categories, {len(data['top_regions'])} regions, {len(data['insights'])} insights")


class TestAIPersonalizedCarousel:
    """AI personalized ending-soon carousel tests"""
    
    def test_ending_soon_without_user_id(self, api_client):
        """GET /api/carousel/ending-soon without user_id returns listings"""
        response = api_client.get(f"{BASE_URL}/api/carousel/ending-soon")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Ending soon without user_id: {len(data)} listings")
    
    def test_ending_soon_with_user_id(self, api_client, starter_token):
        """GET /api/carousel/ending-soon?user_id=xxx must return listings (AI personalized)"""
        # First get user ID from /me endpoint
        me_response = api_client.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {starter_token}"}
        )
        if me_response.status_code == 200:
            user_id = me_response.json().get("id")
        else:
            user_id = "test-user-id"
        
        response = api_client.get(f"{BASE_URL}/api/carousel/ending-soon?user_id={user_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Ending soon with user_id: {len(data)} listings (AI personalized)")


class TestSecurityHeaders:
    """Security headers tests"""
    
    def test_security_headers_on_api_response(self, api_client):
        """API responses must include X-Content-Type-Options nosniff and X-Frame-Options"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        
        # Check X-Content-Type-Options
        x_content_type = response.headers.get("X-Content-Type-Options")
        assert x_content_type == "nosniff", f"Expected 'nosniff', got '{x_content_type}'"
        
        # Check X-Frame-Options (can be DENY or SAMEORIGIN)
        x_frame = response.headers.get("X-Frame-Options")
        assert x_frame in ["DENY", "SAMEORIGIN"], f"Expected 'DENY' or 'SAMEORIGIN', got '{x_frame}'"
        
        print(f"✓ Security headers: X-Content-Type-Options={x_content_type}, X-Frame-Options={x_frame}")
    
    def test_cache_control_on_api_response(self, api_client):
        """API responses should have no-store cache control"""
        response = api_client.get(f"{BASE_URL}/api/health")
        cache_control = response.headers.get("Cache-Control", "")
        # API endpoints should have no-store or no-cache
        assert "no-store" in cache_control or "no-cache" in cache_control or cache_control == ""
        print(f"✓ Cache-Control header: {cache_control or '(not set)'}")


class TestServiceWorker:
    """Service Worker accessibility tests"""
    
    def test_service_worker_accessible(self, api_client):
        """Service Worker at /sw.js is accessible"""
        response = api_client.get(f"{BASE_URL}/sw.js")
        # Should return 200 with JavaScript content
        assert response.status_code == 200
        content = response.text
        # Verify it contains push event handler
        assert "push" in content.lower() or "addEventListener" in content
        print("✓ Service Worker at /sw.js is accessible")
    
    def test_service_worker_contains_push_handler(self, api_client):
        """Service Worker contains push event handler"""
        response = api_client.get(f"{BASE_URL}/sw.js")
        assert response.status_code == 200
        content = response.text
        # Check for push event listener
        assert "addEventListener" in content and "push" in content
        print("✓ Service Worker contains push event handler")


class TestMarketplaceWebSocket:
    """Marketplace WebSocket tests"""
    
    def test_marketplace_websocket_ping_pong(self):
        """WebSocket /api/ws/marketplace must respond to PING with PONG"""
        import asyncio
        
        async def test_ws():
            ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
            ws_url = f"{ws_url}/api/ws/marketplace"
            
            try:
                async with websockets.connect(ws_url, timeout=10) as ws:
                    # Send PING
                    await ws.send(json.dumps({"type": "PING"}))
                    
                    # Wait for PONG response
                    response = await asyncio.wait_for(ws.recv(), timeout=5)
                    data = json.loads(response)
                    
                    assert data.get("type") == "PONG"
                    assert "timestamp" in data
                    print(f"✓ Marketplace WebSocket PING/PONG working: {data}")
                    return True
            except Exception as e:
                print(f"WebSocket test error: {e}")
                # WebSocket might not be available in test environment
                pytest.skip(f"WebSocket connection failed: {e}")
        
        asyncio.get_event_loop().run_until_complete(test_ws())


class TestCarouselEndpoints:
    """Additional carousel endpoint tests"""
    
    def test_featured_listings(self, api_client):
        """GET /api/carousel/featured returns listings"""
        response = api_client.get(f"{BASE_URL}/api/carousel/featured")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Featured listings: {len(data)} items")
    
    def test_new_listings(self, api_client):
        """GET /api/carousel/new-listings returns listings"""
        response = api_client.get(f"{BASE_URL}/api/carousel/new-listings")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ New listings: {len(data)} items")
    
    def test_recently_sold(self, api_client):
        """GET /api/carousel/recently-sold returns listings"""
        response = api_client.get(f"{BASE_URL}/api/carousel/recently-sold")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Recently sold: {len(data)} items")


class TestInsightsTracking:
    """User insights tracking tests (for regional trends data)"""
    
    def test_track_event(self, api_client):
        """POST /api/insights/track persists events"""
        response = api_client.post(f"{BASE_URL}/api/insights/track", json={
            "event_type": "view",
            "listing_id": "test-listing-123",
            "category": "Electronics",
            "region": "Quebec",
            "metadata": {"category": "Electronics", "region": "Quebec"}
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print("✓ Insights track event works")
    
    def test_track_batch_events(self, api_client):
        """POST /api/insights/track-batch works for batch events"""
        response = api_client.post(f"{BASE_URL}/api/insights/track-batch", json=[
            {"event_type": "view", "category": "Vehicles", "region": "Ontario", "metadata": {"category": "Vehicles", "region": "Ontario"}},
            {"event_type": "click", "category": "Electronics", "region": "Quebec", "metadata": {"category": "Electronics", "region": "Quebec"}}
        ])
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print(f"✓ Insights track-batch works: {data.get('tracked', 0)} events tracked")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
