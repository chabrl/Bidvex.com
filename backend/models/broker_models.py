"""
iter217 Phase 5 Hotfix v5b — Broker Ecosystem data models.

Three Mongo collections back the broker ecosystem:

  brokers                       — registered brokers + their license/fee config
  broker_buyer_relationships    — N:1 relationship binding individual buyers
                                  under a licensed broker's umbrella
  broker_bids                   — IMMUTABLE audit trail (every broker-mediated
                                  bid recorded with full attribution)
  broker_invoices               — post-auction billing for completed deals

All four collections use UUID `id` fields and exclude Mongo `_id` from
responses (Pydantic models below). Datetime stored as UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid4())


# ── Fee structure ─────────────────────────────────────────────────────
class BrokerFeeStructure(BaseModel):
    type: Literal["fixed", "percentage"] = "fixed"
    fixed_amount_cad: float = 0.0
    percentage_rate: float = 0.0           # 0.03 == 3%
    min_fee_cad: Optional[float] = None
    max_fee_cad: Optional[float] = None

    @validator("percentage_rate")
    def _v_pct(cls, v: float) -> float:
        if v < 0 or v > 1:
            raise ValueError("percentage_rate must be between 0 and 1 (e.g. 0.03 for 3%)")
        return v

    @validator("fixed_amount_cad")
    def _v_fixed(cls, v: float) -> float:
        if v < 0:
            raise ValueError("fixed_amount_cad must be >= 0")
        return v


# ── Broker ────────────────────────────────────────────────────────────
BrokerStatus = Literal["pending_review", "approved", "rejected", "suspended"]


class BrokerCreate(BaseModel):
    legal_business_name:        str
    operating_province:         str    # 2-letter CA code
    corporate_registration_number: str
    broker_license_number:      str
    regulatory_body:            str    # OMVIC|AMVIC|VSA|SAAQ|OPC|...
    permit_type:                Literal["dealer", "broker", "agent", "corporation"] = "broker"

    license_document_url:       Optional[str] = None
    registration_document_url:  Optional[str] = None
    additional_documents:       List[str] = Field(default_factory=list)

    fee_structure:              BrokerFeeStructure
    default_deposit_amount_cad: float = 500.0

    # iter225 Task 2 — Dynamic provincial license fields
    qc_anq_number:              Optional[str] = None  # QC: Autorité des marchés publics (vehicles)
    qc_opc_number:              Optional[str] = None  # QC: Office de la protection du consommateur
    on_omvic_number:            Optional[str] = None  # ON: OMVIC
    bc_vsa_number:              Optional[str] = None  # BC: Vehicle Sales Authority
    ab_amvic_number:            Optional[str] = None  # AB: AMVIC


class BrokerOut(BaseModel):
    id:                          str
    user_id:                     str
    legal_business_name:         str
    operating_province:          str
    corporate_registration_number: str
    broker_license_number:       str
    regulatory_body:             str
    permit_type:                 str

    license_document_url:        Optional[str] = None
    registration_document_url:   Optional[str] = None
    additional_documents:        List[str] = Field(default_factory=list)

    verification_status:         BrokerStatus
    verification_notes:          Optional[str] = None
    verified_at:                 Optional[datetime] = None
    verified_by:                 Optional[str] = None
    rejection_reason:            Optional[str] = None
    suspended_at:                Optional[datetime] = None
    suspended_reason:            Optional[str] = None

    fee_structure:               BrokerFeeStructure
    default_deposit_amount_cad:  float = 500.0

    total_buyers_managed:        int = 0
    total_deals_completed:       int = 0
    total_revenue_cad:           float = 0.0

    created_at:                  datetime
    updated_at:                  datetime


def make_broker_doc(*, user_id: str, payload: BrokerCreate) -> Dict[str, Any]:
    now = _utcnow()
    return {
        "id":                          _new_id(),
        "user_id":                     user_id,
        "legal_business_name":         payload.legal_business_name.strip(),
        "operating_province":          payload.operating_province.strip().upper(),
        "corporate_registration_number": payload.corporate_registration_number.strip(),
        "broker_license_number":       payload.broker_license_number.strip(),
        "regulatory_body":             payload.regulatory_body.strip(),
        "permit_type":                 payload.permit_type,

        "license_document_url":        payload.license_document_url,
        "registration_document_url":   payload.registration_document_url,
        "additional_documents":        list(payload.additional_documents or []),

        "verification_status":         "pending_review",
        "verification_notes":          None,
        "verified_at":                 None,
        "verified_by":                 None,
        "rejection_reason":            None,
        "suspended_at":                None,
        "suspended_reason":            None,

        "fee_structure":               payload.fee_structure.dict(),
        "default_deposit_amount_cad":  float(payload.default_deposit_amount_cad),

        # iter225 Task 2 — Provincial license numbers (optional, set based on operating_province)
        "qc_anq_number":               (payload.qc_anq_number   or "").strip() or None,
        "qc_opc_number":               (payload.qc_opc_number   or "").strip() or None,
        "on_omvic_number":             (payload.on_omvic_number or "").strip() or None,
        "bc_vsa_number":               (payload.bc_vsa_number   or "").strip() or None,
        "ab_amvic_number":             (payload.ab_amvic_number or "").strip() or None,

        # iter225 Task 3 — Liability agreement (signed inline during apply or later)
        "liability_agreement":           None,
        "liability_agreement_signed":    False,
        "liability_agreement_signed_at": None,

        # iter225 Task 4 — Custom broker-buyer contract (set later from dashboard)
        "custom_terms_html":           None,
        "custom_terms_plain":          None,
        "custom_terms_enabled":        False,
        "custom_terms_updated_at":     None,

        "total_buyers_managed":        0,
        "total_deals_completed":       0,
        "total_revenue_cad":           0.0,

        "created_at":                  now,
        "updated_at":                  now,
    }


# ── Broker–buyer relationship ─────────────────────────────────────────
RelationshipStatus = Literal["pending", "approved", "active", "suspended", "terminated", "rejected"]
DepositStatus      = Literal["pending", "held", "released", "captured", "refunded", "failed"]


class RelationshipRequest(BaseModel):
    broker_id: str
    # The Stripe PaymentMethod ID returned by the front-end's
    # confirmCardSetup / SetupIntent flow. We attach it during the
    # PaymentIntent creation so the manual capture uses this card.
    payment_method_id: Optional[str] = None


class RelationshipOut(BaseModel):
    id:                                str
    broker_id:                         str
    buyer_user_id:                     str
    status:                            RelationshipStatus

    deposit_amount_cad:                float
    deposit_stripe_payment_intent_id:  Optional[str]
    deposit_status:                    DepositStatus
    deposit_held_at:                   Optional[datetime]
    deposit_released_at:               Optional[datetime]

    max_bid_amount_cad:                Optional[float]
    active_bids_count:                 int
    can_bid:                           bool

    kyc_verified:                      bool
    kyc_documents:                     List[str]
    kyc_verified_at:                   Optional[datetime]

    created_at:                        datetime
    updated_at:                        datetime


def make_relationship_doc(
    *,
    broker_id:           str,
    buyer_user_id:       str,
    deposit_amount_cad:  float = 500.0,
) -> Dict[str, Any]:
    now = _utcnow()
    return {
        "id":                              _new_id(),
        "broker_id":                       broker_id,
        "buyer_user_id":                   buyer_user_id,
        "status":                          "pending",

        "deposit_amount_cad":              float(deposit_amount_cad),
        "deposit_stripe_payment_intent_id": None,
        "deposit_status":                  "pending",
        "deposit_held_at":                 None,
        "deposit_released_at":             None,

        "max_bid_amount_cad":              None,
        "active_bids_count":               0,
        "can_bid":                         False,

        "kyc_verified":                    False,
        "kyc_documents":                   [],
        "kyc_verified_at":                 None,

        # iter225 Task 4 — Buyer's acknowledgment of broker's custom contract
        "custom_terms_accepted_at":        None,
        "custom_terms_acceptance":         None,

        "created_at":                      now,
        "updated_at":                      now,
    }


# ── Bid audit trail ───────────────────────────────────────────────────
BidStatus = Literal["placed", "outbid", "winning", "won", "cancelled"]


def make_broker_bid_doc(
    *,
    vehicle_listing_id:           str,
    broker_id:                    str,
    broker_license_number:        str,
    broker_legal_business_name:   str,
    buyer_user_id:                str,
    bid_amount_cad:               float,
    ip_address:                   Optional[str],
    user_agent:                   Optional[str],
    session_id:                   Optional[str],
    auction_state_snapshot:       Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "id":                          _new_id(),
        "vehicle_listing_id":          vehicle_listing_id,
        "broker_id":                   broker_id,
        "buyer_user_id":               buyer_user_id,
        "bid_amount_cad":              float(bid_amount_cad),

        "submitted_by_user_id":        buyer_user_id,
        "broker_license_number":       broker_license_number,
        "broker_legal_business_name":  broker_legal_business_name,

        "status":                      "placed",
        "placed_at":                   _utcnow(),
        "outbid_at":                   None,

        "ip_address":                  ip_address,
        "user_agent":                  user_agent,
        "session_id":                  session_id,
        "auction_state_snapshot":      auction_state_snapshot,
    }


# ── Invoice ───────────────────────────────────────────────────────────
PaymentStatus  = Literal["pending", "paid", "overdue", "failed"]
ReleaseStatus  = Literal["pending", "ready", "released", "delivered"]


def make_invoice_doc(
    *,
    vehicle_listing_id: str,
    broker_id:          str,
    buyer_user_id:      str,
    dealer_user_id:     str,
    hammer_price_cad:   float,
    bidvex_platform_fee_cad: float,
    broker_fee_cad:     float,
    gst_cad:            float,
    qst_cad:            float,
    total_cad:          float,
    pickup_code:        str,
    fee_breakdown:      Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    now = _utcnow()
    # 12-char alphanumeric receipt token (v8.1) — used in public /my-receipt URL
    import secrets, string
    _alphabet = string.ascii_letters + string.digits
    receipt_token = "".join(secrets.choice(_alphabet) for _ in range(12))
    return {
        "id":                          _new_id(),
        "invoice_number":              f"BVX-{now.year}-{str(uuid4())[:6].upper()}",
        "vehicle_listing_id":          vehicle_listing_id,
        "broker_id":                   broker_id,
        "buyer_user_id":               buyer_user_id,
        "dealer_user_id":              dealer_user_id,

        # ─── Hammer (Section A — direct settlement, not Stripe) ───
        "hammer_price_cad":            float(hammer_price_cad),
        "hammer_settlement":           "direct",
        "hammer_payment_received":     False,
        "hammer_payment_method":       None,    # wire | cheque | trust | other
        "hammer_payment_confirmed_at": None,
        "hammer_payment_confirmed_by": None,
        "hammer_payment_proof_url":    None,
        "hammer_payment_note":         None,

        # ─── Service fees (Section B — Stripe-charged) ────────────
        "bidvex_platform_fee_cad":     float(bidvex_platform_fee_cad),
        "broker_fee_cad":              float(broker_fee_cad),
        "gst_cad":                     float(gst_cad),
        "qst_cad":                     float(qst_cad),
        "total_cad":                   float(total_cad),   # Stripe charge total
        "fee_breakdown":               fee_breakdown or {},

        "buyer_payment_status":        "pending",          # pending|paid|overdue|failed
        "buyer_paid_at":               None,
        "stripe_payment_intent_id":    None,
        "stripe_payment_status":       None,               # pending|succeeded|failed
        "stripe_confirmed_at":         None,

        # ─── Release ──────────────────────────────────────────────
        "vehicle_release_status":      "pending",          # pending|ready|released|delivered
        "pickup_code":                 pickup_code,
        "released_at":                 None,

        # ─── Dispute / timeout state ──────────────────────────────
        "reminder_sent_at":            None,
        "non_responsive_flagged_at":   None,
        "admin_action":                None,                # re_auction|deposit_forfeit|suspend_buyer
        "dispute_status":              "none",              # none|open|resolved
        "dispute_opened_at":           None,
        "dispute_resolved_at":         None,
        "dispute_deadline_at":         None,                # released_at + 7 days

        "created_at":                  now,
        # v8.1 — Sharable receipt token (public /my-receipt/{id}?code={token})
        "receipt_token":               receipt_token,
    }
