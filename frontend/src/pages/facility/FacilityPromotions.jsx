/**
 * BidVex — Phase 6.2 Task 6D
 * Promotions tab — featured listing / email blast / reduced reserve badge.
 *
 * Pricing comes from GET /api/promote-config (NOT hardcoded).
 * Active promotion list: GET /api/facility/promotions
 * Create: POST /api/facility/promotions
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Loader2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const PROMO_CARDS = [
  {
    type: 'featured',
    icon: '🔝',
    title: 'Featured Listing',
    blurb: 'Pin your auction to the top of Storage Auctions for 24h / 48h / 72h.',
    showDuration: true,
  },
  {
    type: 'email_blast',
    icon: '📧',
    title: 'Email Blast to Watchers',
    blurb: 'Send a one-time notification to all users who have watchlisted any of your past auctions.',
  },
  {
    type: 'reduced_reserve',
    icon: '🏷',
    title: 'Reduced Reserve Badge',
    blurb: 'Display a "Reserve Lowered" badge to signal urgency. Free — requires actually lowering the reserve.',
    free: true,
  },
];

export default function FacilityPromotions() {
  const [promotions, setPromotions] = useState([]);
  const [pricing, setPricing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedListingId, setSelectedListingId] = useState('');
  const [listings, setListings] = useState([]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const token = window.localStorage.getItem('token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const [promosRes, pricingRes, auctionsRes] = await Promise.all([
        axios.get(`${API}/api/facility/promotions`, { headers }),
        axios.get(`${API}/api/promote-config`, { headers }).catch(() => ({ data: null })),
        axios.get(`${API}/api/facility/auctions?status=live`, { headers }).catch(() => ({ data: { auctions: [] } })),
      ]);
      setPromotions(promosRes.data?.promotions || []);
      setPricing(pricingRes.data);
      setListings(auctionsRes.data?.auctions || []);
    } catch (e) {
      console.error('[FacilityPromotions] load failed', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleActivate = async (type, duration) => {
    if (!selectedListingId) {
      toast.error('Please select a listing to boost first.');
      return;
    }
    try {
      const token = window.localStorage.getItem('token');
      await axios.post(
        `${API}/api/facility/promotions`,
        { listing_id: selectedListingId, type, duration_hours: duration },
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      );
      toast.success('Promotion activated.');
      await fetchAll();
    } catch (e) {
      console.error(e);
      toast.error(e?.response?.data?.detail || 'Failed to activate promotion.');
    }
  };

  // Build pricing labels from the existing /api/promote-config config.
  const featuredPrices = (pricing?.tiers || pricing?.PROMOTION_TIERS || {}) || {};
  const labelForType = (type) => {
    if (type === 'email_blast') {
      const p = pricing?.email_blast_price_cents ?? 499;
      return `$${(p / 100).toFixed(2)} CAD per blast`;
    }
    if (type === 'featured') {
      // Surface 24h base price as the headline
      const basic = featuredPrices.basic?.price_cents ?? 999;
      return `From $${(basic / 100).toFixed(2)} CAD`;
    }
    return 'Free';
  };

  return (
    <div className="space-y-6">
      <Card data-testid="facility-promotions-card">
        <CardHeader><CardTitle>Boost Your Auctions</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {/* Listing picker */}
          <div>
            <label className="text-xs font-medium block mb-1">Listing to promote</label>
            <select
              value={selectedListingId}
              onChange={(e) => setSelectedListingId(e.target.value)}
              className="w-full px-3 py-2 border rounded-md text-sm"
              data-testid="promo-listing-select"
            >
              <option value="">— select a live listing —</option>
              {listings.map((l) => (
                <option key={l.id} value={l.id}>{l.title}</option>
              ))}
            </select>
            {listings.length === 0 && (
              <p className="text-xs text-muted-foreground mt-1">No live listings to promote yet.</p>
            )}
          </div>

          {/* Promo cards */}
          <div className="grid md:grid-cols-3 gap-3">
            {PROMO_CARDS.map((c) => (
              <div key={c.type} className="border rounded-lg p-3 flex flex-col" data-testid={`promo-card-${c.type}`}>
                <div className="text-2xl mb-1">{c.icon}</div>
                <h3 className="font-semibold text-sm mb-1">{c.title}</h3>
                <p className="text-xs text-muted-foreground flex-1 mb-2">{c.blurb}</p>
                <p className="text-xs font-semibold mb-2">{labelForType(c.type)}</p>
                {c.showDuration ? (
                  <div className="flex gap-1">
                    {[24, 48, 72].map((h) => (
                      <Button
                        key={h}
                        onClick={() => handleActivate(c.type, h)}
                        disabled={!selectedListingId}
                        variant="outline"
                        size="sm"
                        className="flex-1 text-xs"
                        data-testid={`promo-activate-${c.type}-${h}h`}
                      >
                        {h}h
                      </Button>
                    ))}
                  </div>
                ) : (
                  <Button
                    onClick={() => handleActivate(c.type)}
                    disabled={!selectedListingId}
                    size="sm"
                    data-testid={`promo-activate-${c.type}`}
                  >
                    Activate →
                  </Button>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Active & Past Promotions</CardTitle></CardHeader>
        <CardContent>
          {loading && (<Loader2 className="h-6 w-6 animate-spin mx-auto" />)}
          {!loading && promotions.length === 0 && (
            <p className="text-sm text-muted-foreground" data-testid="promotions-empty">No promotions yet.</p>
          )}
          <div className="space-y-2">
            {promotions.map((p) => (
              <div
                key={p.id}
                className="border rounded p-2 flex justify-between items-center flex-wrap gap-2"
                data-testid={`promotion-row-${p.id}`}
              >
                <div className="min-w-0">
                  <div className="text-sm font-semibold truncate">{p.listing_title || p.listing_id}</div>
                  <div className="text-xs text-muted-foreground">
                    {p.type} · {p.duration_hours}h · started {p.started_at ? new Date(p.started_at).toLocaleString() : '—'}
                  </div>
                </div>
                <Badge variant={p.status === 'active' ? 'default' : 'secondary'}>{p.status}</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
