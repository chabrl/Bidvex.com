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
            <img src="{BIDVEX_LOGO_BASE64}" alt="BidVex Logo" class="header-logo" />
            <div class="header-text">
                <h1>BidVex</h1>
                <p>Online Auction Platform</p>
                <p>www.bidvex.com | support@bidvex.com</p>
            </div>
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


def payment_letter_template(data: Dict[str, Any]) -> str:
    """
    Generate HTML for Payment Letter PDF
    Professional business letter format
    """
    
    # Calculate grand total (same as Lots Won Summary)
    hammer_total = data['hammer_total']
    premium_amount = data['premium_amount']
    total_tax = data['total_tax']
    grand_total = data['grand_total']
    
    # Format payment deadline
    payment_deadline = data.get('payment_deadline', 'Within 3 business days')
    
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
                line-height: 1.6;
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
            .letter-date {{
                text-align: right;
                margin-bottom: 30px;
                font-size: 10pt;
                color: #666;
            }}
            .recipient {{
                margin-bottom: 30px;
            }}
            .recipient p {{
                margin: 3px 0;
                line-height: 1.4;
            }}
            .subject {{
                font-weight: bold;
                margin: 30px 0 20px 0;
                font-size: 12pt;
            }}
            .letter-body {{
                margin-bottom: 25px;
            }}
            .letter-body p {{
                margin: 15px 0;
                text-align: justify;
            }}
            .highlight-box {{
                background: #f0f8ff;
                border-left: 4px solid #009BFF;
                padding: 20px;
                margin: 25px 0;
            }}
            .highlight-box h3 {{
                color: #009BFF;
                margin: 0 0 15px 0;
                font-size: 14pt;
            }}
            .amount-due {{
                font-size: 24pt;
                color: #009BFF;
                font-weight: bold;
                margin: 10px 0;
            }}
            .payment-methods {{
                margin: 20px 0;
            }}
            .payment-methods ul {{
                list-style: none;
                padding-left: 0;
            }}
            .payment-methods li {{
                padding: 8px 0;
                border-bottom: 1px solid #e0e0e0;
            }}
            .payment-methods li:before {{
                content: "✓ ";
                color: #009BFF;
                font-weight: bold;
                margin-right: 10px;
            }}
            .important {{
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 20px 0;
            }}
            .important strong {{
                color: #856404;
            }}
            .closing {{
                margin-top: 40px;
            }}
            .signature {{
                margin-top: 50px;
            }}
            .signature p {{
                margin: 5px 0;
            }}
            .contact-box {{
                background: #f9f9f9;
                padding: 15px;
                border-radius: 5px;
                margin-top: 30px;
                text-align: center;
            }}
            .contact-box h4 {{
                color: #009BFF;
                margin: 0 0 10px 0;
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
                <p>Online Auction Platform</p>
                <p>www.bidvex.com | support@bidvex.com</p>
            </div>
        </div>

        <div class="letter-date">
            {datetime.now().strftime('%B %d, %Y')}
        </div>

        <div class="recipient">
            <p><strong>{data['buyer']['name']}</strong></p>
            {f"<p>{data['buyer']['company_name']}</p>" if data['buyer'].get('company_name') else ""}
            <p>{data['buyer'].get('billing_address', data['buyer'].get('address', ''))}</p>
            <p>Paddle Number: <strong>{data['paddle_number']}</strong></p>
        </div>

        <div class="subject">
            RE: Payment Due for Auction Lots Won - {data['auction']['title']}
        </div>

        <div class="letter-body">
            <p>Dear {data['buyer']['name'].split()[0]},</p>

            <p>
                Congratulations on your successful bids at our recent auction! We are pleased to confirm 
                that you have won <strong>{data['lots_count']} lot(s)</strong> at the <strong>{data['auction']['title']}</strong> 
                auction which concluded on {data['auction']['auction_end_date'].strftime('%B %d, %Y')}.
            </p>

            <div class="highlight-box">
                <h3>💰 Payment Information</h3>
                <p style="margin: 5px 0;">Invoice Number: <strong>{data['invoice_number']}</strong></p>
                <p style="margin: 5px 0;">Your Paddle Number: <strong>{data['paddle_number']}</strong></p>
                <p class="amount-due">${grand_total:.2f} CAD</p>
                <p style="font-size: 10pt; color: #666; margin: 0;">
                    (Includes hammer price, {data['premium_percentage']}% buyer's premium, and applicable taxes)
                </p>
            </div>

            <p>
                To complete your purchase and arrange for pickup of your items, please submit payment 
                by <strong>{payment_deadline}</strong> using one of the following methods:
            </p>

            <div class="payment-methods">
                <h4 style="color: #009BFF; margin-bottom: 10px;">Accepted Payment Methods:</h4>
                <ul>
                    <li><strong>Credit Card:</strong> Visa or Mastercard</li>
                    <li><strong>Interac e-Transfer:</strong> payments@bidvex.com</li>
                </ul>
            </div>

            <div class="important">
                <strong>⚠️ Important:</strong> Your items will be held for pickup once payment is received in full. 
                Please arrange pickup within 7 days of payment to avoid storage fees.
            </div>

            <p>
                Once your payment is processed, you will receive a confirmation email with pickup 
                instructions and available time slots. If you have any questions about your invoice 
                or need to arrange alternative payment options, please don't hesitate to contact us.
            </p>

            <div class="closing">
                <p>Thank you for participating in our auction. We appreciate your business and look forward to serving you again!</p>
                
                <div class="signature">
                    <p><strong>Sincerely,</strong></p>
                    <p>The BidVex Team</p>
                    <p style="color: #009BFF; font-style: italic;">Online Auction Platform</p>
                </div>
            </div>
        </div>

        <div class="contact-box">
            <h4>📞 Need Assistance?</h4>
            <p style="margin: 5px 0;">Email: <strong>support@bidvex.com</strong></p>
            <p style="margin: 5px 0;">Phone: <strong>{data['buyer']['phone']}</strong></p>
            <p style="margin: 5px 0; font-size: 9pt; color: #666;">
                Business Hours: Monday-Friday, 9:00 AM - 5:00 PM EST
            </p>
        </div>

        <div class="footer">
            <p>This is an automated payment notification from BidVex</p>
            <p>BidVex © {datetime.now().year} | All rights reserved</p>
        </div>
    </body>
    </html>
    """
    
    return html
