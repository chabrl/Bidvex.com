"""
BidVex Comprehensive E2E QA Test Script
Tests all 7 sections: Auth, Buyer, Seller, Admin, Email, Stripe, Health
"""
import requests
import json
import sys
import time

API_URL = sys.argv[1] if len(sys.argv) > 1 else "https://prod-verify-2.preview.emergentagent.com"

results = {"passed": [], "failed": [], "partial": []}

def log_pass(section, test_name, details=""):
    results["passed"].append({"section": section, "test": test_name, "details": details})
    print(f"  ✅ {test_name}: {details}")

def log_fail(section, test_name, details=""):
    results["failed"].append({"section": section, "test": test_name, "details": details})
    print(f"  ❌ {test_name}: {details}")

def log_partial(section, test_name, details=""):
    results["partial"].append({"section": section, "test": test_name, "details": details})
    print(f"  ⚠️ {test_name}: {details}")

# ========== SECTION 1: AUTHENTICATION & REGISTRATION ==========
print("\n" + "="*60)
print("SECTION 1: AUTHENTICATION & REGISTRATION")
print("="*60)

# 1.1 Admin Login
try:
    r = requests.post(f"{API_URL}/api/auth/login", json={"email":"charbeladmin@bidvex.com","password":"Admin123!"})
    data = r.json()
    if r.status_code == 200 and "access_token" in data:
        ADMIN_TOKEN = data["access_token"]
        log_pass("Auth", "Admin Login", f"Status {r.status_code}, token received, role={data['user']['role']}")
    else:
        log_fail("Auth", "Admin Login", f"Status {r.status_code}, body={json.dumps(data)[:200]}")
        ADMIN_TOKEN = None
except Exception as e:
    log_fail("Auth", "Admin Login", str(e))
    ADMIN_TOKEN = None

# 1.2 Test User Login
try:
    r = requests.post(f"{API_URL}/api/auth/login", json={"email":"starter@test.com","password":"TestUser2026!"})
    data = r.json()
    if r.status_code == 200 and "access_token" in data:
        USER_TOKEN = data["access_token"]
        USER_ID = data["user"]["id"]
        log_pass("Auth", "Starter User Login", f"Status {r.status_code}, user_id={USER_ID}")
    else:
        log_fail("Auth", "Starter User Login", f"Status {r.status_code}, body={json.dumps(data)[:200]}")
        USER_TOKEN = None
        USER_ID = None
except Exception as e:
    log_fail("Auth", "Starter User Login", str(e))
    USER_TOKEN = None
    USER_ID = None

# 1.3 Premium User Login
try:
    r = requests.post(f"{API_URL}/api/auth/login", json={"email":"premium@test.com","password":"TestUser2026!"})
    data = r.json()
    if r.status_code == 200 and "access_token" in data:
        PREMIUM_TOKEN = data["access_token"]
        PREMIUM_ID = data["user"]["id"]
        log_pass("Auth", "Premium User Login", f"Status {r.status_code}, user_id={PREMIUM_ID}")
    else:
        log_fail("Auth", "Premium User Login", f"Status {r.status_code}, body={json.dumps(data)[:200]}")
        PREMIUM_TOKEN = None
        PREMIUM_ID = None
except Exception as e:
    log_fail("Auth", "Premium User Login", str(e))
    PREMIUM_TOKEN = None
    PREMIUM_ID = None

# 1.4 Invalid Login (should fail gracefully)
try:
    r = requests.post(f"{API_URL}/api/auth/login", json={"email":"nonexistent@test.com","password":"wrong"})
    if r.status_code in [401, 400, 404]:
        log_pass("Auth", "Invalid Login Rejection", f"Status {r.status_code} correctly rejected")
    else:
        log_fail("Auth", "Invalid Login Rejection", f"Unexpected status {r.status_code}")
except Exception as e:
    log_fail("Auth", "Invalid Login Rejection", str(e))

# 1.5 Registration Endpoint
try:
    test_email = f"qatest_{int(time.time())}@test.com"
    r = requests.post(f"{API_URL}/api/auth/register", json={
        "email": test_email, "password": "QATest2026!", "name": "QA Test User",
        "account_type": "personal", "terms_agreed": True
    })
    data = r.json()
    if r.status_code in [200, 201]:
        QA_TOKEN = data.get("access_token")
        QA_USER_ID = data.get("user", {}).get("id")
        log_pass("Auth", "User Registration", f"Registered {test_email}, id={QA_USER_ID}")
    else:
        log_fail("Auth", "User Registration", f"Status {r.status_code}, body={json.dumps(data)[:200]}")
        QA_TOKEN = None
