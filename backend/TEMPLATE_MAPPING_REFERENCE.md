# BidVex SendGrid Template Mapping Reference

Quick reference for all template IDs and their usage.

---

## Template ID Mapping

| Category | Template ID | Backend Constants |
|----------|-------------|-------------------|
| **Authentication** | `d-e0ee403fbd8646db8011339cf2eeac30` | WELCOME, EMAIL_VERIFICATION, PASSWORD_RESET, PASSWORD_CHANGED |
| **Bidding** | `d-13806757fbd24818b24bc520074ea979` | BID_PLACED, BID_OUTBID, BID_WON, BID_LOST |
| **Auction Updates** | `d-f22625d31ef74262887e3a8f96934bc1` | AUCTION_ENDING_SOON, AUCTION_STARTED, AUCTION_CANCELLED |
| **Seller Notifications** | `d-794b529ec05e407da60b26113e0c4ea1` | NEW_BID_RECEIVED, LISTING_APPROVED, LISTING_REJECTED, ITEM_SOLD |
| **Financial** | `d-a8cb13c061e3449394e900b406e9a391` | INVOICE, PAYMENT_RECEIVED, PAYMENT_FAILED, REFUND_ISSUED |
| **Communication** | `d-3153ed45d6764d0687e69c85ffddcb10` | NEW_MESSAGE |
| **Admin** | `d-94d4a5d7855b4fa38badae9cf12ded41` | REPORT_RECEIVED, ACCOUNT_SUSPENDED |

---

## Usage by Function

### Authentication Templates (d-e0ee403fbd8646db8011339cf2eeac30)

#### 1. Welcome Email
```python
from config.email_templates import send_welcome_email

await send_welcome_email(
    email_service,
    user={'name': 'John Doe', 'email': 'john@example.com', 'account_type': 'personal'},
    language='en'
)
```

**Required Variables:**
- `first_name`, `full_name`, `email`, `login_url`, `explore_url`, `account_type`

#### 2. Password Reset
```python
from config.email_templates import send_password_reset_email

await send_password_reset_email(
    email_service,
    user={'name': 'John Doe', 'email': 'john@example.com'},
    reset_token='abc123xyz',
    language='en'
)
```

**Required Variables:**
- `first_name`, `reset_url`, `expires_in_hours`, `support_email`

---

### Bidding Templates (d-13806757fbd24818b24bc520074ea979)

#### 1. Bid Placed Confirmation
```python
from config.email_templates import send_bid_confirmation

await send_bid_confirmation(
    email_service,
    user={'name': 'John Doe', 'email': 'john@example.com'},
    listing={'title': 'Vintage Watch', 'id': '123', 'images': ['url'], 'current_price': 150},
    bid_amount=150.00,
    language='en'
)
```

**Required Variables:**
- `first_name`, `listing_title`, `listing_url`, `bid_amount`, `currency`, `listing_image`, `auction_end_date`, `current_high_bid`

#### 2. Outbid Notification
```python
from config.email_templates import send_outbid_notification

await send_outbid_notification(
    email_service,
    user={'name': 'John Doe', 'email': 'john@example.com'},
    listing={'title': 'Vintage Watch', 'id': '123', 'images': ['url']},
    new_bid_amount=175.00,
    language='en'
)
```

**Required Variables:**
- `first_name`, `listing_title`, `listing_url`, `new_bid_amount`, `currency`, `listing_image`, `time_remaining`, `bid_now_url`

---

### Auction Updates Templates (d-f22625d31ef74262887e3a8f96934bc1)

#### Auction Ending Soon
```python
await email_service.send_email(
    to='user@example.com',
    template_id=EmailTemplates.AUCTION_ENDING_SOON,
    dynamic_data={
        'first_name': 'John',
        'auction_title': 'Estate Sale',
        'auction_url': 'https://bidvex.com/auction/456',
        'end_time': '2025-12-31 15:00:00',
        'current_bid': '250.00',
        'currency': 'CAD'
    },
    language='en'
)
```

---

### Seller Notifications Templates (d-794b529ec05e407da60b26113e0c4ea1)

