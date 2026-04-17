# BidVex — Auction Marketplace PRD

## Latest: SendGrid Email QA Pass (April 17, 2026)

### P0 Email Template QA — DONE
- **44 template keys** registered in `_TEMPLATE_KEYS` (39 existing + 5 new P0)
- **78 SendGrid template IDs** in `.env` (existing), 5 P0 templates use inline HTML fallback
- **5 new P0 email functions** with full BidVex design system compliance:
  1. `send_pickup_code_email()` — 48px monospace bold pickup code, bilingual EN/FR
  2. `send_escrow_released_email()` — Seller payout confirmation
  3. `send_cancellation_penalty_email()` — $50 penalty notice (red theme)
  4. `send_auto_release_email()` — 48hr expiry auto-release notice
  5. `send_sticky_card_locked_email()` — Payment method locked warning
- **All 10 test emails sent** (5 templates x EN + FR) — all PASS
- **Dark mode** support: `@media (prefers-color-scheme: dark)` in all P0 templates
- **Mobile responsive**: `@media (max-width: 600px)` in all P0 templates
- **BidVex design system** zones: Header (navy+logo), Hero (colored+emoji+headline), Body card, CTA button (#2186C6), Footer (navy+copyright)
- **Language routing**: All functions use `language_preference` with "en"/"fr" lowercase, fallback to "en"
- Escrow service updated to use typed `send_pickup_code_email()` instead of raw `resolve_template()`

### About Us Page — Full Redesign - DONE
### Phase 7: Platform Cleanup & Admin Moderation - DONE
### Phases 1-6: All Complete

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring
- (Enhancement) Create SendGrid dynamic templates for P0 emails (currently using inline HTML fallback)
