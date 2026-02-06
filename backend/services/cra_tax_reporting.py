"""
BidVex CRA Tax Reporting Engine
Generates XML reports for Canada Revenue Agency compliance

Reports Generated:
- GST/HST Summary Report (GST34)
- Annual Transaction Summary
- Seller Payment Report (T5018-like)
- Provincial Tax Summary (QST, PST)
"""

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional
from xml.etree import ElementTree as ET
from xml.dom import minidom
import json

logger = logging.getLogger(__name__)

# Platform tax registration numbers (from env)
PLATFORM_GST_NUMBER = os.environ.get("PLATFORM_GST_NUMBER", "123456789RT0001")
PLATFORM_QST_NUMBER = os.environ.get("PLATFORM_QST_NUMBER", "1234567890TQ0001")
PLATFORM_LEGAL_NAME = os.environ.get("PLATFORM_LEGAL_NAME", "BidVex Inc.")
PLATFORM_BUSINESS_NUMBER = os.environ.get("PLATFORM_BUSINESS_NUMBER", "1763135-9")


class TaxReportType:
    GST_HST_SUMMARY = "gst_hst_summary"
    PROVINCIAL_TAX = "provincial_tax"
    ANNUAL_SUMMARY = "annual_summary"
    SELLER_PAYMENTS = "seller_payments"
    BUYER_TRANSACTIONS = "buyer_transactions"


def _round_currency(amount) -> Decimal:
    """Round to 2 decimal places"""
    return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _format_date(dt: datetime) -> str:
    """Format date for CRA XML (YYYY-MM-DD)"""
    return dt.strftime("%Y-%m-%d")


def _prettify_xml(elem: ET.Element) -> str:
    """Return pretty-printed XML string"""
    rough_string = ET.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


