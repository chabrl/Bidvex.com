"""
BidVex COMPLETE E2E QA Test - All 7 Sections
Run after bugfixes for admin/auctions, trust-safety/fraud-flags
"""
import requests, json, sys, time, os

API_URL = sys.argv[1] if len(sys.argv) > 1 else "https://prod-verify-2.preview.emergentagent.com"
results = {"passed": [], "failed": [], "partial": []}

def lp(s, t, d=""): results["passed"].append({"s": s, "t": t, "d": d}); print(f"  ✅ {t}: {d}")
def lf(s, t, d=""): results["failed"].append({"s": s, "t": t, "d": d}); print(f"  ❌ {t}: {d}")
def lw(s, t, d=""): results["partial"].append({"s": s, "t": t, "d": d}); print(f"  ⚠️ {t}: {d}")

def api(method, path, headers=None, json_data=None, params=None):
    fn = getattr(requests, method)
    kwargs = {"headers": headers or {}}
    if json_data: kwargs["json"] = json_data
    if params: kwargs["params"] = params
    return fn(f"{API_URL}{path}", **kwargs)

# ========== SECTION 1: AUTH ==========
print("\n" + "="*60 + "\nSECTION 1: AUTHENTICATION & REGISTRATION\n" + "="*60)

# Login admin
r = api("post", "/api/auth/login", json_data={"email":"charbeladmin@bidvex.com","password":"Admin123!"})
d = r.json()
ADMIN_TOKEN = d.get("access_token")
ADMIN_ID = d.get("user",{}).get("id")
if r.status_code == 200 and ADMIN_TOKEN:
    lp("Auth", "Admin Login", f"role={d['user']['role']}")
else:
    lf("Auth", "Admin Login", f"Status {r.status_code}")

# Login starter
r = api("post", "/api/auth/login", json_data={"email":"starter@test.com","password":"TestUser2026!"})
d = r.json()
USER_TOKEN = d.get("access_token")
USER_ID = d.get("user",{}).get("id")
if r.status_code == 200 and USER_TOKEN:
    lp("Auth", "Starter User Login", f"id={USER_ID}")
else:
    lf("Auth", "Starter User Login", f"Status {r.status_code}")

# Login premium
r = api("post", "/api/auth/login", json_data={"email":"premium@test.com","password":"TestUser2026!"})
d = r.json()
PREMIUM_TOKEN = d.get("access_token")
PREMIUM_ID = d.get("user",{}).get("id")
if r.status_code == 200 and PREMIUM_TOKEN:
    lp("Auth", "Premium User Login", f"id={PREMIUM_ID}")
else:
    lf("Auth", "Premium User Login", f"Status {r.status_code}")

# Invalid login
r = api("post", "/api/auth/login", json_data={"email":"bad@x.com","password":"wrong"})
lp("Auth","Invalid Login Rejection",f"Status {r.status_code}") if r.status_code in [401,400,404] else lf("Auth","Invalid Login Rejection",f"Status {r.status_code}")

# Registration
r = api("post", "/api/auth/register", json_data={"email":f"qa2_{int(time.time())}@test.com","password":"QATest2026!","name":"QA2","account_type":"personal","terms_agreed":True})
d = r.json()
lp("Auth","Registration",f"id={d.get('user',{}).get('id')}") if r.status_code in [200,201] else lf("Auth","Registration",f"Status {r.status_code}")

# JWT validation
ha = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
r = api("get", "/api/auth/me", headers=ha)
lp("Auth","JWT Validation (/me)",f"Status {r.status_code}") if r.status_code==200 else lf("Auth","JWT Validation",f"Status {r.status_code}")

# Forgot password
r = api("post", "/api/auth/forgot-password", json_data={"email":"charbeladmin@bidvex.com"})
lp("Auth","Forgot Password",f"Status {r.status_code}") if r.status_code in [200,404,429] else lf("Auth","Forgot Password",f"Status {r.status_code}")

# Invalid token
r = api("get", "/api/auth/me", headers={"Authorization":"Bearer invalid"})
lp("Auth","Invalid Token Rejection",f"Status {r.status_code}") if r.status_code in [401,403] else lf("Auth","Invalid Token Rejection",f"Status {r.status_code}")

# ========== SECTION 7: PLATFORM HEALTH ==========
print("\n" + "="*60 + "\nSECTION 7: PLATFORM HEALTH & PERFORMANCE\n" + "="*60)

