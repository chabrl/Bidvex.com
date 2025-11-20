# SendGrid Template Setup Guide for BidVex

## Quick Access
**SendGrid Dashboard:** https://app.sendgrid.com
**Dynamic Templates:** https://app.sendgrid.com/dynamic_templates

---

## Template Creation Checklist

Create the following 22 dynamic templates in SendGrid. For each:
1. Click **Create a Dynamic Template**
2. Give it a name
3. Click **Add Version**
4. Use the HTML templates provided below
5. Copy the Template ID (format: `d-xxxxxxxxxxxxx`)
6. Update `email_templates.py` with the ID

---

## 1. WELCOME EMAIL (Authentication)

**Template Name:** BidVex - Welcome Email
**Subject:** Welcome to BidVex! Start Bidding Today 🎉

**HTML Template:**
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f4f4f4; }
        .container { max-width: 600px; margin: 40px auto; background: white; }
        .header { background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); 
                  color: white; padding: 40px 20px; text-align: center; }
        .content { padding: 40px 30px; }
        .button { display: inline-block; padding: 15px 40px; background: #2563eb; 
                  color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .footer { background: #f9fafb; padding: 20px; text-align: center; 
                  color: #6b7280; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to BidVex!</h1>
        </div>
        <div class="content">
            <h2>Hi {{first_name}},</h2>
            <p>Welcome to BidVex, your premier online auction marketplace!</p>
            
            <p>Your {{account_type}} account is now active and ready to use.</p>
            
            <h3>Get Started:</h3>
            <ul>
                <li>Browse thousands of auctions</li>
                <li>Place bids on items you love</li>
                <li>Track your bids in real-time</li>
                <li>Win amazing deals</li>
            </ul>
            
            <div style="text-align: center;">
                <a href="{{explore_url}}" class="button">Start Exploring</a>
            </div>
            
            <p>Need help? Our support team is here for you at support@bidvex.com</p>
        </div>
        <div class="footer">
            <p>&copy; {{current_year}} BidVex. All rights reserved.</p>
            <p>Montreal, QC, Canada</p>
        </div>
    </div>
</body>
</html>
```

---

## 2. PASSWORD RESET (Authentication)

**Template Name:** BidVex - Password Reset
**Subject:** Reset Your BidVex Password

**HTML Template:**
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f4f4f4; }
        .container { max-width: 600px; margin: 40px auto; background: white; }
        .header { background: #2563eb; color: white; padding: 30px 20px; text-align: center; }
        .content { padding: 40px 30px; }
        .button { display: inline-block; padding: 15px 40px; background: #2563eb; 
                  color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .warning { background: #fef3c7; border-left: 4px solid #f59e0b; 
                   padding: 15px; margin: 20px 0; }
        .footer { background: #f9fafb; padding: 20px; text-align: center; 
                  color: #6b7280; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔒 Password Reset Request</h1>
        </div>
        <div class="content">
            <h2>Hi {{first_name}},</h2>
            <p>We received a request to reset your BidVex password.</p>
            
            <div style="text-align: center;">
                <a href="{{reset_url}}" class="button">Reset Password</a>
            </div>
            
            <div class="warning">
                <strong>⏱️ Important:</strong> This link expires in {{expires_in_hours}} hour(s).
            </div>
            
            <p>If you didn't request this, you can safely ignore this email. 
               Your password will remain unchanged.</p>
            
            <p>For security reasons, we never ask for your password via email.</p>
            
            <p>Need help? Contact us at {{support_email}}</p>
        </div>
        <div class="footer">
            <p>&copy; {{current_year}} BidVex. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
```

---

## 3. BID PLACED CONFIRMATION (Bidding)

**Template Name:** BidVex - Bid Confirmation
**Subject:** Your Bid of {{currency}} {{bid_amount}} Placed Successfully

**HTML Template:**
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f4f4f4; }
        .container { max-width: 600px; margin: 40px auto; background: white; }
        .header { background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                  color: white; padding: 30px 20px; text-align: center; }
        .content { padding: 40px 30px; }
        .item-card { border: 1px solid #e5e7eb; border-radius: 8px; 
                     padding: 20px; margin: 20px 0; }
        .item-image { width: 100%; max-width: 400px; height: 200px; 
                      object-fit: cover; border-radius: 8px; }
        .bid-amount { font-size: 32px; color: #2563eb; font-weight: bold; 
                      text-align: center; margin: 20px 0; }
        .button { display: inline-block; padding: 12px 30px; background: #2563eb; 
                  color: white; text-decoration: none; border-radius: 5px; }
        .footer { background: #f9fafb; padding: 20px; text-align: center; 
                  color: #6b7280; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ Bid Placed Successfully!</h1>
        </div>
        <div class="content">
            <h2>Great news, {{first_name}}!</h2>
            <p>Your bid has been placed successfully.</p>
            
            <div class="item-card">
                {{#if listing_image}}
                <img src="{{listing_image}}" alt="{{listing_title}}" class="item-image">
                {{/if}}
                <h3>{{listing_title}}</h3>
                
                <div class="bid-amount">
                    {{currency}} {{bid_amount}}
                </div>
                
                <p><strong>Current High Bid:</strong> {{currency}} {{current_high_bid}}</p>
                <p><strong>Auction Ends:</strong> {{auction_end_date}}</p>
            </div>
            
            <div style="text-align: center;">
                <a href="{{listing_url}}" class="button">View Auction</a>
            </div>
            
            <p><strong>What's Next?</strong></p>
            <ul>
                <li>We'll notify you if you're outbid</li>
                <li>Track the auction in your dashboard</li>
                <li>Increase your bid anytime before it ends</li>
            </ul>
        </div>
        <div class="footer">
            <p>&copy; {{current_year}} BidVex. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
```

---

## 4. OUTBID NOTIFICATION (Bidding)

**Template Name:** BidVex - You've Been Outbid
**Subject:** ⚠️ You've Been Outbid on {{listing_title}}

**HTML Template:**
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f4f4f4; }
        .container { max-width: 600px; margin: 40px auto; background: white; }
        .header { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); 
                  color: white; padding: 30px 20px; text-align: center; }
        .content { padding: 40px 30px; }
        .alert { background: #fef3c7; border-left: 4px solid #f59e0b; 
                 padding: 20px; margin: 20px 0; }
        .new-bid { font-size: 28px; color: #dc2626; font-weight: bold; 
                   text-align: center; margin: 15px 0; }
        .button { display: inline-block; padding: 15px 40px; background: #dc2626; 
                  color: white; text-decoration: none; border-radius: 5px; }
        .footer { background: #f9fafb; padding: 20px; text-align: center; 
                  color: #6b7280; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ You've Been Outbid!</h1>
        </div>
        <div class="content">
            <h2>Hi {{first_name}},</h2>
            
            <div class="alert">
                <p><strong>Someone just placed a higher bid on:</strong></p>
                <h3>{{listing_title}}</h3>
            </div>
            
            <p><strong>New High Bid:</strong></p>
            <div class="new-bid">{{currency}} {{new_bid_amount}}</div>
            
            <p><strong>Time Remaining:</strong> {{time_remaining}}</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{{bid_now_url}}" class="button">Place New Bid</a>
            </div>
            
            <p>Don't miss out! Act fast to stay in the lead.</p>
        </div>
        <div class="footer">
            <p>&copy; {{current_year}} BidVex. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
```

---

## 5. AUCTION WON (Bidding)

**Template Name:** BidVex - Congratulations! You Won
**Subject:** 🎉 Congratulations! You Won {{listing_title}}

**HTML Template:**
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f4f4f4; }
        .container { max-width: 600px; margin: 40px auto; background: white; }
        .header { background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                  color: white; padding: 40px 20px; text-align: center; }
        .confetti { font-size: 48px; }
        .content { padding: 40px 30px; }
        .winner-card { border: 2px solid #10b981; border-radius: 8px; 
                       padding: 20px; margin: 20px 0; background: #ecfdf5; }
        .winning-bid { font-size: 36px; color: #10b981; font-weight: bold; 
                       text-align: center; margin: 15px 0; }
        .button { display: inline-block; padding: 15px 40px; background: #2563eb; 
                  color: white; text-decoration: none; border-radius: 5px; margin: 10px; }
        .footer { background: #f9fafb; padding: 20px; text-align: center; 
                  color: #6b7280; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="confetti">🎉 🎊 🥳</div>
            <h1>Congratulations!</h1>
            <h2>You Won the Auction!</h2>
        </div>
        <div class="content">
            <h2>Amazing news, {{first_name}}!</h2>
            
            <div class="winner-card">
                <h3>{{listing_title}}</h3>
                <p><strong>Your Winning Bid:</strong></p>
                <div class="winning-bid">{{currency}} {{winning_bid}}</div>
                <p><strong>Seller:</strong> {{seller_name}}</p>
            </div>
            
            <h3>Next Steps:</h3>
            <ol>
                <li><strong>Complete Payment</strong> - Pay securely within 48 hours</li>
                <li><strong>Contact Seller</strong> - Arrange pickup or shipping</li>
                <li><strong>Leave Feedback</strong> - Rate your experience</li>
            </ol>
            
            <div style="text-align: center;">
                <a href="{{payment_url}}" class="button">Complete Payment</a>
                <a href="{{invoice_url}}" class="button" style="background: #6b7280;">View Invoice</a>
            </div>
        </div>
        <div class="footer">
            <p>&copy; {{current_year}} BidVex. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
```

---

## Template Update Instructions

After creating each template:

1. **Copy the Template ID** from the SendGrid dashboard
2. **Open** `/app/backend/config/email_templates.py`
3. **Update the corresponding line:**
   ```python
   WELCOME = 'd-your-actual-template-id-here'
   ```

Example:
```python
class EmailTemplates:
    # Authentication
    WELCOME = 'd-abc123def456ghi789'  # ← Replace this
    PASSWORD_RESET = 'd-jkl012mno345pqr678'  # ← Replace this
    # ... etc
```

---

## Remaining Templates (Quick Reference)

The guide above shows the 5 most critical templates. For the remaining 17:

**Authentication:**
- Email Verification (similar to password reset)
- Password Changed (simple confirmation)

**Bidding:**
- Bid Lost (similar to auction won, but consolation)

**Auction Updates:**
- Auction Ending Soon (urgent reminder with time left)
- Auction Started (notification that upcoming auction is live)
- Auction Cancelled (apology and explanation)

**Seller Notifications:**
- New Bid Received (show bid amount, bidder info)
- Listing Approved (congratulations, go live)
- Listing Rejected (explanation, how to fix)
- Item Sold (congratulations, next steps)

**Financial:**
- Invoice (itemized breakdown)
- Payment Received (confirmation)
- Payment Failed (retry instructions)
- Refund Issued (explanation and amount)

**Communication:**
- New Message (message preview, link to messages)

**Admin:**
- Report Received (acknowledgment)
- Account Suspended (explanation and appeal process)

---

## Testing Templates

After creating and updating IDs:

```bash
cd /app/backend
python test_email_service.py
```

Or test individual template:
```python
from services.email_service import get_email_service
from config.email_templates import EmailTemplates

email_service = get_email_service()

result = await email_service.send_email(
    to='your-test-email@example.com',
    template_id=EmailTemplates.WELCOME,
    dynamic_data={
        'first_name': 'Test',
        'account_type': 'Personal',
        'explore_url': 'https://bidvex.com/marketplace',
        'login_url': 'https://bidvex.com/auth'
    },
    language='en'
)

print(result)
```

---

## Troubleshooting

**Template not rendering:**
- Check template ID is correct
- Verify all variable names match exactly (case-sensitive)
- Ensure template is published (not draft)

**Images not showing:**
- Use full HTTPS URLs for images
- Verify images are publicly accessible
- Test image URLs in browser first

**Variables showing as {{name}}:**
- Template syntax incorrect
- Using wrong template engine (must be Handlebars)
- Variable name mismatch

---

## Pro Tips

1. **Use Test Mode:** Send test emails from SendGrid dashboard before going live
2. **Mobile Preview:** Always check mobile preview in SendGrid
3. **Plain Text:** Add plain text version for email clients that don't support HTML
4. **Unsubscribe:** Include unsubscribe link in footer (required by law)
5. **Spam Score:** Use SendGrid's spam checker before publishing

---

**Created:** {current_date}
**Status:** Template IDs need to be updated after creation
**Priority:** Create WELCOME, PASSWORD_RESET, BID_PLACED, OUTBID, and AUCTION_WON first
