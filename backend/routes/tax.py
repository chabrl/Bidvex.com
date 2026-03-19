"""
Tax Calculation Router
Exposes the central tax engine (services/tax_engine.py) via REST endpoints.

All Quebec GST/QST math lives in tax_engine — this router is a thin HTTP layer.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional

from services.tax_engine import (
    calculate_gst_qst,
    calculate_tax,
    calculate_vehicle_payment,
    calculate_general_payment,
    get_tax_structure_summary,
    get_tax_rates_for_currency,
    invoice_tax_lines,
    BUYER_PREMIUM_RATES,
    GST_RATE,
    QST_RATE,
    BIDVEX_GST_NUMBER,
    BIDVEX_QST_NUMBER,
    BIDVEX_LEGAL_NAME,
    BIDVEX_ADDRESS,
)
from decimal import Decimal

tax_calc_router = APIRouter(prefix="/tax-calc", tags=["Tax Calculations"])


class TaxCalcRequest(BaseModel):
    """Request body for tax calculation."""
    subtotal: float = Field(..., gt=0, description="Pre-tax amount in dollars")
    currency: str = Field(default="CAD", description="Currency code (only CAD is taxed)")
    buyers_premium_rate: Optional[float] = Field(default=None, description="Listing-level buyer premium rate (e.g. 0.15 for 15%)")


class TaxCalcResponse(BaseModel):
    """Response for tax calculation."""
    subtotal: float
    gst_rate: float
    gst_amount: float
    qst_rate: float
    qst_amount: float
    total_tax: float
    total_with_tax: float
    currency: str
    gst_registration: str
    qst_registration: str
    buyers_premium_rate: Optional[float] = None
    buyers_premium_amount: Optional[float] = None


@tax_calc_router.post("/calculate", response_model=TaxCalcResponse)
async def calculate_tax_endpoint(request: TaxCalcRequest):
    """
    Calculate GST (5%) and QST (9.975%) on a given subtotal.

    Uses Decimal arithmetic with ROUND_HALF_UP for accounting precision.
    Example: $100.00 -> GST $5.00, QST $9.98, Total $114.98

    If buyers_premium_rate is provided, appends the premium amount to the response.
    """
    result = calculate_gst_qst(request.subtotal, request.currency)
    if request.buyers_premium_rate is not None:
        premium_amount = round(request.subtotal * request.buyers_premium_rate, 2)
        result["buyers_premium_rate"] = request.buyers_premium_rate
        result["buyers_premium_amount"] = premium_amount
    return result


@tax_calc_router.get("/rates")
async def get_tax_rates(currency: str = Query(default="CAD", description="Currency code")):
    """
    Return current tax rates, registration numbers, and BidVex legal info.
    """
    rates = get_tax_rates_for_currency(currency)
    return {
        "gst_rate_percent": round(rates["tax_rate_gst"], 4),
        "qst_rate_percent": round(rates["tax_rate_qst"], 4),
        "combined_rate_percent": round(rates["tax_rate_gst"] + rates["tax_rate_qst"], 4),
        "gst_registration": BIDVEX_GST_NUMBER,
        "qst_registration": BIDVEX_QST_NUMBER,
        "legal_name": BIDVEX_LEGAL_NAME,
        "address": BIDVEX_ADDRESS,
        "currency": currency,
    }


@tax_calc_router.get("/structure")
async def get_tax_structure():
    """
    Return the full tax structure documentation (jurisdiction, vehicle vs general rules, etc.).
    """
    return get_tax_structure_summary()


@tax_calc_router.get("/invoice-lines")
async def get_invoice_lines(
    subtotal: float = Query(..., gt=0, description="Pre-tax amount"),
    currency: str = Query(default="CAD", description="Currency code"),
):
    """
    Generate tax line items suitable for invoice templates and SendGrid dynamic data.
    """
    lines = invoice_tax_lines(subtotal, currency)
    return {"lines": lines, "subtotal": round(subtotal, 2), "currency": currency}
