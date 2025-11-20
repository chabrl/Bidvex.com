# BidVex EmailService - Implementation Guide

Quick reference for using the EmailService in your application code.

---

## Setup & Import

```python
from services.email_service import get_email_service
from config.email_templates import (
    EmailTemplates,
    EmailDataBuilder,
    send_welcome_email,
    send_password_reset_email,
    send_bid_confirmation,
    send_outbid_notification
)

# Get email service instance
email_service = get_email_service()
```

---

## Common Use Cases

### 1. Send Welcome Email (New User Registration)

```python
@app.post("/api/auth/register")
async def register_user(user_data: UserCreate):
    # Create user in database
    user = await create_user(user_data)
    
    # Send welcome email
    try:
        result = await send_welcome_email(
            email_service,
            user={
                'name': user.name,
                'email': user.email,
                'account_type': user.account_type
            },
            language=user.preferred_language or 'en'
        )
        
        if result['success']:
            logger.info(f"Welcome email sent: {result['message_id']}")
        else:
            logger.error(f"Welcome email failed: {result['error']}")
            # User registration still succeeds even if email fails
            
    except Exception as e:
        logger.exception(f"Welcome email error: {str(e)}")
    
    return user
```

### 2. Send Password Reset Email

```python
@app.post("/api/auth/forgot-password")
async def forgot_password(email: str):
    user = await get_user_by_email(email)
    
    if not user:
        # Don't reveal if user exists
        return {"message": "If account exists, reset link was sent"}
    
    # Generate reset token (expires in 1 hour)
    reset_token = generate_secure_token()
    await store_reset_token(user['id'], reset_token, expires_in=3600)
    
    # Send reset email
    try:
        result = await send_password_reset_email(
            email_service,
            user=user,
            reset_token=reset_token,
            language=user.get('preferred_language', 'en')
        )
        
        if result['success']:
            logger.info(f"Password reset sent to {email}")
        else:
            logger.error(f"Password reset failed: {result['error']}")
            # Consider notifying admin
            
    except Exception as e:
        logger.exception(f"Password reset email error: {str(e)}")
    
    return {"message": "If account exists, reset link was sent"}
```

### 3. Send Bid Confirmation

```python
@app.post("/api/listings/{listing_id}/bid")
async def place_bid(
    listing_id: str,
    bid_data: BidCreate,
    current_user: dict = Depends(get_current_user)
):
    # Process bid
    bid = await create_bid(listing_id, bid_data, current_user['id'])
    listing = await get_listing(listing_id)
    
    # Send confirmation email
    try:
        result = await send_bid_confirmation(
            email_service,
            user=current_user,
            listing=listing,
            bid_amount=bid.amount,
            language=current_user.get('preferred_language', 'en')
        )
        
        if result['success']:
            logger.info(f"Bid confirmation sent: {result['message_id']}")
            
    except Exception as e:
        logger.exception(f"Bid confirmation email error: {str(e)}")
    
    return bid
```

### 4. Send Outbid Notification

```python
async def notify_outbid_users(listing_id: str, new_bid_amount: float):
    """
    Background task to notify previous high bidders they've been outbid.
    """
    # Get previous high bidders (excluding current winner)
    previous_bidders = await get_outbid_users(listing_id, new_bid_amount)
    listing = await get_listing(listing_id)
    
    for bidder in previous_bidders:
        try:
            result = await send_outbid_notification(
                email_service,
                user=bidder,
                listing=listing,
                new_bid_amount=new_bid_amount,
                language=bidder.get('preferred_language', 'en')
            )
            
            if result['success']:
                logger.info(f"Outbid notification sent to {bidder['email']}")
            else:
                logger.error(f"Outbid notification failed: {result['error']}")
                
        except Exception as e:
            logger.exception(f"Outbid notification error: {str(e)}")
```

### 5. Send Auction Won Email

```python
async def notify_auction_winners(auction_id: str):
    """
    Send winning notifications when auction ends.
    """
    winners = await get_auction_winners(auction_id)
    auction = await get_auction(auction_id)
    
    for winner in winners:
        try:
            result = await email_service.send_email(
                to=winner['email'],
                template_id=EmailTemplates.BID_WON,
                dynamic_data=EmailDataBuilder.auction_won_email(
                    winner,
                    auction,
                    winner['winning_bid'],
                    auction.get('currency', 'CAD')
                ),
                language=winner.get('preferred_language', 'en')
            )
            
            if result['success']:
                logger.info(f"Winner notification sent: {winner['email']}")
                
        except Exception as e:
            logger.exception(f"Winner notification error: {str(e)}")
```

### 6. Send Invoice Email

