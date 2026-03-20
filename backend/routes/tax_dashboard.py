"""
Admin Tax Dashboard Router
Provides aggregated tax collection data for GST, QST, HST.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
import logging
import csv
import io

logger = logging.getLogger(__name__)

tax_dashboard_router = APIRouter(prefix="/admin/tax-dashboard", tags=["Admin Tax Dashboard"])
security = HTTPBearer(auto_error=False)

db = None

def set_tax_dashboard_db(database):
    global db
    db = database

# Tax rates (mirror tax_engine.py constants)
GST_RATE = Decimal("0.05")
QST_RATE = Decimal("0.09975")
HST_RATES = {
    "ON": Decimal("0.13"),
    "NB": Decimal("0.15"),
    "NL": Decimal("0.15"),
    "NS": Decimal("0.15"),
    "PE": Decimal("0.15"),
}
QC_CODE = "QC"

# Provinces that use HST
HST_PROVINCES = set(HST_RATES.keys())
# Provinces that use GST+QST
GST_QST_PROVINCES = {"QC"}
# All other Canadian provinces use GST only


async def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from jose import jwt
    import os
    try:
        payload = jwt.decode(credentials.credentials, os.environ.get("JWT_SECRET"), algorithms=["HS256"])
        user_id = payload.get("sub")
        user = await db.users.find_one({"id": user_id})
        if not user or user.get("role") not in ["admin", "super_admin"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_quarter_dates(quarter: str):
    """Return (start, end) datetime for quarter string like 'current', 'last', or 'YYYY-Q1'."""
    now = datetime.now(timezone.utc)
    current_q = (now.month - 1) // 3 + 1
    current_year = now.year

    if quarter == "current":
        q = current_q
        y = current_year
    elif quarter == "last":
        q = current_q - 1
        y = current_year
        if q < 1:
            q = 4
            y -= 1
    else:
        # Format: 2026-Q1
        try:
            parts = quarter.split("-Q")
            y = int(parts[0])
            q = int(parts[1])
        except (ValueError, IndexError):
            return None, None

    start_month = (q - 1) * 3 + 1
    start = datetime(y, start_month, 1, tzinfo=timezone.utc)
    if q == 4:
        end = datetime(y + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(y, start_month + 3, 1, tzinfo=timezone.utc)
    return start, end


def compute_tax_for_transaction(tx):
    """Compute GST, QST, HST amounts from a transaction's fee data and region."""
    region = tx.get("seller_region", tx.get("region", "QC"))
    taxable_amount = Decimal(str(tx.get("platform_fee", 0))) + Decimal(str(tx.get("buyer_premium", 0)))

    gst = Decimal("0")
    qst = Decimal("0")
    hst = Decimal("0")

    if region in HST_PROVINCES:
        rate = HST_RATES.get(region, Decimal("0.13"))
        hst = (taxable_amount * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    elif region in GST_QST_PROVINCES:
        gst = (taxable_amount * GST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        qst = (taxable_amount * QST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        # GST only (Alberta, BC, SK, MB, etc.)
        gst = (taxable_amount * GST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "gst": float(gst),
        "qst": float(qst),
        "hst": float(hst),
        "total_tax": float(gst + qst + hst),
        "taxable_amount": float(taxable_amount),
        "region": region,
    }


@tax_dashboard_router.get("/summary")
async def tax_dashboard_summary(
    period: str = Query("current", description="current, last, YYYY-Q1, or all"),
    start_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    admin: dict = Depends(get_admin_user),
):
    """
    Aggregated tax dashboard with GST/QST/HST totals, regional breakdown, and reserve tracking.
    """
    # Build date filter
    date_filter = {}
    if start_date and end_date:
        try:
            s = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
            e = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            date_filter = {"created_at": {"$gte": s, "$lte": e}}
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    elif period != "all":
        s, e = get_quarter_dates(period)
        if s and e:
            date_filter = {"created_at": {"$gte": s, "$lt": e}}

    # Query completed transactions
    query = {"status": {"$in": ["completed", "paid", "succeeded"]}}
    query.update(date_filter)

    transactions = await db.transactions.find(
        query,
        {"_id": 0, "platform_fee": 1, "buyer_premium": 1, "hammer_price": 1,
         "seller_region": 1, "region": 1, "created_at": 1, "listing_title": 1,
         "listing_id": 1, "buyer_email": 1, "seller_email": 1, "status": 1}
    ).sort("created_at", -1).to_list(10000)

    # Compute tax for each transaction
    total_gst = Decimal("0")
    total_qst = Decimal("0")
    total_hst = Decimal("0")
    total_taxable = Decimal("0")
    total_hammer = Decimal("0")
    regional_breakdown = {}
    tx_count = len(transactions)

    for tx in transactions:
        tax_info = compute_tax_for_transaction(tx)
        total_gst += Decimal(str(tax_info["gst"]))
        total_qst += Decimal(str(tax_info["qst"]))
        total_hst += Decimal(str(tax_info["hst"]))
        total_taxable += Decimal(str(tax_info["taxable_amount"]))
        total_hammer += Decimal(str(tx.get("hammer_price", 0)))

        region = tax_info["region"] or "Unknown"
        if region not in regional_breakdown:
            regional_breakdown[region] = {"gst": 0, "qst": 0, "hst": 0, "total_tax": 0, "transactions": 0, "taxable_amount": 0}
        regional_breakdown[region]["gst"] += tax_info["gst"]
        regional_breakdown[region]["qst"] += tax_info["qst"]
        regional_breakdown[region]["hst"] += tax_info["hst"]
        regional_breakdown[region]["total_tax"] += tax_info["total_tax"]
        regional_breakdown[region]["transactions"] += 1
        regional_breakdown[region]["taxable_amount"] += tax_info["taxable_amount"]

    total_tax_collected = float(total_gst + total_qst + total_hst)
    total_revenue = float(total_taxable)

    # Net cash = total_taxable (fees collected) - total_tax (must remit)
    net_operating_cash = total_revenue - total_tax_collected

    # Regional breakdown as sorted list
    regional_list = [
        {"region": k, **v}
        for k, v in sorted(regional_breakdown.items(), key=lambda x: x[1]["total_tax"], reverse=True)
    ]

    return {
        "period": period,
        "date_range": {
            "start": date_filter.get("created_at", {}).get("$gte", "").isoformat() if date_filter.get("created_at", {}).get("$gte") else None,
            "end": (date_filter.get("created_at", {}).get("$lte") or date_filter.get("created_at", {}).get("$lt", "")).isoformat() if date_filter.get("created_at") else None,
        },
        "totals": {
            "gst_collected": float(total_gst),
            "qst_collected": float(total_qst),
            "hst_collected": float(total_hst),
            "total_tax_collected": total_tax_collected,
            "total_taxable_revenue": total_revenue,
            "total_hammer_volume": float(total_hammer),
            "transaction_count": tx_count,
        },
        "reserve": {
            "total_revenue": total_revenue,
            "tax_liability": total_tax_collected,
            "net_operating_cash": net_operating_cash,
        },
        "regional_breakdown": regional_list,
    }


@tax_dashboard_router.get("/export-csv")
async def export_tax_csv(
    period: str = Query("current"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    admin: dict = Depends(get_admin_user),
):
    """Export tax data as CSV for accountant / CRA filing."""
    date_filter = {}
    if start_date and end_date:
        try:
            s = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
            e = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            date_filter = {"created_at": {"$gte": s, "$lte": e}}
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    elif period != "all":
        s, e = get_quarter_dates(period)
        if s and e:
            date_filter = {"created_at": {"$gte": s, "$lt": e}}

    query = {"status": {"$in": ["completed", "paid", "succeeded"]}}
    query.update(date_filter)

    transactions = await db.transactions.find(
        query,
        {"_id": 0, "platform_fee": 1, "buyer_premium": 1, "hammer_price": 1,
         "seller_region": 1, "region": 1, "created_at": 1, "listing_title": 1,
         "listing_id": 1, "buyer_email": 1, "seller_email": 1,
         "stripe_charge_id": 1}
    ).sort("created_at", 1).to_list(10000)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Transaction Date", "Listing ID", "Item Name",
        "Seller Email", "Seller Region (ISO)",
        "Hammer Price", "Commission Amount", "Buyer Premium",
        "GST (5%)", "QST (9.975%)", "HST", "Total Tax",
        "Stripe Charge ID"
    ])

    for tx in transactions:
        tax_info = compute_tax_for_transaction(tx)
        created = tx.get("created_at", "")
        if isinstance(created, datetime):
            created = created.strftime("%Y-%m-%d %H:%M:%S")

        writer.writerow([
            created,
            tx.get("listing_id", ""),
            tx.get("listing_title", ""),
            tx.get("seller_email", ""),
            tax_info["region"],
            tx.get("hammer_price", 0),
            tx.get("platform_fee", 0),
            tx.get("buyer_premium", 0),
            tax_info["gst"],
            tax_info["qst"],
            tax_info["hst"],
            tax_info["total_tax"],
            tx.get("stripe_charge_id", ""),
        ])

    csv_content = output.getvalue()
    output.close()

    filename = f"bidvex_tax_report_{period}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
