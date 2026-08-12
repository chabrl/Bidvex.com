# iter482 Phase P4A — Foundation Report
## Seller-Controlled Payment Methods: Data Model + Snapshot + Backfill

**Status**: ✅ P4A COMPLETE — awaiting approval before proceeding to P4B
**Date**: Feb 12, 2026
**Guardrails**: DO NOT DEPLOY · L-1 CLOSED · Partner 3% unchanged · No historical financial mutations · No Stripe calls · No new fees · Preview DB only

---

## §1  Scope delivered in P4A

Exactly the foundation layer of the seller-controlled-payment-method architecture — no checkout flow, no Stripe wiring, no frontend, no state machine. This is the minimal, isolated schema + service layer that everything else depends on.

### Files created
| File | Purpose |
|------|---------|
| `services/payment_methods_registry.py` | Canonical registry of the 4 methods (`stripe`, `etransfer`, `cash`, `cheque`), aliases, normalisation, offline/rail helpers. |
| `services/seller_payment_methods_service.py` | Immutable-snapshot logic, buyer-selection gate, edit guard for post-first-bid mutations. |
| `scripts/iter482_p4a_backfill_accepted_payment_methods.py` | Idempotent backfill for pre-P4 rows. Handles listings, multi_item_listings, vehicle_listings, storage_auctions, partner_listings. |
| `tests/test_iter482_p4a_foundation.py` | 51 unit tests: registry, service, model validation, backfill helpers. |

### Files modified
| File | Change |
|------|--------|
| `models/auction_models.py` | Added `accepted_payment_methods: Optional[List[str]]` to `ListingCreate`, `Listing`, `MultiItemListingCreate`; added `accepted_payment_methods_snapshot` + `accepted_payment_methods_locked_at` to `Listing`. Pydantic `field_validator` canonicalises on write. |
| `models/storage_auction.py` | Added `accepted_payment_methods` field to `StorageAuctionCreate` + validator. Preserved legacy `payment_method` singleton. Added `ACCEPTED_PAYMENT_METHODS_ALLOWED` constant. |
| `models/vehicle_models.py` | Added `accepted_payment_methods` field to `VehicleListingCreate` + validator. |

---

## §2  Business rules enforced in P4A

Per Master Payment Remediation §1, §5, §14:

| Rule | Enforcement point |
|------|-------------------|
| At least ONE method required if list is declared | `normalise_list()` raises `ValueError` on empty |
| Only the 4 canonical methods allowed | `normalise()` raises `InvalidPaymentMethodError` on unknown |
| Aliases (`e-transfer`, `check`, `card`) canonicalised on write | `_ALIASES` map in registry |
| Immutable snapshot at first bid | `snapshot_at_first_bid()` — idempotent, produces DB update dict |
| Post-bid edits rejected (409) | `guard_edit()` raises `PaymentMethodsLockedError` |
| Buyer selection gated by SNAPSHOT if locked | `assert_selection_allowed()` — snapshot wins over live list |
| Buyer selection of unaccepted method → 400 | `PaymentMethodNotAcceptedError` |
| Missing config on legacy rows → resolved via `payment_method` singleton fallback | `effective_methods()` precedence rule |
| No silent default of methods for new listings | `validate_new_declaration()` returns non-empty canonical list only |
| No historical data mutated in backfill | Script only touches rows where field is missing/empty |

---

## §3  Data model changes

### 3.1 New fields on listing / auction documents
```
accepted_payment_methods:              List[str]   # canonical slugs, ≥1
accepted_payment_methods_snapshot:     List[str]?  # immutable, set at 1st bid
accepted_payment_methods_locked_at:    datetime?   # ISO-8601, set with snapshot
accepted_payment_methods_source:       str?        # "backfill_iter482_p4a" for backfilled rows
accepted_payment_methods_snapshot_reason: str?     # non-null only on retro-locks
```

### 3.2 Precedence for read-side resolution (`effective_methods()`)
1. `accepted_payment_methods_snapshot` (immutable — wins if set)
2. `accepted_payment_methods` (live seller config)
3. Legacy singleton `payment_method` (wrapped in single-element list)
4. `PaymentMethodsMissingError` (blocks — no silent defaults)

