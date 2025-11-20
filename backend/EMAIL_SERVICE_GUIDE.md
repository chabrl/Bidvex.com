# BidVex Email Service - Complete Guide

## Overview

Production-ready email system using SendGrid with:
- ✅ Dynamic Templates
- ✅ Bilingual Support (EN/FR)
- ✅ Retry Logic with Exponential Backoff
- ✅ Event Tracking via Webhooks
- ✅ Comprehensive Error Logging
- ✅ Bulk Email Support

---

## Quick Start

### 1. Get SendGrid API Key

1. Sign up at https://sendgrid.com (Free tier: 100 emails/day)
2. Navigate to: **Settings → API Keys**
3. Click **Create API Key**
4. Name: `BidVex Production`
5. Permissions: **Full Access** or **Mail Send** + **Template Engine**
6. Copy the API key (starts with `SG.`)

### 2. Configure Environment

Add to `/app/backend/.env`:
```bash
SENDGRID_API_KEY=SG.your_actual_key_here
SENDGRID_FROM_EMAIL=support@bidvex.com
SENDGRID_FROM_NAME=BidVex Auctions
ADMIN_EMAIL=admin@bidvex.com
```

### 3. Verify Domain (Production)

**For production emails to avoid spam:**
1. Go to: **Settings → Sender Authentication**
2. Click **Authenticate Your Domain**
3. Follow DNS configuration steps
4. Wait for verification (can take up to 48 hours)

---

## Creating Email Templates

### 1. Access Dynamic Templates

1. Go to: **Email API → Dynamic Templates**
2. Click **Create a Dynamic Template**
3. Name template (e.g., "Welcome Email - EN")
4. Click **Add Version**
5. Choose **Blank Template** or **Design Editor**

### 2. Template Design

**Using Handlebars Syntax:**
```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .header { background: #2563eb; color: white; padding: 20px; }
        .content { padding: 30px; }
        .button { background: #2563eb; color: white; padding: 15px 30px; }
    </style>
</head>
<body>
    <div class="header">
        <img src="https://bidvex.com/logo.png" alt="BidVex" />
    </div>
    <div class="content">
        <h1>Welcome, {{first_name}}!</h1>
        <p>Thank you for joining BidVex.</p>
        <a href="{{explore_url}}" class="button">Start Bidding</a>
    </div>
    <div class="footer">
        <p>&copy; {{current_year}} BidVex. All rights reserved.</p>
    </div>
</body>
</html>
```

### 3. Get Template ID

After saving, copy the Template ID (format: `d-xxxxxxxxxxxxx`)

### 4. Update Template IDs

Edit `/app/backend/config/email_templates.py`:
```python
class EmailTemplates:
    WELCOME = 'd-abc123...'  # Replace with your template ID
    PASSWORD_RESET = 'd-def456...'
    BID_PLACED = 'd-ghi789...'
    # ... etc
```

---

## Using the Email Service

### Basic Usage

```python
from services.email_service import get_email_service
from config.email_templates import EmailTemplates, EmailDataBuilder

# Get service instance
email_service = get_email_service()

# Send email
result = await email_service.send_email(
    to='user@example.com',
    template_id=EmailTemplates.WELCOME,
    dynamic_data=EmailDataBuilder.welcome_email(user),
    language='en'
)

if result['success']:
    print(f\"Email sent! Message ID: {result['message_id']}\")
else:
    print(f\"Email failed: {result['error']}\")
```

### Example: Welcome Email

```python
from config.email_templates import send_welcome_email

# After user registration
user = {
    'name': 'John Doe',
    'email': 'john@example.com',
    'account_type': 'business'
}

await send_welcome_email(
    email_service=get_email_service(),
    user=user,
    language='en'  # or 'fr' for French
)
```

### Example: Bid Confirmation

```python
from config.email_templates import send_bid_confirmation

await send_bid_confirmation(
    email_service=get_email_service(),
    user=user,
    listing=listing,
    bid_amount=150.00,
    language='en'
)
```

### Example: Bulk Email

```python
recipients = [
    {'email': 'user1@example.com', 'data': {'first_name': 'Alice'}},
    {'email': 'user2@example.com', 'data': {'first_name': 'Bob'}},
]

results = await email_service.send_bulk_email(
    recipients=recipients,
    template_id=EmailTemplates.AUCTION_ENDING_SOON,
    language='en'
)

print(f\"Sent: {results['success']}, Failed: {results['failed']}\")
```

