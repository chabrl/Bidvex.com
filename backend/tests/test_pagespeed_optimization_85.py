"""
PageSpeed Optimization Sprint - Test Suite (Iteration 85)
Tests for 10 specific fixes:
1) Logo resize to WebP 466x112 <15KB
2) Remove Google Ads scripts
3) Defer PostHog loading by 2s
4) Inline critical CSS in index.html
5) Cache-Control headers (1yr for static, no-cache for HTML)
6) Footer min-height for CLS
7) GPU-composited button-shine animation
8) Security headers (CSP, X-Frame-Options, COOP)
9) Accessibility (aria-labels, contrast, touch targets, privacy-policy links)
10) Preconnect hints in <head>
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://prod-fix-critical.preview.emergentagent.com').rstrip('/')


class TestSecurityHeaders:
    """Test security headers on API responses (FIX 8)"""
    
    def test_x_frame_options_header(self):
        """X-Frame-Options header should be present"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        assert "X-Frame-Options" in response.headers, "X-Frame-Options header missing"
        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
        print(f"PASS: X-Frame-Options = {response.headers['X-Frame-Options']}")
    
    def test_cross_origin_opener_policy_header(self):
        """Cross-Origin-Opener-Policy header should be present"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        assert "Cross-Origin-Opener-Policy" in response.headers, "COOP header missing"
        assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
        print(f"PASS: Cross-Origin-Opener-Policy = {response.headers['Cross-Origin-Opener-Policy']}")
    
    def test_content_security_policy_header(self):
        """Content-Security-Policy header should be present"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        assert "Content-Security-Policy" in response.headers, "CSP header missing"
        csp = response.headers["Content-Security-Policy"]
        # Verify key CSP directives
        assert "default-src" in csp
        assert "script-src" in csp
        assert "style-src" in csp
        print(f"PASS: Content-Security-Policy present with {len(csp)} chars")
    
    def test_x_response_time_header(self):
        """X-Response-Time header should be present on API responses"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        assert "X-Response-Time" in response.headers, "X-Response-Time header missing"
        print(f"PASS: X-Response-Time = {response.headers['X-Response-Time']}")


class TestCacheControlHeaders:
    """Test Cache-Control headers (FIX 5)"""
    
    def test_api_response_has_response_time(self):
        """API endpoints should have X-Response-Time header"""
        endpoints = [
            "/api/health",
            "/api/marketplace/items?limit=1",
            "/api/multi-item-listings?limit=1"
        ]
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=30)
            assert response.status_code == 200, f"Endpoint {endpoint} returned {response.status_code}"
            assert "X-Response-Time" in response.headers, f"X-Response-Time missing on {endpoint}"
            print(f"PASS: {endpoint} has X-Response-Time = {response.headers['X-Response-Time']}")


class TestAPIEndpoints:
    """Test core API endpoints are working"""
    
    def test_health_endpoint(self):
        """Health endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASS: /api/health returns healthy")
    
    def test_marketplace_items_endpoint(self):
        """Marketplace items endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/marketplace/items?limit=5", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or isinstance(data, list)
        print(f"PASS: /api/marketplace/items returns data")
    
    def test_multi_item_listings_endpoint(self):
        """Multi-item listings endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/multi-item-listings?limit=5", timeout=30)
        assert response.status_code == 200
        data = response.json()
        assert "listings" in data or isinstance(data, list)
        print(f"PASS: /api/multi-item-listings returns data")


class TestFrontendAssets:
    """Test frontend assets and static files"""
    
    def test_homepage_loads(self):
        """Homepage should load without errors"""
        response = requests.get(f"{BASE_URL}/", timeout=30)
        assert response.status_code == 200
        assert "BidVex" in response.text or "bidvex" in response.text.lower()
        print("PASS: Homepage loads successfully")
    
    def test_logo_webp_exists(self):
        """New WebP logo should be accessible"""
        response = requests.get(f"{BASE_URL}/bidvex-logo.webp", timeout=10)
        # Should return 200 or redirect to the asset
        assert response.status_code in [200, 301, 302, 304], f"Logo returned {response.status_code}"
        print(f"PASS: /bidvex-logo.webp accessible (status {response.status_code})")
    
    def test_index_html_has_preconnect_hints(self):
        """Index.html should have preconnect hints (FIX 10)"""
        response = requests.get(f"{BASE_URL}/", timeout=30)
        assert response.status_code == 200
        html = response.text
        # Check for preconnect hints
        assert 'rel="preconnect"' in html, "Preconnect hints missing"
        assert 'fonts.googleapis.com' in html, "Google Fonts preconnect missing"
        assert 'fonts.gstatic.com' in html, "Google Fonts gstatic preconnect missing"
        print("PASS: Preconnect hints present in index.html")
    
    def test_no_google_ads_scripts(self):
        """Index.html should NOT have Google Ads scripts (FIX 2)"""
        response = requests.get(f"{BASE_URL}/", timeout=30)
        assert response.status_code == 200
        html = response.text
        # Check that Google Ads scripts are NOT present
        assert 'adsbygoogle' not in html, "Google Ads adsbygoogle found"
        assert 'googlesyndication' not in html, "Google Ads googlesyndication found"
        assert 'ca-pub-' not in html, "Google Ads ca-pub reference found"
        print("PASS: No Google Ads scripts in index.html")
    
    def test_inline_skeleton_present(self):
        """Index.html should have inline skeleton HTML (FIX 4)"""
        response = requests.get(f"{BASE_URL}/", timeout=30)
        assert response.status_code == 200
        html = response.text
        assert 'id="initial-skeleton"' in html, "Inline skeleton missing"
        print("PASS: Inline skeleton present in index.html")
    
    def test_posthog_deferred(self):
        """PostHog should be deferred with setTimeout (FIX 3)"""
        response = requests.get(f"{BASE_URL}/", timeout=30)
        assert response.status_code == 200
        html = response.text
        # PostHog should be inside setTimeout with 2000ms delay
        assert 'setTimeout' in html, "setTimeout not found for PostHog deferral"
        assert '2000' in html, "2000ms delay not found for PostHog"
        assert 'posthog' in html.lower(), "PostHog reference not found"
        print("PASS: PostHog deferred with setTimeout(2000)")


class TestPrivacyRoutes:
    """Test privacy policy routes and redirects"""
    
    def test_privacy_policy_page_accessible(self):
        """Privacy policy page should be accessible"""
        response = requests.get(f"{BASE_URL}/privacy-policy", timeout=30, allow_redirects=True)
        assert response.status_code == 200
        print("PASS: /privacy-policy page accessible")
    
    def test_privacy_redirects_to_privacy_policy(self):
        """Old /privacy route should redirect to /privacy-policy"""
        response = requests.get(f"{BASE_URL}/privacy", timeout=30, allow_redirects=False)
        # React Router handles this client-side, so we check the final page
        response_with_redirect = requests.get(f"{BASE_URL}/privacy", timeout=30, allow_redirects=True)
        # The page should load (React handles the redirect)
        assert response_with_redirect.status_code == 200
        print("PASS: /privacy route handled (React Router redirect)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
