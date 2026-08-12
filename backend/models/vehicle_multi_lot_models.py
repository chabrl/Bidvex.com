"""
Multi-Lot Vehicle Auction Models — iter293 (Directive 2)
========================================================

Models a Copart / wholesale-style auction EVENT containing multiple
vehicle LOTS that go live sequentially (or simultaneously with staggered
starts). A single dealer organises the event; each lot has its own
title, photos, condition report, deposit gate, bid history, and winner.

Storage model (single document per event):
    {
      "id":                   <event_id>,
      "title":                "March Wholesale Block",
      "seller_id":            <dealer_id>,
      "timing_mode":          "sequential" | "staggered",
      "start_time":           <event_kickoff_iso>,
      "lot_duration_seconds": 120,   # 2-min window per lot (sequential)
      "stagger_offset_seconds": 60,  # 1-min offset between starts (staggered)
      "status":               "draft" | "upcoming" | "live" | "ended" | "cancelled",
      "current_active_lot_index": 0,
      "lot_sequence":         [<lot_id_1>, <lot_id_2>, ...],
      "lots": [
        {
          "id":             <lot_id>,
          "lot_number":     1,
          "vin":            "...",
          "title":          "...",
          "year":           2020,
          "make":           "Ford",
          "model":          "F-350",
          "starting_price": 10000,
          "current_bid":    0,
          "reserve_price":  null,
          "media":          [...],
          "condition_report": {...},
          "status":         "upcoming" | "live" | "ended" | "sold",
          "start_time":     null,         # set when activated
          "end_time":       null,         # set when activated; extended on soft-close
          "winner_user_id": null,
          "winner_bid_id":  null,
          "bid_count":      0,
        },
        ...
      ],
      "bids": [                            # flat per-event bid log
        {"id": ..., "lot_id": ..., "user_id": ..., "amount": ..., "created_at": ...},
        ...
      ],
      "created_at": ...,
      "updated_at": ...,
    }

Constraints honoured:
- Vehicle Buyer Premium = 0% applies per lot (handled by the existing
  vehicle fee pipeline; lots use the same `compute_buyer_premium`).
- Vehicle Platform Fee = 2.5% applies per lot.
- Deposits per lot = max($200, 10%) — same as single-vehicle auctions.
- Soft-close 2-minute snipe extension applies independently to each lot.
"""
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, timezone
from enum import Enum


# ============= ENUMS =============

class MultiLotTimingMode(str, Enum):
    """How lots inside an event activate.

    SEQUENTIAL  — Copart default. Lot 1 runs for its full window; when it
                  ends (or its soft-close timer drains), Lot 2 auto-
                  activates with `lot_duration_seconds` (default 120s).

    STAGGERED   — All lots start within the same window, each offset
                  from the previous by `stagger_offset_seconds`
                  (default 60s). Use when buyers should be able to
                  watch multiple lots simultaneously.
    """
    SEQUENTIAL = "sequential"
    STAGGERED  = "staggered"


class MultiLotEventStatus(str, Enum):
    DRAFT     = "draft"      # editable by dealer, hidden from public
    UPCOMING  = "upcoming"   # publicly visible, countdown until kickoff
    LIVE      = "live"       # at least one lot is bidding
    ENDED     = "ended"      # all lots have closed
    CANCELLED = "cancelled"  # admin / dealer voided the event


class MultiLotItemStatus(str, Enum):
    UPCOMING = "upcoming"
    LIVE     = "live"
    ENDED    = "ended"
    SOLD     = "sold"


# ============= CREATE PAYLOAD =============

class MultiLotItemCreate(BaseModel):
    """Single lot inside a multi-lot vehicle auction event."""
    vin: str = Field(..., min_length=17, max_length=17)
    year: int = Field(..., ge=1900, le=2100)
    make: str = Field(..., min_length=1, max_length=64)
    model: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=3, max_length=200)
    # iter299 P0 — Bill 96: French lot title (required for QC-located lots).
    title_fr: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = ""
    mileage: int = Field(..., ge=0)
    body_type: str = "sedan"
    transmission: str = "automatic"
    fuel_type: str = "gasoline"
    drivetrain: str = "fwd"
    exterior_color: str = "Unknown"
    interior_color: str = "Unknown"
    ownership_status: str = "owned"
    title_status: str = "clean"
    lien_status: str = "clear"
    location_city: str
    location_province: str
    location_postal_code: Optional[str] = None
    starting_price: float = Field(..., gt=0)
    reserve_price: Optional[float] = None
    bid_increment: float = Field(100.0, gt=0)
    media: List[Dict[str, Any]] = Field(default_factory=list)
    condition_report: Optional[Dict[str, Any]] = None

    @field_validator("vin")
    @classmethod
    def vin_alphanumeric(cls, v: str) -> str:
        v = v.strip().upper()
        if not v.isalnum():
            raise ValueError("VIN must be alphanumeric")
        return v


class MultiLotAuctionCreate(BaseModel):
    """Create payload for a multi-lot vehicle auction event."""
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = ""
    timing_mode: MultiLotTimingMode = MultiLotTimingMode.SEQUENTIAL
    start_time: datetime
    # iter302 Directive 3 — 60s hard minimum per lot (server-side enforcement).
    lot_duration_seconds: int = Field(120, ge=60, le=3600)
    stagger_offset_seconds: int = Field(60, ge=30, le=600)
    # iter306 — Allow zero lots when submission_intent='draft' (CSV bulk import
    # flow: dealer first creates the event stub, then appends lots via the
    # bulk-import endpoint). live/schedule still require ≥1 lot — enforced
    # below in the model_validator.
    lots: List[MultiLotItemCreate] = Field(default_factory=list, max_length=200)
    submission_intent: Optional[str] = "live"   # draft / schedule / live
    # iter482 P4B — Seller-Controlled Accepted Payment Methods (multi-select).
    accepted_payment_methods: Optional[List[str]] = None

    @field_validator("accepted_payment_methods")
    @classmethod
    def _vapm(cls, v):
        if v is None:
            return None
        from services.payment_methods_registry import normalise_list
        return normalise_list(v)

    @field_validator("submission_intent")
    @classmethod
    def normalise_intent(cls, v: Optional[str]) -> str:
        v = (v or "live").lower().strip()
        if v not in ("draft", "schedule", "live"):
            raise ValueError("submission_intent must be one of draft / schedule / live")
        return v

    @model_validator(mode="after")
    def _live_or_schedule_requires_lots(self):
        if self.submission_intent in ("live", "schedule") and len(self.lots) < 1:
            raise ValueError("At least 1 lot is required to schedule or go live.")
        return self


class MultiLotBidCreate(BaseModel):
    """Place a bid on one lot inside a multi-lot event."""
    event_id: str
    lot_id: str
    amount: float = Field(..., gt=0)
