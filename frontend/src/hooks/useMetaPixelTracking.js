/**
 * BidVex — Reusable Meta Pixel tracking hook for auction pages.
 *
 * Encapsulates the 3 funnel events that drive Meta Commerce Manager match
 * rate + Advantage+ optimization, with payloads that match EXACTLY what
 * `backend/services/meta_feed_mapper.py` writes to the catalog feed:
 *
 *   trackViewContent({ listing })
 *   trackAddToCart({ listing, bidAmount })         ← bid intent / watchlist
 *   trackPurchase({ listing, finalWinningPrice, stripeSessionId })
 *
 * Why a hook? Because page-level call-sites tend to drift (someone forgets
 * to pass `currency`, or wires the wrong price field). This hook is the
 * single supported entry point; if you change the schema, change it here.
 *
 * Usage on a vehicle / lot / storage / marketplace detail page:
 *
 *   const { trackViewContent, trackAddToCart, trackPurchase } =
 *     useMetaPixelTracking({ routeHint: 'vehicle' });
 *
 *   useEffect(() => { if (listing) trackViewContent({ listing }); }, [listing]);
 *
 *   const handlePlaceBid = (amount) => {
 *     trackAddToCart({ listing, bidAmount: amount });
 *     // ... existing bid submit logic
 *   };
 *
 *   const handleWatchlistAdd = () => {
 *     trackAddToCart({ listing, bidAmount: listing.current_bid });
 *   };
 *
 *   // on Stripe webhook redirect / payment success page:
 *   trackPurchase({
 *     listingId: listing.id,
 *     listingType: 'vehicle',
 *     finalWinningPrice: invoice.total_cad,
 *     stripeSessionId: invoice.stripe_session_id,
 *   });
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

export function useMetaPixelTracking({ routeHint } = {}) {
  return useMemo(() => ({
    /**
     * ViewContent — auction / lot detail page mount.
     * Payload:  content_ids:[listing.id], content_type:'product'|'vehicle',
     *           value: current_bid, currency:'CAD'
     */
    trackViewContent: ({ listing } = {}) => {
      if (!listing) return;
      _viewContent(listing, { routeHint });
    },

    /**
     * AddToCart — fires on "Place a Bid" intent OR "Add to Watchlist".
     * One dedupe per (listing, session) so a bidding-war user doesn't
     * trigger 12 AddToCart events.
     */
    trackAddToCart: ({ listing, bidAmount } = {}) => {
      if (!listing) return;
      _addToCart({ listing, bidAmount, routeHint });
    },

    /**
     * InitiateCheckout — fires on EVERY successful bid commit. NOT dedupe-
     * protected; each new bid in a bidding war strengthens Meta's signal.
     * Use this in your bid-submit success branch.
     */
    trackBidSubmitted: ({ listing, bidAmount, lotNumber } = {}) => {
      if (!listing) return;
      _initiateCheckout({ listing, bidAmount, lotNumber, routeHint });
    },

    /**
     * AddToWishlist — fires on watchlist add (NOT to be confused with the
     * AddToCart event). Standard Meta event used by some Advantage+
     * audience-builder algorithms.
     */
    trackWatchlistAdd: ({ listing } = {}) => {
      if (!listing) return;
      _wishlist(listing, listing?.current_bid, { routeHint });
    },

    /**
     * Purchase — fires once per (listing, session) on payment confirmation.
     * The `stripeSessionId` is folded into the event_id so the backend
     * Conversions API can fire the same event_id and Meta will deduplicate.
     */
    trackPurchase: ({ listingId, listingType, finalWinningPrice, stripeSessionId, title, category } = {}) => {
      if (!listingId) return;
      const eventId = stripeSessionId
        ? buildEventId({ eventName: 'Purchase', contentId: listingId, discriminator: stripeSessionId })
        : null;
      _purchase({
        listingId,
        listingType: listingType || routeHint,
        totalCharged: finalWinningPrice,
        eventId,
        title,
        category,
      });
    },
  }), [routeHint]);
}

export default useMetaPixelTracking;
