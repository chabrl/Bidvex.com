# Password Reset Email - SendGrid Template Configuration Guide

Guide for configuring the password reset email template in SendGrid to ensure all dynamic variables render correctly.

---

## Issue Summary

**Problem**: Password reset emails were being sent but the reset link button had no href and the expiry message was blank.

**Root Cause**: Mismatch between variable names sent by backend and variable names used in SendGrid template.

**Solution**: Backend now sends both variable name formats for compatibility:
- `reset_url` AND `reset_link`
- `expires_in_hours` AND `expiry_time`

---

## Dynamic Variables Reference

### Variables Sent by Backend

The backend sends the following variables with each password reset email:

```json
{
  "first_name": "Jean",
  "reset_url": "https://bidvex.com/reset-password?token={token}",
  "reset_link": "https://bidvex.com/reset-password?token={token}",
  "expires_in_hours": 1,
  "expiry_time": "1 hour",
  "support_email": "support@bidvex.com"
}
```

### Variable Descriptions

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `first_name` | String | User's first name | "Jean" |
| `reset_url` | String | Full password reset URL | "https://bidvex.com/reset-password?token=abc123" |
| `reset_link` | String | Same as reset_url (alternative name) | "https://bidvex.com/reset-password?token=abc123" |
| `expires_in_hours` | Number | Hours until link expires | 1 |
| `expiry_time` | String | Formatted expiry time | "1 hour" |
| `support_email` | String | Support email address | "support@bidvex.com" |
| `language` | String | User's preferred language | "en" or "fr" |
| `current_year` | Number | Current year | 2025 |

---

## SendGrid Template Configuration

### Template ID

**Authentication Template**: `d-e0ee403fbd8646db8011339cf2eeac30`

This template is shared for:
- Welcome emails
- Email verification
- **Password reset** ← Using this one
- Password changed confirmation

### Required Template Structure

#### 1. Subject Line

**English:**
```
Reset Your BidVex Password
```

**French:**
```
Réinitialisez votre mot de passe BidVex
```

#### 2. Email Body Structure

**English Version:**

```html
<div class="email-container">
  <!-- Header -->
  <div class="header">
    <img src="{{logo_url}}" alt="BidVex" />
    <h1>Password Reset Request</h1>
  </div>
  
  <!-- Content -->
  <div class="content">
    <p>Hi {{first_name}},</p>
    
    <p>We received a request to reset your BidVex password. Click the button below to create a new password:</p>
    
    <!-- CRITICAL: Reset Button with Link -->
    <div class="button-container">
      <a href="{{reset_link}}" class="button primary">
        Reset My Password
      </a>
    </div>
    
    <!-- Expiry Warning -->
    <div class="warning">
      <p><strong>⏰ This link expires in {{expiry_time}}</strong></p>
      <p>For security reasons, please reset your password as soon as possible.</p>
    </div>
    
    <!-- Alternative Link -->
    <p class="small">
      If the button doesn't work, copy and paste this link into your browser:
    </p>
    <p class="code">{{reset_link}}</p>
    
    <!-- Security Notice -->
    <div class="notice">
      <p><strong>Didn't request this?</strong></p>
      <p>If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.</p>
    </div>
    
    <!-- Support -->
    <p class="small">
      Need help? Contact us at <a href="mailto:{{support_email}}">{{support_email}}</a>
    </p>
  </div>
  
  <!-- Footer -->
  <div class="footer">
    <p>&copy; {{current_year}} BidVex. All rights reserved.</p>
  </div>
</div>
```

**French Version:**