r = api("get", "/api/health"); d=r.json()
lp("Health","Health Check","healthy") if d.get("status")=="healthy" else lf("Health","Health Check",str(d))

r = requests.head(f"{API_URL}/api/health")
lp("Health","HEAD Health",f"Status {r.status_code}") if r.status_code==200 else lf("Health","HEAD Health",f"{r.status_code}")

r = api("get", "/api/site-config"); d=r.json()
lp("Health","Site Config",f"Has branding") if "branding" in d else lf("Health","Site Config","Missing branding")

r = api("get", "/api/site-mode"); d=r.json()
lp("Health","Site Mode Live",f"mode={d.get('mode')}") if d.get("mode")=="live" else lf("Health","Site Mode",f"mode={d.get('mode')}")

r = requests.options(f"{API_URL}/api/health", headers={"Origin":"https://bidvex.com","Access-Control-Request-Method":"GET"})
lp("Health","CORS",f"ACAO={r.headers.get('access-control-allow-origin','N/A')}") if r.headers.get("access-control-allow-origin") else lw("Health","CORS","No ACAO header")

t0=time.time(); r=api("get","/api/health"); ms=round((time.time()-t0)*1000)
lp("Health","Response Time",f"{ms}ms") if ms<2000 else lw("Health","Response Time",f"{ms}ms slow")

# ========== SECTION 2: BUYER DASHBOARD ==========
print("\n" + "="*60 + "\nSECTION 2: BUYER DASHBOARD (API)\n" + "="*60)

hu = {"Authorization": f"Bearer {USER_TOKEN}"}
hp = {"Authorization": f"Bearer {PREMIUM_TOKEN}"}

r = api("get", "/api/listings", params={"page":1,"limit":10}); d=r.json()
listings = d if isinstance(d,list) else d.get("listings",[])
lp("Buyer","Listings",f"count={len(listings)}") if r.status_code==200 else lf("Buyer","Listings",f"{r.status_code}")
SID = listings[0]["id"] if listings else None

if SID:
    r = api("get", f"/api/listings/{SID}")
    lp("Buyer","Listing Detail",f"id={SID}") if r.status_code==200 else lf("Buyer","Listing Detail",f"{r.status_code}")

r = api("get", "/api/categories")
lp("Buyer","Categories",f"Status {r.status_code}") if r.status_code==200 else lw("Buyer","Categories",f"{r.status_code}")

r = api("get", "/api/listings", params={"search":"test","page":1,"limit":5})
lp("Buyer","Search",f"Status {r.status_code}") if r.status_code==200 else lf("Buyer","Search",f"{r.status_code}")

r = api("get", "/api/carousel/ending-soon")
lp("Buyer","Ending Soon",f"Status {r.status_code}") if r.status_code==200 else lf("Buyer","Ending Soon",f"{r.status_code}")

r = api("get", "/api/watchlist", headers=hu)
lp("Buyer","Watchlist",f"Status {r.status_code}") if r.status_code==200 else lw("Buyer","Watchlist",f"{r.status_code}")

r = api("get", "/api/notifications", headers=hu)
lp("Buyer","Notifications",f"Status {r.status_code}") if r.status_code==200 else lw("Buyer","Notifications",f"{r.status_code}")

r = api("get", "/api/dashboard", headers=hu)
lp("Buyer","Dashboard",f"Status {r.status_code}") if r.status_code==200 else lf("Buyer","Dashboard",f"{r.status_code}")

r = api("get", "/api/bids/my-bids", headers=hu)
lp("Buyer","Bid History",f"Status {r.status_code}") if r.status_code==200 else lw("Buyer","Bid History",f"{r.status_code}")

r = api("get", "/api/fees/calculate", params={"amount":100,"type":"buyer"})
lp("Buyer","Fee Calculator",f"Status {r.status_code}") if r.status_code==200 else lw("Buyer","Fee Calc",f"{r.status_code}")

# Multi-item listings
r = api("get", "/api/multi-item-listings")
lp("Buyer","Multi-Item Listings",f"Status {r.status_code}") if r.status_code==200 else lw("Buyer","Multi-Item",f"{r.status_code}")

# ========== SECTION 3: SELLER DASHBOARD ==========
print("\n" + "="*60 + "\nSECTION 3: SELLER DASHBOARD (API)\n" + "="*60)

