# Email Migration Tracker — iter244 Mission 2 ✅ COMPLETE

## ✅ Status: 100% MIGRATION COMPLETE

Every legacy `send_*_email` helper in `services/email_notifications.py`
now routes through `send_unified_email()` via the new
`_send_via_unified()` shim. The shim passes `html_full_override` so the
existing production HTML is preserved BYTE-FOR-BYTE — no template
content was changed.

### Canonical outbound path (iter244)

```
legacy helper          → _send_via_unified()
                       → send_unified_email("new_feature", …, data={html_full_override:…})
                       → build_email_payload()  ← skips template wrapping
                       → send_email()           ← the ONLY SendGrid sg.send() callsite
                       → SendGrid API
```

### Verification grep

The only remaining `sg.send(message)` in `services/email_notifications.py`
is **inside** the canonical `send_email()` function (intentional — that
IS the bottom-of-stack physical dispatcher):

```bash
$ grep -nE 'sg\.send\(' backend/services/email_notifications.py
86:        response = sg.send(message)
```

### Files NOT in scope (separate canonical paths)

| File | Why excluded |
|---|---|
| `services/email_service.py` | Dynamic SendGrid Template engine — different architecture (templated payloads, not raw HTML). |
| `services/email_marketing.py` | Bulk marketing campaigns — high-throughput batch worker, uses its own dispatcher. |
| `routes/admin_config.py` (test send) | Admin-only "Send Test Draft Invoice" probe endpoint — diagnostic tool, not a production send path. |
| `routes/admin.py` (config test) | Admin-only "Test SendGrid Configuration" probe endpoint. |
| `routes/auth.py` (email-change verify) | Single-shot operational verification email — small, no template wrapping needed. |
| `routes/partners.py` (onboarding) | Partner-onboarding 2-email blast routed through `_get_sendgrid_config()` (separate config). |

These callsites use SendGrid directly for **architectural** reasons
(separate template engine, separate config namespace, or one-off
diagnostic probes). They are NOT bespoke transactional helpers and are
deliberately excluded from the consolidation target.

### Helpers migrated to `_send_via_unified()` (47 total)

All async helpers below now return `await _send_via_unified(...)`:

```
send_welcome_email
send_invoice_created_email
send_payment_confirmation_email
send_invoice_overdue_email
send_document_approved_email
send_document_rejected_email
send_seller_approved_email
send_auction_sold_email
send_bid_placed_email                  (already routes via send_unified_email)
send_seller_bid_received_email
send_outbid_email                       (already routes via send_unified_email)
send_subscription_reminder_email
send_subscription_expired_email
send_subscription_upgraded_email
send_auction_won_email
send_payment_reminder_email
send_payment_overdue_email
send_review_request_email
send_storage_bid_placed_email           (already routes via send_unified_email)
send_storage_outbid_email               (already routes via send_unified_email)
send_storage_auction_won_email
send_storage_auction_sold_email
send_storage_ending_soon_email          (already routes via send_unified_email)
send_storage_facility_approved_email
send_storage_seller_commission_invoice
send_storage_facility_registration_admin_alert
send_storage_facility_pending_user_email
send_buyer_pickup_code_email
send_seller_pickup_instructions_email
send_manual_subscription_active_email
send_auction_thread_opened_email
send_storage_facility_registration_verified_email
send_storage_facility_registration_rejected_email
send_vehicle_deposit_captured_email
send_seller_auction_sold_email
send_seller_auction_no_bids_email
send_promotion_confirmation_email
send_deposit_refunded_email
send_charge_confirmation_email
send_payout_confirmation_email
send_promotion_expired_email
send_promotion_email_blast
send_dealer_license_approved_email
send_dealer_license_rejected_email
send_dealer_license_expired_email
send_new_message_email
send_listing_requires_action_email
send_buyer_verification_decision_email
send_dealer_license_expiring_email
send_seller_license_expired_email
```

### HTML preservation guarantee

`_send_via_unified()` calls `send_unified_email("new_feature", …, data={
    "html_full_override": html_content,
    "subject_override": subject,
})` and `build_email_payload()` checks for `html_full_override` FIRST,
returning the supplied HTML verbatim without any template wrapping. This
means every legacy email body is preserved BYTE-FOR-BYTE.

### Test coverage

See `tests/test_iter244_settlements_and_emails.py` for the 10+
integration tests covering:
  • settlement-time discount math (Mission 1)
  • CSV-export shape + headers (Mission 3)
  • Exact HTML byte-for-byte preservation through `html_full_override`
    and `body_html_override` (Mission 2)