```html
<div class="email-container">
  <!-- Header -->
  <div class="header">
    <img src="{{logo_url}}" alt="BidVex" />
    <h1>Demande de réinitialisation de mot de passe</h1>
  </div>
  
  <!-- Content -->
  <div class="content">
    <p>Bonjour {{first_name}},</p>
    
    <p>Nous avons reçu une demande de réinitialisation de votre mot de passe BidVex. Cliquez sur le bouton ci-dessous pour créer un nouveau mot de passe:</p>
    
    <!-- CRITICAL: Reset Button with Link -->
    <div class="button-container">
      <a href="{{reset_link}}" class="button primary">
        Réinitialiser mon mot de passe
      </a>
    </div>
    
    <!-- Expiry Warning -->
    <div class="warning">
      <p><strong>⏰ Ce lien expire dans {{expiry_time}}</strong></p>
      <p>Pour des raisons de sécurité, veuillez réinitialiser votre mot de passe dès que possible.</p>
    </div>
    
    <!-- Alternative Link -->
    <p class="small">
      Si le bouton ne fonctionne pas, copiez et collez ce lien dans votre navigateur:
    </p>
    <p class="code">{{reset_link}}</p>
    
    <!-- Security Notice -->
    <div class="notice">
      <p><strong>Vous n'avez pas demandé ceci?</strong></p>
      <p>Si vous n'avez pas demandé de réinitialisation de mot de passe, vous pouvez ignorer cet e-mail en toute sécurité. Votre mot de passe restera inchangé.</p>
    </div>
    
    <!-- Support -->
    <p class="small">
      Besoin d'aide? Contactez-nous à <a href="mailto:{{support_email}}">{{support_email}}</a>
    </p>
  </div>
  
  <!-- Footer -->
  <div class="footer">
    <p>&copy; {{current_year}} BidVex. Tous droits réservés.</p>
  </div>
</div>
```

---

## Critical Template Requirements

### 1. Reset Button MUST Include href

**✅ CORRECT:**
```html
<a href="{{reset_link}}" class="button">Reset Password</a>
```

**❌ WRONG:**
```html
<a class="button">Reset Password</a>
```

### 2. Expiry Message MUST Use Variable

**✅ CORRECT:**
```html
<p>This link expires in {{expiry_time}}</p>
```

**❌ WRONG:**
```html
<p>This link expires in 1 hour</p>  <!-- Hardcoded -->
```

### 3. Alternative Link for Copy/Paste

Always provide the raw link for users who can't click buttons:

```html
<p>Copy and paste this link:</p>
<p class="code">{{reset_link}}</p>
```

---

## Testing the Template

### Step 1: Test in SendGrid Editor

1. Go to SendGrid Dashboard → Email API → Dynamic Templates
2. Open template `d-e0ee403fbd8646db8011339cf2eeac30`
3. Click "Preview & Test"
4. Enter test data:

```json
{
  "first_name": "Jean",
  "reset_link": "https://bidvex.com/reset-password?token=test123",
  "expiry_time": "1 hour",
  "support_email": "support@bidvex.com",
  "language": "fr",
  "current_year": 2025
}
```

5. Verify:
   - ✅ Button has working href
   - ✅ Expiry message shows "1 hour"
   - ✅ Alternative link is visible
   - ✅ All variables render

### Step 2: Test with Backend Script

```bash
cd /app/backend
python test_password_reset_email.py
```

Follow prompts:
1. Enter your email address
2. Check inbox for email
3. Verify button clicks through to reset page
4. Verify expiry message is visible

### Step 3: Test Full Flow

1. Go to login page: https://bidvex.com/auth
2. Click "Forgot password?"
3. Enter your email
4. Check inbox
5. Click reset link in email
6. Verify redirects to: `https://bidvex.com/reset-password?token={token}`
7. Reset password
8. Check for confirmation email

---

## Troubleshooting

### Issue: Button has no link

**Check:**
1. SendGrid template uses `{{reset_link}}` in href attribute
2. Backend is sending `reset_link` variable
3. Variable name is spelled correctly (case-sensitive)

**Fix:**
```html
<!-- Before -->
<a class="button">Reset Password</a>

<!-- After -->
<a href="{{reset_link}}" class="button">Reset Password</a>
```

### Issue: Expiry message is blank

**Check:**
1. SendGrid template uses `{{expiry_time}}`
2. Backend is sending `expiry_time` variable
3. Variable is not null or empty

**Fix:**
```html
<!-- Before -->
<p>This link expires in {{expires_in_hours}} hour(s)</p>

<!-- After -->
<p>This link expires in {{expiry_time}}</p>
```

### Issue: Variables not rendering

**Check:**
1. Variable names match exactly (case-sensitive)
2. Variables wrapped in double curly braces: `{{variable}}`
3. Backend is actually sending the variables

**Backend Logging:**

Check what data is being sent:

```bash
tail -f /var/log/supervisor/backend.out.log | grep "password reset"
```