#### New Bid Received
```python
await email_service.send_email(
    to='seller@example.com',
    template_id=EmailTemplates.NEW_BID_RECEIVED,
    dynamic_data={
        'first_name': 'Jane',
        'listing_title': 'Antique Vase',
        'listing_url': 'https://bidvex.com/listing/789',
        'bid_amount': '300.00',
        'currency': 'CAD',
        'bidder_name': 'John Doe',
        'total_bids': '5'
    },
    language='en'
)
```

---

### Financial Templates (d-a8cb13c061e3449394e900b406e9a391)

#### Invoice Email
```python
from config.email_templates import EmailDataBuilder

await email_service.send_email(
    to='user@example.com',
    template_id=EmailTemplates.INVOICE,
    dynamic_data=EmailDataBuilder.invoice_email(
        user={'name': 'John Doe'},
        invoice={
            'invoice_number': 'BV-2025-001',
            'date': '2025-11-21',
            'total': 450.00,
            'subtotal': 450.00,
            'tax': 67.49,
            'shipping': 0.00,
            'currency': 'CAD',
            'items': [],
            'payment_method': 'Credit Card'
        }
    ),
    language='en'
)
```

---

### Communication Templates (d-3153ed45d6764d0687e69c85ffddcb10)

#### New Message Notification
```python
from config.email_templates import EmailDataBuilder

await email_service.send_email(
    to='user@example.com',
    template_id=EmailTemplates.NEW_MESSAGE,
    dynamic_data=EmailDataBuilder.new_message_email(
        user={'name': 'John Doe'},
        sender={'name': 'Jane Smith', 'id': '123'},
        message_preview='Hello! I have a question about your item...'
    ),
    language='en'
)
```

---

### Admin Templates (d-94d4a5d7855b4fa38badae9cf12ded41)

#### Report Received
```python
await email_service.send_email(
    to='admin@bidvex.com',
    template_id=EmailTemplates.REPORT_RECEIVED,
    dynamic_data={
        'first_name': 'Admin',
        'report_type': 'Spam',
        'reported_item': 'Listing #456',
        'reporter_name': 'John Doe',
        'report_reason': 'This listing appears to be spam',
        'admin_url': 'https://bidvex.com/admin/reports/123'
    },
    language='en'
)
```

---

## Common Dynamic Variables

All templates automatically receive:
- `language` - Language code (en/fr)
- `current_year` - Current year for footer

---

## Template Testing

### Quick Test (Single Template)
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
        dynamic_data={'first_name': 'Test', 'full_name': 'Test User', 
                     'email': 'test@example.com', 'login_url': 'https://bidvex.com',
                     'explore_url': 'https://bidvex.com', 'account_type': 'Personal'},
        language='en'
    )
    print(f'Success: {result[\"success\"]}, Message ID: {result[\"message_id\"]}')

asyncio.run(test())
"
```

### Full Test Suite (All Templates)
```bash
cd /app/backend
python test_production_templates.py
```

---

## SendGrid Dashboard Access

- **URL**: https://app.sendgrid.com/
- **Templates**: Email API → Dynamic Templates
- **Activity**: Activity Feed (real-time email tracking)
- **Stats**: Statistics (delivery rates, open rates, clicks)

---

## Troubleshooting

### Template Not Found Error
**Problem**: `The template_id must be a valid GUID`

**Solution**: 
1. Verify template ID in SendGrid dashboard
2. Check `/app/backend/config/email_templates.py`
3. Ensure template is Active (not Draft)

### Variables Not Rendering
**Problem**: Email shows `{{ variable }}` instead of value

**Solution**:
1. Check variable names match exactly (case-sensitive)
2. Verify `dynamic_data` contains all required variables
3. Use Handlebars syntax: `{{ variable }}` not `${variable}`

### Email Not Sending
**Problem**: `send_email()` returns success=False

**Solution**:
1. Check SENDGRID_API_KEY in `.env`
2. Verify sender email is verified in SendGrid
3. Check backend logs for detailed error messages
4. Ensure template exists and is active

---

**Last Updated**: November 21, 2025  
**Production Status**: ✅ Active  
**Total Templates**: 7 categories, 22 variations
