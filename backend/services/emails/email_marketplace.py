"""
services/emails/email_marketplace.py — iter294 P2

Marketplace + lots + storage email senders. Sourced from
`services/email_notifications.py` for backwards-compat. See iter294 PRD
entry for split rationale.

Public surface:
    send_bid_placed_email           — buyer side
    send_seller_bid_received_email  — seller side
    send_outbid_email               — bidder loses lead
    send_auction_won_email          — bidder wins
    send_auction_sold_email         — seller side
    send_storage_*                  — storage auction flows
    send_buyer_pickup_code_email
    send_seller_pickup_instructions_email
"""
from services.email_notifications import (  # noqa: F401
    send_bid_placed_email,
    send_seller_bid_received_email,
    send_outbid_email,
    send_auction_won_email,
    send_auction_sold_email,
    send_storage_bid_placed_email,
    send_storage_outbid_email,
    send_storage_auction_won_email,
    send_storage_auction_sold_email,
    send_storage_ending_soon_email,
    send_storage_facility_approved_email,
    send_storage_seller_commission_invoice,
    send_storage_facility_registration_admin_alert,
    send_storage_facility_pending_user_email,
    send_storage_facility_registration_verified_email,
    send_storage_facility_registration_rejected_email,
    send_buyer_pickup_code_email,
    send_seller_pickup_instructions_email,
)

__all__ = [
    "send_bid_placed_email",
    "send_seller_bid_received_email",
    "send_outbid_email",
    "send_auction_won_email",
    "send_auction_sold_email",
    "send_storage_bid_placed_email",
    "send_storage_outbid_email",
    "send_storage_auction_won_email",
    "send_storage_auction_sold_email",
    "send_storage_ending_soon_email",
    "send_storage_facility_approved_email",
    "send_storage_seller_commission_invoice",
    "send_storage_facility_registration_admin_alert",
    "send_storage_facility_pending_user_email",
    "send_storage_facility_registration_verified_email",
    "send_storage_facility_registration_rejected_email",
    "send_buyer_pickup_code_email",
    "send_seller_pickup_instructions_email",
]
