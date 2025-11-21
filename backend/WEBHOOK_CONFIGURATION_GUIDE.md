# SendGrid Event Webhook Configuration Guide

Complete guide for setting up email event tracking via SendGrid webhooks.

---

## What is the SendGrid Event Webhook?

The Event Webhook allows you to receive real-time notifications when email events occur:
- **Delivered**: Email successfully delivered to recipient's inbox
- **Opened**: Recipient opened the email
- **Clicked**: Recipient clicked a link in the email
- **Bounced**: Email bounced (invalid address, full mailbox, etc.)
- **Spam Report**: Recipient marked email as spam
- **Unsubscribe**: Recipient unsubscribed

**Benefits:**
- Track email engagement metrics
- Monitor delivery rates
- Identify bounced emails for list cleaning
- Measure campaign effectiveness
- Debug delivery issues

---

## Prerequisites

✅ SendGrid account with API key  
✅ BidVex backend running and accessible  
✅ Webhook endpoint implemented at `/api/webhooks/sendgrid`  
✅ HTTPS enabled on domain (required by SendGrid)

---

## Step-by-Step Configuration

### Step 1: Access SendGrid Dashboard

1. Go to: https://app.sendgrid.com/login
2. Log in with your SendGrid credentials
3. Navigate to: **Settings** → **Mail Settings** → **Event Webhook**

### Step 2: Enable Event Webhook

1. Click **Enable Event Webhook** toggle (turn it ON)
2. Status should show: ✅ Enabled

### Step 3: Configure Webhook URL

**HTTP Post URL:**
```
https://bidvex.com/api/webhooks/sendgrid
```

**Important:**
- Must be HTTPS (not HTTP)
- Must be publicly accessible
- Must respond with 200 OK status
- Must respond within 30 seconds

### Step 4: Select Events to Track

Check these boxes to enable event tracking:

**Recommended (All):**
- ✅ Delivered
- ✅ Opened
- ✅ Clicked
- ✅ Bounced
- ✅ Spam Report
- ✅ Unsubscribe

**Optional:**
- ⬜ Deferred (temporary delivery delay)
- ⬜ Dropped (permanent delivery failure)
- ⬜ Group Unsubscribe
- ⬜ Group Resubscribe

### Step 5: Security Settings (Optional)

**Enable Signed Events:**
- ✅ Check "Enable Signed Event Webhook Requests"
- SendGrid will generate a verification key
- Copy the verification key
- Add to `/app/backend/.env`:
  ```bash
  SENDGRID_WEBHOOK_VERIFY_KEY=your_verification_key_here
  ```

**OAuth (Advanced):**
- Leave unchecked unless you have specific OAuth requirements

### Step 6: Test the Webhook

1. Click **"Test Your Integration"** button
2. SendGrid will send a test POST request to your webhook URL
3. Check if test succeeds (green checkmark appears)

**If test fails:**
- Verify URL is correct and accessible
- Check backend logs: `tail -f /var/log/supervisor/backend.out.log`
- Ensure firewall allows SendGrid IPs
- Verify webhook endpoint returns 200 OK

### Step 7: Save Configuration

1. Click **Save** button at the bottom
2. Confirmation message should appear: "Event Webhook settings saved"

---

## Webhook Endpoint Details

### Endpoint Information

**URL**: `POST /api/webhooks/sendgrid`  
**Location**: `/app/backend/server.py` (around line 2500)  
**Authentication**: None (SendGrid uses signed events for security)  
**Expected Response**: `200 OK`

### Event Payload Structure

SendGrid sends events as JSON array:

```json
[
  {
    "email": "user@example.com",
    "timestamp": 1637683332,
    "event": "delivered",
    "sg_message_id": "abc123.filterdrecv-p3las1-...",
    "smtp-id": "<abc123@sendgrid.com>",
    "response": "250 OK",
    "category": ["welcome_email"],
    "asm_group_id": 1234
  },
  {
    "email": "user@example.com",
    "timestamp": 1637683400,
    "event": "open",
    "sg_message_id": "abc123.filterdrecv-p3las1-...",
    "useragent": "Mozilla/5.0 ...",
    "ip": "192.168.1.1"
  }
]
```

### Current Implementation

The webhook endpoint currently:
1. Receives POST request from SendGrid
2. Parses JSON payload
3. Stores events in MongoDB `email_events` collection
4. Logs event details
5. Returns 200 OK

**Code Location**: `/app/backend/server.py`

