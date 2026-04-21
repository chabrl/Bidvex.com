# BidVex — Auction Marketplace PRD

## Latest: Vehicle Payment Infrastructure OPC Compliance (Feb 15, 2026)

### Vehicle Payment Legal Compliance — DONE (P0)
- BidVex never holds the vehicle hammer price; buyer charged only 2.5% fee + Stripe recovery + tax-on-fee
- `send_auction_won_email` now injects bilingual EN+FR legal notice for vehicles (is_vehicle branch)
- $500 deposit migrated to Stripe `capture_method="manual"` (true HOLD, not charge)
- On auction close: winner + loser deposit holds RELEASED (PaymentIntent cancelled)
- New `capture_deposit` method captures hold only if winner fails to pay fee invoice
- Zero Stripe Connect transfer to vehicle seller (verified: no transfer_data/destination/application_fee_amount)
- Tests: 14/14 backend pass (iteration_153)

## Previous: SendGrid Full Integration Fix (April 20, 2026)

### SendGrid Email Integration — DONE
- FROM address: `noreply@bidvex.com` (BidVex Canada)
- Reply-To: `support@bidvex.com`
- Admin alerts: `info@bidvex.com`
- Domain: `bidvex.com` authenticated + valid in SendGrid
- 88 template IDs configured (44 keys × EN/FR)
- Created `admin_notifications.py` with 4 admin alert functions
- Wired admin new user notification to signup route (fire-and-forget)
- Live E2E test: 5/5 passed (Welcome EN/FR, Admin notify, Bid confirmed, Pickup code)

### Marketplace Filter Bar — DONE
### Cloudflare CDN Optimization — DONE
### About Us Page — DONE
### Phase 7: Platform Cleanup — DONE

## Backlog
- (P2) Post-launch monitoring and alerting
- (Enhancement) Dispute resolution & admin offline order management
- (Enhancement) Scheduler job to auto-capture $500 deposit when fee invoice goes unpaid past deadline
- Railway deployment fix (pending dashboard config)