r = api("get", f"/api/sellers/{ADMIN_ID}/listings", headers=ha)
d=r.json()
lp("Seller","Seller Listings",f"count={d.get('total',len(d) if isinstance(d,list) else '?')}") if r.status_code==200 else lf("Seller","Seller Listings",f"{r.status_code}")

r = api("get", "/api/dashboard/seller", headers=ha)
lp("Seller","Seller Dashboard",f"Status {r.status_code}") if r.status_code==200 else lf("Seller","Seller Dashboard",f"{r.status_code}")

r = api("get", "/api/insights/regional-trends", headers=ha)
lp("Seller","Regional Trends",f"Status {r.status_code}") if r.status_code==200 else lf("Seller","Regional Trends",f"{r.status_code}")

r = api("get", "/api/invoices", headers=ha)
lp("Seller","Invoices",f"Status {r.status_code}") if r.status_code==200 else lw("Seller","Invoices",f"{r.status_code}")

r = api("get", "/api/profiles/me", headers=ha)
lp("Seller","Profile",f"Status {r.status_code}") if r.status_code==200 else lw("Seller","Profile",f"{r.status_code}")

r = api("get", "/api/reviews/seller", headers=ha)
lp("Seller","Reviews",f"Status {r.status_code}") if r.status_code==200 else lw("Seller","Reviews",f"{r.status_code}")

# ========== SECTION 4: ADMIN PANEL ==========
print("\n" + "="*60 + "\nSECTION 4: ADMIN PANEL (11+ Subsections)\n" + "="*60)

admin_endpoints = [
    ("User Management", "/api/admin/users"),
    ("Listings (all)", "/api/admin/listings/all"),
    ("Multi-Item Listings", "/api/admin/multi-item-listings/all"),
    ("Payments", "/api/admin/payments"),
    ("Settings", "/api/admin/settings"),
    ("Analytics", "/api/admin/analytics"),
    ("Fraud Flags", "/api/admin/trust-safety/fraud-flags"),
    ("Trust Scores", "/api/admin/trust-safety"),
    ("Site Config", "/api/admin/site-config"),
    ("Email Templates", "/api/admin/email-templates"),
    ("Vehicles", "/api/admin/vehicles"),
    ("Subscribers", "/api/admin/subscribers"),
    ("Deposits", "/api/admin/deposits"),
    ("Tax Dashboard", "/api/admin/tax-dashboard"),
    ("Monitoring", "/api/admin/monitoring"),
    ("Partners", "/api/admin/partners"),
    ("Team", "/api/admin/team"),
    ("Auctions", "/api/admin/auctions"),
    ("Admin Logs", "/api/admin/logs"),
    ("Transactions", "/api/admin/transactions"),
    ("Promotions", "/api/admin/promotions"),
    ("Reports", "/api/admin/reports"),
    ("Affiliates", "/api/admin/affiliates"),
    ("Pending Listings", "/api/admin/listings/pending"),
    ("Pending Lots", "/api/admin/lots/pending"),
    ("Revenue Analytics", "/api/admin/analytics/revenue"),
    ("User Analytics", "/api/admin/analytics/users"),
    ("Listing Analytics", "/api/admin/analytics/listings"),
    ("Revenue Summary", "/api/admin/finance/revenue-summary"),
    ("Finance Transactions", "/api/admin/finance/transactions"),
    ("Subscriber Stats", "/api/admin/subscribers/stats"),
    ("Deletion Requests", "/api/admin/deletion-requests"),
    ("Collusion Patterns", "/api/admin/trust-safety/collusion-patterns"),
]

for name, path in admin_endpoints:
    try:
        r = requests.get(f"{API_URL}{path}", headers=ha, timeout=15)
        ct = r.headers.get("content-type","")
        if r.status_code == 200 and "json" in ct:
            lp("Admin", name, f"Status 200")
        elif r.status_code == 200 and "html" in ct:
            lf("Admin", name, f"Returns HTML (SPA fallthrough - no backend route)")
        elif r.status_code == 500:
            lf("Admin", name, f"Status 500 - Server Error")
        else:
            lw("Admin", name, f"Status {r.status_code}")
    except Exception as e:
        lf("Admin", name, str(e))

# ========== SECTION 5: EMAILS & NOTIFICATIONS ==========
print("\n" + "="*60 + "\nSECTION 5: EMAILS & NOTIFICATIONS\n" + "="*60)

