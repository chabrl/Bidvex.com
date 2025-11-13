# BidVex Production Deployment Guide

## ✅ Pre-Launch Checklist Completed

### Implemented Features:
- [x] Custom 404 Error Page
- [x] Privacy Policy Page
- [x] Terms of Service Page
- [x] Legal page links in footer
- [x] SEO meta tags (title, description, Open Graph, Twitter cards)
- [x] Favicon and app icons
- [x] Responsive design
- [x] Bilingual support (EN/FR)

---

## 🔴 CRITICAL - Manual Configuration Required

### 1. Stripe Live Mode Configuration

**Current Status:** Using TEST keys (`sk_test_emergent`)

**Action Required:**
1. Log into Stripe Dashboard (https://dashboard.stripe.com)
2. Switch to **Live Mode** (toggle in top right)
3. Navigate to: Developers → API Keys
4. Copy the **Live Secret Key** (starts with `sk_live_...`)
5. Update `/app/backend/.env`:
   ```bash
   STRIPE_API_KEY=sk_live_YOUR_ACTUAL_KEY_HERE
   ```
6. Restart backend: `sudo supervisorctl restart backend`

**Testing Live Payments:**
- Use real card: 4242 4242 4242 4242 (test mode)
- Production: Use actual payment cards
- Test scenarios:
  - [ ] Successful payment
  - [ ] Declined card
  - [ ] Insufficient funds
  - [ ] International cards

**Webhooks Setup:**
1. In Stripe Dashboard → Webhooks
2. Add endpoint: `https://yourdomain.com/api/webhooks/stripe`
3. Select events: `payment_intent.succeeded`, `payment_intent.payment_failed`
4. Copy webhook secret
5. Add to `.env`: `STRIPE_WEBHOOK_SECRET=whsec_...`

---

### 2. Email Service Configuration

**Current Status:** NOT CONFIGURED

**Recommended Service:** SendGrid (free tier: 100 emails/day)

**Setup Steps:**

1. **Create SendGrid Account:**
   - Sign up at https://sendgrid.com
   - Verify your domain or sender email
   - Generate API key

2. **Install SendGrid SDK:**
   ```bash
   cd /app/backend
   pip install sendgrid
   echo "sendgrid==6.10.0" >> requirements.txt
   ```

3. **Add to `.env`:**
   ```bash
   SENDGRID_API_KEY=SG.your_actual_key_here
   SENDGRID_FROM_EMAIL=noreply@bidvex.com
   SENDGRID_FROM_NAME=BidVex Auctions
   ```

4. **Email Templates Needed:**
   - Welcome email (user registration)
   - Bid confirmation
   - Outbid notification
   - Auction won
   - Invoice/receipt
   - Password reset
   - Seller notifications

**Alternative Email Services:**
- Mailgun (10,000 emails/month free)
- AWS SES (very affordable)
- Postmark (100 emails/month free)

---

### 3. Password Reset Functionality

**Current Status:** NOT IMPLEMENTED

**Implementation Required:**

**Backend Endpoints:**
```python
# Add to server.py

@api_router.post("/auth/forgot-password")
async def forgot_password(email: str):
    # 1. Find user by email
    # 2. Generate reset token (JWT with 1-hour expiry)
    # 3. Send email with reset link
    # 4. Return success message
    pass

@api_router.post("/auth/reset-password")
async def reset_password(token: str, new_password: str):
    # 1. Verify token validity
    # 2. Hash new password
    # 3. Update user password
    # 4. Invalidate token
    pass
```

**Frontend Components:**
- ForgotPasswordPage.js
- ResetPasswordPage.js
- Email link format: `https://bidvex.com/reset-password?token=...`

---

### 4. Domain & SSL Configuration

**DNS Setup:**
1. Point domain to server IP:
   ```
   A Record: @ → SERVER_IP
   A Record: www → SERVER_IP
   ```
2. Wait for DNS propagation (up to 48 hours)

**SSL Certificate (Let's Encrypt):**
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d bidvex.com -d www.bidvex.com

# Auto-renewal (already configured)
sudo systemctl status certbot.timer
```

---

### 5. Environment Variables for Production

**Create `/app/backend/.env.production`:**
```bash
# Database
MONGO_URL=mongodb://localhost:27017/bidvex_production

# JWT
JWT_SECRET=YOUR_SUPER_SECURE_RANDOM_STRING_HERE_MIN_32_CHARS

# Stripe
STRIPE_API_KEY=sk_live_YOUR_KEY
STRIPE_WEBHOOK_SECRET=whsec_YOUR_SECRET

# Email
SENDGRID_API_KEY=SG.YOUR_KEY
SENDGRID_FROM_EMAIL=noreply@bidvex.com

# Application
ENVIRONMENT=production
DEBUG=false
FRONTEND_URL=https://bidvex.com
BACKEND_URL=https://bidvex.com/api
```

---

## 📋 Pre-Launch Testing Checklist

### Functional Testing:
- [ ] User registration works
- [ ] Login/logout works across devices
- [ ] Bid placement successful
- [ ] Payment processing (with live keys)
- [ ] Invoice generation
- [ ] Email notifications sent
- [ ] Search and filters work
- [ ] Mobile responsive
- [ ] 404 page displays correctly
- [ ] Legal pages accessible

### Security Testing:
- [ ] HTTPS enforced
- [ ] SQL injection tested
- [ ] XSS prevention verified
- [ ] CSRF tokens implemented
- [ ] Rate limiting active
- [ ] Password hashing (bcrypt)
- [ ] Sensitive data not exposed

### Performance Testing:
- [ ] Page load time < 3 seconds
- [ ] API response time < 500ms
- [ ] Database queries optimized
- [ ] Images compressed
- [ ] CDN configured (if applicable)

### Browser/Device Testing:
- [ ] Chrome (desktop & mobile)
- [ ] Firefox
- [ ] Safari (iOS & macOS)
- [ ] Edge
- [ ] Tablet responsiveness

---

## 🚀 Deployment Steps

### 1. Final Code Review
```bash
# Pull latest code
git pull origin main

# Install dependencies
cd /app/frontend && yarn install
cd /app/backend && pip install -r requirements.txt
```

### 2. Build Frontend
```bash
cd /app/frontend
yarn build
# Serve build directory with nginx or static server
```

### 3. Configure Production Environment
```bash
# Copy production env
cp .env.production .env

# Update environment variables
nano .env
```

### 4. Database Backup
```bash
# Backup MongoDB before launch
mongodump --db bidvex --out /backup/pre-launch-$(date +%Y%m%d)
```

### 5. Start Services
```bash
sudo supervisorctl restart all
sudo systemctl restart nginx
```

### 6. Verify Deployment
- Check https://bidvex.com loads
- Test critical user flows
- Monitor logs: `tail -f /var/log/supervisor/backend.err.log`

---

## 📊 Monitoring & Maintenance

### Log Monitoring:
```bash
# Backend logs
tail -f /var/log/supervisor/backend.err.log

# Frontend logs
tail -f /var/log/supervisor/frontend.err.log

# MongoDB logs
tail -f /var/log/mongodb/mongod.log

# Nginx logs
tail -f /var/log/nginx/error.log
```

### Database Backups:
```bash
# Setup daily backups (cron job)
0 2 * * * mongodump --db bidvex --out /backup/daily-$(date +%Y%m%d)
```

### Security Updates:
```bash
# Weekly security updates
sudo apt update && sudo apt upgrade -y
```

---

## 🆘 Rollback Plan

If production deployment fails:

1. **Revert to previous version:**
   ```bash
   git checkout <previous-commit-hash>
   sudo supervisorctl restart all
   ```

2. **Restore database backup:**
   ```bash
   mongorestore --db bidvex /backup/pre-launch-YYYYMMDD/bidvex
   ```

3. **Check logs for errors:**
   ```bash
   sudo supervisorctl tail -f backend stderr
   ```

---

## 📞 Support Contacts

**Technical Issues:**
- Email: dev@bidvex.com
- Phone: [To be added]

**Legal/Compliance:**
- Email: legal@bidvex.com

**Hosting Provider:**
- Support portal: [To be added]

---

## ✅ Post-Launch Monitoring (First 48 Hours)

### Critical Metrics to Watch:
- [ ] Server uptime
- [ ] Payment success rate
- [ ] Email delivery rate
- [ ] Error rates
- [ ] User registration rate
- [ ] Bid placement rate

### Action Items:
- Monitor logs continuously
- Respond to user feedback immediately
- Fix critical bugs within 2 hours
- Document all issues and resolutions

---

## 📝 Legal Compliance

**Privacy Policy & Terms:**
- [x] Pages created
- [ ] **MUST BE REVIEWED BY LEGAL COUNSEL**
- [ ] Update with actual business address
- [ ] Add GDPR compliance (if serving EU users)
- [ ] Add CCPA compliance (if serving California users)

**Required Disclosures:**
- Business registration number
- Physical address
- Contact information
- Dispute resolution process

---

## 🎉 Launch Day Checklist

**Morning of Launch:**
- [ ] Verify all services running
- [ ] Test critical user flows
- [ ] Confirm Stripe live keys active
- [ ] Test email sending
- [ ] Check SSL certificate valid
- [ ] Monitor server load

**During Launch:**
- [ ] Monitor logs in real-time
- [ ] Be ready to respond to issues
- [ ] Track user registrations
- [ ] Monitor payment processing

**End of Day:**
- [ ] Review all metrics
- [ ] Document any issues encountered
- [ ] Plan fixes for tomorrow
- [ ] Celebrate! 🎊

---

## 📈 Future Enhancements (Post-Launch)

- [ ] Google Analytics integration
- [ ] Email verification for new users
- [ ] Two-factor authentication (2FA)
- [ ] Advanced admin moderation tools
- [ ] Mobile app (React Native)
- [ ] API rate limiting per user
- [ ] Advanced fraud detection
- [ ] Automated auction management
- [ ] Bulk listing tools
- [ ] Seller analytics dashboard

---

**Document Version:** 1.0
**Last Updated:** {current_date}
**Next Review:** After 30 days of production operation
