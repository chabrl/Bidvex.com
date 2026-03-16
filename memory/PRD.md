# BidVex Auction Platform - Product Requirements Document

## Last Updated: March 16, 2026

## Original Problem Statement
Build and maintain a sophisticated full-stack auction platform (BidVex) with:
- Real-time bidding capabilities
- Multi-item and single-item auction listings
- Comprehensive admin panel
- Canadian tax compliance system
- Full bilingual support (EN/FR)
- Hybrid Fee Calculation Engine
- Quebec Tax & Invoicing Engine
- Marketplace Engine with Stripe Connect
- Subscription Tier System
- Seller Earnings Dashboard
- Trust Status Verification via SetupIntent
- Enterprise Vehicle Auction Module
- Partner Account System with Stripe Connect
- Admin Command Center with financial reporting
- **Sign-up Terms & Policy Consent (Clickwrap)** NEW
- **Admin RBAC Team Management** NEW
- **AI Chatbot (Claude Sonnet 4.5)** NEW

## Architecture
```
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI (Python) 
Database: MongoDB Atlas (Cloud)
Authentication: JWT + Emergent Google Auth
AI: Claude Sonnet 4.5 via emergentintegrations (upgraded from GPT-4)
Payments: Stripe Connect + SetupIntents + Subscriptions + Tax Engine
Email: SendGrid
Background Jobs: APScheduler
i18n: react-i18next (EN/FR bilingual support)
PDF Generation: ReportLab (bilingual invoices)
```

## Current Status: ALL P0 FEATURES COMPLETE

### Session Update (Mar 16, 2026 — Logic & Legal Sync)

**Logic Changes Implemented:**
- Payment deadline updated from "3 business days" to "14 days of auction close" across all invoice templates
- Late penalty: Verified 2% monthly rate (LATE_PAYMENT_MONTHLY_RATE=0.02) already in place
- Partner fees hardcoded: PARTNER_PLATFORM_FEE_RATE=0.03 (3%), PARTNER_ANNUAL_ACCESS_FEE=100.00 ($100 CAD/year)
- Anti-sniping: Verified 2-minute extension active for all auction types
- Bid retraction: 1-hour window documented in legal (no retraction endpoint exists — bids are binding by design)
- Personalized Recommendations: Added opt-out toggle to Account Settings > Notifications tab
- Footer: Added mailing address (103-761 Chalifoux Street, Sherbrooke, QC J1G 0A8), updated copyright to "© 2026 BidVex Inc."
- Signup checkbox: Confirmed linking to /legal#terms (March 2026 version)
- User model: Added `personalized_recommendations: bool = True` field

**Testing:** iteration_50 — 100% backend, 100% frontend (16/16 verified)

### Session Update (Mar 16, 2026 — Legal & Partner Fee Update)

**Legal Page Overhaul:**
- Replaced placeholder content with live text from bidvex.com/terms-of-service and bidvex.com/privacy-policy
- Added Section 7.2: Partner Account Fees ($100 CAD/year + 3% hammer commission, BP flexibility)
- Added Section 7.4: All fees in CAD, GST/QST applied on top
- Added Section 9: Listing Promotions & Marketing (non-refundable, pay-as-you-go emails final)
- Updated Section 10.3: Subscription/platform fees non-refundable
- Updated address across all sections: 103-761 Chalifoux Street, Sherbrooke, QC

**Partner Signup Flow:**
- Business account signup shows Partner Account Fees (CAD) disclosure before terms checkbox
- Become-a-Partner page application form shows fee summary (3 items) and NEQ verification note
- Chatbot updated with partner fee knowledge ($100/year + 3%), promotions policy, and address

**Testing:** iteration_49 — 100% backend, 100% frontend (15/15 features verified)

### Session Summary (Mar 16, 2026 — Latest)

**3 New Features Implemented:**

