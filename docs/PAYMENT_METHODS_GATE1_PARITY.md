# iter484.2 — Gate 1: Payment-Method Parity Audit + Fix
**Owner ask (excerpted):** "Verify whether the new AcceptedPaymentMethodsCard is present and correct on Storage / Vehicle / Vehicle Multi-Lot detail pages + Buy Now flow. The objective is consistent buyer disclosure across all auction types."
**Constraint:** canonical registry stays `{stripe, etransfer, cash, cheque}`. NO `wire`. Seller's configured methods are the source of truth.
**Status:** ✅ Gate 1 complete. Preview only. No deploy. No Stripe/tax/fee/commission changes.

---

## 1. Audit (before-state)

| Surface | Data field used | UI | Verdict |
|---|---|---|---|
| Storage detail (`pages/storage/StorageAuctionDetail.js` lines 484–503) | `auction.payment_methods_accepted` — LEGACY field name | 3 hardcoded badges (stripe / cash / etransfer) — **NO cheque**, wrong field | 🔴 BUG |
| Vehicle detail (`pages/vehicles/VehicleDetailPage.js` line 1748) | none (used `PaymentTermsDisplay` helper) | Hardcoded blurb "**Bank transfer, certified cheque, credit card**" — completely disconnected from seller data | 🔴 BUG (buyer-misleading) |
| Vehicle multi-lot detail (`pages/vehicles/VehicleMultiLotDetailPage.js`) | none | **No payment-methods UI at all** | 🔴 GAP |
| Vehicle Buy Now flow (`VehicleDetailPage.js` lines 931–990) | uses backend `/api/payments/vehicle-buy-now-checkout` | Stripe-only (2.5% platform fee copy). Buyer disclosure prior to Buy Now is handled by the newly-wired card on the same page | ✅ Sufficient — no code change to Buy Now flow |
| Multi-item (iter484.2) | ✅ correct | shipped | ✅ Ship |
| Single-item marketplace (iter484.2) | ✅ correct | shipped | ✅ Ship |

**DB reality check:**
- 31 of 31 storage auctions have canonical `accepted_payment_methods` populated (29 also have legacy `payment_methods_accepted`).
- 0 vehicle / vehicle-multi-lot auctions on preview today — future-safe wiring only.

## 2. Fix (delivered)

### 2.1 Storage — `StorageAuctionDetail.js`
- **Removed** the 3-hardcoded-badge Card (lines 484–503) that read the wrong `payment_methods_accepted` field.
- **Wired** `<AcceptedPaymentMethodsCard listing={auction} />` — driven by the canonical `accepted_payment_methods` (with snapshot precedence).
- **Preserved** the "if Stripe, 2.9%+$0.30 processing fee" hint copy immediately below the card so nothing regressed.

### 2.2 Vehicle — `VehicleDetailPage.js` + `LegalDisclaimers.js`
- **Added** `<AcceptedPaymentMethodsCard listing={vehicle} />` INSIDE the Rules tab, immediately BEFORE the generic `<PaymentTermsDisplay />`. Buyer sees seller-approved methods FIRST, then generic payment deadline / penalty rules.
- **Removed** the hardcoded blurb "Bank transfer, certified cheque, credit card (subject to processing fee)" from `LegalDisclaimers.js::PaymentTermsDisplay` — the sibling card now owns that disclosure.

### 2.3 Vehicle Multi-Lot — `VehicleMultiLotDetailPage.js`
- **Added** `<AcceptedPaymentMethodsCard listing={event} />` immediately above the "Lot Queue" grid. Auction-level (applies to every lot in the event).

### 2.4 Guardrails held
- ✅ Canonical registry: `stripe / etransfer / cash / cheque` — no `wire`.
- ✅ Seller's configured methods = source of truth (via `resolveAcceptedMethods` helper).
- ✅ Zero touch to Stripe charge / payout / commission / tax / fee code.
- ✅ Reserve-price UI still confined to vehicle-only (iter484.1 revert intact).

## 3. Test evidence

| Suite | Result |
|---|---|
| `test_iter484_2_payment_methods_visibility.py` | 15/15 ✅ |
| `test_iter484_reserve_settlement.py` | 23/23 ✅ |
| `test_iter482_p4_end_to_end.py` | 14/14 (+3 skipped) ✅ |
| `test_iter482_p4a_foundation.py` | 48/48 ✅ |
| **Core regression sample** | **103 passed** in 12.56s |

Component reuse: Storage / Vehicle / VML now use the SAME `AcceptedPaymentMethodsCard` component that was E2E-verified by the testing agent against `alexboul1993@gmail.com`'s multi-item auction. Behaviour is identical.

## 4. Pre-bid acknowledgement — NOT extended to Storage/Vehicle in Gate 1

The pre-bid ack checkbox is present on Single-item and Multi-item detail pages (iter484.2 core). Storage and Vehicle bid forms already have their own domain-specific gates:
- **Storage:** deposit pre-authorisation acknowledgement (`storage-bid-deposit-notice`) + Stripe card-on-file check.
- **Vehicle:** currently disabled system-wide (`vehicle_bidding_enabled=False`).

**Recommendation:** if you want the payment-methods ack checkbox on Storage bid form too, flag it and I'll wire a parallel `bid-payment-ack-checkbox` in Gate 1.1. Not shipped by default because it may interact with the existing deposit ack UX.

## 5. Follow-ups (documented, NOT shipped)

- Optional Gate 1.1: pre-bid ack checkbox on Storage bid form (see §4).
- Vehicle Buy Now dialog copy at `VehicleDetailPage.js` line 877/881 currently says "Only the 2.5% platform fee (+ Stripe + tax) is charged now. You pay the seller directly for the vehicle." This is FEE copy, not method copy — unchanged in Gate 1.

---

## 6. Files modified in Gate 1

| File | Change |
|---|---|
| `frontend/src/pages/storage/StorageAuctionDetail.js` | +import; replaced hardcoded 3-badge card with canonical `AcceptedPaymentMethodsCard` |
| `frontend/src/pages/vehicles/VehicleDetailPage.js` | +import; wired card into Rules tab |
| `frontend/src/pages/vehicles/VehicleMultiLotDetailPage.js` | +import; wired card above Lot Queue |
| `frontend/src/components/vehicles/LegalDisclaimers.js` | removed hardcoded "Accepted Payment Methods" blurb (owned by card now) |
| `docs/PAYMENT_METHODS_GATE1_PARITY.md` | this document |

**Reused (no changes):** `frontend/src/components/AcceptedPaymentMethodsCard.jsx` — no need to modify. Same read helper `resolveAcceptedMethods()` used across all surfaces.

---

## 7. STOP + gate hand-off to platform owner

Per your directive "STOP and report after each major gate", Gate 1 is complete.
Please review this document. Once approved, I'll proceed to Gate 2 — Vehicle Reserve UI.
