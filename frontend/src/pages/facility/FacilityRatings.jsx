/**
 * BidVex — Phase 6.2 Task 6E
 * Ratings & Reviews tab — distribution bar chart + reviews list + reply form.
 *
 * Backend:
 *   GET  /api/facility/ratings
 *   POST /api/facility/ratings/{id}/reply (one reply per review, 24h edit window)
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Loader2, Star } from 'lucide-react';
import { authHeaders } from '../../utils/authToken';

const API = process.env.REACT_APP_BACKEND_URL || '';

function StarRow({ value }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          className={`h-3.5 w-3.5 ${n <= value ? 'fill-amber-400 text-amber-400' : 'text-slate-300'}`}
        />
      ))}
    </div>
  );
}

export default function FacilityRatings() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [replyDrafts, setReplyDrafts] = useState({});
  const [submittingId, setSubmittingId] = useState(null);

  const fetchRatings = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/api/facility/ratings`, {
        headers: authHeaders(),
      });
      setData(res.data);
    } catch (e) {
      console.error('[FacilityRatings] load failed', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchRatings(); }, [fetchRatings]);

  const submitReply = async (ratingId) => {
    const text = (replyDrafts[ratingId] || '').trim();
    if (text.length < 5) {
      toast.error('Reply must be at least 5 characters.');
      return;
    }
    setSubmittingId(ratingId);
    try {
      await axios.post(
        `${API}/api/facility/ratings/${ratingId}/reply`,
        { reply_text: text },
        { headers: authHeaders() },
      );
      toast.success('Reply posted.');
      setReplyDrafts({ ...replyDrafts, [ratingId]: '' });
      await fetchRatings();
    } catch (e) {
      console.error(e);
      toast.error(e?.response?.data?.detail?.message_en || 'Failed to post reply.');
    } finally {
      setSubmittingId(null);
    }
  };

  if (loading) {
    return (
      <Card><CardContent className="py-12 text-center"><Loader2 className="h-6 w-6 animate-spin mx-auto" /></CardContent></Card>
    );
  }

  const summary = data?.summary || {};
  const ratings = data?.ratings || [];
  const pct = summary.distribution_pct || {};

  return (
    <div className="space-y-6">
      <Card data-testid="facility-ratings-summary">
        <CardHeader><CardTitle>Reputation Overview</CardTitle></CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-[200px,1fr] gap-6">
            <div className="text-center">
              <div className="text-5xl font-bold" data-testid="facility-avg-rating">
                {summary.avg_rating?.toFixed(1) || '0.0'}
              </div>
              <div className="text-xs text-muted-foreground mt-1">out of 5.0</div>
              <div className="mt-2"><StarRow value={Math.round(summary.avg_rating || 0)} /></div>
              <div className="text-xs text-muted-foreground mt-2">{summary.total_reviews ?? 0} reviews</div>
            </div>
            <div>
              {[5, 4, 3, 2, 1].map((n) => (
                <div key={n} className="flex items-center gap-2 mb-1.5">
                  <span className="text-xs w-3 text-right">{n}</span>
                  <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                  <div className="flex-1 bg-slate-200 rounded h-2 overflow-hidden">
                    <div
                      className="h-full bg-amber-400"
                      style={{ width: `${pct[n] || 0}%` }}
                    />
                  </div>
                  <span className="text-xs w-10 text-right text-muted-foreground">{pct[n] || 0}%</span>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card data-testid="facility-reviews-list">
        <CardHeader><CardTitle>Reviews</CardTitle></CardHeader>
        <CardContent>
          {ratings.length === 0 && (
            <p className="text-sm text-muted-foreground" data-testid="facility-reviews-empty">
              No reviews yet. Reviews appear after a buyer's cleanout is approved.
            </p>
          )}

          <div className="space-y-4">
            {ratings.map((r) => {
              const hasReply = !!r.reply?.reply_text;
              return (
                <div key={r.id} className="border rounded-lg p-3" data-testid={`review-${r.id}`}>
                  <div className="flex items-start justify-between mb-1">
                    <div>
                      <div className="flex items-center gap-2">
                        <StarRow value={r.rating || 0} />
                        <span className="text-xs text-muted-foreground">
                          {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {r.buyer_display_name || 'Buyer'} · auction {r.listing_id?.slice(0, 12) || ''}…
                      </div>
                    </div>
                  </div>
                  <p className="text-sm mt-1.5 break-words">{r.review_text}</p>

                  {/* Reply section */}
                  {hasReply ? (
                    <div className="mt-3 ml-4 pl-3 border-l-2 border-blue-300 bg-blue-50 dark:bg-blue-900/20 p-2 rounded-r" data-testid={`review-reply-${r.id}`}>
                      <div className="text-[10px] uppercase font-semibold text-blue-700 mb-0.5">
                        Reply from facility
                      </div>
                      <p className="text-sm">{r.reply.reply_text}</p>
                      <div className="text-[10px] text-muted-foreground mt-1">
                        {r.reply.replied_at ? new Date(r.reply.replied_at).toLocaleString() : ''}
                      </div>
                    </div>
                  ) : (
                    <div className="mt-2 flex gap-2 items-start">
                      <textarea
                        value={replyDrafts[r.id] || ''}
                        onChange={(e) => setReplyDrafts({ ...replyDrafts, [r.id]: e.target.value })}
                        placeholder="Reply to this review (one reply allowed, 24h edit window)…"
                        className="flex-1 border rounded text-sm p-2 min-h-[60px]"
                        data-testid={`review-reply-input-${r.id}`}
                      />
                      <Button
                        onClick={() => submitReply(r.id)}
                        disabled={submittingId === r.id}
                        size="sm"
                        data-testid={`review-reply-submit-${r.id}`}
                      >
                        {submittingId === r.id ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Post'}
                      </Button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
