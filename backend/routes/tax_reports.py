"""
Tax Reporting Router
CRA compliance and tax report generation endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

tax_router = APIRouter(prefix="/tax", tags=["Tax Reporting"])
security = HTTPBearer(auto_error=False)

# Database will be injected from main app
db = None

def set_tax_db(database):
    global db
    db = database


# Import services (will be imported after db is set)
async def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify user is admin"""
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
    except:
        raise HTTPException(status_code=401, detail="Invalid token")


@tax_router.get("/reports")
async def list_tax_reports(
    report_type: str = None,
    year: int = None,
    limit: int = 20,
    admin: dict = Depends(get_admin_user)
):
    """
    List all generated tax reports
    Admin only
    """
    from services.cra_tax_reporting import get_tax_reports
    
    reports = await get_tax_reports(db, report_type, year, limit)
    return {
        "reports": reports,
        "count": len(reports)
    }


@tax_router.get("/reports/{report_id}")
async def get_tax_report(
    report_id: str,
    admin: dict = Depends(get_admin_user)
):
    """
    Get specific tax report with full details
    Admin only
    """
    from services.cra_tax_reporting import get_tax_report_by_id
    
    report = await get_tax_report_by_id(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return report


@tax_router.get("/reports/{report_id}/download")
async def download_tax_report_xml(
    report_id: str,
    admin: dict = Depends(get_admin_user)
):
    """
    Download tax report as XML file
    Admin only
    """
    from services.cra_tax_reporting import download_tax_report_xml
    
    xml_content = await download_tax_report_xml(db, report_id)
    if not xml_content:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Get report for filename
    from services.cra_tax_reporting import get_tax_report_by_id
    report = await get_tax_report_by_id(db, report_id)
    
    filename = f"bidvex_tax_report_{report.get('report_type', 'unknown')}_{report_id[:8]}.xml"
    
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@tax_router.post("/reports/gst-hst")
async def generate_gst_hst_report(
    start_date: str,
    end_date: str,
    reporting_period: str = "quarterly",
    admin: dict = Depends(get_admin_user)
):
    """
    Generate GST/HST Summary Report
    For CRA GST34 filing
    Admin only
    """
    from services.cra_tax_reporting import generate_gst_hst_report
    
    try:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DD)")
    
    result = await generate_gst_hst_report(db, start, end, reporting_period)
    return result


@tax_router.post("/reports/qst")
async def generate_qst_report(
    start_date: str,
    end_date: str,
    admin: dict = Depends(get_admin_user)
):
    """
    Generate Quebec QST Report
    For Revenu Québec filing
    Admin only
    """
    from services.cra_tax_reporting import generate_qst_report
    
    try:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    result = await generate_qst_report(db, start, end)
    return result


@tax_router.post("/reports/seller-payments/{year}")
async def generate_seller_payments_report(
    year: int,
    admin: dict = Depends(get_admin_user)
):
    """
    Generate Annual Seller Payments Report
    T5018-style for CRA
    Admin only
    """
    from services.cra_tax_reporting import generate_seller_payments_report
    
    if year < 2020 or year > datetime.now().year:
        raise HTTPException(status_code=400, detail="Invalid year")
    
    result = await generate_seller_payments_report(db, year)
    return result


@tax_router.post("/reports/annual-summary/{year}")
async def generate_annual_summary(
    year: int,
    admin: dict = Depends(get_admin_user)
):
    """
    Generate Comprehensive Annual Tax Summary
    Includes all tax types for year-end filing
    Admin only
    """
    from services.cra_tax_reporting import generate_annual_summary
    
    if year < 2020 or year > datetime.now().year:
        raise HTTPException(status_code=400, detail="Invalid year")
    
    result = await generate_annual_summary(db, year)
    return result


@tax_router.get("/summary/{year}")
async def get_tax_summary(
    year: int,
    admin: dict = Depends(get_admin_user)
):
    """
    Get quick tax summary for a year
    Without generating full report
    """
    start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    
    # Quick aggregation
    invoices = await db.vehicle_invoices.find({
        "invoice_type": "buyer",
        "payment_status": "paid",
        "paid_at": {"$gte": start_date, "$lte": end_date}
    }).to_list(length=10000)
    
    total_sales = sum(inv.get("hammer_price", 0) for inv in invoices)
    total_gst = sum(inv.get("tax_gst", 0) for inv in invoices)
    total_hst = sum(inv.get("tax_hst", 0) for inv in invoices)
    total_pst = sum(inv.get("tax_pst", 0) for inv in invoices)
    total_qst = sum(inv.get("tax_qst", 0) for inv in invoices)
    total_tax = total_gst + total_hst + total_pst + total_qst
    total_revenue = sum(inv.get("buyer_premium", 0) + inv.get("platform_fee", 0) for inv in invoices)
    
    return {
        "year": year,
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "taxes": {
            "gst": total_gst,
            "hst": total_hst,
            "pst": total_pst,
            "qst": total_qst,
            "total": total_tax
        },
        "invoice_count": len(invoices)
    }
