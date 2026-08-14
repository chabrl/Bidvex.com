/**
 * BidVex — Reusable Meta + Google (GA4/Ads) commerce tracking hook.
 *
 * Encapsulates the 3 funnel events that drive Meta Commerce Manager match
 * rate + Google Merchant Center attribution + Advantage+ optimization,
 * with payloads that match EXACTLY what
 * `backend/services/meta_feed_mapper.py` writes to the catalog feed:
 *
 *   trackViewContent({ listing, lot? })
 *   trackAddToCart({ listing, lot?, bidAmount })
 *   trackBidSubmitted({ listing, lot?, bidAmount, lotNumber? })
 *   trackPurchase({ listingId, listingType, finalWinningPrice, stripeSessionId })
 *
 * P7.5 — the hook now emits BOTH:
 *   • Meta Pixel:  ViewContent / AddToCart / InitiateCheckout / Purchase
 *   • Google GA4:  view_item / add_to_cart / purchase
 * with the SAME canonical content ID so Meta Commerce Manager AND
 * Google Merchant Center resolve to the same catalog row.
 *
 * When `lot` is supplied, both pipelines use the per-lot canonical ID
 * (`LOT-<parent>-L<lot_number>` or `VML-<parent>-<lot_id[:8]>`) so the
 * multi-lot catalog decomposition matches.
 *
 * Why a hook? Because page-level call-sites tend to drift (someone forgets
 * to pass `currency`, or wires the wrong price field). This hook is the
 * single supported entry point.
 */
import { useMemo } from 'react';
import {
  trackViewContent  as _viewContent,
  trackAddToCart    as _addToCart,
  trackInitiateCheckout as _initiateCheckout,
  trackPurchase     as _purchase,
  trackAddToWishlist as _wishlist,
  buildEventId,
} from '../utils/metaPixel';
import {
  getCanonicalContentId,
  getLotContentId,
} from '../utils/metaContentId';
import {
  trackGA4ViewItem,
  trackGA4AddToCart,
  trackGA4Purchase,
  trackGoogleAdsPurchase,
  setEnhancedConversionsUserData,
} from '../utils/analytics_events';

const _extractPrice = (listing, lot) => {
  if (lot) {
    return Number(lot.current_price ?? lot.current_bid ?? lot.starting_price ?? 0) || 0;
  }
  if (!listing) return 0;
  const candidates = [
    listing.current_bid,
    listing.current_price,
    listing.starting_bid,
    listing.starting_price,
  ];
  for (const v of candidates) {
    if (typeof v === 'number' && v > 0) return v;
  }
  return 0;
};

export function useMetaPixelTracking({ routeHint } = {}) {
  return useMemo(() => ({
    /**
     * ViewContent + view_item — auction / lot detail page mount.
     * When `lot` is passed, both pipelines resolve to the per-lot
     * canonical ID so multi-lot catalog rows attribute correctly.
     */
    trackViewContent: ({ listing, lot } = {}) => {
      if (!listing) return;
      _viewContent(listing, { routeHint, lot });
      const contentId = lot
        ? getLotContentId(listing, lot, { routeHint })
        : getCanonicalContentId(listing);
      if (contentId) {
        trackGA4ViewItem({
          contentId,
          value: _extractPrice(listing, lot),
          itemName: (lot && (lot.title || lot.title_en)) || listing.title || '',
          itemCategory: listing.category || '',
          currency: listing.currency || 'CAD',
        });
      }
    },

    /**
     * AddToCart + add_to_cart — fires on "Place a Bid" intent OR
     * "Add to Watchlist". One dedupe per (listing, session) so a
     * bidding-war user doesn't trigger 12 AddToCart events.
     */
    trackAddToCart: ({ listing, lot, bidAmount } = {}) => {
      if (!listing) return;
      _addToCart({ listing, lot, bidAmount, routeHint });
      const contentId = lot
        ? getLotContentId(listing, lot, { routeHint })
        : getCanonicalContentId(listing);
      if (contentId) {
        trackGA4AddToCart({
          contentId,
          value: Number(bidAmount || _extractPrice(listing, lot) || 0),
          itemName: (lot && (lot.title || lot.title_en)) || listing.title || '',
          itemCategory: listing.category || '',
          currency: listing.currency || 'CAD',
        });
      }
    },

    /**
     * InitiateCheckout — fires on EVERY successful bid commit. NOT dedupe-
     * protected; each new bid in a bidding war strengthens Meta's signal.
     * Use this in your bid-submit success branch. Note: GA4 does NOT get
     * a matching event; GA4 reserves `add_to_cart` for intent and
     * `purchase` for completion — repeated bids are not commerce events.
     */
    trackBidSubmitted: ({ listing, lot, bidAmount, lotNumber } = {}) => {
      if (!listing) return;
      _initiateCheckout({ listing, lot, bidAmount, lotNumber, routeHint });
    },

    /**
     * AddToWishlist — fires on watchlist add (NOT to be confused with the
     * AddToCart event). Standard Meta event used by some Advantage+
     * audience-builder algorithms.
     */
    trackWatchlistAdd: ({ listing, lot } = {}) => {
      if (!listing) return;
      _wishlist(listing, listing?.current_bid, { routeHint, lot });
    },

    /**
     * Purchase + purchase — fires once per (listing, session) on payment
     * confirmation. The `stripeSessionId` is folded into the event_id so
     * the backend Conversions API can fire the same event_id and Meta
     * will deduplicate. GA4 `purchase` uses the Stripe session as
     * `transaction_id` so GA4 dedupes replays.
     *
     * Enhanced Conversions user_data (SHA-256 email/phone) is emitted
     * BEFORE the purchase event when `identity` is supplied.
     */
    trackPurchase: async ({
      listingId,
      listingType,
      finalWinningPrice,
      stripeSessionId,
      title,
      category,
      identity,
      lotContentId,
    } = {}) => {
      if (!listingId) return;
      const eventId = stripeSessionId
        ? buildEventId({
            eventName: 'Purchase',
            contentId: lotContentId || listingId,
            discriminator: stripeSessionId,
          })
        : null;
      _purchase({
        listingId: lotContentId || listingId,
        listingType: listingType || routeHint,
        totalCharged: finalWinningPrice,
        eventId,
        title,
        category,
      });
      // Enhanced Conversions user_data must precede the conversion event
      // in the same event batch. Fire-and-forget; failure never blocks.
      try {
        if (identity && (identity.email || identity.phone)) {
          await setEnhancedConversionsUserData(identity);
        }
      } catch (e) {
        // Silent — user_data is optional
      }
      if (stripeSessionId) {
        trackGA4Purchase({
          contentId: lotContentId || listingId,
          value: finalWinningPrice,
          transactionId: stripeSessionId,
          itemName: title || '',
          itemCategory: category || '',
          currency: 'CAD',
        });
        trackGoogleAdsPurchase({
          value: finalWinningPrice,
          transactionId: stripeSessionId,
          currency: 'CAD',
        });
      }
    },
  }), [routeHint]);
}

export default useMetaPixelTracking;