async def generate_gst_hst_report(
    db,
    start_date: datetime,
    end_date: datetime,
    reporting_period: str = "quarterly"
) -> Dict[str, Any]:
    """
    Generate GST/HST Summary Report
    
    Collects all GST and HST collected during the period
    for filing GST34 return
    """
    # Fetch all paid invoices in the period
    invoices = await db.vehicle_invoices.find({
        "invoice_type": "buyer",
        "payment_status": "paid",
        "paid_at": {"$gte": start_date, "$lte": end_date}
    }).to_list(length=10000)
    
    # Aggregate tax data
    gst_collected = Decimal("0")
    hst_on_collected = Decimal("0")
    hst_ns_nb_nl_pe_collected = Decimal("0")
    total_taxable_sales = Decimal("0")
    
    # Track by province
    provincial_breakdown = {}
    
    for inv in invoices:
        tax_type = inv.get("tax_type", "GST")
        gst = Decimal(str(inv.get("tax_gst", 0)))
        hst = Decimal(str(inv.get("tax_hst", 0)))
        subtotal = Decimal(str(inv.get("subtotal_before_tax", 0)))
        province = inv.get("buyer_province", "ON")
        
        total_taxable_sales += subtotal
        
        if tax_type == "HST":
            if province == "ON":
                hst_on_collected += hst
            else:
                hst_ns_nb_nl_pe_collected += hst
        else:
            gst_collected += gst
        
        # Track by province
        if province not in provincial_breakdown:
            provincial_breakdown[province] = {
                "taxable_sales": Decimal("0"),
                "gst": Decimal("0"),
                "hst": Decimal("0"),
                "pst": Decimal("0"),
                "qst": Decimal("0"),
                "invoice_count": 0
            }
        
        provincial_breakdown[province]["taxable_sales"] += subtotal
        provincial_breakdown[province]["gst"] += gst
        provincial_breakdown[province]["hst"] += hst
        provincial_breakdown[province]["pst"] += Decimal(str(inv.get("tax_pst", 0)))
        provincial_breakdown[province]["qst"] += Decimal(str(inv.get("tax_qst", 0)))
        provincial_breakdown[province]["invoice_count"] += 1
    
    # Calculate totals
    total_gst_hst = gst_collected + hst_on_collected + hst_ns_nb_nl_pe_collected
    
    # Build XML
    root = ET.Element("GSTHSTReturn")
    root.set("version", "1.0")
    root.set("generatedAt", datetime.now(timezone.utc).isoformat())
    
    # Header
    header = ET.SubElement(root, "Header")
    ET.SubElement(header, "BusinessNumber").text = PLATFORM_BUSINESS_NUMBER
    ET.SubElement(header, "GSTNumber").text = PLATFORM_GST_NUMBER
    ET.SubElement(header, "LegalName").text = PLATFORM_LEGAL_NAME
    ET.SubElement(header, "ReportingPeriod").text = reporting_period
    ET.SubElement(header, "StartDate").text = _format_date(start_date)
    ET.SubElement(header, "EndDate").text = _format_date(end_date)
    
    # Summary
    summary = ET.SubElement(root, "Summary")
    ET.SubElement(summary, "TotalTaxableSales").text = str(_round_currency(total_taxable_sales))
    ET.SubElement(summary, "GSTCollected").text = str(_round_currency(gst_collected))
    ET.SubElement(summary, "HSTOntarioCollected").text = str(_round_currency(hst_on_collected))
    ET.SubElement(summary, "HSTAtlanticCollected").text = str(_round_currency(hst_ns_nb_nl_pe_collected))
    ET.SubElement(summary, "TotalGSTHSTCollected").text = str(_round_currency(total_gst_hst))
    ET.SubElement(summary, "TotalInvoices").text = str(len(invoices))
    
    # Line items for GST34
    line_items = ET.SubElement(root, "GST34LineItems")
    ET.SubElement(line_items, "Line101_TotalSalesAndRevenue").text = str(_round_currency(total_taxable_sales))
    ET.SubElement(line_items, "Line105_TotalGSTHSTCollected").text = str(_round_currency(total_gst_hst))
    ET.SubElement(line_items, "Line108_TotalITCs").text = "0.00"  # Input Tax Credits - would need expense tracking
    ET.SubElement(line_items, "Line109_NetTax").text = str(_round_currency(total_gst_hst))
    
    # Provincial breakdown
    provinces = ET.SubElement(root, "ProvincialBreakdown")
    for prov, data in provincial_breakdown.items():
        prov_elem = ET.SubElement(provinces, "Province")
        prov_elem.set("code", prov)
        ET.SubElement(prov_elem, "TaxableSales").text = str(_round_currency(data["taxable_sales"]))
        ET.SubElement(prov_elem, "GST").text = str(_round_currency(data["gst"]))
        ET.SubElement(prov_elem, "HST").text = str(_round_currency(data["hst"]))
        ET.SubElement(prov_elem, "PST").text = str(_round_currency(data["pst"]))
        ET.SubElement(prov_elem, "QST").text = str(_round_currency(data["qst"]))
        ET.SubElement(prov_elem, "InvoiceCount").text = str(data["invoice_count"])
    
    xml_string = _prettify_xml(root)
    
    # Store report in database
    report_id = str(uuid.uuid4())
    await db.tax_reports.insert_one({
        "id": report_id,
        "report_type": TaxReportType.GST_HST_SUMMARY,
        "period_start": start_date,
        "period_end": end_date,
        "reporting_period": reporting_period,
        "xml_content": xml_string,
        "summary": {
            "total_taxable_sales": float(_round_currency(total_taxable_sales)),
            "gst_collected": float(_round_currency(gst_collected)),
            "hst_collected": float(_round_currency(hst_on_collected + hst_ns_nb_nl_pe_collected)),
            "total_gst_hst": float(_round_currency(total_gst_hst)),
            "invoice_count": len(invoices)
        },
        "provincial_breakdown": {k: {kk: float(vv) if isinstance(vv, Decimal) else vv for kk, vv in v.items()} for k, v in provincial_breakdown.items()},
        "created_at": datetime.now(timezone.utc)
    })
    
    logger.info(f"Generated GST/HST report {report_id}: ${total_gst_hst} collected from {len(invoices)} invoices")
    
    return {
        "report_id": report_id,
        "report_type": TaxReportType.GST_HST_SUMMARY,
        "period": f"{_format_date(start_date)} to {_format_date(end_date)}",
        "summary": {
            "total_taxable_sales": float(_round_currency(total_taxable_sales)),
            "gst_collected": float(_round_currency(gst_collected)),
            "hst_collected": float(_round_currency(hst_on_collected + hst_ns_nb_nl_pe_collected)),
            "total_gst_hst": float(_round_currency(total_gst_hst)),
            "invoice_count": len(invoices)
        },
        "xml": xml_string
    }


