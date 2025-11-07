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
            <h3>💳 PAYMENT INSTRUCTIONS - IMPORTANT</h3>
            
            <div style="background: #fff3cd; padding: 15px; margin: 15px 0; border-left: 4px solid #ffc107; border-radius: 3px;">
                <p style="margin: 0 0 10px 0; font-weight: bold; color: #856404;">⚠️ Two-Part Payment Required:</p>
                <p style="margin: 5px 0; font-size: 10pt; color: #856404;">
                    1. <strong>To Seller:</strong> Pay ${hammer_total:.2f} CAD (Hammer Total) directly to the auction seller<br>
                    2. <strong>To BidVex:</strong> Pay ${premium_amount + total_tax:.2f} CAD (Premium + Taxes) to BidVex
                </p>
            </div>
            
            <p><strong>Payment to BidVex (Premium + Taxes):</strong></p>
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
                <h3>💰 Total Payment Due</h3>
                <p style="margin: 5px 0;">Invoice Number: <strong>{data['invoice_number']}</strong></p>
                <p style="margin: 5px 0;">Your Paddle Number: <strong>{data['paddle_number']}</strong></p>
                <p class="amount-due">${grand_total:.2f} CAD</p>
                <p style="font-size: 10pt; color: #666; margin: 0;">
                    (Includes hammer price, {data['premium_percentage']}% buyer's premium, and applicable taxes)
                </p>
            </div>
            
            <div class="important">
                <strong>⚠️ IMPORTANT - Two-Part Payment Required:</strong>
                <p style="margin: 10px 0 5px 0;">Your total payment is split into two parts:</p>
                <ol style="margin: 5px 0; padding-left: 20px;">
                    <li style="margin: 5px 0;"><strong>Payment to Seller:</strong> ${hammer_total:.2f} CAD (Hammer Total)<br>
                        <span style="font-size: 9pt; color: #666;">Pay this amount directly to the auction seller</span>
                    </li>
                    <li style="margin: 5px 0;"><strong>Payment to BidVex:</strong> ${premium_amount + total_tax:.2f} CAD (Premium + Taxes)<br>
                        <span style="font-size: 9pt; color: #666;">This covers BidVex's 5% buyer's premium and applicable taxes</span>
                    </li>
                </ol>
            </div>

            <p>
                To complete your purchase, please submit the <strong>BidVex portion (${premium_amount + total_tax:.2f} CAD)</strong> 
                by <strong>{payment_deadline}</strong> using one of the following methods:
            </p>

            <div class="payment-methods">
                <h4 style="color: #009BFF; margin-bottom: 10px;">Payment Methods for BidVex Portion:</h4>
                <ul>
                    <li><strong>Credit Card:</strong> Visa or Mastercard</li>
                    <li><strong>Interac e-Transfer:</strong> payments@bidvex.com (Reference: Invoice #{data['invoice_number']})</li>
                </ul>
                <p style="font-size: 9pt; color: #666; margin-top: 10px;">
                    Note: The seller will contact you separately regarding payment arrangements for the hammer total.
                </p>
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



def seller_statement_template(data: Dict[str, Any]) -> str:
    """
    Generate HTML for Seller Statement PDF
    Shows all lots (sold/unsold), buyer assignments, commission, net payout
    """
    
    # Calculate totals
    total_lots = len(data['lots'])
    sold_lots = [lot for lot in data['lots'] if lot.get('status') == 'sold']
    unsold_lots = [lot for lot in data['lots'] if lot.get('status') != 'sold']
    
    total_sold = len(sold_lots)
    total_unsold = len(unsold_lots)
    
    total_hammer = sum(lot.get('hammer_price', 0) for lot in sold_lots)
    commission_rate = data.get('commission_rate', 15.0)
    commission_amount = total_hammer * (commission_rate / 100)
    net_payout = total_hammer - commission_amount
    
    # Generate lots table rows
    lots_rows = ""
    for lot in data['lots']:
        status_class = "sold" if lot.get('status') == 'sold' else "unsold"
        status_text = "Sold" if lot.get('status') == 'sold' else "Unsold"
        
        buyer_info = ""
        hammer_price = ""
        
        if lot.get('status') == 'sold':
            buyer_name = lot.get('buyer_name', 'N/A')
            paddle_num = lot.get('paddle_number', 'N/A')
            buyer_info = f"{buyer_name}<br><small>Paddle #{paddle_num}</small>"
            hammer_price = f"${lot.get('hammer_price', 0):.2f}"
        else:
            buyer_info = "-"
            hammer_price = "-"
        
        lots_rows += f"""
        <tr class="{status_class}">
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">{lot['lot_number']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0;">
                <strong>{lot['title']}</strong><br>
                <span style="font-size: 11px; color: #666;">{lot['description'][:80]}...</span>
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: center;">
                <span class="status-badge status-{status_class.lower()}">{status_text}</span>
            </td>
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; text-align: right;">{hammer_price}</td>
            <td style="padding: 8px; border-bottom: 1px solid #e0e0e0; font-size: 11px;">{buyer_info}</td>
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
            .document-title {{
                text-align: center;
                margin: 20px 0;
            }}
            .document-title h2 {{
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
                padding: 10px 8px;
                text-align: left;
                font-weight: bold;
                font-size: 10pt;
            }}
            td {{
                padding: 8px;
                border-bottom: 1px solid #e0e0e0;
                font-size: 10pt;
            }}
            tr.sold {{
                background: #f0fff0;
            }}
            tr.unsold {{
                background: #fff5f5;
            }}
            .status-badge {{
                padding: 3px 8px;
                border-radius: 3px;
                font-size: 9pt;
                font-weight: bold;
            }}
            .status-sold {{
                background: #d4edda;
                color: #155724;
            }}
            .status-unsold {{
                background: #f8d7da;
                color: #721c24;
            }}
            .summary-section {{
                margin-top: 30px;
                padding: 20px;
                background: #f9f9f9;
                border-radius: 5px;
            }}
            .summary-row {{
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px solid #e0e0e0;
            }}
            .summary-row.highlight {{
                background: #009BFF;
                color: white;
                font-weight: bold;
                font-size: 14pt;
                padding: 12px 15px;
                margin-top: 10px;
                border-radius: 3px;
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

        <div class="document-title">
            <h2>SELLER STATEMENT</h2>
            <p style="color: #666; font-size: 10pt; margin: 5px 0;">Statement Date: {datetime.now().strftime('%B %d, %Y')}</p>
        </div>

        <div class="info-section">
            <div class="info-col">
                <div class="info-box">
                    <h3>SELLER INFORMATION</h3>
                    <p><strong>{data['seller']['name']}</strong></p>
                    {f"<p>{data['seller']['company_name']}</p>" if data['seller'].get('company_name') else ""}
                    <p>{data['seller'].get('address', 'N/A')}</p>
                    <p>Email: {data['seller']['email']}</p>
                    <p>Phone: {data['seller']['phone']}</p>
                </div>
            </div>
            <div class="info-col">
                <div class="info-box">
                    <h3>AUCTION DETAILS</h3>
                    <p><strong>{data['auction']['title']}</strong></p>
                    <p>Location: {data['auction']['city']}, {data['auction']['region']}</p>
                    <p>End Date: {data['auction']['auction_end_date'].strftime('%B %d, %Y')}</p>
                    <p>Total Lots Submitted: {total_lots}</p>
                </div>
            </div>
        </div>

        <h3 style="color: #009BFF; margin: 30px 0 15px 0;">LOT BREAKDOWN</h3>
        <table>
            <thead>
                <tr>
                    <th style="width: 8%;">Lot #</th>
                    <th style="width: 35%;">Description</th>
                    <th style="width: 12%; text-align: center;">Status</th>
                    <th style="width: 15%; text-align: right;">Hammer Price</th>
                    <th style="width: 30%;">Buyer Info</th>
                </tr>
            </thead>
            <tbody>
                {lots_rows}
            </tbody>
        </table>

        <div class="summary-section">
            <h3 style="color: #009BFF; margin: 0 0 15px 0;">FINANCIAL SUMMARY</h3>
            <div class="summary-row">
                <span>Total Lots Submitted:</span>
                <span><strong>{total_lots}</strong></span>
            </div>
            <div class="summary-row">
                <span>Lots Sold:</span>
                <span style="color: #155724;"><strong>{total_sold}</strong></span>
            </div>
            <div class="summary-row">
                <span>Lots Unsold:</span>
                <span style="color: #721c24;"><strong>{total_unsold}</strong></span>
            </div>
            <div class="summary-row">
                <span>Total Hammer Value:</span>
                <span><strong>${total_hammer:.2f}</strong></span>
            </div>
            <div class="summary-row">
                <span>Commission Deducted ({commission_rate}%):</span>
                <span style="color: #dc3545;">-${commission_amount:.2f}</span>
            </div>
            <div class="summary-row highlight">
                <span>NET PAYOUT TO SELLER:</span>
                <span>${net_payout:.2f} CAD</span>
            </div>
        </div>

        <div style="margin-top: 30px; padding: 15px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 3px;">
            <p style="margin: 0; font-size: 10pt;"><strong>Note:</strong> Payment will be processed within 5-7 business days after auction completion. You will receive a separate Seller Receipt for your records.</p>
        </div>

        <div class="footer">
            <p>Thank you for consigning with BidVex</p>
            <p>BidVex © {datetime.now().year} | All rights reserved</p>
        </div>
    </body>
    </html>
    """
    
    return html


def seller_receipt_template(data: Dict[str, Any]) -> str:
    """
    Generate HTML for Seller Receipt PDF
    Shows net payout calculation (zero commission policy)
    """
    
    total_hammer = data['total_hammer']
    commission_rate = data.get('commission_rate', 0.0)
    commission_amount = total_hammer * (commission_rate / 100)
    
    # Tax on commission (GST/QST) - will be 0 if commission is 0
    tax_rate_gst = data.get('tax_rate_gst', 5.0)
    tax_rate_qst = data.get('tax_rate_qst', 9.975)
    
    gst_on_commission = commission_amount * (tax_rate_gst / 100)
    qst_on_commission = commission_amount * (tax_rate_qst / 100)
    total_tax = gst_on_commission + qst_on_commission
    
    total_deductions = commission_amount + total_tax
    net_payout = total_hammer - total_deductions
    
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
            .document-title {{
                text-align: center;
                margin: 20px 0;
            }}
            .document-title h2 {{
                color: #333;
                font-size: 20pt;
                margin: 0;
            }}
            .info-box {{
                background: #f9f9f9;
                padding: 20px;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .info-box h3 {{
                margin: 0 0 15px 0;
                font-size: 12pt;
                color: #009BFF;
            }}
            .info-box p {{
                margin: 5px 0;
                font-size: 10pt;
            }}
            .calculation-section {{
                margin: 30px 0;
                padding: 25px;
                background: #f9f9f9;
                border-radius: 5px;
            }}
            .calc-row {{
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #e0e0e0;
                font-size: 11pt;
            }}
            .calc-row.subtotal {{
                font-weight: bold;
                margin-top: 10px;
                padding-top: 15px;
                border-top: 2px solid #333;
            }}
            .calc-row.total {{
                background: #009BFF;
                color: white;
                font-weight: bold;
                font-size: 16pt;
                padding: 15px;
                margin-top: 15px;
                border-radius: 3px;
            }}
            .payment-info {{
                margin: 30px 0;
                padding: 20px;
                background: #e7f3ff;
                border-left: 4px solid #009BFF;
                border-radius: 3px;
            }}
            .payment-info h3 {{
                color: #009BFF;
                margin: 0 0 15px 0;
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

        <div class="document-title">
            <h2>SELLER RECEIPT</h2>
            <p style="color: #666; font-size: 10pt; margin: 5px 0;">Receipt #: {data['receipt_number']}</p>
            <p style="color: #666; font-size: 10pt; margin: 5px 0;">Date: {datetime.now().strftime('%B %d, %Y')}</p>
        </div>

        <div class="info-box">
            <h3>SELLER INFORMATION</h3>
            <p><strong>{data['seller']['name']}</strong></p>
            {f"<p>{data['seller']['company_name']}</p>" if data['seller'].get('company_name') else ""}
            <p>{data['seller'].get('address', 'N/A')}</p>
            <p>Email: {data['seller']['email']}</p>
        </div>

        <div class="info-box">
            <h3>AUCTION DETAILS</h3>
            <p><strong>{data['auction']['title']}</strong></p>
            <p>Auction End Date: {data['auction']['auction_end_date'].strftime('%B %d, %Y')}</p>
            <p>Lots Sold: {data['lots_sold']} of {data['total_lots']} submitted</p>
        </div>

        <div class="calculation-section">
            <h3 style="color: #009BFF; margin: 0 0 20px 0;">PAYOUT CALCULATION</h3>
            
            <div class="calc-row">
                <span>Total Hammer Value (All Lots Sold):</span>
                <span><strong>${total_hammer:.2f}</strong></span>
            </div>
            
            <div class="calc-row">
                <span>Commission ({commission_rate}%):</span>
                <span>-${commission_amount:.2f}</span>
            </div>
            
            <div class="calc-row">
                <span>GST on Commission ({tax_rate_gst}%):</span>
                <span>-${gst_on_commission:.2f}</span>
            </div>
            
            <div class="calc-row">
                <span>QST on Commission ({tax_rate_qst}%):</span>
                <span>-${qst_on_commission:.2f}</span>
            </div>
            
            <div class="calc-row subtotal">
                <span>Total Deductions:</span>
                <span>-${total_deductions:.2f}</span>
            </div>
            
            <div class="calc-row total">
                <span>NET PAYOUT TO SELLER:</span>
                <span>${net_payout:.2f} CAD</span>
            </div>
        </div>
        
        {f'<div style="background: #e7f3ff; padding: 15px; margin: 20px 0; border-left: 4px solid #009BFF; border-radius: 3px;"><p style="margin: 0; color: #0066cc; font-weight: bold;">📢 No commission charged for this auction</p></div>' if commission_rate == 0.0 else ''}

        <div class="payment-info">
            <h3>💳 PAYMENT INFORMATION</h3>
            <p><strong>Payment Method:</strong> {data.get('payment_method', 'Bank Transfer')}</p>
            <p><strong>Payment Date:</strong> {data.get('payment_date', 'Within 5-7 business days')}</p>
            <p style="margin-top: 15px; font-size: 10pt; color: #666;">
                Payment will be transferred to the bank account on file. Please allow 3-5 business days for the transfer to complete.
            </p>
        </div>

        <div style="margin-top: 30px; padding: 15px; background: #d4edda; border-left: 4px solid #28a745; border-radius: 3px;">
            <p style="margin: 0; font-size: 10pt;"><strong>✓ Payment Processed:</strong> This receipt confirms that your payout has been calculated and will be processed according to the payment schedule above.</p>
        </div>

        <div class="footer">
            <p>Thank you for your partnership with BidVex</p>
            <p>BidVex © {datetime.now().year} | All rights reserved</p>
            <p style="margin-top: 10px;">Questions? Contact us at support@bidvex.com</p>
        </div>
    </body>
    </html>
    """
    
    return html


def commission_invoice_template(data: Dict[str, Any]) -> str:
    """
    Generate HTML for Commission Invoice PDF
    Invoice FROM BidVex TO Seller for commission on sold lots
    """
    
    commission_amount = data['commission_amount']
    tax_rate_gst = data.get('tax_rate_gst', 5.0)
    tax_rate_qst = data.get('tax_rate_qst', 9.975)
    
    gst_on_commission = commission_amount * (tax_rate_gst / 100)
    qst_on_commission = commission_amount * (tax_rate_qst / 100)
    total_due = commission_amount + gst_on_commission + qst_on_commission
    
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
            .invoice-header {{
                display: flex;
                justify-content: space-between;
                margin: 30px 0;
            }}
            .invoice-title {{
                font-size: 24pt;
                color: #009BFF;
                font-weight: bold;
            }}
            .invoice-details {{
                text-align: right;
                font-size: 10pt;
            }}
            .invoice-details p {{
                margin: 3px 0;
            }}
            .parties {{
                display: flex;
                justify-content: space-between;
                margin: 30px 0;
            }}
            .party-box {{
                width: 48%;
                padding: 15px;
                background: #f9f9f9;
                border-radius: 5px;
            }}
            .party-box h3 {{
                margin: 0 0 10px 0;
                font-size: 11pt;
                color: #009BFF;
            }}
            .party-box p {{
                margin: 3px 0;
                font-size: 10pt;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 30px 0;
            }}
            th {{
                background: #009BFF;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: bold;
            }}
            td {{
                padding: 12px;
                border-bottom: 1px solid #e0e0e0;
            }}
            .totals {{
                float: right;
                width: 50%;
                margin-top: 20px;
            }}
            .total-row {{
                display: flex;
                justify-content: space-between;
                padding: 8px 15px;
                border-bottom: 1px solid #e0e0e0;
            }}
            .total-row.grand {{
                background: #009BFF;
                color: white;
                font-weight: bold;
                font-size: 14pt;
                margin-top: 10px;
                border-radius: 3px;
            }}
            .payment-terms {{
                clear: both;
                margin-top: 40px;
                padding: 20px;
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                border-radius: 3px;
            }}
            .payment-terms h3 {{
                color: #856404;
                margin: 0 0 10px 0;
            }}
            .footer {{
                margin-top: 60px;
                text-align: center;
                font-size: 9pt;
                color: #666;
                border-top: 2px solid #009BFF;
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

        <div class="invoice-header">
            <div class="invoice-title">COMMISSION INVOICE</div>
            <div class="invoice-details">
                <p><strong>Invoice #:</strong> {data['invoice_number']}</p>
                <p><strong>Date:</strong> {datetime.now().strftime('%B %d, %Y')}</p>
                <p><strong>Due Date:</strong> {data.get('due_date', 'Upon Receipt')}</p>
            </div>
        </div>

        <div class="parties">
            <div class="party-box">
                <h3>FROM (SERVICE PROVIDER)</h3>
                <p><strong>BidVex Inc.</strong></p>
                <p>123 Auction Street</p>
                <p>Montreal, QC H1A 1A1</p>
                <p>Canada</p>
                <p>Email: billing@bidvex.com</p>
                <p>Phone: 1-800-BIDVEX</p>
            </div>
            <div class="party-box">
                <h3>TO (CONSIGNOR)</h3>
                <p><strong>{data['seller']['name']}</strong></p>
                {f"<p>{data['seller']['company_name']}</p>" if data['seller'].get('company_name') else ""}
                <p>{data['seller'].get('address', 'N/A')}</p>
                <p>Email: {data['seller']['email']}</p>
                <p>Phone: {data['seller']['phone']}</p>
            </div>
        </div>

        <h3 style="color: #009BFF; margin: 30px 0 10px 0;">AUCTION SERVICES PROVIDED</h3>
        <table>
            <thead>
                <tr>
                    <th style="width: 60%;">Description</th>
                    <th style="width: 20%; text-align: right;">Rate</th>
                    <th style="width: 20%; text-align: right;">Amount</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>
                        <strong>Auction Commission Services</strong><br>
                        <span style="font-size: 10pt; color: #666;">
                            Auction: {data['auction']['title']}<br>
                            Date: {data['auction']['auction_end_date'].strftime('%B %d, %Y')}<br>
                            Total Hammer Value: ${data['total_hammer']:.2f}<br>
                            Lots Sold: {data['lots_sold']}
                        </span>
                    </td>
                    <td style="text-align: right; vertical-align: top;">{data['commission_rate']}%</td>
                    <td style="text-align: right; vertical-align: top;"><strong>${commission_amount:.2f}</strong></td>
                </tr>
            </tbody>
        </table>

        <div class="totals">
            <div class="total-row">
                <span>Subtotal (Commission):</span>
                <span>${commission_amount:.2f}</span>
            </div>
            <div class="total-row">
                <span>GST ({tax_rate_gst}%):</span>
                <span>${gst_on_commission:.2f}</span>
            </div>
            <div class="total-row">
                <span>QST ({tax_rate_qst}%):</span>
                <span>${qst_on_commission:.2f}</span>
            </div>
            <div class="total-row grand">
                <span>TOTAL DUE:</span>
                <span>${total_due:.2f} CAD</span>
            </div>
        </div>

        <div class="payment-terms">
            <h3>{'📢 COMMISSION NOTICE' if commission_amount == 0 else '⚠️ PAYMENT TERMS'}</h3>
            {f'''
            <p style="margin: 5px 0; font-size: 11pt; color: #0066cc; font-weight: bold;">
                No commission charged for this auction.
            </p>
            <p style="margin: 5px 0; font-size: 10pt;">
                <strong>Net Payout:</strong> Your full hammer total of ${data['total_hammer']:.2f} CAD will be transferred within 5-7 business days.
            </p>
            <p style="margin: 15px 0 0 0; font-size: 9pt; color: #856404;">
                BidVex is pleased to offer this auction with zero commission to sellers. 
                You will receive 100% of the hammer value (before applicable buyer's premium, which is collected separately).
            </p>
            ''' if commission_amount == 0 else f'''
            <p style="margin: 5px 0; font-size: 10pt;">
                <strong>Payment Method:</strong> This amount will be automatically deducted from your seller payout.
            </p>
            <p style="margin: 5px 0; font-size: 10pt;">
                <strong>Net Payout:</strong> Your net payout (after commission and taxes) is ${data['net_payout']:.2f} CAD.
            </p>
            <p style="margin: 15px 0 0 0; font-size: 9pt; color: #856404;">
                This invoice represents the commission owed to BidVex for auction services provided. 
                The commission and applicable taxes have been deducted from your gross hammer total, 
                and your net payout will be transferred within 5-7 business days.
            </p>
            '''}
        </div>

        <div class="footer">
            <p><strong>BidVex Inc.</strong> | Online Auction Platform</p>
            <p>GST/HST Registration #: 123456789RT0001 | QST Registration #: 1234567890TQ0001</p>
            <p style="margin-top: 10px;">Thank you for your business</p>
            <p>BidVex © {datetime.now().year} | All rights reserved</p>
        </div>
    </body>
    </html>
    """
    
    return html

