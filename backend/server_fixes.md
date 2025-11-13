# Backend Fixes for BidVex Issues

## Issue 1: Multi-Lot Auction Visibility
**Problem**: GET /api/multi-item-listings defaults to status='active' only, excluding 'upcoming' auctions
**Fix**: Return both active and upcoming listings by default, or make it more flexible

## Issue 2: Filters Not Working
**Problem**: GET /api/multi-item-listings doesn't accept filter parameters (category, region, currency, search)
**Fix**: Add query parameters for filtering

## Issue 3: Bid Type Validation Error
**Problem**: Function signature says Dict[str, float] but bid_type should be string
**Fix**: Change type hint to allow Any or create proper model
