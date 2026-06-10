"""
services/email_notifications.py — iter295 P2 / iter297 P2

# ============================================================ #
#                                                              #
#  DEPRECATED — DO NOT USE THIS MODULE IN NEW CODE.            #
#                                                              #
#  Use the bucketed modules directly:                          #
#    services.emails.email_vehicles     — vehicle-specific     #
#    services.emails.email_marketplace  — marketplace + lots   #
#                                          + storage senders   #
#    services.emails.email_system       — welcome, invoices,   #
#                                          subscriptions, ...  #
#                                                              #
#  This file remains as a backward-compat shim ONLY so the     #
#  ~80 legacy `from services.email_notifications import …`     #
#  call sites keep working. A DeprecationWarning is emitted on #
#  EVERY import so the migration to the bucketed modules is    #
#  visible in logs.                                            #
#                                                              #
#  TODO(iter310): remove this shim once every caller is        #
#  migrated. Tracking ticket: BIDVEX-EMAIL-SHIM-REMOVAL.       #
#                                                              #
# ============================================================ #

BACKWARD-COMPAT SHIM. The function bodies have been physically
migrated to services/emails/{email_vehicles,email_marketplace,email_system}.py.
This file only re-exports them so the ~80 callers across the
codebase keep working unchanged.

New callers should import from the bucketed modules directly:
    from services.emails.email_vehicles    import send_dealer_license_approved_email
    from services.emails.email_marketplace import send_auction_won_email
    from services.emails.email_system      import send_welcome_email
"""
import warnings as _warnings
import logging as _logging

_warnings.warn(
    "services.email_notifications is deprecated — import from "
    "services.emails.email_{vehicles,marketplace,system} directly. "
    "This shim will be removed in iter310 (tracking ticket "
    "BIDVEX-EMAIL-SHIM-REMOVAL).",
    DeprecationWarning,
    stacklevel=2,
)
_logging.getLogger(__name__).info(
    "[DEPRECATED] services.email_notifications imported — migrate "
    "caller to services.emails.email_{vehicles,marketplace,system}"
)

from services.emails._email_core import (  # noqa: F401, E402 — re-export
    SENDGRID_API_KEY, SENDGRID_AVAILABLE, sg, FRONTEND_URL,
    FROM_EMAIL, FROM_NAME,
    TRANSACTIONAL_FROM_EMAIL, TRANSACTIONAL_FROM_NAME,
    TRANSACTIONAL_REPLY_TO, TRANSACTIONAL_REPLY_TO_NAME,
    B2B_PARTNER_FROM_EMAIL, B2B_PARTNER_FROM_NAME,
    B2B_PARTNER_REPLY_TO, B2B_PARTNER_REPLY_TO_NAME,
    MARKETING_REPLY_TO, MARKETING_REPLY_TO_NAME,
    _format_currency, _format_date, _format_currency_fr,
    _detect_language, _section_label, _base_template, _storage_panel,
    send_email, send_unified_email, _send_via_unified,
)
from services.emails.email_vehicles import (  # noqa: F401 — re-export
    send_buyer_verification_decision_email,
    send_dealer_license_approved_email,
    send_dealer_license_expired_email,
    send_dealer_license_expiring_email,
    send_dealer_license_rejected_email,
    send_listing_requires_action_email,
    send_seller_auction_no_bids_email,
    send_seller_auction_sold_email,
    send_seller_license_expired_email,
    send_vehicle_deposit_captured_email,
)
from services.emails.email_marketplace import (  # noqa: F401 — re-export
    send_auction_sold_email,
    send_auction_won_email,
    send_bid_placed_email,
    send_buyer_pickup_code_email,
    send_outbid_email,
    send_seller_bid_received_email,
    send_seller_pickup_instructions_email,
    send_storage_auction_sold_email,
    send_storage_auction_won_email,
    send_storage_bid_placed_email,
    send_storage_ending_soon_email,
    send_storage_facility_approved_email,
    send_storage_facility_pending_user_email,
    send_storage_facility_registration_admin_alert,
    send_storage_facility_registration_rejected_email,
    send_storage_facility_registration_verified_email,
    send_storage_outbid_email,
    send_storage_seller_commission_invoice,
)
from services.emails.email_system import (  # noqa: F401 — re-export
    send_auction_thread_opened_email,
    send_charge_confirmation_email,
    send_deposit_refunded_email,
    send_document_approved_email,
    send_document_rejected_email,
    send_invoice_created_email,
    send_invoice_overdue_email,
    send_manual_subscription_active_email,
    send_new_message_email,
    send_payment_confirmation_email,
    send_payment_overdue_email,
    send_payment_reminder_email,
    send_payout_confirmation_email,
    send_promotion_confirmation_email,
    send_promotion_email_blast,
    send_promotion_expired_email,
    send_review_request_email,
    send_seller_approved_email,
    send_subscription_expired_email,
    send_subscription_reminder_email,
    send_subscription_upgraded_email,
    send_welcome_email,
)
