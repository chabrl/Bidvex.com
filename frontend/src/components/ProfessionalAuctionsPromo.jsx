/**
 * iter217 Phase 3 — Professional Auctions homepage section.
 *
 * Shows active Lot-Auction listings from BidVex-verified partners and
 * licensed vehicle dealers. Auto-hides when zero partner lots are active.
 *
 * Positioned AFTER the hero, BEFORE the Storage Auctions Promo —
 * the most prominent non-hero slot.
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardFooter } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { MapPin, Clock, Package, ArrowRight, Gavel } from 'lucide-react';
import Countdown from 'react-countdown';
import { SellerAccountBadge } from './PrivateSaleBadge';
import API_BASE from '../config';

const API = API_BASE;

const ProfessionalAuctionsPromo = ({ navigate }) => {
  const { t, i18n } = useTranslation();
  const [listings, setListings] = useState([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await axios.get(`${API}/multi-item-listings`, {
          params: {
            seller_account_type: 'partner,vehicle_dealer',
            status: 'active',
            promoted_first: true,
            limit: 8,
          },
        });
        if (!cancelled && Array.isArray(data)) {
          setListings(data);
        }
      } finally {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Visibility rule: hide section entirely when zero active partner lots.
  if (!loaded) return null;
  if (!listings.length) return null;

  const formatCurrency = (amount, currency = 'CAD') => {
    if (amount == null) return '—';
    return new Intl.NumberFormat(i18n.language === 'fr' ? 'fr-CA' : 'en-CA', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const getLocalized = (listing, key) => {
    const lang = (i18n.language || 'en').startsWith('fr') ? 'fr' : 'en';
    return listing[`${key}_${lang}`] || listing[key] || '';
  };

  return (
    <section
      data-testid="professional-auctions-promo"
      className="py-12 sm:py-16"
      style={{ background: 'linear-gradient(180deg, #f8fafc 0%, #eff6ff 100%)' }}
    >
      <div className="container mx-auto px-4">
        <div className="mb-8 max-w-3xl">
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold mb-3" style={{ color: '#0f172a' }}>
            🔨 {t('home.proAuctions.title', 'Professional Auctions — Lots & Liquidations')}
          </h2>
          <p className="text-sm sm:text-base" style={{ color: '#475569', lineHeight: 1.6 }}>
            {t(
              'home.proAuctions.subtitle',
              'Licensed auctioneers, liquidators and professional dealers — verified by BidVex.'
            )}
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {listings.slice(0, 8).map((listing) => {
            const firstLot = listing.lots?.[0];
            const imageUrl =
              firstLot?.images?.[0] ||
              listing.lots?.find((l) => l.images?.length > 0)?.images?.[0];
            const totalStarting = (listing.lots || []).reduce(
              (sum, l) => sum + (l.starting_price || 0),
              0
            );
            const endingSoon =
              listing.auction_end_date &&
              new Date(listing.auction_end_date) - Date.now() < 24 * 60 * 60 * 1000;

            return (
              <Card
                key={listing.id}
                className="group overflow-hidden hover:shadow-xl transition-all duration-300 border-slate-200 dark:border-slate-700 cursor-pointer"
                data-testid="pro-auction-card"
                onClick={() => navigate(`/lots/${listing.id}`)}
              >
                <div className="relative aspect-[4/3] overflow-hidden bg-slate-100">
                  {imageUrl ? (
                    <img
                      src={imageUrl}
                      alt={getLocalized(listing, 'title')}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                      loading="lazy"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <Gavel className="h-16 w-16" style={{ color: '#94a3b8' }} />
                    </div>
                  )}
                  <div className="absolute top-2 left-2 z-10">
                    <SellerAccountBadge
                      accountType={listing.seller_account_type || 'partner'}
                      companyName={listing.seller_partner_company_name}
                      variant="compact"
                    />
                  </div>
                  <Badge className="absolute top-2 right-2 bg-slate-900/80 text-white border-0">
                    <Package className="h-3 w-3 mr-1" />
                    {t('listingDetail.lotsCount', { count: listing.total_lots, defaultValue: '{{count}} Lots' })}
                  </Badge>
                  {listing.auction_end_date && (
                    <div
                      className="absolute bottom-2 left-2 backdrop-blur text-white px-2.5 py-1 rounded-full text-xs flex items-center gap-1.5"
                      style={{
                        background: endingSoon ? 'rgba(220,38,38,0.85)' : 'rgba(15,23,42,0.8)',
                      }}
                    >
                      <Clock className="h-3 w-3" />
                      <Countdown
                        date={new Date(listing.auction_end_date)}
                        renderer={({ days, hours, minutes }) => (
                          <span>
                            {days}d {hours}h {minutes}m
                          </span>
                        )}
                      />
                    </div>
                  )}
                </div>

                <CardContent className="p-3.5">
                  {listing.seller_partner_company_name && (
                    <p className="text-xs uppercase tracking-wide mb-1" style={{ color: '#475569', fontWeight: 600 }}>
                      {listing.seller_partner_company_name}
                    </p>
                  )}
                  <h3
                    className="font-semibold text-sm line-clamp-2 mb-2"
                    style={{ color: '#0f172a' }}
                  >
                    {getLocalized(listing, 'title')}
                  </h3>
                  {(listing.city || listing.region) && (
                    <div className="flex items-center gap-1 text-xs mb-2" style={{ color: '#64748b' }}>
                      <MapPin className="h-3 w-3" />
                      <span>
                        {listing.city}
                        {listing.city && listing.region ? ', ' : ''}
                        {listing.region}
                      </span>
                    </div>
                  )}
                  <p className="text-xs" style={{ color: '#94a3b8' }}>
                    {t('home.proAuctions.totalStarting', 'Total starting value')}
                  </p>
                  <p className="text-base font-bold" style={{ color: '#1d4ed8' }}>
                    {formatCurrency(totalStarting, firstLot?.currency || 'CAD')}
                  </p>
                </CardContent>

                <CardFooter className="p-3.5 pt-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="w-full text-xs font-medium"
                    style={{ color: '#1d4ed8' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/lots/${listing.id}`);
                    }}
                  >
                    {t('home.proAuctions.browseLots', 'Browse Lots')} <ArrowRight className="h-3 w-3 ml-1" />
                  </Button>
                </CardFooter>
              </Card>
            );
          })}
        </div>

        {/* iter217 — Apply-as-partner footer strip */}
        <div
          className="mt-10 rounded-xl px-6 py-5 flex flex-col sm:flex-row items-start sm:items-center gap-4 justify-between"
          style={{ background: '#0f172a' }}
        >
          <p className="text-white text-sm sm:text-base" style={{ lineHeight: 1.5 }}>
            {t(
              'home.proAuctions.applyCopy',
              'Are you a licensed auctioneer or liquidator?'
            )}
          </p>
          <Button
            data-testid="apply-as-partner-btn"
            className="text-white border-0"
            style={{ background: '#06b6d4' }}
            onClick={() => navigate('/become-a-partner')}
          >
            {t('home.proAuctions.applyBtn', 'Apply as Partner')} <ArrowRight className="h-4 w-4 ml-1.5" />
          </Button>
        </div>
      </div>
    </section>
  );
};

export default ProfessionalAuctionsPromo;