```python
@app.post("/api/invoices/{invoice_id}/send")
async def send_invoice_email(
    invoice_id: str,
    current_user: dict = Depends(get_current_user)
):
    invoice = await get_invoice(invoice_id)
    
    # Verify user owns this invoice
    if invoice['user_id'] != current_user['id']:
        raise HTTPException(403, "Not authorized")
    
    try:
        result = await email_service.send_email(
            to=current_user['email'],
            template_id=EmailTemplates.INVOICE,
            dynamic_data=EmailDataBuilder.invoice_email(
                current_user,
                invoice
            ),
            language=current_user.get('preferred_language', 'en')
        )
        
        if result['success']:
            # Update invoice record
            await mark_invoice_sent(invoice_id, result['message_id'])
            return {"message": "Invoice sent", "message_id": result['message_id']}
        else:
            raise HTTPException(500, f"Failed to send invoice: {result['error']}")
            
    except Exception as e:
        logger.exception(f"Invoice email error: {str(e)}")
        raise HTTPException(500, "Failed to send invoice")
```

### 7. Send Bulk Emails (e.g., Auction Ending Soon)

```python
async def send_auction_ending_notifications(auction_id: str):
    """
    Notify all watchers that auction is ending in 24 hours.
    """
    auction = await get_auction(auction_id)
    watchers = await get_auction_watchers(auction_id)
    
    # Prepare recipients list
    recipients = []
    for watcher in watchers:
        recipients.append({
            'email': watcher['email'],
            'data': {
                'first_name': watcher['name'].split()[0],
                'auction_title': auction['title'],
                'auction_url': f'https://bidvex.com/auction/{auction_id}',
                'end_time': auction['end_date'],
                'current_bid': f"{auction['current_price']:.2f}",
                'currency': auction.get('currency', 'CAD')
            }
        })
    
    # Send bulk emails
    try:
        result = await email_service.send_bulk_email(
            recipients=recipients,
            template_id=EmailTemplates.AUCTION_ENDING_SOON,
            language='en'  # Or per-user language
        )
        
        logger.info(
            f"Auction ending notifications: {result['success']} sent, "
            f"{result['failed']} failed"
        )
        
        if result['failed'] > 0:
            logger.warning(f"Failed emails: {result['errors']}")
            
    except Exception as e:
        logger.exception(f"Bulk email error: {str(e)}")
```

### 8. Send Custom Email (Not Using Template)

```python
async def send_custom_notification(user_email: str, subject: str, content: str):
    """
    Send a custom email without using a template.
    Note: This requires creating a message with content directly.
    """
    from sendgrid.helpers.mail import Mail, Email, To, Content
    
    email_service = get_email_service()
    
    if not email_service.is_configured():
        logger.error("Email service not configured")
        return False
    
    message = Mail(
        from_email=Email(email_service.from_email, email_service.from_name),
        to_emails=To(user_email),
        subject=subject,
        plain_text_content=Content('text/plain', content)
    )
    
    try:
        response = email_service.client.send(message)
        logger.info(f"Custom email sent: {response.status_code}")
        return True
    except Exception as e:
        logger.exception(f"Custom email error: {str(e)}")
        return False
```

---

## Advanced Features

### 1. Send Email with CC/BCC

```python
result = await email_service.send_email(
    to='user@example.com',
    template_id=EmailTemplates.INVOICE,
    dynamic_data=invoice_data,
    language='en',
    cc=['manager@bidvex.com'],
    bcc=['accounting@bidvex.com']
)
```

### 2. Send Email with Custom Reply-To

```python
result = await email_service.send_email(
    to='user@example.com',
    template_id=EmailTemplates.NEW_MESSAGE,
    dynamic_data=message_data,
    language='en',
    reply_to='seller@example.com'
)
```

### 3. Customize Retry Attempts

```python
result = await email_service.send_email(
    to='user@example.com',
    template_id=EmailTemplates.IMPORTANT_NOTIFICATION,
    dynamic_data=data,
    language='en',
    max_retries=5  # Default is 3
)
```

---

## Error Handling Best Practices

### 1. Always Wrap in Try-Catch

```python
try:
    result = await email_service.send_email(...)
    
    if result['success']:
        logger.info(f"Email sent: {result['message_id']}")
    else:
        logger.error(f"Email failed: {result['error']}")
        # Handle failure (notify admin, retry later, etc.)
        
except Exception as e:
    logger.exception(f"Unexpected email error: {str(e)}")
    # Handle exception
```

### 2. Don't Block Critical Operations

