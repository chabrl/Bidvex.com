/**
 * iter217 Phase 5 Hotfix v5b — Broker CRM Dashboard.
 *
 * Route: /broker/dashboard
 *
 * MVP scope: Overview + My Buyers (the two revenue-critical tabs).
 * Active Deals / Pipeline / Revenue / Settings are stubs in this MVP
 * and ship in Hotfix v6.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import API_BASE from '../config';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import {
  LayoutDashboard, Users, Car, ClipboardList, DollarSign, Settings,
  AlertTriangle, CheckCircle2, Clock, XCircle, ShieldCheck,
} from 'lucide-react';

const TABS = [
  { id: 'overview',  icon: LayoutDashboard, label_en: 'Overview',     label_fr: 'Vue d\'ensemble' },
  { id: 'buyers',    icon: Users,           label_en: 'My Buyers',    label_fr: 'Mes acheteurs' },
  { id: 'deals',     icon: Car,             label_en: 'Active Deals', label_fr: 'Affaires actives', soon: true },
  { id: 'pipeline',  icon: ClipboardList,   label_en: 'Pipeline',     label_fr: 'Pipeline',         soon: true },
  { id: 'revenue',   icon: DollarSign,      label_en: 'Revenue',      label_fr: 'Revenus',          soon: true },
  { id: 'settings',  icon: Settings,        label_en: 'Settings',     label_fr: 'Paramètres',       soon: true },
];

const _fmt = (n) =>
  new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(n || 0));

const STATUS_BADGES = {
  pending:    { en: 'Pending',    fr: 'En attente',   color: 'bg-amber-100 text-amber-800',     icon: Clock },
  approved:   { en: 'Approved',   fr: 'Approuvé',     color: 'bg-emerald-100 text-emerald-800', icon: CheckCircle2 },
  active:     { en: 'Active',     fr: 'Actif',        color: 'bg-emerald-100 text-emerald-800', icon: CheckCircle2 },
  suspended:  { en: 'Suspended',  fr: 'Suspendu',     color: 'bg-orange-100 text-orange-800',   icon: AlertTriangle },
  terminated: { en: 'Terminated', fr: 'Terminé',      color: 'bg-slate-100 text-slate-700',     icon: XCircle },
  rejected:   { en: 'Rejected',   fr: 'Rejeté',       color: 'bg-rose-100 text-rose-800',       icon: XCircle },
};

export default function BrokerDashboardPage() {
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const navigate = useNavigate();

  const [broker, setBroker]     = useState(null);
  const [tab, setTab]           = useState('overview');
  const [buyers, setBuyers]     = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

  const loadBroker = useCallback(async () => {
    try {
      const r = await axios.get(`${API_BASE}/api/brokers/me`, {
        headers: { Authorization: `Bearer ${_token()}` },
      });
      setBroker(r.data);
    } catch (e) {
      if (e?.response?.status === 404) {
        navigate('/become-a-broker');
      } else {
        setError(e?.response?.data?.detail?.error || 'failed_to_load_broker');
      }
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  const loadBuyers = useCallback(async () => {
    try {
      const r = await axios.get(`${API_BASE}/api/broker-relationships/my-buyers`, {
        headers: { Authorization: `Bearer ${_token()}` },
      });
      setBuyers(r.data?.data || []);
    } catch (e) {
      // silent for tab 1; show on tab 2 if error
    }
  }, []);

  useEffect(() => { loadBroker(); }, [loadBroker]);
  useEffect(() => { if (broker) loadBuyers(); }, [broker, loadBuyers]);

  const handleBuyerAction = async (relId, action) => {
    try {
      const path = action === 'approve'
        ? `/api/broker-relationships/${relId}/approve`
        : action === 'reject'
        ? `/api/broker-relationships/${relId}/reject`
        : action === 'suspend'
        ? `/api/broker-relationships/${relId}/suspend`
        : action === 'terminate'
        ? `/api/broker-relationships/${relId}/terminate`
        : null;
      if (!path) return;
      await axios.post(`${API_BASE}${path}`, {}, { headers: { Authorization: `Bearer ${_token()}` } });
      await loadBuyers();
    } catch (e) {
      alert(e?.response?.data?.detail?.error || 'Action failed');
    }
  };

  if (loading) return <div className="container mx-auto py-12 text-center text-slate-500">Loading…</div>;
  if (error)   return <div className="container mx-auto py-12 text-center text-rose-500" data-testid="broker-dashboard-error">{String(error)}</div>;

  const pendingBuyers = buyers.filter(b => b.status === 'pending').length;
  const activeBuyers  = buyers.filter(b => b.status === 'active').length;

  return (
    <div className="container mx-auto max-w-7xl py-6 px-4">
      <header className="flex items-start justify-between gap-4 mb-6 flex-wrap" data-testid="broker-dashboard-header">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold">{broker.legal_business_name}</h1>
          <p className="text-sm text-slate-500">
            {broker.operating_province} · {broker.regulatory_body}
            {broker.verification_status !== 'approved' && (
              <Badge className="ml-2 bg-amber-100 text-amber-800" data-testid="broker-not-approved-badge">
                <Clock className="h-3 w-3 mr-1" />
                {lang === 'fr' ? 'En attente d\'approbation' : 'Pending approval'}
              </Badge>
            )}
            {broker.verification_status === 'approved' && (
              <Badge className="ml-2 bg-emerald-100 text-emerald-800" data-testid="broker-approved-badge">
                <ShieldCheck className="h-3 w-3 mr-1" />
                {lang === 'fr' ? 'Approuvé' : 'Approved'}
              </Badge>
            )}
          </p>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-6">
        {/* Sidebar */}
        <aside className="space-y-1" data-testid="broker-dashboard-sidebar">
          {TABS.map(tEl => {
            const Icon = tEl.icon;
            return (
              <button
                key={tEl.id}
                onClick={() => setTab(tEl.id)}
                className={`w-full text-left px-3 py-2 rounded flex items-center gap-3 text-sm transition ${
                  tab === tEl.id
                    ? 'bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white'
                    : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
                data-testid={`broker-tab-${tEl.id}`}
              >
                <Icon className="h-4 w-4" />
                <span>{lang === 'fr' ? tEl.label_fr : tEl.label_en}</span>
                {tEl.soon && <Badge className="ml-auto text-[10px] bg-slate-200 text-slate-700">v6</Badge>}
              </button>
            );
          })}
        </aside>

        {/* Content */}
        <main>
          {tab === 'overview' && (
            <section className="space-y-4" data-testid="broker-overview">
              {broker.verification_status !== 'approved' && (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    {lang === 'fr'
                      ? 'Votre demande est en cours d\'examen. Vous pourrez gérer des acheteurs une fois approuvé (24-48h).'
                      : 'Your application is under review. You can manage buyers once approved (24-48h).'}
                  </AlertDescription>
                </Alert>
              )}
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
                <KPI label={lang === 'fr' ? 'Acheteurs actifs' : 'Active Buyers'}   value={activeBuyers} testid="kpi-active-buyers" />
                <KPI label={lang === 'fr' ? 'Demandes en attente' : 'Pending Requests'} value={pendingBuyers} testid="kpi-pending-buyers" />
                <KPI label={lang === 'fr' ? 'Affaires gagnées' : 'Deals Won'}       value={broker.total_deals_completed || 0} testid="kpi-deals-won" />
                <KPI label={lang === 'fr' ? 'Revenu total' : 'Total Revenue'}        value={_fmt(broker.total_revenue_cad)} testid="kpi-revenue" />
                <KPI label={lang === 'fr' ? 'Acheteurs gérés' : 'Total Buyers Managed'} value={broker.total_buyers_managed || 0} testid="kpi-total-buyers" />
              </div>
              <Card><CardContent className="p-5">
                <h3 className="font-semibold mb-2">{lang === 'fr' ? 'Structure de frais' : 'Fee Structure'}</h3>
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  {broker.fee_structure?.type === 'fixed'
                    ? (lang === 'fr' ? `Fixe : ${_fmt(broker.fee_structure.fixed_amount_cad)} par véhicule` : `Fixed: ${_fmt(broker.fee_structure.fixed_amount_cad)} per vehicle`)
                    : (lang === 'fr' ? `Pourcentage : ${(broker.fee_structure?.percentage_rate * 100).toFixed(2)} % du prix final` : `Percentage: ${(broker.fee_structure?.percentage_rate * 100).toFixed(2)}% of hammer price`)}
                </p>
              </CardContent></Card>
            </section>
          )}

          {tab === 'buyers' && (
            <section data-testid="broker-buyers">
              <h2 className="text-xl font-semibold mb-4">{lang === 'fr' ? 'Mes acheteurs' : 'My Buyers'}</h2>
              {buyers.length === 0 ? (
                <Card><CardContent className="p-8 text-center text-slate-500">
                  {lang === 'fr' ? 'Aucun acheteur lié pour le moment.' : 'No buyer requests yet.'}
                </CardContent></Card>
              ) : (
                <div className="space-y-2">
                  {buyers.map((b) => {
                    const s = STATUS_BADGES[b.status] || STATUS_BADGES.pending;
                    const Icon = s.icon;
                    return (
                      <Card key={b.id} data-testid={`buyer-row-${b.id}`}>
                        <CardContent className="p-4 flex items-center gap-3 flex-wrap">
                          <div className="flex-1 min-w-[200px]">
                            <div className="font-semibold">{b.buyer_full_name || b.buyer_email}</div>
                            <div className="text-xs text-slate-500">{b.buyer_email}</div>
                          </div>
                          <Badge className={s.color}>
                            <Icon className="h-3 w-3 mr-1" />
                            {lang === 'fr' ? s.fr : s.en}
                          </Badge>
                          <Badge variant="outline">
                            {lang === 'fr' ? 'Dépôt' : 'Deposit'}: {b.deposit_status}
                          </Badge>
                          <div className="flex gap-2">
                            {b.status === 'pending' && (
                              <>
                                <Button size="sm" onClick={() => handleBuyerAction(b.id, 'approve')} data-testid={`buyer-approve-${b.id}`}>
                                  {lang === 'fr' ? 'Approuver' : 'Approve'}
                                </Button>
                                <Button size="sm" variant="outline" onClick={() => handleBuyerAction(b.id, 'reject')} data-testid={`buyer-reject-${b.id}`}>
                                  {lang === 'fr' ? 'Rejeter' : 'Reject'}
                                </Button>
                              </>
                            )}
                            {b.status === 'active' && (
                              <>
                                <Button size="sm" variant="outline" onClick={() => handleBuyerAction(b.id, 'suspend')} data-testid={`buyer-suspend-${b.id}`}>
                                  {lang === 'fr' ? 'Suspendre' : 'Suspend'}
                                </Button>
                                <Button size="sm" variant="outline" onClick={() => handleBuyerAction(b.id, 'terminate')} data-testid={`buyer-terminate-${b.id}`}>
                                  {lang === 'fr' ? 'Terminer' : 'Terminate'}
                                </Button>
                              </>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </section>
          )}

          {(tab === 'deals' || tab === 'pipeline' || tab === 'revenue' || tab === 'settings') && (
            <Card><CardContent className="p-8 text-center" data-testid={`broker-tab-soon-${tab}`}>
              <Clock className="mx-auto h-10 w-10 text-slate-400 mb-3" />
              <h3 className="font-semibold mb-1">
                {lang === 'fr' ? 'Disponible dans Hotfix v6' : 'Coming in Hotfix v6'}
              </h3>
              <p className="text-sm text-slate-500">
                {lang === 'fr'
                  ? 'Cet onglet est livré dans la prochaine mise à jour.'
                  : 'This tab ships in the next update.'}
              </p>
            </CardContent></Card>
          )}
        </main>
      </div>
    </div>
  );
}

const KPI = ({ label, value, testid }) => (
  <Card data-testid={testid}>
    <CardContent className="p-4">
      <div className="text-xs text-slate-500 uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
    </CardContent>
  </Card>
);
