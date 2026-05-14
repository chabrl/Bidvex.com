import API_BASE from '../../config';
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import {
  Loader2, Package, DollarSign, TrendingUp, Receipt, Plus, ShieldCheck,
  Clock, Sparkles,
} from 'lucide-react';
import StorageFooterBanner from './StorageFooterBanner';
import PromoteAuctionModal from './PromoteAuctionModal';
import StorageVerificationBanner from './StorageVerificationBanner';

const API = API_BASE;

const StorageDashboard = () => {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const isFr = (i18n.language || '').startsWith('fr');
  const [dashboard, setDashboard] = useState(null);
  const [auctions, setAuctions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pendingState, setPendingState] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, a] = await Promise.all([
        axios.get(`${API}/storage-facilities/dashboard`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/storage-facilities/my-auctions`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      setDashboard(d.data);
      setAuctions(a.data?.auctions || []);
      setPendingState(null);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (detail?.error === 'facility_not_verified') {
        setPendingState('pending');
      } else if (err.response?.status === 403 || err.response?.status === 404) {
        setPendingState('not_registered');
      } else {
        toast.error('Failed to load dashboard');
      }
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const [promoteTarget, setPromoteTarget] = useState(null);

  if (loading) return <div className="min-h-screen flex justify-center items-center"><Loader2 className="h-10 w-10 animate-spin text-blue-600" /></div>;

  if (pendingState === 'not_registered') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900 px-4">
        <Card className="max-w-md p-8 text-center">
          <Package className="h-16 w-16 mx-auto text-blue-600 mb-3" />
          <h2 className="text-xl font-bold mb-2">{t('storage.dashboard.noFacilityAccount')}</h2>
          <p className="text-sm text-muted-foreground mb-5">
            {t('storage.dashboard.registerYourStorageFacilityToStartListin')}
          </p>
          <Link to="/storage-auctions/register-facility">
            <Button className="bg-blue-600 hover:bg-blue-700 text-white">{t('storage.dashboard.registerNow')}</Button>
          </Link>
        </Card>
      </div>
    );
  }

  if (pendingState === 'pending') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900 px-4">
        <Card className="max-w-md p-8 text-center" data-testid="dashboard-pending-state">
          <Clock className="h-16 w-16 mx-auto text-amber-500 mb-3" />
          <h2 className="text-xl font-bold mb-2">{t('storage.dashboard.awaitingVerification')}</h2>
          <p className="text-sm text-muted-foreground">
            {t('storage.dashboard.yourApplicationIsUnderReviewYouLlBeEmail')}
          </p>
        </Card>
      </div>
    );
  }

  const d = dashboard || {};
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-8" data-testid="storage-dashboard">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <ShieldCheck className="h-6 w-6 text-blue-600" />
              {d.facility?.company_name}
            </h1>
            <p className="text-sm text-muted-foreground">{d.facility?.city}, {d.facility?.province}</p>
          </div>
          <Link to="/storage-auctions/create">
            <Button className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="create-auction-btn">
              <Plus className="h-4 w-4 mr-1" /> {t('storage.dashboard.createNewAuction')}
            </Button>
          </Link>
        </div>

        {/* iter213 — Verification progress banner (hidden once verified) */}
        <StorageVerificationBanner facility={d.facility} isFr={isFr} />

        {/* Stat cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <Card className="p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1">
              <Package className="h-3 w-3" /> {t('storage.dashboard.activeAuctions')}
            </p>
            <p className="text-3xl font-black mt-1">{d.active_auctions || 0}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1">
              <TrendingUp className="h-3 w-3" /> {t('storage.dashboard.totalSold')}
            </p>
            <p className="text-3xl font-black mt-1">{d.total_sold || 0}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1">
              <DollarSign className="h-3 w-3" /> {t('storage.dashboard.revenueThisMonth')}
            </p>
            <p className="text-3xl font-black mt-1">${Number(d.revenue_this_month || 0).toLocaleString()}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground flex items-center gap-1">
              <Receipt className="h-3 w-3" /> {t('storage.dashboard.bidvexCommission5')}
            </p>
            <p className="text-3xl font-black mt-1 text-amber-600">${Number(d.commission_owed || 0).toLocaleString()}</p>
          </Card>
        </div>

        {/* My Auctions list */}
        <Card className="p-5">
          <h3 className="font-bold mb-3">{t('storage.dashboard.myAuctions2')} ({auctions.length})</h3>
          {auctions.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              {t('storage.dashboard.noAuctionsYetClickCreateNewAuctionToStar')}
            </p>
          ) : (
            <div className="divide-y">
              {auctions.map(a => (
                <div key={a.id} className="py-3 flex items-center justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold flex items-center gap-2 flex-wrap">
                      Unit #{a.unit_number} — {a.unit_size}
                      {a.promotion_tier && (
                        <Badge className="bg-gradient-to-r from-amber-400 to-orange-500 text-white border-0 text-[10px] uppercase" data-testid={`promotion-active-${a.id}`}>
                          <Sparkles className="h-3 w-3 mr-1" />
                          {a.promotion_tier} • {t('storage.dashboard.active')}
                        </Badge>
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {a.bid_count || 0} bids • Current ${Number(a.current_bid || 0).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant="outline">{a.live_status || a.status}</Badge>
                    {(a.live_status === 'active' || a.status === 'active' || a.status === 'upcoming') && !a.promotion_tier && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-amber-300 text-amber-700 hover:bg-amber-50"
                        onClick={() => setPromoteTarget(a)}
                        data-testid={`promote-auction-btn-${a.id}`}
                      >
                        <Sparkles className="h-3 w-3 mr-1" />
                        {t('storage.dashboard.promotePromouvoir')}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
      <StorageFooterBanner />
      <PromoteAuctionModal
        auction={promoteTarget}
        open={!!promoteTarget}
        onOpenChange={(o) => { if (!o) setPromoteTarget(null); }}
        onSuccess={() => { setPromoteTarget(null); load(); }}
        isFr={isFr}
      />
    </div>
  );
};

export default StorageDashboard;
