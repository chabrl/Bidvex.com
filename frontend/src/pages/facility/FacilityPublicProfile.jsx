/**
 * BidVex — Phase 6.2 Task 6F
 * Public facility profile page (no login required).
 * Route: /storage/facility/:facilityId
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useParams, useNavigate, NavLink } from 'react-router-dom';

import { Card, CardContent, CardHeader } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Loader2, Star, ShieldCheck, ExternalLink } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

export default function FacilityPublicProfile() {
  const { facilityId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API}/api/facility/public/${facilityId}`);
        if (!cancelled) setData(res.data);
      } catch (e) {
        if (!cancelled) setError(e?.response?.status === 404 ? 'Facility not found.' : 'Failed to load.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [facilityId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" data-testid="facility-public-loading">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="container mx-auto px-4 py-16 text-center" data-testid="facility-public-error">
        <p>{error}</p>
        <NavLink to="/storage-auctions" className="text-blue-600 underline mt-2 inline-block">
          Browse storage auctions
        </NavLink>
      </div>
    );
  }

  const fac = data?.facility || {};
  const summary = data?.summary || {};
  const active = data?.active_auctions || [];
  const upcoming = data?.upcoming_auctions || [];
  const reviews = data?.recent_reviews || [];

  return (
    <div className="container mx-auto px-4 py-6 max-w-5xl" data-testid="facility-public-profile">
      {/* Hero */}
      <div className="bg-gradient-to-br from-slate-900 to-slate-700 text-white rounded-xl p-6 mb-6">
        <div className="flex items-start gap-4 flex-wrap">
          {fac.picture && (
            <img src={fac.picture} alt="" className="h-16 w-16 rounded-full object-cover border-2 border-white" />
          )}
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2 break-words">
              {fac.name}
              {fac.verified && (
                <Badge className="bg-emerald-400 text-emerald-900 border-emerald-300 text-xs">
                  <ShieldCheck className="h-3 w-3 mr-1" /> Verified
                </Badge>
              )}
            </h1>
            <p className="text-sm opacity-90 mt-1">
              {[fac.city, fac.region].filter(Boolean).join(', ') || 'Storage Facility'}
            </p>
            <div className="flex items-center gap-2 mt-2">
              <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
              <span className="font-semibold">{summary.avg_rating?.toFixed(1) || '0.0'}</span>
              <span className="text-xs opacity-80">({summary.total_reviews || 0} reviews)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Active auctions */}
      <section className="mb-6" data-testid="facility-public-active">
        <h2 className="text-lg font-bold mb-3">🟢 Live Auctions ({active.length})</h2>
        {active.length === 0 ? (
          <p className="text-sm text-muted-foreground">No live auctions right now.</p>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {active.map((a) => (
              <Card
                key={a.id}
                className="cursor-pointer hover:shadow-lg transition-shadow overflow-hidden"
                onClick={() => navigate(`/storage-auctions/${a.id}`)}
                data-testid={`public-active-${a.id}`}
              >
                <div className="h-32 bg-slate-200">
                  {a.images?.[0] ? (
                    <img src={a.images[0]} alt={a.title} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-4xl">📦</div>
                  )}
                </div>
                <CardContent className="p-3">
                  <h3 className="text-sm font-semibold truncate">{a.title}</h3>
                  <div className="text-xs text-muted-foreground mt-1">
                    Current bid: <strong>${Number(a.current_price || 0).toFixed(2)}</strong>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* Upcoming */}
      {upcoming.length > 0 && (
        <section className="mb-6" data-testid="facility-public-upcoming">
          <h2 className="text-lg font-bold mb-3">📅 Upcoming Auctions ({upcoming.length})</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {upcoming.map((a) => (
              <Card
                key={a.id}
                className="cursor-pointer hover:shadow-lg transition-shadow overflow-hidden"
                onClick={() => navigate(`/storage-auctions/${a.id}`)}
              >
                <CardContent className="p-3">
                  <h3 className="text-sm font-semibold truncate">{a.title}</h3>
                  <div className="text-xs text-muted-foreground mt-1">
                    Starts {a.start_time ? new Date(a.start_time).toLocaleString() : '—'}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* Recent reviews */}
      <section data-testid="facility-public-reviews">
        <h2 className="text-lg font-bold mb-3">⭐ Recent Reviews</h2>
        {reviews.length === 0 ? (
          <p className="text-sm text-muted-foreground">No reviews yet.</p>
        ) : (
          <div className="space-y-3">
            {reviews.map((r) => (
              <Card key={r.id} className="p-3" data-testid={`public-review-${r.id}`}>
                <div className="flex items-center gap-2 mb-1">
                  <div className="flex gap-0.5">
                    {[1, 2, 3, 4, 5].map((n) => (
                      <Star key={n} className={`h-3 w-3 ${n <= (r.rating || 0) ? 'fill-amber-400 text-amber-400' : 'text-slate-300'}`} />
                    ))}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {r.buyer_display_name || 'Buyer'} · {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}
                  </span>
                </div>
                <p className="text-sm">{r.review_text}</p>
                {r.reply?.reply_text && (
                  <div className="mt-2 ml-3 pl-2 border-l-2 border-blue-300 text-xs">
                    <strong>Facility reply:</strong> {r.reply.reply_text}
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
