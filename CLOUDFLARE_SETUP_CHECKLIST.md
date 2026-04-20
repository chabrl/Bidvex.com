# CLOUDFLARE DASHBOARD SETUP CHECKLIST — bidvex.com

> Complete these steps in order. Each step includes the exact navigation path and recommended setting.

---

## Step 1 — SSL/TLS Settings

**Go to:** SSL/TLS → Overview

- Set encryption mode to: **Full (Strict)**
- Why: Railway provides a valid SSL cert. Full Strict ensures end-to-end encryption and prevents MITM/downgrade attacks.

**Go to:** SSL/TLS → Edge Certificates

- Toggle ON: **Always Use HTTPS**
- Toggle ON: **Automatic HTTPS Rewrites**
- Toggle ON: **HTTP Strict Transport Security (HSTS)**
  - Max Age: 12 months
  - Include subdomains: Yes
  - Preload: Yes
  - No-Sniff Header: Already handled by your backend middleware
- Minimum TLS Version: **TLS 1.2**
- Why: Forces all HTTP traffic to HTTPS. HSTS tells browsers to never attempt HTTP.

---

## Step 2 — Cache Rules: Static Assets (Long Cache)

**Go to:** Caching → Cache Rules → Create Rule

- **Rule name:** `Cache Static Assets — 1 Year`
- **When (If):** URI Path matches regex `\.(js|css|png|jpg|jpeg|gif|svg|woff|woff2|ico|webp|avif|mp4)$`
  - *Alternative if regex isn't available:* Use "File extension" matches `js, css, png, jpg, jpeg, gif, svg, woff, woff2, ico, webp, avif`
- **Then:**
  - Cache eligibility: **Eligible for cache**
  - Edge TTL: **1 year** (or max available)
  - Browser TTL: **1 day** (86400 seconds)
  - Respect origin headers: **Yes** (your backend already sends `immutable` for hashed assets)
- Why: React CRA produces content-hashed filenames (`main.a3f9c2.js`). These never change, so caching forever is safe. Browser TTL of 1 day ensures users eventually get fresh assets after a deploy.

---

## Step 3 — Cache Rules: API Routes (Bypass Cache)

**Go to:** Caching → Cache Rules → Create Rule

- **Rule name:** `Bypass API Cache`
- **When (If):** URI Path starts with `/api/`
- **Then:**
  - Cache eligibility: **Bypass cache**
- Why: Your backend sends `CDN-Cache-Control` headers that differentiate public vs private API routes. However, as a safety net, bypassing all `/api/` at the Cloudflare level ensures no user-specific auction data (bids, session, dashboard) is ever cached at the edge. The public endpoints (`/api/marketplace/items`, `/api/site-config`) respond fast enough without CDN caching.

> **Advanced (optional):** If you later want to CDN-cache public endpoints, create a separate rule:
> - When: URI Path starts with `/api/marketplace/` AND Request Method equals `GET`
> - Then: Eligible for cache, Edge TTL = 5 minutes, Respect origin `CDN-Cache-Control` header

---

## Step 4 — Cache Rules: HTML (No Cache)

**Go to:** Caching → Cache Rules → Create Rule

- **Rule name:** `No Cache HTML Entry Point`
- **When (If):** URI Path equals `/` OR File extension matches `html`
- **Then:**
  - Cache eligibility: **Bypass cache**
- Why: The HTML entry point must always be fresh so users load the latest React bundle references after each deploy.

---

## Step 5 — Purge Settings

**Go to:** Caching → Configuration

- **Purge Cache:** After every deploy, purge all cache OR use the API:
  ```
  curl -X POST "https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/purge_cache" \
    -H "Authorization: Bearer {API_TOKEN}" \
    -H "Content-Type: application/json" \
    --data '{"purge_everything":true}'
  ```
- **Caching Level:** Standard
- **Browser Cache TTL:** Respect Existing Headers (your backend sets these correctly)
- **Always Online:** ON (serves stale content if Railway is temporarily down)

---

## Step 6 — Speed Optimizations

**Go to:** Speed → Optimization → Content Optimization

- **Auto Minify:** Check JS ✅, CSS ✅, HTML ✅
- **Brotli compression:** ON
- **Early Hints:** ON (103 status code — preloads fonts/CSS before HTML finishes)
- **Rocket Loader:** OFF (can break React hydration)
- **Mirage:** OFF (not needed — your images already use `loading="lazy"`)

**Go to:** Speed → Optimization → Protocol Optimization

- **HTTP/2:** ON (default)
- **HTTP/3 (QUIC):** ON
- **0-RTT Connection Resumption:** ON

---

## Step 7 — Security Level

**Go to:** Security → Settings

- **Security Level:** Medium
- **Bot Fight Mode:** ON
- **Challenge Passage:** 30 minutes
- **Browser Integrity Check:** ON
- Why: Blocks obvious bots from scraping your listings while allowing legitimate search engine crawlers.