### 3.3 Backfill migration outcome (preview DB, `bazario_db`)
| Collection | Scanned | Backfilled | Snapshot locked? |
|------------|---------|------------|------------------|
| `listings` | 1 | 1 | Only if `bid_count > 0` |
| `multi_item_listings` | 3 | 3 | Same rule |
| `vehicle_listings` | 1 | 1 | Same rule |
| `storage_auctions` | 31 | 31 | Same rule |
| `partner_listings` | 0 | 0 | — |
| **Total** | **36** | **36** | Idempotent — second dry-run reports 0 |

---

## §4  Test results — 287/287 PASS

| Suite | Count | Result |
|-------|-------|--------|
| iter482 P3 baseline (regression) | 158 | ✅ |
| iter482 P3.1 reconciliation + API smoke | 78 | ✅ |
| **iter482 P4A foundation (new)** | **51** | **✅** |
| **Grand total** | **287** | **✅** |

Zero regressions. Pre-existing `test_iter445_storage_bp_locked` failures (402 seller-Stripe-onboarding on preview env) are UNCHANGED by P4A — confirmed by running against P3.1 baseline pre-change.

---

## §5  What P4A does NOT do (deferred to next phases)

| Deferred to | Item |
|-------------|------|
| **P4B** | Route-layer enforcement (POST /listings must include `accepted_payment_methods`). Currently the Pydantic model treats it as `Optional` for backward compat — route layer wraps this in Phase P4B. |
| **P4B** | Buyer selection API endpoint (`POST /api/checkout/select-payment-method`) with terms-ack persistence + IP/UA. |
| **P4B** | Offline-payment path (buyer selects cash/etransfer/cheque → `AWAITING_OFFLINE_PAYMENT` state). |
| **P4C** | Stripe manual-capture wiring at auction end (`PaymentIntent(capture_method="manual")`). |
| **P4C** | Settle-payment workflow + state machine + BalanceTransaction reconciliation. |
| **P4C** | Feature flag `SELLER_CONTROLLED_PAYMENT_METHODS`. |
| **P4D** | Frontend (seller multi-select, buyer selector, PaymentStatusCard). |
| **P4E** | Full test matrix (all seller × payment × tier × province combos, ≥ 500 cases). |
| **P4E** | 4 required final docs. |

---

## §6  Guardrails HONOURED in P4A

| Guardrail | How it's satisfied |
|-----------|-------------------|
| DO NOT DEPLOY | Zero deploy actions. Preview DB only. |
| DO NOT touch production | Backfill run against preview `bazario_db` only. |
| DO NOT charge real cards | No Stripe API calls in P4A. |
| DO NOT execute live refunds | No refund code touched. |
| DO NOT change 3% Partner platform fee | Zero fee-calculator changes. |
| DO NOT enable buyer Stripe recovery pre-L-1 | Zero `payment_cost_engine` changes. L-1 status unchanged (REQUIRES_TAX_LEGAL_REVIEW). |
| DO NOT create duplicate calculators | No calculator changes — pure schema + registry. |
| DO NOT hardcode Stripe fees | Zero hardcoded rates added. |
| DO NOT silently default seller payment methods | Missing config raises `PaymentMethodsMissingError`. Backfill for legacy rows is explicit + logged. |
| DO NOT recalculate historical invoices | Backfill only adds new field; never touches `transactions`, `receipts`, `seller_payouts`. |
| DO NOT change historical financial records | Zero writes to financial collections. |
| Integer cents everywhere | N/A — P4A is schema-only. |

---

## §7  ⛔ STOP HERE — awaiting approval to proceed

Please review and confirm you want to proceed to **P4B** which will:
- Wire the field into the 4 listing-creation route handlers (fail 400 if missing).
- Add the buyer-selection endpoint + terms-ack persistence (with IP + UA).
- Add the offline-payment state (`AWAITING_OFFLINE_PAYMENT`).
- Add the `first_bid → snapshot_at_first_bid` call in the bidding path.
- Add API endpoint `GET /api/listings/{id}/accepted-payment-methods` (returns snapshot if locked).

No code beyond P4A has been written. **Standing by.**
