"""
Invoice HTML Templates for BidVex
"""

from datetime import datetime
from typing import List, Dict, Any
from logo_data import BIDVEX_LOGO_BASE64

def lots_won_template(data: Dict[str, Any]) -> str:
    """
    Generate HTML for Buyer Lots Won Summary PDF
    Matches Renaissance Bistro format
    """
    
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
    
    # Generate lots table rows
    lots_rows = ""
    for lot in data['lots']:
        lots_rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">{lot['lot_number']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">
                <strong>{lot['title']}</strong><br>
                <span style="font-size: 12px; color: #666;">{lot['description'][:100]}...</span>
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: center;">{lot['quantity']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;">${lot['hammer_price']:.2f}</td>
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
                margin-bottom: 20px;
            }}
            .info-col {{
                display: table-cell;
                width: 50%;
                vertical-align: top;
            }}
            .info-box {{
                background: #f9f9f9;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 10px;
            }}
            .info-box h3 {{
                margin: 0 0 10px 0;
                font-size: 12pt;
                color: #009BFF;
            }}
            .info-box p {{
                margin: 3px 0;
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
                padding: 10px;
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
                padding: 5px 10px;
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
            <h1>BidVex</h1>
            <p>Online Auction Platform</p>
            <p>www.bidvex.com | support@bidvex.com</p>
        </div>

        <div class="invoice-title">
            <h2>LOTS WON SUMMARY</h2>
            <p>Invoice #: {data['invoice_number']}</p>
            <p>Date: {datetime.now().strftime('%B %d, %Y')}</p>
        </div>

        <div class="info-section">
            <div class="info-col">
                <div class="info-box">
                    <h3>BUYER INFORMATION</h3>
                    <p><strong>{data['buyer']['name']}</strong></p>
                    {f"<p>{data['buyer']['company_name']}</p>" if data['buyer'].get('company_name') else ""}
                    <p>{data['buyer'].get('billing_address', data['buyer'].get('address', 'N/A'))}</p>
                    <p>Phone: {data['buyer']['phone']}</p>
                    <p>Email: {data['buyer']['email']}</p>
                    <p><strong>Paddle #: {data['paddle_number']}</strong></p>
                </div>
            </div>
            <div class="info-col">
                <div class="info-box">
                    <h3>AUCTION DETAILS</h3>
                    <p><strong>{data['auction']['title']}</strong></p>
                    <p>Location: {data['auction']['city']}, {data['auction']['region']}</p>
                    <p>End Date: {data['auction']['auction_end_date'].strftime('%B %d, %Y %I:%M %p')}</p>
                    <p>Total Lots Won: {len(data['lots'])}</p>
                </div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th style="width: 10%;">Lot #</th>
                    <th style="width: 50%;">Description</th>
                    <th style="width: 10%; text-align: center;">Qty</th>
                    <th style="width: 30%; text-align: right;">Hammer Price</th>
                </tr>
            </thead>
            <tbody>
                {lots_rows}
            </tbody>
        </table>

        <div class="totals-section">
            <div class="totals-row">
                <span>Hammer Total:</span>
                <span>${hammer_total:.2f}</span>
            </div>
            <div class="totals-row">
                <span>Buyer's Premium ({data['premium_percentage']}%):</span>
                <span>${premium_amount:.2f}</span>
            </div>
            <div class="totals-row">
                <span>Subtotal:</span>
                <span>${subtotal_before_tax:.2f}</span>
            </div>
            <div class="totals-row">
                <span>GST ({data['tax_rate_gst']}%) on Hammer:</span>
                <span>${gst_on_hammer:.2f}</span>
            </div>
            <div class="totals-row">
                <span>QST ({data['tax_rate_qst']}%) on Hammer:</span>
                <span>${qst_on_hammer:.2f}</span>
            </div>
            <div class="totals-row">
                <span>GST ({data['tax_rate_gst']}%) on Premium:</span>
                <span>${gst_on_premium:.2f}</span>
            </div>
            <div class="totals-row">
                <span>QST ({data['tax_rate_qst']}%) on Premium:</span>
                <span>${qst_on_premium:.2f}</span>
            </div>
            <div class="totals-row grand-total">
                <span>TOTAL DUE:</span>
                <span>${grand_total:.2f} CAD</span>
            </div>
        </div>

        <div class="payment-info">
            <h3>PAYMENT INSTRUCTIONS</h3>
            <p><strong>Payment Methods Accepted:</strong></p>
            <ul>
                <li>Visa / Mastercard</li>
                <li>Interac e-Transfer to: payments@bidvex.com</li>
            </ul>
            <p><strong>Payment Deadline:</strong> {data.get('payment_deadline', 'Within 3 business days')}</p>
            
            {f'''
            <h3 style="margin-top: 20px;">PICKUP INFORMATION</h3>
            <p><strong>Location:</strong> {data['auction']['location']}</p>
            <p><strong>Hours:</strong> Monday-Friday, 9:00 AM - 5:00 PM</p>
            <p><strong>Pickup Deadline:</strong> Within 7 days of payment</p>
            ''' if data['auction'].get('location') else ''}
            
            <p style="margin-top: 20px;"><strong>Questions?</strong> Contact us at support@bidvex.com or {data['buyer']['phone']}</p>
        </div>

        <div class="footer">
            <p>Thank you for your business!</p>
            <p>BidVex © {datetime.now().year} | All rights reserved</p>
        </div>
    </body>
    </html>
    """
    
    return html
