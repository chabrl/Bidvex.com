import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { formatCurrency } from '../utils/currencyFormatter';
import {
  ArrowLeft, Store, Package, Clock, Eye, Gavel, MapPin, Star, ExternalLink
} from 'lucide-react';
import SEO from '../components/SEO';
import { SellerReputationCard, SellerReviewsList } from '../components/SellerReputation';

const API = `${API_BASE}/api`;

const StorefrontPage = () => {
  const { userId } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API}/storefronts/${userId}`)
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [userId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900">
        <div className="animate-spin h-8 w-8 border-2 border-cyan-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 dark:bg-slate-900 px-4">
        <Store className="h-16 w-16 text-slate-300 mb-4" />
        <h2 className="text-xl font-semibold text-slate-700 dark:text-slate-200 mb-2">{t('storefront.notFound')}</h2>
        <Button onClick={() => navigate(-1)} variant="outline">{t('storefront.goBack')}</Button>
      </div>
    );
  }

  const { seller, storefront, listings, has_storefront } = data;
  const accentColor = storefront?.accent_color || '#06b6d4';

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900" data-testid="storefront-page">
      <SEO title={`${seller.name}'s Store — BidVex`} description={storefront?.tagline || `Browse ${seller.name}'s listings on BidVex`} path={`/store/${userId}`} />

      <div className="relative h-48 sm:h-64" style={{ background: storefront?.banner_url ? `url(${storefront.banner_url}) center/cover` : `linear-gradient(135deg, ${accentColor}33, ${accentColor}11)` }}>
        <div className="absolute inset-0 bg-gradient-to-b from-transparent to-slate-900/60" />
        <div className="absolute top-4 left-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)} className="text-white bg-black/30 hover:bg-black/50 backdrop-blur" data-testid="storefront-back-btn">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 -mt-16 relative z-10">
        <div className="flex items-end gap-4 mb-6">
          <div className="w-24 h-24 sm:w-28 sm:h-28 rounded-2xl border-4 border-white dark:border-slate-800 shadow-xl overflow-hidden bg-slate-200">
            {seller.picture ? (
              <img src={seller.picture} alt={seller.name} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-3xl font-bold" style={{ background: `linear-gradient(135deg, ${accentColor}, ${accentColor}99)`, color: 'white' }}>
                {seller.name?.charAt(0) || 'S'}
              </div>
            )}
          </div>
          <div className="pb-1">
            <div className="flex items-center gap-2">
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white">{seller.name}</h1>
              {has_storefront && (
                <Badge className="text-xs font-semibold" style={{ background: accentColor, color: 'white' }}>
                  <Star className="h-3 w-3 mr-1" /> {t('storefront.proSeller')}
                </Badge>
              )}
            </div>
            {storefront?.tagline && (
              <p className="text-slate-600 dark:text-slate-300 text-sm mt-1">{storefront.tagline}</p>
            )}
          </div>
        </div>

        {storefront?.about && (
          <Card className="mb-6 border-0 shadow-sm dark:bg-slate-800/50">
            <CardContent className="p-4 sm:p-6">
              <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{storefront.about}</p>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="md:col-span-1">
            <SellerReputationCard sellerId={userId} />
          </div>
          <div className="md:col-span-2">
            <SellerReviewsList sellerId={userId} />
          </div>
        </div>

        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-800 dark:text-slate-200">
            {t('storefront.activeListings', { count: listings.length })}
          </h2>
        </div>

        {listings.length === 0 ? (
          <div className="text-center py-16">
            <Package className="h-12 w-12 mx-auto text-slate-300 mb-3" />
            <p className="text-slate-500">{t('storefront.noActiveListings')}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 pb-12">
            {listings.map(item => (
              <Card
                key={item.id}
                className="cursor-pointer overflow-hidden border-0 shadow-md hover:shadow-xl transition-all duration-300 dark:bg-slate-800/50 group"
                onClick={() => navigate(`/listing/${item.id}`)}
                data-testid={`storefront-listing-${item.id}`}
              >
                <div className="relative aspect-square bg-slate-100 dark:bg-slate-700 overflow-hidden">
                  {item.images?.[0] ? (
                    <img src={item.images[0]} alt={item.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center"><Package className="h-10 w-10 text-slate-400" /></div>
                  )}
                  {item.is_featured && (
                    <Badge className="absolute top-2 left-2 bg-amber-500 text-white border-0 text-xs">
                      <Star className="h-3 w-3 mr-1" /> {t('storefront.featured')}
                    </Badge>
                  )}
                </div>
                <CardContent className="p-3 sm:p-4">
                  <h3 className="font-medium text-sm line-clamp-1 text-slate-900 dark:text-slate-100 mb-1">{item.title}</h3>
                  <p className="text-lg font-bold mb-2" style={{ color: accentColor }}>{formatCurrency(item.current_price)}</p>
                  <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
                    <span className="flex items-center gap-1"><Eye className="h-3 w-3" /> {item.views || 0}</span>
                    <span className="flex items-center gap-1"><Gavel className="h-3 w-3" /> {item.total_bids || item.bid_count || 0}</span>
                    {item.city && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {item.city}</span>}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default StorefrontPage;
