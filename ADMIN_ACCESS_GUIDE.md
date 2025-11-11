# 🛡️ BidVex Admin Panel Access Guide

## ✅ Admin User Created Successfully!

Your test admin account has been created and is ready to use.

---

## 🔑 Admin Login Credentials

```
Email:    admin@admin.bazario.com
Password: Admin123!
URL:      https://bidvex-auctions.preview.emergentagent.com
```

---

## 📍 How to Access the Admin Panel

### Step 1: Login
1. Go to: `https://bidvex-auctions.preview.emergentagent.com/auth`
2. Enter credentials:
   - Email: `admin@admin.bazario.com`
   - Password: `Admin123!`
3. Click "Login"

### Step 2: Access Admin Dashboard
After login, you have **3 ways** to access the admin panel:

**Option 1: User Menu (NEW!)**
- Click on your profile icon (top right)
- You'll see a new menu item: **"🛡️ Admin Panel"** in blue
- Click it to go directly to admin dashboard

**Option 2: Direct URL**
- Navigate to: `https://bidvex-auctions.preview.emergentagent.com/admin`

**Option 3: From any dashboard**
- The admin button appears in the user dropdown menu

---

## 🎛️ Admin Panel Features

### Main Dashboard
The admin dashboard has 6 main sections:

1. **👥 Users** - User management and roles
2. **📦 Lots** - Lot moderation and approval
3. **🔨 Auctions** - Auction control and management
4. **🛡️ Trust & Safety** - Security and fraud prevention
5. **📊 Analytics** - Platform statistics and insights
6. **⚙️ Settings** - System configuration

### Settings Sub-Tabs
Under the Settings tab, you'll find:

1. **Categories** - Manage auction categories
2. **Promotions** - Create promotional campaigns
3. **Affiliates** - Manage affiliate program
4. **💱 Currency Appeals** ⭐ **NEW!**
5. **Reports** - View user reports
6. **Messages** - Message oversight
7. **Announcements** - Platform announcements
8. **Logs** - System audit logs

---

## 💱 How to Review Currency Appeals

### Accessing Currency Appeals

1. Login as admin
2. Go to Admin Dashboard
3. Click on **"Settings"** tab
4. Click on **"💱 Currency Appeals"** sub-tab

### Appeal Review Interface

Each appeal shows:

**Appeal Information:**
- User ID (first 8 characters)
- Status badge: 🟡 PENDING / 🟢 APPROVED / 🔴 REJECTED
- Requested currency: 🇨🇦 CAD or 🇺🇸 USD
- Submission date

**Appeal Details:**
- 📝 Reason: User's explanation for currency change
- 📍 Current Location: User's claimed location
- 📎 Proof Documents: Uploaded supporting documents (if any)

**Review Actions:**
For pending appeals, you can:

1. **Add Admin Notes** (optional but recommended)
   - Click in the "Admin Notes" field
   - Type your reasoning for the decision
   
2. **Approve the Appeal**
   - Click the green "Approve Appeal" button
   - This will:
     * Change user's currency to requested currency
     * Unlock their currency (allow manual changes)
     * Update appeal status to APPROVED
   
3. **Reject the Appeal**
   - Click the red "Reject Appeal" button
   - This will:
     * Keep user's current enforced currency
     * Keep currency locked
     * Update appeal status to REJECTED

### Appeal Statistics

The dashboard shows:
- 🟡 Pending: Number of appeals awaiting review
- 🟢 Approved: Number of approved appeals
- 🔴 Rejected: Number of rejected appeals

---

## 🎯 Currency Enforcement System Overview

### How It Works

1. **User Registration**
   - IP geolocation detects user's country
   - System assigns currency: 🇨🇦 Canada → CAD, 🇺🇸 USA → USD
   - If confidence is high (≥70%) → Currency locked

2. **Currency Lock**
   - User cannot change currency in profile settings
   - Auction creation pre-fills enforced currency
   - System shows 🔒 badge and compliance message

3. **Appeal Process**
   - User sees "Request Currency Change" button
   - Submits appeal with reason and proof
   - Admin reviews and approves/rejects
   - If approved → Currency unlocked

### When to Approve Appeals

**✅ Good reasons to approve:**
- User relocated to different country (with proof)
- User traveling temporarily
- VPN/proxy false positive
- Business operating in multiple countries
- Legitimate documentation provided