```python
@app.post("/api/webhooks/sendgrid")
async def sendgrid_webhook(request: Request):
    """
    Receive and process SendGrid event webhook.
    Events: delivered, opened, clicked, bounced, spam, unsubscribe
    """
    try:
        events = await request.json()
        
        # Store each event in MongoDB
        for event in events:
            await db.email_events.insert_one({
                'email': event.get('email'),
                'event': event.get('event'),
                'timestamp': datetime.fromtimestamp(event.get('timestamp', 0)),
                'message_id': event.get('sg_message_id'),
                'smtp_id': event.get('smtp-id'),
                'response': event.get('response'),
                'reason': event.get('reason'),
                'url': event.get('url'),  # For click events
                'useragent': event.get('useragent'),  # For open events
                'ip': event.get('ip'),
                'raw_event': event  # Store full event for debugging
            })
        
        logger.info(f"Processed {len(events)} SendGrid webhook events")
        return {"status": "success", "processed": len(events)}
        
    except Exception as e:
        logger.error(f"SendGrid webhook error: {str(e)}")
        # Still return 200 OK to avoid retry storms
        return {"status": "error", "message": str(e)}
```

---

## Verifying Webhook is Working

### Method 1: Send Test Email

```bash
cd /app/backend
python -c "
import asyncio
from services.email_service import get_email_service
from config.email_templates import EmailTemplates

async def test():
    service = get_email_service()
    result = await service.send_email(
        to='your-email@example.com',
        template_id=EmailTemplates.WELCOME,
        dynamic_data={
            'first_name': 'Webhook',
            'full_name': 'Test User',
            'email': 'test@example.com',
            'login_url': 'https://bidvex.com',
            'explore_url': 'https://bidvex.com',
            'account_type': 'Personal'
        },
        language='en'
    )
    print(f'Email sent! Message ID: {result[\"message_id\"]}')

asyncio.run(test())
"
```

### Method 2: Check Backend Logs

```bash
# Watch for webhook events in real-time
tail -f /var/log/supervisor/backend.out.log | grep webhook

# Look for lines like:
# INFO: Processed 1 SendGrid webhook events
```

### Method 3: Query MongoDB

```bash
mongosh bazario_db

# View recent webhook events
db.email_events.find().sort({timestamp: -1}).limit(10).pretty()

# Count events by type
db.email_events.aggregate([
  { $group: { _id: "$event", count: { $sum: 1 } } }
])

# Find events for specific email
db.email_events.find({ email: "user@example.com" })
```

### Method 4: SendGrid Activity Feed

1. Go to SendGrid Dashboard → **Activity**
2. Search for your test email
3. Click to view details
4. Check "Event Webhook" section
5. Verify webhook POST request succeeded

---

## Webhook Event Types Explained

### 1. Delivered
```json
{
  "event": "delivered",
  "email": "user@example.com",
  "smtp-id": "<abc@sendgrid.com>",
  "response": "250 OK",
  "timestamp": 1637683332
}
```
**Meaning**: Email successfully delivered to recipient's mail server  
**Action**: Mark email as delivered in your system

### 2. Opened
```json
{
  "event": "open",
  "email": "user@example.com",
  "timestamp": 1637683400,
  "useragent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
  "ip": "192.168.1.1"
}
```
**Meaning**: Recipient opened the email  
**Action**: Track engagement, update open rate metrics  
**Note**: Requires image tracking pixel (enabled by default)

### 3. Clicked
```json
{
  "event": "click",
  "email": "user@example.com",
  "url": "https://bidvex.com/listing/123",
  "timestamp": 1637683500
}
```
**Meaning**: Recipient clicked a link in the email  
**Action**: Track click-through rates, popular links  
**Note**: SendGrid rewrites links for tracking

### 4. Bounced
```json
{
  "event": "bounce",
  "email": "invalid@example.com",
  "reason": "550 5.1.1 User unknown",
  "type": "bounce",
  "status": "5.1.1",
  "timestamp": 1637683600
}
```
**Meaning**: Email bounced (hard or soft bounce)  
**Action**: Remove from mailing list (hard bounce), retry later (soft bounce)

### 5. Spam Report
```json
{
  "event": "spamreport",
  "email": "user@example.com",
  "timestamp": 1637683700
}
```
**Meaning**: Recipient marked email as spam  
**Action**: Remove from mailing list, review email content

### 6. Unsubscribe
```json
{
  "event": "unsubscribe",
  "email": "user@example.com",
  "timestamp": 1637683800
}
```
**Meaning**: Recipient unsubscribed  
**Action**: Update user preferences, stop sending emails

---

## Using Webhook Data

### Track Email Engagement