---

## Bilingual Support

### Template Strategy

**Option 1: Separate Templates**
- Create two templates: one EN, one FR
- Select template ID based on user language

**Option 2: Single Template with Conditionals**
```handlebars
{{#if (eq language "fr")}}
    <h1>Bienvenue, {{first_name}}!</h1>
{{else}}
    <h1>Welcome, {{first_name}}!</h1>
{{/if}}
```

### Language Detection

```python
# Get user's preferred language
user_language = user.get('preferred_language', 'en')

await email_service.send_email(
    to=user['email'],
    template_id=EmailTemplates.WELCOME,
    dynamic_data=data,
    language=user_language
)
```

---

## Event Tracking (Webhook)

### 1. Configure Webhook in SendGrid

1. Go to: **Settings → Mail Settings → Event Webhook**
2. **HTTP Post URL:** `https://yourdomain.com/api/webhooks/sendgrid`
3. **Events to Track:**
   - ☑ Processed
   - ☑ Delivered
   - ☑ Opened
   - ☑ Clicked
   - ☑ Bounced
   - ☑ Dropped
4. Click **Enable Event Webhook**

### 2. Monitor Events

Events are stored in MongoDB `email_events` collection:

```python
# Query email events
events = await db.email_events.find({
    'email': 'user@example.com'
}).to_list(100)

# Check if email was delivered
delivered = await db.email_events.find_one({
    'message_id': 'msg_id_here',
    'event_type': 'delivered'
})
```

### 3. Analytics

```python
# Email delivery rate
total_sent = await db.email_events.count_documents({'event_type': 'processed'})
delivered = await db.email_events.count_documents({'event_type': 'delivered'})
delivery_rate = (delivered / total_sent) * 100

# Open rate
opened = await db.email_events.count_documents({'event_type': 'open'})
open_rate = (opened / delivered) * 100

print(f\"Delivery Rate: {delivery_rate:.1f}%\")
print(f\"Open Rate: {open_rate:.1f}%\")
```

---

## Retry Logic

The email service automatically retries failed sends:

- **Max Retries:** 3 attempts
- **Backoff:** Exponential (1s, 2s, 4s)
- **Final Failure:** Notifies admin

```python
# Custom retry configuration
await email_service.send_email(
    to='user@example.com',
    template_id=EmailTemplates.INVOICE,
    dynamic_data=data,
    max_retries=5  # Override default
)
```

---

## Error Handling

### Graceful Degradation

If SendGrid is not configured:
```python
email_service = get_email_service()

if not email_service.is_configured():
    logger.warning(\"Email service disabled\")
    # Continue without email, or show warning to user
```

### Admin Notifications

On persistent failures, admin receives notification:
```
Subject: [BidVex] Email Delivery Failure

Failed to send email after multiple retries.

Recipient: user@example.com
Template ID: d-abc123
Error: 401 Unauthorized
Time: 2024-01-15T10:30:00Z
```

---

## Integration Examples

### User Registration

```python
@api_router.post(\"/auth/register\")
async def register(user_data: UserCreate):
    # Create user
    user = await create_user(user_data)
    
    # Send welcome email
    email_service = get_email_service()
    if email_service.is_configured():
        await send_welcome_email(
            email_service=email_service,
            user=user.dict(),
            language=user.preferred_language or 'en'
        )
    
    return {\"message\": \"Registration successful\"}
```

### Bid Placement

```python
@api_router.post(\"/listings/{id}/bid\")
async def place_bid(
    listing_id: str,
    bid_data: BidCreate,
    current_user: User = Depends(get_current_user)
):
    # Process bid
    bid = await process_bid(listing_id, bid_data, current_user)
    
    # Send confirmation email
    email_service = get_email_service()
    if email_service.is_configured():
        listing = await db.listings.find_one({\"id\": listing_id})
        await send_bid_confirmation(
            email_service=email_service,
            user=current_user.dict(),
            listing=listing,
            bid_amount=bid_data.amount,
            language=current_user.preferred_language
        )
    
    return {\"message\": \"Bid placed successfully\"}
```

### Password Reset

```python
@api_router.post(\"/auth/forgot-password\")
async def forgot_password(email: str):
    user = await db.users.find_one({\"email\": email})
    if not user:
        return {\"message\": \"If email exists, reset link sent\"}
    
    # Generate reset token
    reset_token = generate_reset_token(user['id'])
    
    # Send reset email
    email_service = get_email_service()
    if email_service.is_configured():
        await send_password_reset_email(
            email_service=email_service,
            user=user,
            reset_token=reset_token,
            language=user.get('preferred_language', 'en')
        )
    
    return {\"message\": \"If email exists, reset link sent\"}
```

