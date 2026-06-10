"""iter241 Mission 2 — Bidding emails (bid placed, outbid, won)."""
from services.emails.email_marketplace import (
    send_bid_placed_email,
    send_outbid_email,
    send_auction_won_email,
    send_seller_bid_received_email,
    send_auction_sold_email,
)

__all__ = [
    "send_bid_placed_email",
    "send_outbid_email",
    "send_auction_won_email",
    "send_seller_bid_received_email",
    "send_auction_sold_email",
]