**❌ Reasons to reject:**
- No valid explanation
- Attempting to avoid taxes
- Suspicious activity
- Insufficient proof
- Contradictory information

---

## 🔍 Testing Currency Appeals

### Create a Test Appeal (as regular user)

1. Register a new user (non-admin email)
2. Check if currency is locked in profile
3. Click "Request Currency Change" button
4. Fill out appeal form:
   - Requested Currency: USD or CAD
   - Reason: "Testing appeal system"
   - Current Location: "Montreal, QC"
5. Submit appeal

### Review as Admin

1. Login as admin@admin.bazario.com
2. Go to Admin → Settings → Currency Appeals
3. Find your test appeal (should be PENDING)
4. Add admin notes: "Test approval"
5. Click "Approve Appeal"
6. Verify appeal status changes to APPROVED

### Verify Results

1. Logout from admin
2. Login as the user who submitted appeal
3. Go to Profile Settings
4. Check that currency selector is now unlocked
5. Currency should be changed to requested currency

---

## 🚨 Troubleshooting

### Can't see Admin Panel menu item?

Check if your user has admin privileges:

```bash
mongosh mongodb://localhost:27017/bazario

db.users.findOne({email: "your-email@example.com"})
```

Look for:
- `email` ending with `@admin.bazario.com`, OR
- `account_type: "admin"`, OR
- `role: "admin"` or `"superadmin"`

### Update user to admin:

```bash
db.users.updateOne(
  {email: "your-email@example.com"},
  {$set: {
    account_type: "admin",
    role: "admin",
    email: "admin@admin.bazario.com"
  }}
)
```

### Currency Appeals not loading?

1. Check backend is running: `curl http://localhost:8001/api/health`
2. Check browser console for errors (F12)
3. Verify you're logged in as admin
4. Try refreshing the page

### Can't approve/reject appeals?

1. Verify you're using admin@admin.bazario.com email
2. Check backend logs: `tail -f /var/log/supervisor/backend.out.log`
3. Ensure appeal ID is valid
4. Try adding admin notes before reviewing

---

## 📊 Additional Admin Features

### User Management
- View all registered users
- Update user roles and permissions
- Ban/suspend users
- View user activity logs

### Auction Control
- End auctions early
- Extend auction deadlines
- Cancel auctions
- Manage auction status

### Trust & Safety
- Review reported content
- Monitor suspicious activity
- Manage security settings
- View fraud detection logs

### Analytics
- Platform revenue statistics
- User growth metrics
- Auction performance
- Category popularity

---

## 🔐 Security Best Practices

1. **Keep admin credentials secure**
   - Don't share admin password
   - Use strong, unique passwords
   - Enable 2FA (when implemented)

2. **Review appeals thoroughly**
   - Check all provided documentation
   - Look for suspicious patterns
   - Document your reasoning in admin notes

3. **Monitor admin logs**
   - Regularly check Admin Logs tab
   - Review all administrative actions
   - Report any unauthorized access

4. **Use admin email pattern**
   - Admin emails should end with @admin.bazario.com
   - Regular users cannot have this domain
   - Helps prevent privilege escalation

---

## 💡 Tips for Efficient Appeal Review

1. **Batch Processing**
   - Review multiple appeals at once
   - Sort by submission date
   - Focus on oldest pending appeals first

2. **Quick Decisions**
   - Clear documentation = Quick approval
   - No documentation = Request more info
   - Suspicious activity = Reject

3. **Communication**
   - Use admin notes to document reasoning
   - Helps with audit trails
   - Useful for future reference

4. **Follow-up**
   - Check if approved users created auctions
   - Monitor for abuse of unlocked currency
   - Review rejection patterns

---

## 📞 Support

If you encounter any issues or have questions:

1. Check this guide first
2. Review backend logs for errors
3. Test with different browsers
4. Clear browser cache if UI issues
5. Restart backend/frontend if needed

---

## ✅ Quick Start Checklist

- [x] Admin user created: admin@admin.bazario.com
- [x] Admin panel accessible via user menu
- [x] Currency Appeals tab added to Settings
- [x] Appeal review interface implemented
- [x] Statistics dashboard included
- [x] Test credentials provided

**You're all set to manage currency appeals! 🎉**

---

**Last Updated:** 2025-01-21
**Version:** 1.0.0
**System:** BidVex Currency Enforcement