async def generate_qst_report(
    db,
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    """
    Generate Quebec QST Report
    
    For Quebec provincial tax filing
    """
    # Fetch Quebec invoices
    invoices = await db.vehicle_invoices.find({
        "invoice_type": "buyer",
        "payment_status": "paid",
        "paid_at": {"$gte": start_date, "$lte": end_date},
        "buyer_province": "QC"
    }).to_list(length=10000)
    
    total_taxable = Decimal("0")
    total_qst = Decimal("0")
    total_gst = Decimal("0")
    
    for inv in invoices:
        total_taxable += Decimal(str(inv.get("subtotal_before_tax", 0)))
        total_qst += Decimal(str(inv.get("tax_qst", 0)))
        total_gst += Decimal(str(inv.get("tax_gst", 0)))
    
    # Build XML
    root = ET.Element("QSTReturn")
    root.set("version", "1.0")
    root.set("generatedAt", datetime.now(timezone.utc).isoformat())
    
    header = ET.SubElement(root, "Header")
    ET.SubElement(header, "QSTNumber").text = PLATFORM_QST_NUMBER
    ET.SubElement(header, "GSTNumber").text = PLATFORM_GST_NUMBER
    ET.SubElement(header, "LegalName").text = PLATFORM_LEGAL_NAME
    ET.SubElement(header, "StartDate").text = _format_date(start_date)
    ET.SubElement(header, "EndDate").text = _format_date(end_date)
    
    summary = ET.SubElement(root, "Summary")
    ET.SubElement(summary, "TotalTaxableSales").text = str(_round_currency(total_taxable))
    ET.SubElement(summary, "GSTCollected").text = str(_round_currency(total_gst))
    ET.SubElement(summary, "QSTCollected").text = str(_round_currency(total_qst))
    ET.SubElement(summary, "TotalTaxCollected").text = str(_round_currency(total_gst + total_qst))
    ET.SubElement(summary, "TransactionCount").text = str(len(invoices))
    
    xml_string = _prettify_xml(root)
    
    report_id = str(uuid.uuid4())
    await db.tax_reports.insert_one({
        "id": report_id,
        "report_type": TaxReportType.PROVINCIAL_TAX,
        "province": "QC",
        "period_start": start_date,
        "period_end": end_date,
        "xml_content": xml_string,
        "summary": {
            "total_taxable": float(_round_currency(total_taxable)),
            "gst_collected": float(_round_currency(total_gst)),
            "qst_collected": float(_round_currency(total_qst)),
            "invoice_count": len(invoices)
        },
        "created_at": datetime.now(timezone.utc)
    })
    
    return {
        "report_id": report_id,
        "report_type": "qst_return",
        "period": f"{_format_date(start_date)} to {_format_date(end_date)}",
        "summary": {
            "total_taxable": float(_round_currency(total_taxable)),
            "gst_collected": float(_round_currency(total_gst)),
            "qst_collected": float(_round_currency(total_qst)),
            "invoice_count": len(invoices)
        },
        "xml": xml_string
    }


async def generate_seller_payments_report(
    db,
    year: int
) -> Dict[str, Any]:
    """
    Generate Annual Seller Payments Report
    
    T5018-style report for payments to contractors/sellers
    Used for CRA reporting of payments over $500
    """
    start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    
    # Fetch all seller settlements
    settlements = await db.vehicle_invoices.find({
        "invoice_type": "seller_settlement",
        "settlement_status": "completed",
        "settled_at": {"$gte": start_date, "$lte": end_date}
    }).to_list(length=10000)
    
    # Aggregate by seller
    seller_totals = {}
    for settlement in settlements:
        seller_id = settlement.get("seller_id")
        if seller_id not in seller_totals:
            seller_totals[seller_id] = {
                "gross_payments": Decimal("0"),
                "commissions_paid": Decimal("0"),
                "net_payments": Decimal("0"),
                "transaction_count": 0,
                "seller_name": settlement.get("seller_name", "Unknown"),
                "seller_email": settlement.get("seller_email", "")
            }
        
        seller_totals[seller_id]["gross_payments"] += Decimal(str(settlement.get("hammer_price", 0)))
        seller_totals[seller_id]["commissions_paid"] += Decimal(str(settlement.get("seller_commission", 0)))
        seller_totals[seller_id]["net_payments"] += Decimal(str(settlement.get("net_payout", 0)))
        seller_totals[seller_id]["transaction_count"] += 1
    
    # Build XML
    root = ET.Element("SellerPaymentsReport")
    root.set("version", "1.0")
    root.set("year", str(year))
    root.set("generatedAt", datetime.now(timezone.utc).isoformat())
    
    header = ET.SubElement(root, "Header")
    ET.SubElement(header, "BusinessNumber").text = PLATFORM_BUSINESS_NUMBER
    ET.SubElement(header, "LegalName").text = PLATFORM_LEGAL_NAME
    ET.SubElement(header, "TaxYear").text = str(year)
    
    # Summary
    total_gross = sum(s["gross_payments"] for s in seller_totals.values())
    total_commissions = sum(s["commissions_paid"] for s in seller_totals.values())
    total_net = sum(s["net_payments"] for s in seller_totals.values())
    
    summary = ET.SubElement(root, "Summary")
    ET.SubElement(summary, "TotalSellers").text = str(len(seller_totals))
    ET.SubElement(summary, "TotalGrossPayments").text = str(_round_currency(total_gross))
    ET.SubElement(summary, "TotalCommissions").text = str(_round_currency(total_commissions))
    ET.SubElement(summary, "TotalNetPayments").text = str(_round_currency(total_net))
    ET.SubElement(summary, "TotalTransactions").text = str(len(settlements))
    
    # Individual seller records (T5018 style)
    sellers_elem = ET.SubElement(root, "Sellers")
    reportable_sellers = 0
    
    for seller_id, data in seller_totals.items():
        # Only include sellers with payments over $500 (CRA threshold)
        if data["net_payments"] >= 500:
            reportable_sellers += 1
            seller_elem = ET.SubElement(sellers_elem, "Seller")
            seller_elem.set("id", seller_id)
            ET.SubElement(seller_elem, "Name").text = data["seller_name"]
            ET.SubElement(seller_elem, "GrossPayments").text = str(_round_currency(data["gross_payments"]))
            ET.SubElement(seller_elem, "CommissionsPaid").text = str(_round_currency(data["commissions_paid"]))
            ET.SubElement(seller_elem, "NetPayments").text = str(_round_currency(data["net_payments"]))
            ET.SubElement(seller_elem, "TransactionCount").text = str(data["transaction_count"])
    
    ET.SubElement(summary, "ReportableSellers").text = str(reportable_sellers)
    
    xml_string = _prettify_xml(root)
    
    report_id = str(uuid.uuid4())
    await db.tax_reports.insert_one({
        "id": report_id,
        "report_type": TaxReportType.SELLER_PAYMENTS,
        "year": year,
        "xml_content": xml_string,
        "summary": {
            "total_sellers": len(seller_totals),
            "reportable_sellers": reportable_sellers,
            "total_gross": float(_round_currency(total_gross)),
            "total_commissions": float(_round_currency(total_commissions)),
            "total_net": float(_round_currency(total_net)),
            "transaction_count": len(settlements)
        },
        "created_at": datetime.now(timezone.utc)
    })
    
    logger.info(f"Generated seller payments report {report_id}: {reportable_sellers} reportable sellers, ${total_net} total")
    
    return {
        "report_id": report_id,
        "report_type": TaxReportType.SELLER_PAYMENTS,
        "year": year,
        "summary": {
            "total_sellers": len(seller_totals),
            "reportable_sellers": reportable_sellers,
            "total_gross": float(_round_currency(total_gross)),
            "total_commissions": float(_round_currency(total_commissions)),
            "total_net": float(_round_currency(total_net)),
            "transaction_count": len(settlements)
        },
        "xml": xml_string
    }


async def generate_annual_summary(
    db,
    year: int
) -> Dict[str, Any]:
    """
    Generate comprehensive annual tax summary
    
    Includes all tax types for year-end filing
    """
    start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    
    # Fetch all paid invoices
    invoices = await db.vehicle_invoices.find({
        "invoice_type": "buyer",
        "payment_status": "paid",
        "paid_at": {"$gte": start_date, "$lte": end_date}
    }).to_list(length=10000)
    
    # Initialize totals
    totals = {
        "total_sales": Decimal("0"),
        "total_buyer_premiums": Decimal("0"),
        "total_platform_fees": Decimal("0"),
        "total_gst": Decimal("0"),
        "total_hst": Decimal("0"),
        "total_pst": Decimal("0"),
        "total_qst": Decimal("0"),
        "total_tax": Decimal("0"),
        "total_revenue": Decimal("0"),
        "invoice_count": len(invoices)
    }
    
    monthly_breakdown = {}
    
    for inv in invoices:
        month_key = inv.get("paid_at", inv.get("created_at")).strftime("%Y-%m")
        
        if month_key not in monthly_breakdown:
            monthly_breakdown[month_key] = {
                "sales": Decimal("0"),
                "gst": Decimal("0"),
                "hst": Decimal("0"),
                "pst": Decimal("0"),
                "qst": Decimal("0"),
                "revenue": Decimal("0"),
                "count": 0
            }
        
        hammer = Decimal(str(inv.get("hammer_price", 0)))
        premium = Decimal(str(inv.get("buyer_premium", 0)))
        platform_fee = Decimal(str(inv.get("platform_fee", 0)))
        gst = Decimal(str(inv.get("tax_gst", 0)))
        hst = Decimal(str(inv.get("tax_hst", 0)))
        pst = Decimal(str(inv.get("tax_pst", 0)))
        qst = Decimal(str(inv.get("tax_qst", 0)))
        
        totals["total_sales"] += hammer
        totals["total_buyer_premiums"] += premium
        totals["total_platform_fees"] += platform_fee
        totals["total_gst"] += gst
        totals["total_hst"] += hst
        totals["total_pst"] += pst
        totals["total_qst"] += qst
        totals["total_tax"] += gst + hst + pst + qst
        totals["total_revenue"] += premium + platform_fee
        
        monthly_breakdown[month_key]["sales"] += hammer
        monthly_breakdown[month_key]["gst"] += gst
        monthly_breakdown[month_key]["hst"] += hst
        monthly_breakdown[month_key]["pst"] += pst
        monthly_breakdown[month_key]["qst"] += qst
        monthly_breakdown[month_key]["revenue"] += premium + platform_fee
        monthly_breakdown[month_key]["count"] += 1
    
    # Build XML
    root = ET.Element("AnnualTaxSummary")
    root.set("version", "1.0")
    root.set("year", str(year))
    root.set("generatedAt", datetime.now(timezone.utc).isoformat())
    
    header = ET.SubElement(root, "Header")
    ET.SubElement(header, "BusinessNumber").text = PLATFORM_BUSINESS_NUMBER
    ET.SubElement(header, "GSTNumber").text = PLATFORM_GST_NUMBER
    ET.SubElement(header, "QSTNumber").text = PLATFORM_QST_NUMBER
    ET.SubElement(header, "LegalName").text = PLATFORM_LEGAL_NAME
    ET.SubElement(header, "TaxYear").text = str(year)
    
    # Annual totals
    annual = ET.SubElement(root, "AnnualTotals")
    ET.SubElement(annual, "TotalSales").text = str(_round_currency(totals["total_sales"]))
    ET.SubElement(annual, "TotalBuyerPremiums").text = str(_round_currency(totals["total_buyer_premiums"]))
    ET.SubElement(annual, "TotalPlatformFees").text = str(_round_currency(totals["total_platform_fees"]))
    ET.SubElement(annual, "TotalRevenue").text = str(_round_currency(totals["total_revenue"]))
    ET.SubElement(annual, "TotalGST").text = str(_round_currency(totals["total_gst"]))
    ET.SubElement(annual, "TotalHST").text = str(_round_currency(totals["total_hst"]))
    ET.SubElement(annual, "TotalPST").text = str(_round_currency(totals["total_pst"]))
    ET.SubElement(annual, "TotalQST").text = str(_round_currency(totals["total_qst"]))
    ET.SubElement(annual, "TotalTaxCollected").text = str(_round_currency(totals["total_tax"]))
    ET.SubElement(annual, "TotalInvoices").text = str(totals["invoice_count"])
    
    # Monthly breakdown
    months_elem = ET.SubElement(root, "MonthlyBreakdown")
    for month, data in sorted(monthly_breakdown.items()):
        month_elem = ET.SubElement(months_elem, "Month")
        month_elem.set("period", month)
        ET.SubElement(month_elem, "Sales").text = str(_round_currency(data["sales"]))
        ET.SubElement(month_elem, "GST").text = str(_round_currency(data["gst"]))
        ET.SubElement(month_elem, "HST").text = str(_round_currency(data["hst"]))
        ET.SubElement(month_elem, "PST").text = str(_round_currency(data["pst"]))
        ET.SubElement(month_elem, "QST").text = str(_round_currency(data["qst"]))
        ET.SubElement(month_elem, "Revenue").text = str(_round_currency(data["revenue"]))
        ET.SubElement(month_elem, "TransactionCount").text = str(data["count"])
    
    xml_string = _prettify_xml(root)
    
    report_id = str(uuid.uuid4())
    await db.tax_reports.insert_one({
        "id": report_id,
        "report_type": TaxReportType.ANNUAL_SUMMARY,
        "year": year,
        "xml_content": xml_string,
        "summary": {k: float(v) if isinstance(v, Decimal) else v for k, v in totals.items()},
        "monthly_breakdown": {k: {kk: float(vv) if isinstance(vv, Decimal) else vv for kk, vv in v.items()} for k, v in monthly_breakdown.items()},
        "created_at": datetime.now(timezone.utc)
    })
    
    logger.info(f"Generated annual summary {report_id}: ${totals['total_tax']} total tax, ${totals['total_revenue']} revenue")
    
    return {
        "report_id": report_id,
        "report_type": TaxReportType.ANNUAL_SUMMARY,
        "year": year,
        "summary": {k: float(v) if isinstance(v, Decimal) else v for k, v in totals.items()},
        "monthly_breakdown": {k: {kk: float(vv) if isinstance(vv, Decimal) else vv for kk, vv in v.items()} for k, v in monthly_breakdown.items()},
        "xml": xml_string
    }


async def get_tax_reports(
    db,
    report_type: str = None,
    year: int = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Get list of generated tax reports"""
    query = {}
    if report_type:
        query["report_type"] = report_type
    if year:
        query["year"] = year
    
    cursor = db.tax_reports.find(query, {"_id": 0, "xml_content": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_tax_report_by_id(db, report_id: str) -> Optional[Dict[str, Any]]:
    """Get specific tax report with XML content"""
    return await db.tax_reports.find_one({"id": report_id}, {"_id": 0})


async def download_tax_report_xml(db, report_id: str) -> Optional[str]:
    """Get XML content for download"""
    report = await db.tax_reports.find_one({"id": report_id}, {"xml_content": 1})
    return report.get("xml_content") if report else None