---

## Testing

### Test Mode

SendGrid provides test API keys that don't send real emails:
```bash
# Use test key for development
SENDGRID_API_KEY=SG.test_key_here
```

### Manual Test

```python
# Test email sending
from services.email_service import get_email_service

email_service = get_email_service()

result = await email_service.send_email(
    to='test@example.com',
    template_id='d-test-template',
    dynamic_data={'name': 'Test User'},
    language='en'
)

print(result)  # {'success': True, 'message_id': '...'}
```

### Check Logs

```bash
# Monitor email logs
tail -f /var/log/supervisor/backend.err.log | grep -i \"email\\|sendgrid\"
```

---

## Troubleshooting

### Issue: Emails not sending

**Check:**
1. API key is set in `.env`
2. API key has correct permissions
3. SendGrid account is active (not suspended)
4. From email is verified in SendGrid

```bash
# Verify configuration
python3 -c \"import os; print(os.environ.get('SENDGRID_API_KEY')[:10] if os.environ.get('SENDGRID_API_KEY') else 'NOT SET')\"
```

### Issue: Emails going to spam

**Solutions:**
1. Authenticate your domain (DKIM/SPF)
2. Avoid spam trigger words
3. Include unsubscribe link
4. Maintain low bounce rate
5. Use professional email content

### Issue: Template ID not found

**Check:**
1. Template ID is correct (format: `d-xxxxx`)
2. Template is published (not draft)
3. Template has at least one version

### Issue: Dynamic data not showing

**Check:**
1. Variable names match template (case-sensitive)
2. Data is being passed correctly
3. Template syntax is correct: `{{variable}}`

---

## Best Practices

### 1. Email Frequency

- Don't spam users with excessive emails
- Implement email preferences (what emails to receive)
- Respect unsubscribe requests immediately

### 2. Content Guidelines

- Keep subject lines under 50 characters
- Include plain text alternative
- Add unsubscribe link
- Mobile-responsive design
- Clear call-to-action

### 3. Security

- Never include sensitive data (passwords, full credit cards)
- Use HTTPS links only
- Verify email domains before sending
- Monitor bounce rates

### 4. Performance

- Use bulk email for batch operations
- Queue emails for better performance
- Implement rate limiting
- Monitor SendGrid quotas

---

## Monitoring & Analytics

### Key Metrics to Track

1. **Delivery Rate:** % of emails successfully delivered
2. **Open Rate:** % of delivered emails opened
3. **Click Rate:** % of opened emails with clicks
4. **Bounce Rate:** % of emails that bounced
5. **Unsubscribe Rate:** % of users unsubscribing

### Query Examples

```python
from datetime import datetime, timedelta

# Get last 24h metrics
yesterday = datetime.now() - timedelta(days=1)

pipeline = [
    {\"$match\": {\"created_at\": {\"$gte\": yesterday.isoformat()}}},
    {\"$group\": {
        \"_id\": \"$event_type\",
        \"count\": {\"$sum\": 1}
    }}
]

metrics = await db.email_events.aggregate(pipeline).to_list(100)
print(metrics)
```

---

## Production Checklist

- [ ] SendGrid account created and verified
- [ ] Domain authenticated (DKIM/SPF)
- [ ] All template IDs updated in `email_templates.py`
- [ ] API key added to production `.env`
- [ ] Webhook endpoint configured in SendGrid
- [ ] Test emails sent successfully
- [ ] Admin email configured
- [ ] Email events being tracked
- [ ] Unsubscribe link in all templates
- [ ] Privacy policy updated with email practices
- [ ] Monitoring dashboard set up

---

## Support

**SendGrid Documentation:**
- API Reference: https://docs.sendgrid.com/api-reference
- Dynamic Templates: https://docs.sendgrid.com/ui/sending-email/how-to-send-an-email-with-dynamic-transactional-templates
- Event Webhook: https://docs.sendgrid.com/for-developers/tracking-events/event

**BidVex Support:**
- Email: dev@bidvex.com
- Documentation: `/app/backend/EMAIL_SERVICE_GUIDE.md`

---

**Version:** 1.0
**Last Updated:** {current_date}
**Author:** BidVex Engineering Team