```python
@app.get("/api/emails/{email}/stats")
async def get_email_stats(email: str):
    """Get email engagement statistics for a user."""
    
    events = await db.email_events.find({"email": email}).to_list(None)
    
    stats = {
        "total_sent": 0,
        "delivered": 0,
        "opened": 0,
        "clicked": 0,
        "bounced": 0,
        "spam_reports": 0,
        "open_rate": 0,
        "click_rate": 0
    }
    
    for event in events:
        event_type = event.get('event')
        if event_type == 'delivered':
            stats['delivered'] += 1
        elif event_type == 'open':
            stats['opened'] += 1
        elif event_type == 'click':
            stats['clicked'] += 1
        elif event_type == 'bounce':
            stats['bounced'] += 1
        elif event_type == 'spamreport':
            stats['spam_reports'] += 1
    
    # Calculate rates
    if stats['delivered'] > 0:
        stats['open_rate'] = (stats['opened'] / stats['delivered']) * 100
        stats['click_rate'] = (stats['clicked'] / stats['delivered']) * 100
    
    return stats
```

### Monitor Delivery Issues

```python
@app.get("/api/admin/email-health")
async def email_health_check():
    """Check email delivery health metrics."""
    
    # Get events from last 7 days
    seven_days_ago = datetime.now() - timedelta(days=7)
    
    events = await db.email_events.find({
        "timestamp": {"$gte": seven_days_ago}
    }).to_list(None)
    
    total_sent = len(events)
    bounced = len([e for e in events if e.get('event') == 'bounce'])
    spam = len([e for e in events if e.get('event') == 'spamreport'])
    
    bounce_rate = (bounced / total_sent * 100) if total_sent > 0 else 0
    spam_rate = (spam / total_sent * 100) if total_sent > 0 else 0
    
    health_status = "healthy"
    if bounce_rate > 5 or spam_rate > 0.1:
        health_status = "warning"
    if bounce_rate > 10 or spam_rate > 0.5:
        health_status = "critical"
    
    return {
        "status": health_status,
        "total_sent": total_sent,
        "bounce_rate": bounce_rate,
        "spam_rate": spam_rate,
        "period": "7 days"
    }
```

---

## Troubleshooting

### Webhook Not Receiving Events

**Problem**: No events appearing in MongoDB

**Solutions:**
1. Check webhook is enabled in SendGrid dashboard
2. Verify URL is correct and publicly accessible
3. Test with SendGrid's "Test Your Integration" button
4. Check backend logs for errors
5. Ensure MongoDB connection is working
6. Verify firewall allows SendGrid IPs

**SendGrid IP Ranges:**
```
167.89.0.0/17
167.89.64.0/18
167.89.118.0/23
```

### Events Delayed

**Problem**: Events arrive late

**Solutions:**
- SendGrid may batch events (up to 30 seconds)
- Check SendGrid Activity Feed for timestamps
- Verify server time is synchronized (NTP)

### Duplicate Events

**Problem**: Same event received multiple times

**Solutions:**
- Use `sg_message_id` + `event` + `timestamp` as unique key
- Implement idempotency in webhook handler
- SendGrid may retry if no 200 OK received

### Webhook Errors

**Problem**: SendGrid shows webhook failures

**Solutions:**
1. Ensure endpoint returns 200 OK within 30 seconds
2. Don't perform heavy processing in webhook handler
3. Queue events for async processing
4. Return 200 OK even if processing fails

---

## Security Best Practices

### 1. Enable Signed Events

Add signature verification to webhook endpoint:

```python
import hmac
import hashlib

@app.post("/api/webhooks/sendgrid")
async def sendgrid_webhook(request: Request):
    # Verify signature
    signature = request.headers.get('X-Twilio-Email-Event-Webhook-Signature')
    timestamp = request.headers.get('X-Twilio-Email-Event-Webhook-Timestamp')
    
    verify_key = os.environ.get('SENDGRID_WEBHOOK_VERIFY_KEY')
    
    if verify_key:
        body = await request.body()
        payload = timestamp.encode('utf-8') + body
        expected_signature = hmac.new(
            verify_key.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        if signature != expected_signature:
            raise HTTPException(403, "Invalid signature")
    
    # Process events...
```

### 2. Rate Limiting

Implement rate limiting to prevent abuse:

```python
from fastapi_limiter.depends import RateLimiter

@app.post("/api/webhooks/sendgrid", dependencies=[Depends(RateLimiter(times=100, seconds=60))])
async def sendgrid_webhook(request: Request):
    # Process events...
```

### 3. IP Whitelisting

Only accept requests from SendGrid IPs (optional)

---

## Next Steps

1. ✅ **Configure webhook in SendGrid dashboard** (10 minutes)
2. ✅ **Test with real email** (5 minutes)
3. ✅ **Verify events in MongoDB** (2 minutes)
4. ✅ **Monitor for 24 hours** (ongoing)
5. ✅ **Build analytics dashboard** (future)

---

**Last Updated**: November 21, 2025  
**Status**: Ready for Configuration  
**Estimated Setup Time**: 15-20 minutes
