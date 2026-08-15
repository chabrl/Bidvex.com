# Production Bid Removal — Lot 58758582-f53a-46d8-bc0b-87cf9de60523 / lot #1

**Date:** 2026-08-15 03:14 UTC
**Environment:** Production data (shared Atlas cluster — writes issued from preview backend, immediately reflected in production frontend)
**Actor:** Main agent, per explicit user confirmation (option "a" — full pristine revert including auto_bid deletion)
**Ticket context:** User's own test bid ($7.00 on lot #1 of "Bicycles, Furniture and Extra Goods") placed via their auto-bid bot; requested rollback to original starting state ($2.00, no bids).

---

## 1. Identity verification (belt-and-suspenders before writing)

| Assertion                                     | Value                                                    | OK |
|-----------------------------------------------|----------------------------------------------------------|----|
| `lot_bids` row exists with id                 | `8a5ac7dd-2b3b-4569-b5a3-37010482a335`                   | ✅ |
| Bidder id                                     | `8940074d-da97-43ca-9a0b-c59d39411ed6`                   | ✅ |
| Bidder email                                  | `charbel911@gmail.com` (super_admin, "Bidvex Team")      | ✅ |
| Row targets correct listing + lot             | listing `58758582-…`, lot #1                             | ✅ |
| `auto_bids` row exists with id                | `df58d92b-1ce6-4b92-9949-e14e50215a5d`                   | ✅ |
| Auto-bid user id matches bidder               | Same super_admin id                                      | ✅ |
| Lot subdoc has expected `highest_bidder_id`   | Matches bidder                                           | ✅ |
| Lot `starting_price`                          | `2.0`                                                    | ✅ |

All checks passed → writes authorised.

---

## 2. Before snapshot

**`lot_bids` row**
```json
{
  "id":         "8a5ac7dd-2b3b-4569-b5a3-37010482a335",
  "listing_id": "58758582-f53a-46d8-bc0b-87cf9de60523",
  "lot_number": 1,
  "bidder_id":  "8940074d-da97-43ca-9a0b-c59d39411ed6",
  "amount":     7,
  "bid_type":   "normal",
  "created_at": "2026-08-15T02:54:43.611563+00:00"
}
```

**`auto_bids` row**
```json
{
  "id":         "df58d92b-1ce6-4b92-9949-e14e50215a5d",
  "user_id":    "8940074d-da97-43ca-9a0b-c59d39411ed6",
  "listing_id": "58758582-f53a-46d8-bc0b-87cf9de60523",
  "lot_number": 1,
  "max_bid":    7.04,
  "is_active":  false,
  "strategy":   "min_to_lead",
  "created_at": "2026-08-15T02:50:57.443190+00:00"
}
```

**`multi_item_listings.lots[lot_number=1]` inline bid state (relevant fields)**
```json
{
  "lot_number":        1,
  "starting_price":    2.0,
  "current_price":     7,
  "bid_count":         1,
  "highest_bidder_id": "8940074d-da97-43ca-9a0b-c59d39411ed6",
  "has_reserve":       null,
  "reserve_price":     70.0,
  "reserve_met":       null,
  "lot_status":        "active",
  "lot_end_time":      "2026-08-21T20:01:00+00:00"
}
```

Full raw dump: `/app/docs/PROD_BID_REMOVAL_lot58758582-f53a-46d8-bc0b-87cf9de60523_1_BEFORE.json`

---

## 3. Writes issued (three, in order)

| # | Collection            | Operation           | Filter                                         | Result             |
|---|-----------------------|---------------------|------------------------------------------------|--------------------|
| 1 | `lot_bids`            | `delete_one`        | `id=8a5ac7dd-…` AND `bidder_id=8940074d-…`     | deleted_count=1 ✅ |
| 2 | `multi_item_listings` | `update_one` (`$set` on positional-filtered lot) | `id=58758582-…`, `lots.$[l].lot_number=1` — set `current_price=2.0`, `bid_count=0`, `highest_bidder_id=null` | matched=1, modified=1 ✅ |
| 3 | `auto_bids`           | `delete_one`        | `id=df58d92b-…` AND `user_id=8940074d-…`       | deleted_count=1 ✅ |

Full run log: `/app/docs/PROD_BID_REMOVAL_lot58758582_1.log`

---

## 4. After snapshot

**`lot_bids` row**: `null` (deleted). ✅

**`auto_bids` row**: `null` (deleted). ✅

**`multi_item_listings.lots[lot_number=1]` inline bid state**
```json
{
  "lot_number":        1,
  "starting_price":    2.0,
  "current_price":     2.0,          // was 7
  "bid_count":         0,            // was 1
  "highest_bidder_id": null,         // was 8940074d-…
  "has_reserve":       null,         // UNCHANGED
  "reserve_price":     70.0,         // UNCHANGED
  "reserve_met":       null,         // UNCHANGED
  "lot_status":        "active",     // UNCHANGED
  "lot_end_time":      "2026-08-21T20:01:00+00:00"   // UNCHANGED
}
```

Full raw dump: `/app/docs/PROD_BID_REMOVAL_lot58758582-f53a-46d8-bc0b-87cf9de60523_1_AFTER.json`

---

## 5. Verification

| Check                                                                   | Result |
|-------------------------------------------------------------------------|--------|
| Post-write `lot_inline_fields` match the pristine "clean lot" pattern (current_price=starting_price, bid_count=0, highest_bidder_id=null) | ✅ Match |
| Reserve / status / end-time fields byte-identical to before             | ✅ Unchanged |
| Other 23 lots on this listing — bid state unaffected                    | ✅ 0 lots with non-zero bid_count |
| Production UI (`https://launchapp-4-r-1774886029.emergent.host/lots/58758582-…/lot/1`) shows CURRENT BID $2.00, NEXT VALID BID $7.00 | ✅ Confirmed via screenshot |
| No side-effect data to clean up (payments, escrow, Stripe events, receipts, outbid notifications, watchers, emails) | ✅ All pre-scanned as zero |

---

## 6. Not touched

- Any other lot on this listing (23 lots) — verified untouched via post-write scan.
- Any other listing.
- Any other user's data.
- Any billing / tax / security / escrow / Stripe / payment code path.
- All reserve fields (`has_reserve`, `reserve_price`, `reserve_met`) — user's earlier reserve edits from 2026-08-14 preserved.
- Lot status and countdown (`lot_status`, `lot_end_time`).

---

## 7. Rollback instructions (if ever needed)

Given the two JSON snapshots preserved on disk:

```python
# Restore the lot_bids row:
db.lot_bids.insert_one(BEFORE_snapshot["before"]["lot_bid_row"])

# Restore the auto_bids row:
db.auto_bids.insert_one(BEFORE_snapshot["before"]["auto_bid_row"])

# Restore inline lot state:
db.multi_item_listings.update_one(
    {"id": "58758582-f53a-46d8-bc0b-87cf9de60523"},
    {"$set": {
        "lots.$[l].current_price":     7,
        "lots.$[l].bid_count":         1,
        "lots.$[l].highest_bidder_id": "8940074d-da97-43ca-9a0b-c59d39411ed6",
    }},
    array_filters=[{"l.lot_number": 1}],
)
```

Rollback is exact and reversible because all three writes are on primary-keyed docs.