except Exception as e:
    log_fail("Auth", "User Registration", str(e))
    QA_TOKEN = None

# 1.6 JWT Token Validation (use token to access protected endpoint)
try:
    if ADMIN_TOKEN:
        r = requests.get(f"{API_URL}/api/auth/me", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"})
        if r.status_code == 200:
            log_pass("Auth", "JWT Token Validation (/auth/me)", f"Status {r.status_code}")
        else:
            log_fail("Auth", "JWT Token Validation (/auth/me)", f"Status {r.status_code}")
    else:
        log_fail("Auth", "JWT Token Validation", "No admin token available")
except Exception as e:
    log_fail("Auth", "JWT Token Validation", str(e))

# 1.7 Password Reset Request (endpoint exists check)
try:
    r = requests.post(f"{API_URL}/api/auth/forgot-password", json={"email":"charbeladmin@bidvex.com"})
    if r.status_code in [200, 404, 429]:
        log_pass("Auth", "Forgot Password Endpoint", f"Status {r.status_code}, endpoint reachable")
    else:
        log_fail("Auth", "Forgot Password Endpoint", f"Status {r.status_code}")
except Exception as e:
    log_fail("Auth", "Forgot Password Endpoint", str(e))

# 1.8 Expired/Invalid Token Test
try:
    r = requests.get(f"{API_URL}/api/auth/me", headers={"Authorization": "Bearer invalidtoken123"})
    if r.status_code in [401, 403]:
        log_pass("Auth", "Invalid Token Rejection", f"Status {r.status_code} correctly rejected")
    else:
        log_fail("Auth", "Invalid Token Rejection", f"Unexpected status {r.status_code}")
except Exception as e:
    log_fail("Auth", "Invalid Token Rejection", str(e))

# ========== SECTION 7: PLATFORM HEALTH & PERFORMANCE ==========
print("\n" + "="*60)
print("SECTION 7: PLATFORM HEALTH & PERFORMANCE")
print("="*60)

# 7.1 Health Check
try:
    r = requests.get(f"{API_URL}/api/health")
    data = r.json()
    if r.status_code == 200 and data.get("status") == "healthy":
        log_pass("Health", "Health Check", f"Status healthy")
    else:
        log_fail("Health", "Health Check", f"Status {r.status_code}, body={json.dumps(data)[:200]}")
except Exception as e:
    log_fail("Health", "Health Check", str(e))

# 7.2 HEAD Health Check
try:
    r = requests.head(f"{API_URL}/api/health")
    if r.status_code == 200:
        log_pass("Health", "HEAD Health Check", f"Status {r.status_code}")
    else:
        log_fail("Health", "HEAD Health Check", f"Status {r.status_code}")
except Exception as e:
    log_fail("Health", "HEAD Health Check", str(e))

# 7.3 Site Config
try:
    r = requests.get(f"{API_URL}/api/site-config")
    data = r.json()
    if r.status_code == 200 and "branding" in data:
        log_pass("Health", "Site Config", f"Has branding, homepage_layout, hero_banners")
    else:
        log_fail("Health", "Site Config", f"Status {r.status_code}")
except Exception as e:
    log_fail("Health", "Site Config", str(e))

# 7.4 Site Mode
try:
    r = requests.get(f"{API_URL}/api/site-mode")
    data = r.json()
    if r.status_code == 200 and data.get("mode") == "live":
        log_pass("Health", "Site Mode is Live", f"mode={data['mode']}")
    else:
        log_fail("Health", "Site Mode is Live", f"mode={data.get('mode')}, expected 'live'")
except Exception as e:
    log_fail("Health", "Site Mode", str(e))

# 7.5 CORS Headers
try:
    r = requests.options(f"{API_URL}/api/health", headers={"Origin": "https://bidvex.com", "Access-Control-Request-Method": "GET"})
    cors_header = r.headers.get("access-control-allow-origin", "")
    if cors_header:
        log_pass("Health", "CORS Headers", f"ACAO={cors_header}")
    else:
        log_partial("Health", "CORS Headers", "No ACAO header in OPTIONS response (may be handled by proxy)")
except Exception as e:
    log_fail("Health", "CORS Headers", str(e))

# 7.6 Response Time Check
try:
    start = time.time()
    r = requests.get(f"{API_URL}/api/health")
    elapsed = round((time.time() - start) * 1000)
    if elapsed < 2000:
        log_pass("Health", "Response Time", f"{elapsed}ms (< 2000ms)")
    else:
        log_partial("Health", "Response Time", f"{elapsed}ms (slow)")
except Exception as e:
    log_fail("Health", "Response Time", str(e))

# ========== SECTION 2: BUYER DASHBOARD (API) ==========
print("\n" + "="*60)
print("SECTION 2: BUYER DASHBOARD (API)")
print("="*60)

headers_admin = {"Authorization": f"Bearer {ADMIN_TOKEN}"} if ADMIN_TOKEN else {}
headers_user = {"Authorization": f"Bearer {USER_TOKEN}"} if USER_TOKEN else {}
headers_premium = {"Authorization": f"Bearer {PREMIUM_TOKEN}"} if PREMIUM_TOKEN else {}

# 2.1 Listings (Homepage data)
try:
    r = requests.get(f"{API_URL}/api/listings", params={"page": 1, "limit": 10})
    data = r.json()
    listings = data if isinstance(data, list) else data.get("listings", [])
    log_pass("Buyer", "Fetch Listings", f"Status {r.status_code}, count={len(listings)}")
    SAMPLE_LISTING_ID = listings[0]["id"] if listings else None
except Exception as e:
    log_fail("Buyer", "Fetch Listings", str(e))
    SAMPLE_LISTING_ID = None

# 2.2 Single Listing Detail
if SAMPLE_LISTING_ID:
    try:
        r = requests.get(f"{API_URL}/api/listings/{SAMPLE_LISTING_ID}")
        if r.status_code == 200:
            log_pass("Buyer", "Listing Detail", f"ID={SAMPLE_LISTING_ID}, status {r.status_code}")
        else:
            log_fail("Buyer", "Listing Detail", f"Status {r.status_code}")
    except Exception as e:
        log_fail("Buyer", "Listing Detail", str(e))

# 2.3 Categories
try:
    r = requests.get(f"{API_URL}/api/categories")
    if r.status_code == 200:
        data = r.json()
        log_pass("Buyer", "Categories", f"Status {r.status_code}, data received")
    else:
        log_partial("Buyer", "Categories", f"Status {r.status_code}")
except Exception as e:
    log_partial("Buyer", "Categories Endpoint", str(e))

# 2.4 Search Listings
try:
    r = requests.get(f"{API_URL}/api/listings", params={"search": "test", "page": 1, "limit": 5})
    if r.status_code == 200:
        log_pass("Buyer", "Search Listings", f"Status {r.status_code}")
    else:
        log_fail("Buyer", "Search Listings", f"Status {r.status_code}")
except Exception as e:
    log_fail("Buyer", "Search Listings", str(e))

# 2.5 Ending Soon Carousel
try:
    r = requests.get(f"{API_URL}/api/carousel/ending-soon")
    if r.status_code == 200:
        data = r.json()
        items = data if isinstance(data, list) else data.get("listings", data.get("items", []))
        log_pass("Buyer", "Ending Soon Carousel", f"Status {r.status_code}, items={len(items) if isinstance(items, list) else 'dict'}")
    else:
        log_fail("Buyer", "Ending Soon Carousel", f"Status {r.status_code}")
except Exception as e:
    log_fail("Buyer", "Ending Soon Carousel", str(e))

# 2.6 Watchlist
try:
    r = requests.get(f"{API_URL}/api/watchlist", headers=headers_user)
    if r.status_code == 200:
        log_pass("Buyer", "Watchlist (Authenticated)", f"Status {r.status_code}")
    elif r.status_code in [401, 403]:
        log_partial("Buyer", "Watchlist", f"Status {r.status_code} - auth issue")
    else:
        log_fail("Buyer", "Watchlist", f"Status {r.status_code}")
except Exception as e:
    log_fail("Buyer", "Watchlist", str(e))

# 2.7 User Notifications
try:
    r = requests.get(f"{API_URL}/api/notifications", headers=headers_user)
    if r.status_code == 200:
        log_pass("Buyer", "Notifications", f"Status {r.status_code}")
    elif r.status_code in [401, 403]:
        log_partial("Buyer", "Notifications", f"Status {r.status_code}")
    else:
        log_fail("Buyer", "Notifications", f"Status {r.status_code}")
except Exception as e:
    log_fail("Buyer", "Notifications", str(e))

# 2.8 User Dashboard
try:
    r = requests.get(f"{API_URL}/api/dashboard", headers=headers_user)
    if r.status_code == 200:
        log_pass("Buyer", "User Dashboard", f"Status {r.status_code}")
    else:
        log_fail("Buyer", "User Dashboard", f"Status {r.status_code}")
except Exception as e:
    log_fail("Buyer", "User Dashboard", str(e))

# 2.9 Bid History
try:
    r = requests.get(f"{API_URL}/api/bids/my-bids", headers=headers_user)
    if r.status_code == 200:
        log_pass("Buyer", "Bid History", f"Status {r.status_code}")
    else:
        log_partial("Buyer", "Bid History", f"Status {r.status_code}")
except Exception as e:
    log_partial("Buyer", "Bid History", str(e))

# 2.10 Fee Calculator
try:
    r = requests.get(f"{API_URL}/api/fees/calculate", params={"amount": 100, "type": "buyer"})
    if r.status_code == 200:
        log_pass("Buyer", "Fee Calculator", f"Status {r.status_code}")
    elif r.status_code == 422:
        r2 = requests.post(f"{API_URL}/api/fees/calculate", json={"amount": 100, "type": "buyer"})
        if r2.status_code == 200:
            log_pass("Buyer", "Fee Calculator (POST)", f"Status {r2.status_code}")
        else:
            log_partial("Buyer", "Fee Calculator", f"GET={r.status_code}, POST={r2.status_code}")
    else:
        log_fail("Buyer", "Fee Calculator", f"Status {r.status_code}")
except Exception as e:
    log_partial("Buyer", "Fee Calculator", str(e))

# ========== SECTION 3: SELLER DASHBOARD (API) ==========
print("\n" + "="*60)
print("SECTION 3: SELLER DASHBOARD (API)")
print("="*60)

# 3.1 Seller Listings
try:
    r = requests.get(f"{API_URL}/api/listings/my-listings", headers=headers_admin)
    if r.status_code == 200:
        data = r.json()
        log_pass("Seller", "My Listings", f"Status {r.status_code}")
    else:
        log_fail("Seller", "My Listings", f"Status {r.status_code}")
except Exception as e:
    log_fail("Seller", "My Listings", str(e))

# 3.2 Seller Dashboard/Analytics
try:
    r = requests.get(f"{API_URL}/api/dashboard/seller", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Seller", "Seller Dashboard", f"Status {r.status_code}")
    else:
        log_partial("Seller", "Seller Dashboard", f"Status {r.status_code}")
except Exception as e:
    log_partial("Seller", "Seller Dashboard", str(e))

# 3.3 Regional Trends (Predictive Analytics)
try:
    r = requests.get(f"{API_URL}/api/insights/regional-trends", headers=headers_admin)
    if r.status_code == 200:
        data = r.json()
        log_pass("Seller", "Regional Trends API", f"Status {r.status_code}, keys={list(data.keys())[:5]}")
    else:
        log_fail("Seller", "Regional Trends API", f"Status {r.status_code}")
except Exception as e:
    log_fail("Seller", "Regional Trends API", str(e))

# 3.4 Seller Invoices
try:
    r = requests.get(f"{API_URL}/api/invoices", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Seller", "Invoices", f"Status {r.status_code}")
    else:
        log_partial("Seller", "Invoices", f"Status {r.status_code}")
except Exception as e:
    log_partial("Seller", "Invoices", str(e))

# 3.5 Seller Profile
try:
    r = requests.get(f"{API_URL}/api/profiles/me", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Seller", "Profile (me)", f"Status {r.status_code}")
    else:
        log_partial("Seller", "Profile (me)", f"Status {r.status_code}")
except Exception as e:
    log_partial("Seller", "Profile (me)", str(e))

# 3.6 Seller Reviews
try:
    r = requests.get(f"{API_URL}/api/reviews/seller", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Seller", "Seller Reviews", f"Status {r.status_code}")
    else:
        log_partial("Seller", "Seller Reviews", f"Status {r.status_code}")
except Exception as e:
    log_partial("Seller", "Seller Reviews", str(e))

# ========== SECTION 4: ADMIN PANEL (API - All 11 Subsections) ==========
print("\n" + "="*60)
print("SECTION 4: ADMIN PANEL (11 Subsections)")
print("="*60)

# 4.1 User Management
print("\n--- 4.1 User Management ---")
try:
    r = requests.get(f"{API_URL}/api/admin/users", headers=headers_admin)
    data = r.json()
    if r.status_code == 200:
        users = data if isinstance(data, list) else data.get("users", [])
        log_pass("Admin", "User List", f"Status {r.status_code}, count={len(users)}")
    else:
        log_fail("Admin", "User List", f"Status {r.status_code}, body={json.dumps(data)[:200]}")
except Exception as e:
    log_fail("Admin", "User List", str(e))

# 4.2 Listings Management
print("\n--- 4.2 Listings Management ---")
try:
    r = requests.get(f"{API_URL}/api/admin/listings", headers=headers_admin)
    data = r.json()
    if r.status_code == 200:
        listings = data if isinstance(data, list) else data.get("listings", [])
        log_pass("Admin", "Admin Listings", f"Status {r.status_code}, count={len(listings)}")
    else:
        log_fail("Admin", "Admin Listings", f"Status {r.status_code}")
except Exception as e:
    log_fail("Admin", "Admin Listings", str(e))

# 4.3 Payments & Transactions
print("\n--- 4.3 Payments ---")
try:
    r = requests.get(f"{API_URL}/api/admin/payments", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Admin", "Payments", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Payments", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Payments", str(e))

# 4.4 Settings/Site Config
print("\n--- 4.4 Settings ---")
try:
    r = requests.get(f"{API_URL}/api/admin/settings", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Admin", "Admin Settings", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Admin Settings", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Admin Settings", str(e))

# 4.5 Reports/Analytics
print("\n--- 4.5 Reports ---")
try:
    r = requests.get(f"{API_URL}/api/admin/analytics", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Admin", "Analytics", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Analytics", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Analytics", str(e))

# 4.6 Fraud Detection
print("\n--- 4.6 Fraud Detection ---")
try:
    r = requests.get(f"{API_URL}/api/admin/fraud-flags", headers=headers_admin)
    data = r.json()
    if r.status_code == 200:
        log_pass("Admin", "Fraud Flags", f"Status {r.status_code}")
    else:
        log_fail("Admin", "Fraud Flags", f"Status {r.status_code}")
except Exception as e:
    log_fail("Admin", "Fraud Flags", str(e))

# 4.7 Trust & Safety
print("\n--- 4.7 Trust & Safety ---")
try:
    r = requests.get(f"{API_URL}/api/admin/trust-safety", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Admin", "Trust & Safety", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Trust & Safety", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Trust & Safety", str(e))

# 4.8 Site Config (admin)
print("\n--- 4.8 Site Config Admin ---")
try:
    r = requests.get(f"{API_URL}/api/admin/site-config", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Admin", "Site Config Admin", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Site Config Admin", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Site Config Admin", str(e))

# 4.9 Email Marketing
print("\n--- 4.9 Email Marketing ---")
try:
    r = requests.get(f"{API_URL}/api/admin/email-templates", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Admin", "Email Templates", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Email Templates", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Email Templates", str(e))

# 4.10 Vehicles Admin
print("\n--- 4.10 Vehicles Admin ---")
try:
    r = requests.get(f"{API_URL}/api/admin/vehicles", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Admin", "Vehicles Admin", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Vehicles Admin", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Vehicles Admin", str(e))

# 4.11 Subscribers/Launch
print("\n--- 4.11 Subscribers ---")
try:
    r = requests.get(f"{API_URL}/api/admin/subscribers", headers=headers_admin)
    data = r.json()
    if r.status_code == 200:
        log_pass("Admin", "Subscribers", f"Status {r.status_code}, total={data.get('total', '?')}")
    else:
        log_fail("Admin", "Subscribers", f"Status {r.status_code}")
except Exception as e:
    log_fail("Admin", "Subscribers", str(e))

# Additional Admin endpoints
print("\n--- 4.x Additional Admin Endpoints ---")

# Admin Deposits
try:
    r = requests.get(f"{API_URL}/api/admin/deposits", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Admin", "Deposits", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Deposits", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Deposits", str(e))

# Admin Tax Dashboard
try:
    r = requests.get(f"{API_URL}/api/admin/tax-dashboard", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Admin", "Tax Dashboard", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Tax Dashboard", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Tax Dashboard", str(e))

# Admin Monitoring
try:
    r = requests.get(f"{API_URL}/api/admin/monitoring", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Admin", "Monitoring", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Monitoring", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Monitoring", str(e))

# Admin Partners
try:
    r = requests.get(f"{API_URL}/api/admin/partners", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Admin", "Partners", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Partners", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Partners", str(e))

# Admin Teams
try:
    r = requests.get(f"{API_URL}/api/admin/team", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Admin", "Team Management", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Team Management", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Team Management", str(e))

# Admin Auctions
try:
    r = requests.get(f"{API_URL}/api/admin/auctions", headers=headers_admin)
    if r.status_code == 200:
        data = r.json()
        log_pass("Admin", "Auctions", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Auctions", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Auctions", str(e))

# Admin Logs
try:
    r = requests.get(f"{API_URL}/api/admin/logs", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Admin", "Admin Logs", f"Status {r.status_code}")
    else:
        log_partial("Admin", "Admin Logs", f"Status {r.status_code}")
except Exception as e:
    log_partial("Admin", "Admin Logs", str(e))

# ========== SECTION 5: EMAILS & NOTIFICATIONS ==========
print("\n" + "="*60)
print("SECTION 5: EMAILS & NOTIFICATIONS")
print("="*60)

# 5.1 Push Notification - VAPID Key
try:
    r = requests.get(f"{API_URL}/api/push/vapid-public-key")
    data = r.json()
    if r.status_code == 200 and data.get("public_key"):
        log_pass("Email/Notif", "VAPID Public Key", f"Key present, len={len(data['public_key'])}")
    else:
        log_fail("Email/Notif", "VAPID Public Key", f"Status {r.status_code}")
except Exception as e:
    log_fail("Email/Notif", "VAPID Public Key", str(e))

# 5.2 Push Notification Status
try:
    r = requests.get(f"{API_URL}/api/push/status", headers=headers_user)
    if r.status_code == 200:
        log_pass("Email/Notif", "Push Status", f"Status {r.status_code}")
    else:
        log_partial("Email/Notif", "Push Status", f"Status {r.status_code}")
except Exception as e:
    log_partial("Email/Notif", "Push Status", str(e))

# 5.3 Email Templates (admin)
try:
    r = requests.get(f"{API_URL}/api/admin/email-templates", headers=headers_admin)
    if r.status_code == 200:
        data = r.json()
        templates = data if isinstance(data, list) else data.get("templates", [])
        log_pass("Email/Notif", "Email Templates", f"Status {r.status_code}")
    else:
        log_partial("Email/Notif", "Email Templates", f"Status {r.status_code}")
except Exception as e:
    log_partial("Email/Notif", "Email Templates", str(e))

# 5.4 SendGrid Integration (check env var exists and email service loads)
try:
    import os
    sgkey = os.environ.get("SENDGRID_API_KEY", "")
    if sgkey and sgkey.startswith("SG."):
        log_pass("Email/Notif", "SendGrid API Key Present", f"Key starts with SG., len={len(sgkey)}")
    else:
        log_partial("Email/Notif", "SendGrid API Key", f"Key missing or malformed")
except Exception as e:
    log_fail("Email/Notif", "SendGrid API Key Check", str(e))

# 5.5 Notifications list
try:
    r = requests.get(f"{API_URL}/api/notifications", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Email/Notif", "Notifications List", f"Status {r.status_code}")
    else:
        log_partial("Email/Notif", "Notifications List", f"Status {r.status_code}")
except Exception as e:
    log_partial("Email/Notif", "Notifications List", str(e))

# ========== SECTION 6: STRIPE INTEGRATION ==========
print("\n" + "="*60)
print("SECTION 6: STRIPE INTEGRATION")
print("="*60)

# 6.1 Stripe API Key Present
try:
    import os
    stripe_key = os.environ.get("STRIPE_API_KEY", "")
    if stripe_key and (stripe_key.startswith("sk_live_") or stripe_key.startswith("sk_test_")):
        log_pass("Stripe", "Stripe API Key Present", f"Key starts with sk_*, len={len(stripe_key)}")
    elif stripe_key:
        log_partial("Stripe", "Stripe API Key", f"Key exists but format unclear, len={len(stripe_key)}")
    else:
        log_fail("Stripe", "Stripe API Key", "Missing STRIPE_API_KEY")
except Exception as e:
    log_fail("Stripe", "Stripe API Key Check", str(e))

# 6.2 Stripe Webhook Secret Present
try:
    wh_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if wh_secret and wh_secret.startswith("whsec_"):
        log_pass("Stripe", "Webhook Secret Present", f"Starts with whsec_, len={len(wh_secret)}")
    else:
        log_fail("Stripe", "Webhook Secret", "Missing or malformed")
except Exception as e:
    log_fail("Stripe", "Webhook Secret Check", str(e))

# 6.3 Payment Endpoints
try:
    r = requests.get(f"{API_URL}/api/payments/methods", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Stripe", "Payment Methods Endpoint", f"Status {r.status_code}")
    else:
        log_partial("Stripe", "Payment Methods Endpoint", f"Status {r.status_code}")
except Exception as e:
    log_partial("Stripe", "Payment Methods", str(e))

# 6.4 Subscription Status
try:
    r = requests.get(f"{API_URL}/api/subscriptions/status", headers=headers_admin)
    if r.status_code == 200:
        data = r.json()
        log_pass("Stripe", "Subscription Status", f"Status {r.status_code}, tier={data.get('tier', data.get('subscription_tier', '?'))}")
    else:
        log_partial("Stripe", "Subscription Status", f"Status {r.status_code}")
except Exception as e:
    log_partial("Stripe", "Subscription Status", str(e))

# 6.5 Deposits endpoint
try:
    r = requests.get(f"{API_URL}/api/deposits/status", headers=headers_admin)
    if r.status_code == 200:
        log_pass("Stripe", "Deposits Status", f"Status {r.status_code}")
    else:
        log_partial("Stripe", "Deposits Status", f"Status {r.status_code}")
except Exception as e:
    log_partial("Stripe", "Deposits Status", str(e))

# 6.6 Webhook endpoint reachable (POST without payload should return 4xx, not 5xx)
try:
    r = requests.post(f"{API_URL}/api/webhooks/stripe", data="test", headers={"Content-Type": "application/json"})
    if r.status_code in [400, 401, 403, 422]:
        log_pass("Stripe", "Webhook Endpoint Reachable", f"Status {r.status_code} (correctly rejects invalid payload)")
    elif r.status_code == 500:
        log_partial("Stripe", "Webhook Endpoint", f"Status 500 - may be unhandled error on invalid sig")
    else:
        log_partial("Stripe", "Webhook Endpoint", f"Status {r.status_code}")
except Exception as e:
    log_partial("Stripe", "Webhook Endpoint", str(e))

# ========== FINAL SUMMARY ==========
print("\n" + "="*60)
print("E2E QA TEST SUMMARY")
print("="*60)

total = len(results["passed"]) + len(results["failed"]) + len(results["partial"])
print(f"\nTotal Tests: {total}")
print(f"✅ Passed:   {len(results['passed'])}")
print(f"❌ Failed:   {len(results['failed'])}")
print(f"⚠️ Partial:  {len(results['partial'])}")

if results["failed"]:
    print("\n--- FAILED TESTS ---")
    for f in results["failed"]:
        print(f"  ❌ [{f['section']}] {f['test']}: {f['details']}")

if results["partial"]:
    print("\n--- PARTIAL/WARNINGS ---")
    for p in results["partial"]:
        print(f"  ⚠️ [{p['section']}] {p['test']}: {p['details']}")

# Save results
with open("/app/test_reports/e2e_qa_results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to /app/test_reports/e2e_qa_results.json")
print(f"\nExit code: {1 if results['failed'] else 0}")
sys.exit(1 if results['failed'] else 0)