---

## Step 8 — WAF Rate Limiting

**Go to:** Security → WAF → Rate Limiting Rules → Create Rule

### Rule 1: API Rate Limit
- **Rule name:** `API Rate Limit — 60/min`
- **When:** URI path starts with `/api/`
- **Rate:** 60 requests per 1 minute, per IP
- **Then:** Block for 1 minute
- **Response:** 429 Too Many Requests
- Why: Prevents auction sniping bots and API abuse.

### Rule 2: Auth Brute Force Protection
- **Rule name:** `Auth Brute Force — 10/min`
- **When:** URI path starts with `/api/auth/login`
- **Rate:** 10 requests per 1 minute, per IP
- **Then:** Block for 10 minutes
- Why: Stops credential stuffing attacks against login endpoint.

### Rule 3: Bid Spam Protection
- **Rule name:** `Bid Rate Limit — 20/min`
- **When:** URI path contains `/bids` AND Request method equals `POST`
- **Rate:** 20 requests per 1 minute, per IP
- **Then:** Block for 2 minutes
- Why: Prevents automated bid flooding on auctions.

---

## Step 9 — Page Rules

**Go to:** Rules → Page Rules → Create Rule

### Rule 1: Force HTTPS
- **URL:** `http://bidvex.com/*`
- **Setting:** Always Use HTTPS

### Rule 2: WWW Redirect
- **URL:** `www.bidvex.com/*`
- **Setting:** Forwarding URL (301) → `https://bidvex.com/$1`
- Why: Your backend middleware also handles this, but doing it at Cloudflare is faster (no round-trip to origin).

---

## Step 10 — DNS Verification

**Go to:** DNS → Records

### Must be PROXIED (orange cloud ✅):
| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A or CNAME | `bidvex.com` | Railway IP or CNAME | ✅ Proxied |
| CNAME | `www` | `bidvex.com` | ✅ Proxied |

### Must be DNS Only (gray cloud):
| Type | Name | Content | Proxy |
|------|------|---------|-------|
| MX | `bidvex.com` | (your mail server) | ❌ DNS Only |
| TXT | `bidvex.com` | `v=spf1 include:sendgrid.net ~all` | ❌ DNS Only |
| CNAME | `em1234.bidvex.com` | (SendGrid CNAME for DKIM) | ❌ DNS Only |
| CNAME | `url1234.bidvex.com` | (SendGrid link tracking) | ❌ DNS Only |

> **Important:** MX and TXT records must NEVER be proxied or email delivery will break.

---

## Step 11 — Redirect Rules (Clean URLs)

**Go to:** Rules → Redirect Rules → Create Rule

- **Rule name:** `Trailing slash redirect`
- **When:** URI path ends with `/` AND URI path is not `/`
- **Then:** Dynamic redirect to same URL without trailing slash (301)
- Why: Prevents duplicate content in search engines.

---

## Step 12 — Web Analytics

**Go to:** Analytics & Logs → Web Analytics

- **Enable Web Analytics** for bidvex.com
- This is free, privacy-friendly (no cookies), and gives you:
  - Page views, unique visitors, top pages
  - Core Web Vitals (LCP, FID, CLS)
  - Traffic by country (useful for your global auction marketplace)

---

## Step 13 — Network Settings

**Go to:** Network

- **WebSockets:** ON (required for real-time auction bidding)
- **gRPC:** OFF (not used)
- **Onion Routing:** OFF
- **IP Geolocation:** ON (useful for geo-targeted auction alerts)
- **Maximum Upload Size:** 100MB (for listing images)

---

## Step 14 — Scrape Shield

**Go to:** Scrape Shield

- **Email Address Obfuscation:** ON
- **Server-side Excludes:** ON
- **Hotlink Protection:** ON (prevents other sites from embedding your listing images)
- Why: Protects `info@bidvex.com` from being harvested by bots.

---

## Post-Setup Verification Checklist

After completing all steps, verify:

- [ ] `curl -I https://bidvex.com` returns `HTTP/2 200` with `cf-cache-status: DYNAMIC`
- [ ] `curl -I https://bidvex.com/static/js/main.*.js` returns `cf-cache-status: HIT` (after 2nd request)
- [ ] `curl -I https://bidvex.com/api/health` returns `cache-control: no-store` headers
- [ ] `https://www.bidvex.com` redirects to `https://bidvex.com` (301)
- [ ] `http://bidvex.com` redirects to `https://bidvex.com` (301)
- [ ] WebSocket connections work for real-time bidding
- [ ] SendGrid emails still deliver (MX/TXT records not proxied)
- [ ] Cloudflare Analytics shows traffic data

---

*Generated for BidVex Inc. — April 2026*
