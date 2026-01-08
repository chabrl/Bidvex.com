# BidVex Test Results

## Test Session: Auction Scheduling & Seller Obligations

### Test Objectives
1. Test "Visit Before Auction" date-only picker with validation
2. Test Seller Obligations consolidated block
3. Verify UI visibility in both light/dark modes

### Test Credentials
- Admin: charbel@admin.bazario.com / Admin123!
- Test User: pioneer@bidvextest.com / test123

### Pages to Test
1. `/create-multi-item-listing` - Step 4 contains the new features
2. Need to fill Steps 1-3 to reach Step 4

### New Features Implemented
1. Visit Before Auction - Date-only picker with:
   - Calendar date input (no time selector)
   - Validation: inspection date must be BEFORE auction end date
   - Error message when invalid date selected
   - Grayed out dates after auction end date (via max attribute)

2. Consolidated Seller Agreement Block with:
   - Currency Exchange display (1 USD = 1.42 CAD)
   - Logistics dropdown (Yes/No) with details textarea
   - Removal Deadline dropdown (3-30 days) + custom field
   - Site Capabilities (address, tailgate access, forklift checkboxes)
   - Refund Policy radio buttons (Non-Refundable / Refundable)
   - Seller Commitment checkbox (required before submission)

### Incorporate User Feedback
- None yet
