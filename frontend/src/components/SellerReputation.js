import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Star, Award, Trophy, ShieldCheck } from 'lucide-react';

const API = `${API_BASE}/api`;

const badgeConfig = {
  top_rated: {
    label: 'Top Rated',
    icon: Trophy,
    className: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 border-amber-300',
  },
  trusted_seller: {
    label: 'Trusted Seller',
    icon: ShieldCheck,
    className: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 border-blue-300',
  },
  new_seller: {
    label: 'New Seller',
    icon: Award,
    className: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 border-slate-300',
  },
};

/**
 * Compact reputation display for listing cards.
 * Shows: star icon + average rating + review count (3+ reviews)
 * Shows: "New Seller" label (< 3 reviews)
 * Accepts optional pre-fetched `reputation` prop to avoid N+1 requests.
 */
export const SellerRatingInline = ({ sellerId, reputation }) => {
  const [rep, setRep] = useState(reputation || null);

  useEffect(() => {
    if (reputation) { setRep(reputation); return; }
    if (!sellerId) return;
    axios
      .get(`${API}/reviews/reputation/${sellerId}`)
      .then((res) => setRep(res.data))
      .catch(() => {});
  }, [sellerId, reputation]);

  if (!rep) return null;

  if (rep.total_reviews < 3) {
    return (
      <div className="flex items-center gap-1 text-xs" data-testid="seller-rating-inline-new">
        <Award className="h-3.5 w-3.5 text-slate-400" />
        <span className="text-slate-500 font-medium">New Seller</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1 text-xs" data-testid="seller-rating-inline">
      <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
      <span className="font-semibold">{rep.average_rating_display?.toFixed(1)}</span>
      <span className="text-slate-400">({rep.total_reviews})</span>
    </div>
  );
};

/**
 * Full reputation badge for seller profile / storefront.
 * Shows: badge + average + count + 5-star breakdown bars
 */
export const SellerReputationCard = ({ sellerId }) => {
  const [rep, setRep] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sellerId) return;
    setLoading(true);
    axios
      .get(`${API}/reviews/reputation/${sellerId}`)
      .then((res) => setRep(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [sellerId]);

  if (loading) return null;
  if (!rep) return null;

  const badge = badgeConfig[rep.badge] || badgeConfig.new_seller;
  const BadgeIcon = badge.icon;
  const total = rep.total_reviews;
  const breakdown = rep.rating_breakdown || {};
  const hasScore = rep.average_rating_display !== null && total >= 3;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border p-4 space-y-3" data-testid="seller-reputation-card">
      {/* Badge */}
      <div className="flex items-center justify-between">
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${badge.className}`}>
          <BadgeIcon className="h-3.5 w-3.5" />
          {badge.label}
        </div>
        <span className="text-xs text-slate-400">{total} review{total !== 1 ? 's' : ''}</span>
      </div>

      {/* Score */}
      {hasScore ? (
        <div className="flex items-center gap-3">
          <span className="text-3xl font-bold">{rep.average_rating_display.toFixed(1)}</span>
          <div>
            <div className="flex gap-0.5">
              {[1, 2, 3, 4, 5].map((s) => (
                <Star
                  key={s}
                  className={`h-4 w-4 ${
                    s <= Math.round(rep.average_rating_display)
                      ? 'fill-amber-400 text-amber-400'
                      : 'fill-slate-200 text-slate-200'
                  }`}
                />
              ))}
            </div>
            <p className="text-xs text-slate-500 mt-0.5">Based on {total} reviews</p>
          </div>
        </div>
      ) : (
        <p className="text-sm text-slate-500">
          {total > 0
            ? `${3 - total} more review${3 - total > 1 ? 's' : ''} needed to display rating`
            : 'No reviews yet'}
        </p>
      )}

      {/* Breakdown Bars */}
      {hasScore && (
        <div className="space-y-1.5">
          {[5, 4, 3, 2, 1].map((star) => {
            const count = breakdown[String(star)] || 0;
            const pct = total > 0 ? (count / total) * 100 : 0;
            return (
              <div key={star} className="flex items-center gap-2 text-xs">
                <span className="w-4 text-right text-slate-500">{star}</span>
                <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                <div className="flex-1 h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-amber-400 rounded-full transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="w-6 text-right text-slate-400">{count}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Category Averages */}
      {rep.category_averages && Object.keys(rep.category_averages).length > 0 && hasScore && (
        <div className="pt-2 border-t space-y-1.5">
          {rep.category_averages.item_accuracy && (
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Item Accuracy</span>
              <span className="font-medium">{rep.category_averages.item_accuracy.toFixed(1)}/5</span>
            </div>
          )}
          {rep.category_averages.communication && (
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Communication</span>
              <span className="font-medium">{rep.category_averages.communication.toFixed(1)}/5</span>
            </div>
          )}
          {rep.category_averages.shipping_speed && (
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">Shipping Speed</span>
              <span className="font-medium">{rep.category_averages.shipping_speed.toFixed(1)}/5</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * Review list with pagination for seller profile pages.
 */
export const SellerReviewsList = ({ sellerId }) => {
  const [reviews, setReviews] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const limit = 5;

  useEffect(() => {
    if (!sellerId) return;
    fetchReviews();
  }, [sellerId, page]); // eslint-disable-line

  const fetchReviews = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/reviews/seller/${sellerId}?page=${page}&limit=${limit}`);
      setReviews(res.data.reviews);
      setTotal(res.data.total);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  if (loading && page === 1) return null;
  if (total === 0) return null;

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="space-y-4" data-testid="seller-reviews-list">
      <h3 className="font-semibold text-lg">
        Buyer Reviews <span className="text-slate-400 font-normal">({total})</span>
      </h3>

      <div className="space-y-3">
        {reviews.map((review) => (
          <div key={review.id} className="bg-white dark:bg-slate-900 rounded-lg border p-4" data-testid="review-card">
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                {review.buyer_avatar ? (
                  <img src={review.buyer_avatar} alt="" className="w-8 h-8 rounded-full" />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
                    <span className="text-xs font-semibold text-blue-600">{review.buyer_display_name?.[0]}</span>
                  </div>
                )}
                <div>
                  <p className="text-sm font-medium">{review.buyer_display_name}</p>
                  <p className="text-xs text-slate-400">
                    {new Date(review.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <div className="flex gap-0.5">
                {[1, 2, 3, 4, 5].map((s) => (
                  <Star
                    key={s}
                    className={`h-4 w-4 ${s <= review.rating ? 'fill-amber-400 text-amber-400' : 'fill-slate-200 text-slate-200'}`}
                  />
                ))}
              </div>
            </div>
            {review.comment && (
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-2">{review.comment}</p>
            )}
            {(review.item_accuracy || review.communication || review.shipping_speed) && (
              <div className="flex gap-4 mt-2 text-xs text-slate-400">
                {review.item_accuracy && <span>Accuracy: {review.item_accuracy}/5</span>}
                {review.communication && <span>Communication: {review.communication}/5</span>}
                {review.shipping_speed && <span>Shipping: {review.shipping_speed}/5</span>}
              </div>
            )}
          </div>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex justify-center gap-2 pt-2">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 text-sm border rounded disabled:opacity-50 min-h-[44px]"
          >
            Previous
          </button>
          <span className="flex items-center text-sm text-slate-500">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="px-3 py-1.5 text-sm border rounded disabled:opacity-50 min-h-[44px]"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};
