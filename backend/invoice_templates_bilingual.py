""" 
Bilingual Invoice HTML Templates for BidVex
Supports English (en) and French (fr)
"""

from datetime import datetime
from typing import List, Dict, Any
from logo_data import BIDVEX_LOGO_BASE64
from invoice_translations import get_translation as t

def lots_won_template(data: Dict[str, Any], lang: str = "en") -> str:
    """
    Generate HTML for Buyer Lots Won Summary PDF
    Bilingual support: English (en) / French (fr)

    iter451 — Each lot line renders `Unit Price × Quantity = Line Total`.
    Callers must set `lot['unit_price']` (per-unit) and `lot['hammer_price']`
    (the ALREADY-multiplied line total = unit_price × quantity). When a
    legacy caller omits `unit_price`, we back-derive it as
    `hammer_price / quantity` so historical invoices still render.
    """

    # Ensure every lot has unit_price / hammer_price / quantity that
    # reconcile: hammer_price == unit_price × quantity.
    for _lot in data.get('lots', []):
        _qty = int(_lot.get('quantity') or 1) or 1
        if _lot.get('unit_price') in (None, ""):
            _hp = float(_lot.get('hammer_price') or 0)
            _lot['unit_price'] = round(_hp / _qty, 2) if _qty else _hp

    # Calculate totals
    hammer_total = sum(lot['hammer_price'] for lot in data['lots'])
    premium_amount = hammer_total * (data['premium_percentage'] / 100)
    subtotal_before_tax = hammer_total + premium_amount
    
    # Tax on hammer
    gst_on_hammer = hammer_total * (data['tax_rate_gst'] / 100)
    qst_on_hammer = hammer_total * (data['tax_rate_qst'] / 100)
    
    # Tax on premium
    gst_on_premium = premium_amount * (data['tax_rate_gst'] / 100)
    qst_on_premium = premium_amount * (data['tax_rate_qst'] / 100)
    
    total_tax = gst_on_hammer + qst_on_hammer + gst_on_premium + qst_on_premium
    grand_total = subtotal_before_tax + total_tax
    
    # Generate lots table rows — iter451 shows `Unit × Qty = Total`.
    lots_rows = ""
    for lot in data['lots']:
        _unit = float(lot.get('unit_price') or 0)
        _qty = int(lot.get('quantity') or 1)
        _line = float(lot.get('hammer_price') or 0)
        lots_rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">{lot['lot_number']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">
                <strong>{lot['title']}</strong><br>
                <span style="font-size: 12px; color: #666;">{lot['description'][:100]}...</span>
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;">${_unit:.2f}</td>
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: center;">{_qty}</td>
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;"><strong>${_line:.2f}</strong></td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: letter;
                margin: 0.75in;
            }}
            body {{
                font-family: 'Arial', 'Helvetica', sans-serif;
                font-size: 11pt;
                line-height: 1.4;
                color: #333;
            }}
            .header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 30px;
                border-bottom: 3px solid #009BFF;
                padding-bottom: 20px;
            }}
            .header-logo {{
                width: 150px;
                height: auto;
            }}
            .header-text {{
                flex: 1;
                text-align: center;
            }}
            .header h1 {{
                color: #009BFF;
                margin: 0;
                font-size: 28pt;
                font-weight: bold;
            }}
            .header p {{
                margin: 5px 0;
                font-size: 10pt;
                color: #666;
            }}
            .invoice-title {{
                text-align: center;
                margin: 20px 0;
            }}
            .invoice-title h2 {{
                color: #333;
                font-size: 20pt;
                margin: 0;
            }}
            .info-section {{
                display: table;
                width: 100%;
                margin: 20px 0;
            }}
            .info-col {{
                display: table-cell;
                width: 50%;
                vertical-align: top;
                padding: 0 10px;
            }}
            .info-box {{
                background: #f9f9f9;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 15px;
            }}
            .info-box h3 {{
                margin: 0 0 10px 0;
                font-size: 11pt;
                color: #009BFF;
            }}
            .info-box p {{
                margin: 5px 0;
                font-size: 10pt;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th {{
                background: #009BFF;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: bold;
            }}
            td {{
                padding: 8px;
                border-bottom: 1px solid #e0e0e0;
            }}
            .totals-section {{
                float: right;
                width: 50%;
                margin-top: 20px;
            }}
            .totals-row {{
                display: flex;
                justify-content: space-between;
                padding: 8px 15px;
                border-bottom: 1px solid #e0e0e0;
            }}
            .totals-row.grand-total {{
                background: #009BFF;
                color: white;
                font-weight: bold;
                font-size: 14pt;
                margin-top: 10px;
            }}
            .payment-info {{
                clear: both;
                margin-top: 40px;
                padding-top: 20px;
                border-top: 2px solid #009BFF;
            }}
            .payment-info h3 {{
                color: #009BFF;
                margin-bottom: 10px;
            }}
            .footer {{
                margin-top: 40px;
                text-align: center;
                font-size: 9pt;
                color: #666;
                border-top: 1px solid #e0e0e0;
                padding-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <img src="{BIDVEX_LOGO_BASE64}" alt="BidVex Logo" class="header-logo" />
            <div class="header-text">
                <h1>BidVex</h1>
                <p>{t('online_auction_platform', lang)}</p>
                <p>www.bidvex.com | service@bidvex.com</p>
            </div>
        </div>

        <div class="invoice-title">
            <h2>{t('lots_won_summary', lang)}</h2>
            <p>{t('invoice_number', lang)}: {data['invoice_number']}</p>
            <p>{t('date', lang)}: {datetime.now().strftime('%B %d, %Y')}</p>
        </div>

        <div class="info-section">
            <div class="info-col">
                <div class="info-box">
                    <h3>{t('buyer_information', lang)}</h3>
                    <p><strong>{data['buyer']['name']}</strong></p>
                    {f"<p>{data['buyer']['company_name']}</p>" if data['buyer'].get('company_name') else ""}
                    <p>{data['buyer'].get('billing_address', data['buyer'].get('address', 'N/A'))}</p>
                    <p>{t('phone', lang)}: {data['buyer']['phone']}</p>
                    <p>{t('email', lang)}: {data['buyer']['email']}</p>
                    <p><strong>{t('paddle_number', lang)}: {data['paddle_number']}</strong></p>
                </div>
            </div>
            <div class="info-col">
                <div class="info-box">
                    <h3>{t('auction_details', lang)}</h3>
                    <p><strong>{data['auction']['title']}</strong></p>
                    <p>{t('location', lang)}: {data['auction']['city']}, {data['auction']['region']}</p>
                    <p>{t('end_date', lang)}: {data['auction']['auction_end_date'].strftime('%B %d, %Y %I:%M %p')}</p>
                    <p>{t('total_lots_won', lang)}: {len(data['lots'])}</p>
                </div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th style="width: 8%;">{t('lot_number', lang)}</th>
                    <th style="width: 42%;">{t('description', lang)}</th>
                    <th style="width: 15%; text-align: right;">{t('unit_price', lang)}</th>
                    <th style="width: 10%; text-align: center;">{t('quantity', lang)}</th>
                    <th style="width: 25%; text-align: right;">{t('line_total', lang)}</th>
                </tr>
            </thead>
            <tbody>
                {lots_rows}
            </tbody>
        </table>

        <div class="totals-section">
            <div class="totals-row">
                <span>{t('hammer_total', lang)}:</span>
                <span>${hammer_total:.2f}</span>
            </div>
            <div class="totals-row">
                <span>{t('buyers_premium', lang)} ({data['premium_percentage']}%):</span>
                <span>${premium_amount:.2f}</span>
            </div>
            <div class="totals-row">
                <span>{t('subtotal', lang)}:</span>
                <span>${subtotal_before_tax:.2f}</span>
            </div>
            <div class="totals-row">
                <span>{t('gst_on_hammer', lang, data['tax_rate_gst'])}:</span>
                <span>${gst_on_hammer:.2f}</span>
            </div>
            <div class="totals-row">
                <span>{t('qst_on_hammer', lang, data['tax_rate_qst'])}:</span>
                <span>${qst_on_hammer:.2f}</span>
            </div>
            <div class="totals-row">
                <span>{t('gst_on_premium', lang, data['tax_rate_gst'])}:</span>
                <span>${gst_on_premium:.2f}</span>
            </div>
            <div class="totals-row">
                <span>{t('qst_on_premium', lang, data['tax_rate_qst'])}:</span>
                <span>${qst_on_premium:.2f}</span>
            </div>
            <div class="totals-row grand-total">
                <span>{t('total_due', lang)}:</span>
                <span>${grand_total:.2f} {data.get('currency', 'CAD')}</span>
            </div>
        </div>

        <div class="payment-info">
            <h3>{t('payment_instructions', lang)}</h3>
            
            <div style="background: #fff3cd; padding: 15px; margin: 15px 0; border-left: 4px solid #ffc107; border-radius: 3px;">
                <p style="margin: 0 0 10px 0; font-weight: bold; color: #856404;">{t('two_part_payment_warning', lang)}</p>
                <p style="margin: 5px 0; font-size: 10pt; color: #856404;">
                    1. {t('payment_to_seller', lang, f'${hammer_total:.2f}')}<br>
                    2. {t('payment_to_bidvex', lang, f'${premium_amount + total_tax:.2f}')}
                </p>
            </div>
            
            <p><strong>{t('payment_to_bidvex_label', lang)}</strong></p>
            <ul>
                <li>{t('payment_methods_accepted', lang)}</li>
                <li>{t('etransfer', lang)}</li>
            </ul>
            <p><strong>{t('payment_deadline', lang)}:</strong> {data.get('payment_deadline', t('within_3_business_days', lang) if lang == 'en' else 'Dans les 14 jours suivant la clôture')}</p>
            
            <p style="margin-top: 20px;"><strong>{t('questions', lang)}</strong> {t('contact_us', lang, data['buyer']['phone'])}</p>
        </div>

        <div class="footer">
            <p>{t('thank_you', lang)}</p>
            <p>BidVex © {datetime.now().year} | {t('all_rights_reserved', lang)}</p>
        </div>
    </body>
    </html>
    """
    
    return html
