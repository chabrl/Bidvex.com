"""
services/emails/email_system.py — iter294 P2

Cross-cutting / system-level email senders (welcome, invoices,
subscriptions, payments, charges, messages, etc.). Sourced from
`services/email_notifications.py` for backwards-compat.

Public surface:
    send_email                              — low-level dispatcher
    send_unified_email                      — branded template wrapper
    send_welcome_email
    send_invoice_*                          — invoice lifecycle
    send_payment_confirmation_email
    send_payment_reminder_email
    send_payment_overdue_email
    send_document_approved_email
    send_document_rejected_email
    send_seller_approved_email
    send_subscription_*                     — subscription lifecycle
    send_review_request_email
    send_manual_subscription_active_email
    send_auction_thread_opened_email
    send_promotion_*                        — promotion emails
    send_deposit_refunded_email
    send_charge_confirmation_email
    send_payout_confirmation_email
    send_new_message_email
    send_listing_requires_action_email
    send_buyer_verification_decision_email
"""
from services.email_notifications import (  # noqa: F401
    send_email,
    send_unified_email,
    send_welcome_email,
    send_invoice_created_email,
    send_invoice_overdue_email,
    send_payment_confirmation_email,
    send_payment_reminder_email,
    send_payment_overdue_email,
    send_document_approved_email,
    send_document_rejected_email,
    send_seller_approved_email,
    send_subscription_reminder_email,
    send_subscription_expired_email,
    send_subscription_upgraded_email,
    send_review_request_email,
    send_manual_subscription_active_email,
    send_auction_thread_opened_email,
    send_promotion_confirmation_email,
    send_promotion_expired_email,
    send_promotion_email_blast,
    send_deposit_refunded_email,
    send_charge_confirmation_email,
    send_payout_confirmation_email,
    send_new_message_email,
    send_listing_requires_action_email,
    send_buyer_verification_decision_email,
)

__all__ = [
    "send_email", "send_unified_email", "send_welcome_email",
    "send_invoice_created_email", "send_invoice_overdue_email",
    "send_payment_confirmation_email", "send_payment_reminder_email",
    "send_payment_overdue_email",
    "send_document_approved_email", "send_document_rejected_email",
    "send_seller_approved_email",
    "send_subscription_reminder_email", "send_subscription_expired_email",
    "send_subscription_upgraded_email",
    "send_review_request_email", "send_manual_subscription_active_email",
    "send_auction_thread_opened_email",
    "send_promotion_confirmation_email", "send_promotion_expired_email",
    "send_promotion_email_blast",
    "send_deposit_refunded_email", "send_charge_confirmation_email",
    "send_payout_confirmation_email",
    "send_new_message_email", "send_listing_requires_action_email",
    "send_buyer_verification_decision_email",
]