1. **Sign-up Terms & Policy Consent (Clickwrap)**
   - Backend: `terms_agreed` field added to UserCreate model, validated on registration (400 error if false)
   - `terms_agreed_at` timestamp stored in user document
   - Frontend: Mandatory checkbox on signup form with Square/CheckSquare icons
   - Links to `/legal#terms` and `/legal#privacy` open in new tab
   - "Create Account" button disabled until checkbox is checked
   - `/legal` page consolidates Terms of Service and Privacy Policy
   - Testing: 100% (iteration_48) — Backend + Frontend verified

2. **Admin RBAC Team Management**
   - Backend: New `routes/team.py` with full CRUD API
   - Roles: Admin (full access), Manager (operations), Support (view-only)
   - Unique invite link system: admin generates link, team member accepts and creates account
   - Endpoints: invite, accept, list members, list invitations, update role, remove member, cancel invitation
   - Frontend: TeamManager component in Admin Dashboard under "Team" primary tab
   - InviteAcceptPage for accepting invitations at `/invite/:token`
   - Testing: 100% (iteration_48) — 11 backend + 4 frontend tests passed

3. **AI Chatbot (Claude Sonnet 4.5)**
   - Upgraded from GPT-4 to Claude Sonnet 4.5 via emergentintegrations
   - Updated system prompt with pricing knowledge: $213.45 Premium, $355.54 VIP
   - Added No Refund policy enforcement to chatbot responses
   - Existing widget (AIAssistant.js) continues to work seamlessly
   - Testing: 100% (iteration_48) — Chatbot responds correctly about pricing and policies

**New API Endpoints:**
- `POST /api/team/invite` — Invite team member (admin only)
- `GET /api/team/invite/{token}/info` — Get invitation details
- `POST /api/team/invite/{token}/accept` — Accept invitation and create account
- `GET /api/team/members` — List team members (admin only)
- `GET /api/team/invitations` — List invitations (admin only)
- `PUT /api/team/members/{id}/role` — Update member role (admin only)
- `DELETE /api/team/members/{id}` — Remove team member (admin only)
- `DELETE /api/team/invitations/{id}` — Cancel invitation (admin only)
- `GET /api/team/permissions` — Get current user's permissions
- `GET /api/team/roles` — Get role definitions

**New Files Created:**
- `/app/backend/routes/team.py` — RBAC team management API
- `/app/frontend/src/pages/LegalPage.js` — Consolidated legal page
- `/app/frontend/src/pages/InviteAcceptPage.js` — Invite acceptance page
- `/app/frontend/src/components/admin/TeamManager.js` — Admin team management UI

**Files Modified:**
- `/app/backend/server.py` — Added terms_agreed to UserCreate, team router registration
- `/app/backend/routes/auth.py` — Added terms_agreed validation
- `/app/backend/services/ai_assistant_v2.py` — Switched to Claude Sonnet 4.5, added pricing/refund knowledge
- `/app/frontend/src/pages/AuthPage.js` — Added consent checkbox
- `/app/frontend/src/pages/AdminDashboard.js` — Added Team tab
- `/app/frontend/src/App.js` — Added /legal and /invite/:token routes

**New Database Collections:**
- `team_invitations` — Team invitation records (email, role, token, status, expires_at)

**User Schema Updates:**
- `terms_agreed_at` (datetime) — Timestamp of terms consent
- `team_member` (boolean) — Whether user is a team member
- `team_joined_at` (datetime) — When user joined the team

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`

## Upcoming Tasks (Prioritized)

### P1 - High Priority
- [ ] Refactor monolithic `server.py` into modular route files

### P2 - Medium Priority
- [ ] Cache marketplace filter counts for performance
- [ ] PDF Invoice cloud storage
- [ ] Editable buyer premium in auction creation UI for partners
- [ ] Partner Pro subscription tier

### P3 - Low Priority
- [ ] Cookie consent translation (i18n integration)
- [ ] "Email to Friend" feature for vehicle listings
- [ ] Database indexing on `auction_id` in bids collection
- [ ] "Verified Auction Firm" badge on partner listings
