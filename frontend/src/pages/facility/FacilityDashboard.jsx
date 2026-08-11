/**
 * BidVex — Phase 6.2 Task 6
 * Storage Facility Manager Dashboard.
 *
 * Route: /facility/dashboard (+ /facility/dashboard/:tab)
 * Access: storage_facility role (admin bypasses). Redirects others to /login.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useNavigate, useParams, NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Loader2, Package, BarChart3, Megaphone, Star, Settings, ShieldCheck, ExternalLink } from 'lucide-react';
import { authHeaders } from '../../utils/authToken';

import FacilityAuctions from './FacilityAuctions';
import FacilityAnalytics from './FacilityAnalytics';
import FacilityPromotions from './FacilityPromotions';
import FacilityRatings from './FacilityRatings';
import BusinessSettingsCard from '../../components/BusinessSettingsCard';

const API = process.env.REACT_APP_BACKEND_URL || '';

const NAV = [
  { key: 'auctions',  label_en: 'My Auctions',         label_fr: 'Mes enchères',     icon: Package },
  { key: 'analytics', label_en: 'Analytics',           label_fr: 'Analyses',         icon: BarChart3 },
  { key: 'promotions',label_en: 'Promotions',          label_fr: 'Promotions',       icon: Megaphone },
  { key: 'ratings',   label_en: 'Ratings & Reviews',   label_fr: 'Avis et notes',    icon: Star },
  { key: 'settings',  label_en: 'Settings',            label_fr: 'Paramètres',       icon: Settings },
];

export default function FacilityDashboard() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { tab } = useParams();
  const activeTab = tab || 'auctions';

  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchOverview = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/api/facility/overview`, {
        headers: authHeaders(),
      });
      setOverview(res.data);
    } catch (e) {
      console.error('[FacilityDashboard] overview failed:', e);
      if (e?.response?.status === 401) {
        navigate('/login?return_to=/facility/dashboard');
      } else if (e?.response?.status === 403) {
        setError(t('facility.notAuthorized', {
          defaultValue: 'This area is reserved for verified storage facility accounts. Apply from your profile.',
        }));
      } else {
        setError(t('facility.loadFailed', 'Failed to load dashboard.'));
      }
    } finally {
      setLoading(false);
    }
  }, [navigate, t]);

  useEffect(() => { fetchOverview(); }, [fetchOverview]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" data-testid="facility-dashboard-loading">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-16 max-w-xl text-center" data-testid="facility-dashboard-error">
        <p className="text-base text-muted-foreground mb-4">{error}</p>
        <Button onClick={() => navigate('/profile')} data-testid="facility-back-to-profile">
          {t('facility.backToProfile', 'Back to profile')}
        </Button>
      </div>
    );
  }

  const counts = overview?.counts || {};
  const fac = overview?.facility || {};
  const lang = (i18n.language || 'en').startsWith('fr') ? 'fr' : 'en';

  const navTo = (k) => navigate(`/facility/dashboard/${k}`);

  return (
    <div className="container mx-auto px-4 py-6 max-w-7xl" data-testid="facility-dashboard">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap mb-6">
        <div className="flex items-center gap-3">
          {fac.picture && (
            <img src={fac.picture} alt="" className="h-12 w-12 rounded-full object-cover" />
          )}
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2" data-testid="facility-header-name">
              {fac.name}
              {fac.verified && (
                <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300 text-xs" data-testid="facility-verified-badge">
                  <ShieldCheck className="h-3 w-3 mr-1" /> Verified
                </Badge>
              )}
            </h1>
            {(fac.city || fac.region) && (
              <p className="text-xs text-muted-foreground">{[fac.city, fac.region].filter(Boolean).join(', ')}</p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => navigate('/profile')} variant="outline" size="sm" data-testid="facility-edit-profile-btn">
            ✎ Edit Profile
          </Button>
          <Button
            onClick={() => navigate(`/storage/facility/${fac.id}`)}
            variant="outline"
            size="sm"
            data-testid="facility-view-public-btn"
          >
            <ExternalLink className="h-3 w-3 mr-1" /> Public Profile
          </Button>
        </div>
      </div>

      {/* Quick-stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6" data-testid="facility-quick-stats">
        {[
          { key: 'live',     label: 'Live',     count: counts.live ?? 0,     tone: 'bg-emerald-50 text-emerald-800 border-emerald-300' },
          { key: 'upcoming', label: 'Upcoming', count: counts.upcoming ?? 0, tone: 'bg-blue-50 text-blue-800 border-blue-300' },
          { key: 'ended',    label: 'Ended',    count: counts.ended ?? 0,    tone: 'bg-slate-100 text-slate-800 border-slate-300' },
          { key: 'drafts',   label: 'Drafts',   count: counts.drafts ?? 0,   tone: 'bg-amber-50 text-amber-800 border-amber-300' },
        ].map((c) => (
          <button
            type="button"
            key={c.key}
            onClick={() => navigate(`/facility/dashboard/auctions?status=${c.key}`)}
            className={`rounded-lg border ${c.tone} p-4 text-left hover:shadow-md transition-shadow`}
            data-testid={`facility-stat-${c.key}`}
          >
            <div className="text-3xl font-bold tabular-nums">{c.count}</div>
            <div className="text-xs uppercase tracking-wide mt-1 opacity-80">{c.label}</div>
            <div className="text-[10px] mt-0.5 opacity-70">auctions</div>
          </button>
        ))}
      </div>

      {/* Body — sidebar + main panel */}
      <div className="grid md:grid-cols-[200px,1fr] gap-6">
        <nav
          className="bg-white dark:bg-slate-900 border rounded-lg p-2 md:sticky md:top-4 self-start overflow-x-auto"
          data-testid="facility-sidebar"
        >
          <ul className="flex md:flex-col gap-1 min-w-max md:min-w-0">
            {NAV.map((n) => {
              const Icon = n.icon;
              const isActive = activeTab === n.key;
              return (
                <li key={n.key}>
                  <button
                    type="button"
                    onClick={() => navTo(n.key)}
                    data-testid={`facility-nav-${n.key}`}
                    className={`flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap transition-colors ${
                      isActive
                        ? 'bg-slate-900 text-white'
                        : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {lang === 'fr' ? n.label_fr : n.label_en}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <main className="min-w-0">
          {activeTab === 'auctions' && <FacilityAuctions />}
          {activeTab === 'analytics' && <FacilityAnalytics />}
          {activeTab === 'promotions' && <FacilityPromotions />}
          {activeTab === 'ratings' && <FacilityRatings />}
          {activeTab === 'settings' && (
            <Card>
              <CardHeader><CardTitle>Settings</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                {/* iter477 — Shared Business & Billing Profile (logo + tax IDs
                    that appear on every invoice / receipt / statement). */}
                <div className="border rounded-lg p-4 bg-slate-50 dark:bg-slate-800/50">
                  <p className="text-sm font-medium mb-1">
                    {lang === 'fr' ? 'Profil de facturation' : 'Business & Billing Profile'}
                  </p>
                  <p className="text-xs text-muted-foreground mb-3">
                    {lang === 'fr'
                      ? 'Ces informations et votre logo apparaissent sur chaque facture, reçu et relevé émis pour votre installation.'
                      : 'These details and your logo appear on every invoice, receipt, and statement issued for your facility.'}
                  </p>
                  <BusinessSettingsCard variant="facility" />
                </div>
                <p className="text-sm text-muted-foreground">
                  Facility account settings are managed from your{' '}
                  <NavLink to="/profile" className="text-blue-600 underline">profile page</NavLink>.
                </p>
              </CardContent>
            </Card>
          )}
        </main>
      </div>
    </div>
  );
}
