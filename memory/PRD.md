# BidVex Auction Marketplace - Product Requirements Document

## Overview
BidVex is a full-stack auction marketplace with React frontend, FastAPI backend, and MongoDB.

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next, @tanstack/react-query
- **Backend**: FastAPI, MongoDB, Stripe, SendGrid, APScheduler
- **Infrastructure**: S3-compatible object storage (AWS S3 / Cloudflare R2)

## Test Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Completed Work

### Core Platform
- Subscriptions (Free/Premium/Partner Pro/VIP), real-time bidding, multi-item lots, vehicles, verification, messaging, PDF invoices, notifications

### i18n Overhaul (March 2026)
- JSON-based EN/FR, CI audit gate, 202 strings fixed, 481 unused keys removed

### E-Commerce Checkout (March 20, 2026)
- Buy Now + Auction Winner flows with server-side pricing, Stripe sessions, webhooks

### Mobile UI Fixes (March 21, 2026)
- Marketplace filters, Messages layout, Bid input, Seller Dashboard deletion

### Full Regression (March 21, 2026)
- Webhooks, subscriptions, tax calculations — 51/51 pass

### Post-Purchase Review System (March 21, 2026)
- Reviews, Reputation, Moderation, Emails, Frontend — 38/38 tests pass (Iteration 79)

### Seller Rating on Listing Cards + Detail Pages (March 21, 2026)
- SellerRatingInline, Batch Reputation API, Full Breakdown — 15/15 tests pass (Iteration 80)

### Partner Program Page Fixes (March 21, 2026)
- Translation, Layout, Pricing — 29/29 tests pass (Iteration 81)

### Pre-Launch Platform Audit (March 21, 2026)
- i18n Coverage, Backend Fix, Mobile Layout — 22/22 tests pass (Iteration 82)

### Subscription Pricing Page Redesign (March 21, 2026)
- 2x2 grid, tier-specific design, VIP card — 100% pass (Iteration 83)

### Performance Optimization Sprint (March 23, 2026)
- Keep-alive ping, MongoDB connection pooling, marketplace cache, subscription cache, pre-warming — 100% frontend, 82% backend (Iteration 84)

### PageSpeed Optimization Sprint (March 23, 2026)
- Logo optimization, Google Ads removal, PostHog deferral, critical CSS, cache-control headers, CLS fixes, security headers, accessibility — 100% pass (Iteration 85)

### Critical Production Fixes (March 23, 2026)
- Admin Dashboard fixed, Listing detail cache + retry, Server.py error logging, WWW redirect, CLS footer, Accessibility — 22/22 pass (Iteration 86)

### Remove emergentintegrations Dependency (March 24, 2026)
- **Replaced all `emergentintegrations` imports** with standard PyPI packages for Railway/external deployment:
  - `emergentintegrations.llm.chat.LlmChat` → `openai.AsyncOpenAI` (GPT-4o)
  - `emergentintegrations.openai.OpenAIChatIntegration` → `openai.AsyncOpenAI` (GPT-4o)
  - `emergentintegrations.payments.stripe.checkout.StripeCheckout` → `stripe` SDK directly
  - Emergent Object Storage REST API → `boto3` S3 client
- Removed `emergentintegrations==0.1.0` from requirements.txt
- All 204 packages in requirements.txt are now standard PyPI packages
- Created `backend/.env.example` with placeholder values
- Both `.env` files removed from git tracking
- **AI features** (chatbot, fraud detection, trust/safety scanning) now use `openai` SDK directly
- **Payments** (vehicle checkout, deposits) now use `stripe` SDK directly
- **Object storage** (invoices) now uses `boto3` S3 client

## Environment Variables for External Deployment

### Required for core features:
- `MONGO_URL` — MongoDB connection string
- `DB_NAME` — Database name
- `JWT_SECRET` — JWT signing secret
- `STRIPE_API_KEY` — Stripe secret key
- `STRIPE_PUBLISHABLE_KEY` — Stripe publishable key
- `SENDGRID_API_KEY` — SendGrid API key
- `FRONTEND_URL` — Frontend URL for CORS

### Required for AI features:
- `EMERGENT_LLM_KEY` — Set this to your OpenAI API key (sk-...)

### Required for object storage (invoices):
- `AWS_ACCESS_KEY_ID` — S3 access key
- `AWS_SECRET_ACCESS_KEY` — S3 secret key
- `S3_BUCKET_NAME` — Bucket name (default: bidvex-storage)
- `S3_REGION` — Region (default: us-east-1)
- `S3_ENDPOINT_URL` — Custom endpoint for Cloudflare R2 / MinIO (leave empty for AWS S3)

## Backlog
- (P2) Cloudflare CDN setup
- (P2) Post-launch monitoring and alerting
- (Post-Launch) Configure production secrets
- (Low Priority) Add i18n to internal EmailMarketingPricing page
- (Enhancement) Real-time performance dashboard
- (Enhancement) Automated weekly Lighthouse audits
