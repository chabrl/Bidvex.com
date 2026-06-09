"""
services/emails/email_vehicles.py — iter294 P2

Vehicle-specific email senders. Sourced from `services/email_notifications.py`
to avoid breaking any existing imports across the codebase. Over time
the underlying implementations can migrate here verbatim.

Public surface:
    send_vehicle_deposit_captured_email
    send_dealer_license_approved_email
    send_dealer_license_rejected_email
    send_dealer_license_expired_email
    send_seller_auction_sold_email
    send_seller_auction_no_bids_email
"""
from services.email_notifications import (  # noqa: F401
    send_vehicle_deposit_captured_email,
    send_dealer_license_approved_email,
    send_dealer_license_rejected_email,
    send_dealer_license_expired_email,
    send_seller_auction_sold_email,
    send_seller_auction_no_bids_email,
)

__all__ = [
    "send_vehicle_deposit_captured_email",
    "send_dealer_license_approved_email",
    "send_dealer_license_rejected_email",
    "send_dealer_license_expired_email",
    "send_seller_auction_sold_email",
    "send_seller_auction_no_bids_email",
]
