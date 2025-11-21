# BidVex Authentication & Password Reset Flow Guide

Complete guide for the authentication system including login, registration, and password reset functionality.

---

## Table of Contents

1. [Overview](#overview)
2. [Login Flow](#login-flow)
3. [Registration Flow](#registration-flow)
4. [Forgot Password Flow](#forgot-password-flow)
5. [Reset Password Flow](#reset-password-flow)
6. [Security Features](#security-features)
7. [Email Templates](#email-templates)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The BidVex authentication system provides:
- ✅ Email/Password login
- ✅ User registration (Personal & Business accounts)
- ✅ Google OAuth integration
- ✅ Secure password reset via email
- ✅ JWT token-based authentication
- ✅ Session management
- ✅ SendGrid email integration

---

## Login Flow

### Frontend: `/auth`

**Page**: `/app/frontend/src/pages/AuthPage.js`

**Features:**
- Email and password input fields
- "Forgot Password?" link
- Toggle between login and registration
- Google OAuth button
- Responsive glassmorphism design
- ARIA labels for accessibility

**Code Example:**

```javascript
import { useAuth } from '../contexts/AuthContext';

const { login } = useAuth();

const handleLogin = async (email, password) => {
  try {
    await login(email, password);
    navigate('/marketplace');
    toast.success('Welcome back!');
  } catch (error) {
    toast.error(error.response?.data?.detail || 'Login failed');
  }
};
```

### Backend: `POST /api/auth/login`

**Location**: `/app/backend/server.py` (line ~598)

**Request:**
```json
{
  "email": "user@example.com",
  "password": "userpassword"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid-here",
    "email": "user@example.com",
    "name": "John Doe",
    "account_type": "personal",
    ...
  }
}
```

**Process:**
1. Validate email exists in database
2. Verify password using bcrypt
3. Generate JWT token (7 days expiry)
4. Return token + user data
5. Frontend stores token in localStorage
6. Sets Authorization header for all future requests

---

## Registration Flow

### Frontend: `/auth` (Registration Mode)

**Features:**
- Name, email, password, phone fields
- Account type selection (Personal/Business)
- Conditional business fields (Company name, Tax number)
- Welcome email sent on success

**Code Example:**

```javascript
const { register } = useAuth();

const handleRegister = async (userData) => {
  try {
    await register(userData);
    navigate('/marketplace');
    toast.success('Account created successfully!');
  } catch (error) {
    toast.error(error.response?.data?.detail || 'Registration failed');
  }
};
```

### Backend: `POST /api/auth/register`

**Request:**
```json
{
  "email": "newuser@example.com",
  "password": "securepassword",
  "name": "John Doe",
  "phone": "+1234567890",
  "account_type": "personal",
  "company_name": "",
  "tax_number": ""
}
```

**Response:**
```json
{
  "access_token": "jwt-token-here",
  "token_type": "bearer",
  "user": { ... }
}
```

**Process:**
1. Validate email doesn't exist
2. Hash password with bcrypt
3. Create user document in MongoDB
4. Generate JWT token
5. **Send welcome email** (if SendGrid configured)
6. Return token + user data

**Welcome Email Integration:**

```python
from services.email_service import get_email_service
from config.email_templates import send_welcome_email

# After user creation
email_service = get_email_service()

if email_service.is_configured():
    await send_welcome_email(
        email_service,
        user={'name': user.name, 'email': user.email, 'account_type': user.account_type},
        language=user.preferred_language or 'en'
    )
```

---

## Forgot Password Flow

### Frontend: `/forgot-password`

**Page**: `/app/frontend/src/pages/ForgotPasswordPage.js`

**Features:**
- Single email input field
- Success state with instructions
- Security: Always shows success (prevents email enumeration)
- Link back to login page
- Professional design with icons

**User Experience:**
1. User clicks "Forgot Password?" on login page
2. Enters email address
3. Receives confirmation message
4. Checks email for reset link
5. Link expires in 1 hour

**Code Example:**

```javascript
const handleForgotPassword = async (email) => {
  try {
    await axios.post(`${API}/auth/forgot-password`, { email });
    setEmailSent(true);
    toast.success('Reset instructions sent to your email');
  } catch (error) {
    // Still show success to prevent email enumeration
    setEmailSent(true);
  }
};
```

### Backend: `POST /api/auth/forgot-password`

**Location**: `/app/backend/server.py` (line ~660)

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "message": "If an account with that email exists, a password reset link has been sent.",
  "success": true
}
```

**Process:**

1. **Check if user exists** (silently)
2. **Generate secure token**: UUID v4
3. **Set expiry**: 1 hour from now
4. **Store token** in `password_reset_tokens` collection:
   ```json
   {
     "id": "token-uuid",
     "user_id": "user-uuid",
     "token": "reset-token-uuid",
     "expires_at": "2025-11-21T17:00:00Z",
     "used": false,
     "created_at": "2025-11-21T16:00:00Z"
   }
   ```
5. **Send password reset email** using SendGrid template

**Email Integration:**

```python
from services.email_service import get_email_service
from config.email_templates import send_password_reset_email

email_service = get_email_service()

if email_service.is_configured():
    result = await send_password_reset_email(
        email_service,
        user=user_doc,
        reset_token=reset_token,
        language=user_doc.get('preferred_language', 'en')
    )
    
    if result['success']:
        logger.info(f"Password reset email sent: {result.get('message_id')}")
```

**Email Template Variables:**
- `first_name`: User's first name
- `reset_url`: `https://bidvex.com/reset-password?token={{token}}`
- `expires_in_hours`: 1
- `support_email`: support@bidvex.com

---

## Reset Password Flow

### Frontend: `/reset-password?token={token}`

**Page**: `/app/frontend/src/pages/ResetPasswordPage.js`

**Features:**
- Token validation on page load
- New password input with show/hide toggle
- Confirm password field
- Password strength requirements (6+ characters)
- Real-time password match validation
- Expiry time display
- Success state with redirect

**User Experience:**
1. User clicks reset link in email
2. Page verifies token is valid
3. User enters new password (twice)
4. Password validated (length, match)
5. Success message + redirect to login
6. Old sessions invalidated

**Code Example:**

```javascript
// Verify token on page load
useEffect(() => {
  const verifyToken = async () => {
    const response = await axios.get(
      `${API}/auth/verify-reset-token/${token}`
    );
    
    setTokenValid(response.data.valid);
    setExpiresInMinutes(response.data.expires_in_minutes);
  };
  
  verifyToken();
}, [token]);

// Submit new password
const handleResetPassword = async (token, newPassword) => {
  await axios.post(`${API}/auth/reset-password`, {
    token,
    new_password: newPassword
  });
  
  navigate('/auth');
  toast.success('Password reset successful!');
};
```

### Backend: `GET /api/auth/verify-reset-token/{token}`

**Location**: `/app/backend/server.py` (line ~743)

**Purpose**: Verify token before showing reset form

**Response:**
```json
{
  "valid": true,
  "message": "Token is valid",
  "expires_in_minutes": 45
}
```

### Backend: `POST /api/auth/reset-password`

**Location**: `/app/backend/server.py` (line ~705)

**Request:**
```json
{
  "token": "reset-token-uuid",
  "new_password": "newSecurePassword123"
}
```

**Response:**
```json
{
  "message": "Password reset successful. Please log in with your new password.",
  "success": true
}
```

**Process:**

1. **Validate token**:
   - Check token exists and not used
   - Check not expired
2. **Validate password**:
   - Minimum 6 characters
   - Confirm passwords match (frontend)
3. **Update password**:
   - Hash new password with bcrypt
   - Update user document
4. **Mark token as used**
5. **Invalidate all sessions** for security
6. **Send confirmation email**

**Security Measures:**
- Token can only be used once
- Token expires after 1 hour
- All existing sessions invalidated
- Password confirmation email sent

---

## Security Features

### Password Hashing

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash password
hashed = pwd_context.hash(plain_password)

# Verify password
is_valid = pwd_context.verify(plain_password, hashed_password)
```

### JWT Tokens

```python
from jose import jwt
import os
from datetime import datetime, timedelta

# Generate token
access_token = jwt.encode(
    {
        'sub': user_id,
        'exp': datetime.utcnow() + timedelta(days=7)
    },
    os.environ['JWT_SECRET'],
    algorithm='HS256'
)

# Verify token
payload = jwt.decode(token, os.environ['JWT_SECRET'], algorithms=['HS256'])
```

### Token Expiry

- **JWT tokens**: 7 days
- **Reset tokens**: 1 hour
- **Sessions**: Until logout

### Prevention Measures

1. **Email Enumeration Prevention**:
   - Always return success message for forgot password
   - Don't reveal if email exists

2. **Brute Force Protection**:
   - Consider adding rate limiting
   - Failed login attempts tracking (future)

3. **Session Security**:
   - All sessions invalidated on password reset
   - Token stored in localStorage
   - Authorization header on all requests

---

## Email Templates

### Authentication Template

**SendGrid Template ID**: `d-e0ee403fbd8646db8011339cf2eeac30`

**Email Types:**
1. Welcome Email
2. Email Verification
3. Password Reset
4. Password Changed

### Template Variables

#### Welcome Email
```json
{
  "first_name": "John",
  "full_name": "John Doe",
  "email": "john@example.com",
  "login_url": "https://bidvex.com/auth",
  "explore_url": "https://bidvex.com/marketplace",
  "account_type": "Personal"
}
```

#### Password Reset
```json
{
  "first_name": "John",
  "reset_url": "https://bidvex.com/reset-password?token={{token}}",
  "expires_in_hours": 1,
  "support_email": "support@bidvex.com"
}
```

#### Password Changed
```json
{
  "first_name": "John",
  "email": "john@example.com",
  "change_time": "2025-11-21 16:00 UTC",
  "support_email": "support@bidvex.com",
  "login_url": "https://bidvex.com/auth"
}
```

---

## Testing

### Manual Testing Checklist

#### Login Tests
- [ ] Valid credentials → Success
- [ ] Invalid email → Error message
- [ ] Invalid password → Error message
- [ ] Empty fields → Validation error
- [ ] Token stored in localStorage
- [ ] Redirect to marketplace

#### Registration Tests
- [ ] Valid data → Success + welcome email
- [ ] Duplicate email → Error
- [ ] Business account → Extra fields shown
- [ ] Token stored in localStorage
- [ ] Redirect to marketplace

#### Forgot Password Tests
- [ ] Valid email → Success message
- [ ] Invalid email → Same success message (security)
- [ ] Email received with reset link
- [ ] Link format correct
- [ ] Instructions clear

#### Reset Password Tests
- [ ] Valid token → Show form
- [ ] Expired token → Error message
- [ ] Used token → Error message
- [ ] Invalid token → Error message
- [ ] Password too short → Validation error
- [ ] Passwords don't match → Validation error
- [ ] Success → Confirmation email + redirect
- [ ] Old sessions invalidated

### Backend API Testing

#### Test Forgot Password
```bash
curl -X POST http://localhost:8001/api/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

**Expected**: 200 OK with success message

#### Test Verify Token
```bash
curl http://localhost:8001/api/auth/verify-reset-token/your-token-here
```

**Expected**: `{"valid": true, "message": "Token is valid", "expires_in_minutes": 45}`

#### Test Reset Password
```bash
curl -X POST http://localhost:8001/api/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token": "your-token-here",
    "new_password": "newPassword123"
  }'
```

**Expected**: 200 OK with success message

### Email Testing

Run the production template test:

```bash
cd /app/backend
python test_production_templates.py
```

Select your email and verify:
- Password reset email arrives
- Reset link is correct
- Password changed email arrives
- All variables render correctly

---

## Troubleshooting

### Issue: Forgot password email not sending

**Check:**
1. SendGrid API key configured in `.env`
2. Backend logs: `tail -f /var/log/supervisor/backend.out.log | grep email`
3. Email service status: `email_service.is_configured()`
4. Template ID correct: `d-e0ee403fbd8646db8011339cf2eeac30`

**Solution:**
```python
# Test email service
from services.email_service import get_email_service

email_service = get_email_service()
print(f"Configured: {email_service.is_configured()}")
```

### Issue: Reset token invalid

**Check:**
1. Token exists in database:
   ```bash
   mongosh bazario_db --eval "db.password_reset_tokens.find({token: 'your-token'}).pretty()"
   ```
2. Token not expired (check `expires_at`)
3. Token not already used (`used: false`)

**Solution:** Request new reset link

### Issue: Password reset not working

**Check:**
1. New password meets requirements (6+ characters)
2. Token valid and not expired
3. Backend logs for errors
4. Database connection working

### Issue: Sessions not invalidated

**Check:**
1. `db.sessions.delete_many({"user_id": user_id})` executed
2. MongoDB connection working
3. User logged out and needs to login again

---

## Database Collections

### users
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "password": "bcrypt-hashed-password",
  "name": "John Doe",
  "account_type": "personal",
  "preferred_language": "en",
  "created_at": "2025-11-21T16:00:00Z",
  ...
}
```

### password_reset_tokens
```json
{
  "id": "uuid",
  "user_id": "user-uuid",
  "token": "reset-token-uuid",
  "expires_at": "2025-11-21T17:00:00Z",
  "used": false,
  "created_at": "2025-11-21T16:00:00Z"
}
```

### sessions
```json
{
  "user_id": "user-uuid",
  "session_token": "jwt-token",
  "created_at": "2025-11-21T16:00:00Z"
}
```

---

## Integration Examples

### Add Forgot Password to Custom Page

```javascript
import { Link } from 'react-router-dom';

// In your login form
<Link 
  to="/forgot-password" 
  className="text-sm text-primary hover:underline"
>
  Forgot password?
</Link>
```

### Programmatic Password Reset

```javascript
// Send reset email
const sendResetEmail = async (email) => {
  await axios.post('/api/auth/forgot-password', { email });
};

// Reset password
const resetPassword = async (token, newPassword) => {
  await axios.post('/api/auth/reset-password', {
    token,
    new_password: newPassword
  });
};
```

### Check if User is Authenticated

```javascript
import { useAuth } from '../contexts/AuthContext';

const MyComponent = () => {
  const { user, loading } = useAuth();
  
  if (loading) return <LoadingSpinner />;
  if (!user) return <Redirect to="/auth" />;
  
  return <div>Welcome {user.name}!</div>;
};
```

---

## Best Practices

### Frontend
1. ✅ Always validate form inputs
2. ✅ Show loading states during API calls
3. ✅ Display user-friendly error messages
4. ✅ Use ARIA labels for accessibility
5. ✅ Test keyboard navigation
6. ✅ Responsive design for mobile
7. ✅ Clear call-to-actions

### Backend
1. ✅ Hash passwords with bcrypt
2. ✅ Use secure random tokens (UUID)
3. ✅ Set token expiry times
4. ✅ Log all authentication events
5. ✅ Prevent email enumeration
6. ✅ Validate all inputs
7. ✅ Use HTTPS in production

### Security
1. ✅ Never log passwords
2. ✅ Rate limit auth endpoints
3. ✅ Use secure JWT secrets
4. ✅ Invalidate sessions on password change
5. ✅ Send confirmation emails
6. ✅ Use HTTPS for reset links
7. ✅ Clear expired tokens regularly

---

## Support

**Backend Code**: `/app/backend/server.py`  
**Frontend Pages**: 
- `/app/frontend/src/pages/AuthPage.js`
- `/app/frontend/src/pages/ForgotPasswordPage.js`
- `/app/frontend/src/pages/ResetPasswordPage.js`

**Email Templates**: `/app/backend/config/email_templates.py`  
**Email Service**: `/app/backend/services/email_service.py`

**Database**: MongoDB `bazario_db`  
**Collections**: `users`, `password_reset_tokens`, `sessions`

---

**Last Updated**: November 21, 2025  
**Version**: 1.0.0  
**Status**: Production Ready ✅