r = api("get", "/api/push/vapid-public-key"); d=r.json()
lp("Notif","VAPID Key",f"len={len(d.get('public_key',''))}") if d.get("public_key") else lf("Notif","VAPID Key","Missing")

r = api("get", "/api/push/status", headers=hu)
lp("Notif","Push Status",f"Status {r.status_code}") if r.status_code==200 else lw("Notif","Push Status",f"{r.status_code}")

r = api("get", "/api/admin/email-templates", headers=ha)
lp("Notif","Email Templates",f"Status {r.status_code}") if r.status_code==200 else lw("Notif","Email Templates",f"{r.status_code}")

r = api("get", "/api/notifications", headers=ha)
lp("Notif","Notifications List",f"Status {r.status_code}") if r.status_code==200 else lw("Notif","Notifications",f"{r.status_code}")

# Check SendGrid config in backend .env
try:
    with open("/app/backend/.env") as f:
        env_content = f.read()
    if "SENDGRID_API_KEY=SG." in env_content:
        lp("Notif","SendGrid Key in .env","Present & formatted correctly")
    else:
        lw("Notif","SendGrid Key","Not found in .env")
except:
    lw("Notif","SendGrid Key","Could not read .env")

# ========== SECTION 6: STRIPE INTEGRATION ==========
print("\n" + "="*60 + "\nSECTION 6: STRIPE INTEGRATION\n" + "="*60)

try:
    with open("/app/backend/.env") as f:
        env_content = f.read()
    if "STRIPE_API_KEY=sk_" in env_content:
        lp("Stripe","API Key in .env","Present")
    else:
        lf("Stripe","API Key","Missing in .env")
    if "STRIPE_WEBHOOK_SECRET=whsec_" in env_content:
        lp("Stripe","Webhook Secret in .env","Present")
    else:
        lf("Stripe","Webhook Secret","Missing in .env")
    if "STRIPE_PUBLISHABLE_KEY=pk_" in env_content:
        lp("Stripe","Publishable Key in .env","Present")
    else:
        lw("Stripe","Publishable Key","Missing")
except:
    lf("Stripe","Env File Read","Failed")

r = api("get", "/api/payments/methods", headers=ha)
lp("Stripe","Payment Methods",f"Status {r.status_code}") if r.status_code==200 else lw("Stripe","Payment Methods",f"{r.status_code}")

r = api("get", "/api/subscriptions/status", headers=ha); d=r.json()
lp("Stripe","Subscription Status",f"tier={d.get('tier',d.get('subscription_tier','?'))}") if r.status_code==200 else lw("Stripe","Subscription",f"{r.status_code}")

r = api("get", "/api/deposits/status", headers=ha)
lp("Stripe","Deposits",f"Status {r.status_code}") if r.status_code==200 else lw("Stripe","Deposits",f"{r.status_code}")

r = requests.post(f"{API_URL}/api/webhooks/stripe", data="test", headers={"Content-Type":"application/json"})
lp("Stripe","Webhook Reachable",f"Status {r.status_code} (rejects invalid)") if r.status_code in [400,401,403,422] else lw("Stripe","Webhook",f"Status {r.status_code}")

# ========== FINAL SUMMARY ==========
print("\n" + "="*60 + "\nCOMPLETE E2E QA RESULTS\n" + "="*60)
total = len(results["passed"]) + len(results["failed"]) + len(results["partial"])
print(f"\nTotal: {total}  |  ✅ Passed: {len(results['passed'])}  |  ❌ Failed: {len(results['failed'])}  |  ⚠️ Partial: {len(results['partial'])}")

if results["failed"]:
    print("\n--- ❌ FAILURES ---")
    for f in results["failed"]:
        print(f"  [{f['s']}] {f['t']}: {f['d']}")

if results["partial"]:
    print("\n--- ⚠️ WARNINGS ---")
    for p in results["partial"]:
        print(f"  [{p['s']}] {p['t']}: {p['d']}")

with open("/app/test_reports/e2e_qa_final.json", "w") as f:
    json.dump({"total": total, "passed": len(results["passed"]), "failed": len(results["failed"]), "partial": len(results["partial"]), "details": results}, f, indent=2)

print(f"\nSaved: /app/test_reports/e2e_qa_final.json")
