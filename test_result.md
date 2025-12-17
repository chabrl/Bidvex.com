# Test Result Documentation

## Current Focus
- Anti-sniping (2-minute rule) implementation
- Production hardening tasks
- Items marketplace integration

## Testing Required

### 1. Anti-Sniping Logic (2-Minute Rule)
- Test bid placed within final 2 minutes extends auction by 2 minutes
- Test T_new = Time of Bid + 120 seconds
- Test unlimited extensions (repeat as needed)
- Test WebSocket broadcasts new end time to all clients
- Test countdown timer "jumps" back on extension

### 2. Cascading Impact (Independent Extensions)
- Verify Item 1 extension does NOT affect Item 2/3 end times
- Each lot maintains independent end time

### 3. Error Handling
- Test bid rejection shows helpful message: "Your bid must be at least $X.XX to lead"
- Test auction ended message
- Test cannot bid on own listing

### 4. Items Marketplace
- Test /items route shows DecomposedMarketplace
- Test "Browse Items" nav link works
- Test "Explore Items" button on homepage works
- Test promoted items shown first

## Backend Testing Tasks
1. POST /api/bids with bid in final 2 minutes triggers extension
2. Response includes extension_applied: true and new_auction_end
3. WebSocket BID_UPDATE includes time_extended and new_auction_end
4. GET /api/marketplace/items returns items

## Frontend Testing Tasks
1. Homepage shows "Browse Individual Items" section
2. Navbar shows "Browse Items" link
3. /items page loads ItemsMarketplacePage
4. Countdown timer updates when extension received

## Test Credentials
- Bidder: bidtest@example.com / TestPassword123!
- Seller: seller.wstest@example.com / TestPassword123!

## Incorporate User Feedback
- Anti-sniping window: 2 minutes (120 seconds)
- Extension formula: T_new = Time of Bid + 120 seconds
- Unlimited extensions allowed
- Cascading extensions are INDEPENDENT per item