```python
# BAD: Blocking registration if email fails
@app.post("/api/auth/register")
async def register_user(user_data: UserCreate):
    user = await create_user(user_data)
    
    # This could raise exception and fail registration
    result = await send_welcome_email(email_service, user)
    if not result['success']:
        raise HTTPException(500, "Email failed")  # ❌ Bad!
    
    return user


# GOOD: Email is nice-to-have, not critical
@app.post("/api/auth/register")
async def register_user(user_data: UserCreate):
    user = await create_user(user_data)
    
    # Send email in background, don't block
    try:
        asyncio.create_task(send_welcome_email(email_service, user))
    except Exception as e:
        logger.error(f"Failed to queue welcome email: {str(e)}")
    
    return user  # ✅ Registration succeeds regardless
```

### 3. Check Service Configuration

```python
if email_service.is_configured():
    # Send email
    result = await email_service.send_email(...)
else:
    logger.warning("Email service not configured - email not sent")
    # Continue without email
```

---

## Background Tasks

For sending emails asynchronously without blocking the request:

```python
from fastapi import BackgroundTasks

@app.post("/api/auctions/{auction_id}/complete")
async def complete_auction(
    auction_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    # Complete auction
    auction = await mark_auction_complete(auction_id)
    
    # Queue email notifications as background task
    background_tasks.add_task(notify_auction_winners, auction_id)
    background_tasks.add_task(notify_sellers, auction_id)
    
    return {"message": "Auction completed", "auction": auction}
```

---

## Monitoring Email Delivery

### Check if Email Was Sent

```python
# Store message_id when sending
result = await email_service.send_email(...)
if result['success']:
    message_id = result['message_id']
    
    # Store in database for tracking
    await store_email_log(
        user_id=user['id'],
        email=user['email'],
        template_id=EmailTemplates.WELCOME,
        message_id=message_id,
        timestamp=datetime.now()
    )
```

### Query Email Events from MongoDB

```python
@app.get("/api/emails/{message_id}/events")
async def get_email_events(message_id: str):
    """
    Get delivery events for a specific email.
    """
    events = await db.email_events.find({
        'sg_message_id': message_id
    }).to_list(None)
    
    return {
        'message_id': message_id,
        'events': events,
        'delivered': any(e['event'] == 'delivered' for e in events),
        'opened': any(e['event'] == 'open' for e in events),
        'clicked': any(e['event'] == 'click' for e in events)
    }
```

---

## Testing

### Test Email Service in Development

```python
# Create test endpoint
@app.post("/api/test/email")
async def test_email_endpoint(
    email: str,
    current_user: dict = Depends(get_current_user)
):
    """Test endpoint - remove in production"""
    
    if not current_user.get('is_admin'):
        raise HTTPException(403, "Admin only")
    
    result = await email_service.send_email(
        to=email,
        template_id=EmailTemplates.WELCOME,
        dynamic_data={
            'first_name': 'Test',
            'full_name': 'Test User',
            'email': email,
            'login_url': 'https://bidvex.com/auth',
            'explore_url': 'https://bidvex.com/marketplace',
            'account_type': 'Personal'
        },
        language='en'
    )
    
    return result
```

---

## Common Pitfalls

❌ **Don't:** Hardcode email addresses
```python
# Bad
await email_service.send_email(to='user@example.com', ...)
```

✅ **Do:** Use user data from database
```python
# Good
await email_service.send_email(to=user['email'], ...)
```

---

❌ **Don't:** Block critical operations waiting for email
```python
# Bad - registration fails if email fails
user = await create_user(data)
await send_welcome_email(email_service, user)  # Blocks!
return user
```

✅ **Do:** Send emails in background
```python
# Good - registration succeeds even if email fails
user = await create_user(data)
asyncio.create_task(send_welcome_email(email_service, user))
return user
```

---

❌ **Don't:** Expose SendGrid errors to users
```python
# Bad
try:
    await send_email(...)
except Exception as e:
    raise HTTPException(500, str(e))  # Exposes internal error
```

✅ **Do:** Return user-friendly messages
```python
# Good
try:
    await send_email(...)
except Exception as e:
    logger.exception(f"Email error: {str(e)}")
    return {"message": "Email queued for delivery"}
```

---

## Additional Resources

- **Email Service Code**: `/app/backend/services/email_service.py`
- **Template Configuration**: `/app/backend/config/email_templates.py`
- **Production Status**: `/app/backend/EMAIL_SERVICE_PRODUCTION_STATUS.md`
- **Template Setup Guide**: `/app/backend/SENDGRID_TEMPLATE_SETUP.md`
- **Test Suite**: `/app/backend/test_email_service.py`

---

**Last Updated**: November 20, 2025