Should see:
```
INFO: Sending password reset email with data: {'first_name': 'Jean', 'reset_link': '...', 'expiry_time': '1 hour', ...}
```

### Issue: Link doesn't work

**Check:**
1. Token is included in URL
2. URL is properly formatted
3. Token hasn't expired (1 hour limit)
4. Token hasn't been used already

**Valid URL format:**
```
https://bidvex.com/reset-password?token=bidvex-sync
```

---

## Backend Code Reference

### Data Builder Function

**Location:** `/app/backend/config/email_templates.py`

```python
@staticmethod
def password_reset_email(
    user: Dict[str, Any],
    reset_token: str,
    expires_in_hours: int = 1
) -> Dict[str, Any]:
    """Build data for password reset email."""
    reset_url = f'https://bidvex.com/reset-password?token={reset_token}'
    expiry_message = f'{expires_in_hours} hour' if expires_in_hours == 1 else f'{expires_in_hours} hours'
    
    return {
        'first_name': user.get('name', '').split()[0],
        # Both variable name formats for template compatibility
        'reset_url': reset_url,
        'reset_link': reset_url,  # Alternative name used in template
        'expires_in_hours': expires_in_hours,
        'expiry_time': expiry_message,  # Formatted expiry time
        'support_email': 'support@bidvex.com'
    }
```

### Email Sending Function

**Location:** `/app/backend/server.py`

```python
from config.email_templates import send_password_reset_email, EmailDataBuilder

# Log email data being sent
email_data = EmailDataBuilder.password_reset_email(user_doc, reset_token)
logger.info(f"Sending password reset email with data: {email_data}")

# Send email
result = await send_password_reset_email(
    email_service,
    user=user_doc,
    reset_token=reset_token,
    language=user_doc.get('preferred_language', 'en')
)
```

---

## Variable Mapping Table

| Backend Variable | SendGrid Template Variable | Description |
|------------------|---------------------------|-------------|
| `reset_url` | `{{reset_url}}` or `{{reset_link}}` | Full password reset URL |
| `reset_link` | `{{reset_link}}` | Same as reset_url (preferred) |
| `expires_in_hours` | `{{expires_in_hours}}` | Numeric hours (1) |
| `expiry_time` | `{{expiry_time}}` | Formatted string ("1 hour") |
| `first_name` | `{{first_name}}` | User's first name |
| `support_email` | `{{support_email}}` | Support contact email |

---

## Best Practices

### 1. Always Use Both Variable Names

Send both `reset_url` and `reset_link` for template compatibility:

```python
{
    'reset_url': url,
    'reset_link': url  # Ensures compatibility
}
```

### 2. Format Expiry Time

Don't just send number of hours, send formatted message:

```python
# Good
'expiry_time': '1 hour'  # or '2 hours', '30 minutes', etc.

# Less good
'expires_in_hours': 1  # Requires template to format
```

### 3. Provide Alternative Link

Always include plain text link for users who can't click buttons:

```html
<p>Or copy this link: {{reset_link}}</p>
```

### 4. Security Notice

Include notice for users who didn't request reset:

```html
<p>If you didn't request this, ignore this email.</p>
```

### 5. Log Everything

Log email data before sending for debugging:

```python
logger.info(f"Email data: {email_data}")
```

---

## Bilingual Support

### Option 1: Single Template with Conditionals

```html
{{#if (eq language "fr")}}
  <h1>Réinitialisez votre mot de passe</h1>
  <p>Bonjour {{first_name}},</p>
{{else}}
  <h1>Reset Your Password</h1>
  <p>Hi {{first_name}},</p>
{{/if}}
```

### Option 2: Separate Templates

Create separate template versions:
- `d-...-en` (English)
- `d-...-fr` (French)

Update backend to select template based on language.

---

## Support

**Backend Code**: `/app/backend/server.py` (line ~667)  
**Email Templates**: `/app/backend/config/email_templates.py`  
**Test Script**: `/app/backend/test_password_reset_email.py`  
**SendGrid Dashboard**: https://app.sendgrid.com/

**Template ID**: `d-e0ee403fbd8646db8011339cf2eeac30`

---

**Last Updated**: November 21, 2025  
**Status**: ✅ Fixed and Validated  
**Issue Resolved**: Reset link and expiry time now render correctly
