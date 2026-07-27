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
import B2BCouponActivationCard from '../components/B2BCouponActivationCard';
import {
  LayoutDashboard, Users, Car, ClipboardList, DollarSign, Settings,
  AlertTriangle, CheckCircle2, Clock, XCircle, ShieldCheck,
  BookOpenCheck, FileEdit, Save,
} from 'lucide-react';

const TABS = [
  { id: 'overview',  icon: LayoutDashboard, label_en: 'Overview',     label_fr: 'Vue d\'ensemble' },
  { id: 'buyers',    icon: Users,           label_en: 'My Buyers',    label_fr: 'Mes acheteurs' },
  { id: 'ledger',    icon: BookOpenCheck,   label_en: 'Reconciliation', label_fr: 'Réconciliation' },
  { id: 'deals',     icon: Car,             label_en: 'Active Deals', label_fr: 'Affaires actives' },
  { id: 'pipeline',  icon: ClipboardList,   label_en: 'Pipeline',     label_fr: 'Pipeline' },
  { id: 'revenue',   icon: DollarSign,      label_en: 'Revenue',      label_fr: 'Revenus' },
  { id: 'contract',  icon: FileEdit,        label_en: 'Custom Terms', label_fr: 'Contrat sur mesure' },
  { id: 'settings',  icon: Settings,        label_en: 'Settings',     label_fr: 'Paramètres' },
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
  const [subscription, setSubscription] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

  const loadBroker = useCallback(async () => {
    try {
      const r = await axios.get(`${API_BASE}/brokers/me`, {
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

  const loadAnalytics = useCallback(async () => {
    try {
      const r = await axios.get(`${API_BASE}/brokers/me/analytics`, {
        headers: { Authorization: `Bearer ${_token()}` },
      });
      setAnalytics(r.data);
    } catch { /* noop */ }
  }, []);

  const loadBuyers = useCallback(async () => {
    try {
      const r = await axios.get(`${API_BASE}/broker-relationships/my-buyers`, {
        headers: { Authorization: `Bearer ${_token()}` },
      });
      setBuyers(r.data?.data || []);
    } catch (e) {
      // silent for tab 1; show on tab 2 if error
    }
  }, []);

  useEffect(() => { loadBroker(); }, [loadBroker]);
  useEffect(() => {
    if (!broker) return;
    loadBuyers();
    loadAnalytics();
    // Refresh analytics every 60s for real-time accuracy
    const i = setInterval(loadAnalytics, 60000);
    return () => clearInterval(i);
  }, [broker, loadBuyers, loadAnalytics]);
  useEffect(() => {
    if (!broker) return;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/brokers/me/subscription`, {
          headers: { Authorization: `Bearer ${_token()}` },
        });
        setSubscription(r.data);
      } catch { /* noop */ }
    })();
  }, [broker]);

  // iter397 — Start Stripe Checkout for the broker's annual fee.
  const [payingFee, setPayingFee] = React.useState(false);
  const handlePayAnnualFee = async () => {
    if (payingFee) return;
    setPayingFee(true);
    try {
      const r = await axios.post(
        `${API_BASE}/broker-subscription/create-checkout-session`,
        {},
        { headers: { Authorization: `Bearer ${_token()}` } }
      );
      if (r.data?.already_active) {
        setSubscription((s) => ({ ...(s || {}), status: 'active', expires_at: r.data.expires_at }));
        setPayingFee(false);
        return;
      }
      if (r.data?.checkout_url) {
        window.location.href = r.data.checkout_url;
        return;
      }
      setPayingFee(false);
    } catch (e) {
      setPayingFee(false);
      // Surface the Stripe error in-line via the existing error banner
      setError(e?.response?.data?.detail?.message || e?.response?.data?.detail || 'Checkout failed');
    }
  };

  const handleBuyerAction = async (relId, action) => {
    try {
      const path = action === 'approve'
        ? `/broker-relationships/${relId}/approve`
        : action === 'reject'
        ? `/broker-relationships/${relId}/reject`
        : action === 'suspend'
        ? `/broker-relationships/${relId}/suspend`
        : action === 'terminate'
        ? `/broker-relationships/${relId}/terminate`
        : null;
      if (!path) return;
      await axios.post(`${API_BASE}${path}`, {}, { headers: { Authorization: `Bearer ${_token()}` } });
      await Promise.all([loadBuyers(), loadAnalytics(), loadBroker()]);
    } catch (e) {
      alert(e?.response?.data?.detail?.error || 'Action failed');
    }
  };

  if (loading) return <div className="container mx-auto py-12 text-center text-slate-500">Loading…</div>;
  if (error)   return <div className="container mx-auto py-12 text-center text-rose-500" data-testid="broker-dashboard-error">{String(error)}</div>;

  const pendingBuyers = buyers.filter(b => b.status === 'pending').length;
  const activeBuyers  = buyers.filter(b => b.status === 'active').length;

  return (
    <div className="container mx-auto max-w-7xl py-6 px-4" data-testid="broker-dashboard-page">
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

      {/* iter254 Mission 1 — B2B Partner Program coupon activation card.
          Self-gates on the user's B2B role; non-B2B users see nothing. */}
      <div className="mb-6">
        <B2BCouponActivationCard />
      </div>

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
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-3" data-testid="broker-overview-kpis">
                <KPI label={lang === 'fr' ? 'Acheteurs actifs' : 'Active Buyers'}   value={analytics?.active_buyers ?? activeBuyers} testid="kpi-active-buyers" />
                <KPI label={lang === 'fr' ? 'Demandes en attente' : 'Pending Requests'} value={analytics?.pending_requests ?? pendingBuyers} testid="kpi-pending-buyers" />
                <KPI label={lang === 'fr' ? 'Affaires gagnées' : 'Deals Won'}       value={analytics?.deals_won ?? 0} testid="kpi-deals-won" />
                <KPI label={lang === 'fr' ? 'Revenu total' : 'Total Revenue'}        value={_fmt(analytics?.total_revenue_cad ?? 0)} testid="kpi-revenue" />
                <KPI label={lang === 'fr' ? 'Total acheteurs' : 'Total Buyers'}      value={analytics?.total_buyers ?? buyers.length} testid="kpi-total-buyers" />
              </div>
              <Card><CardContent className="p-5">
                <h3 className="font-semibold mb-2">{lang === 'fr' ? 'Structure de frais' : 'Fee Structure'}</h3>
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  {broker.fee_structure?.type === 'fixed'
                    ? (lang === 'fr' ? `Fixe : ${_fmt(broker.fee_structure.fixed_amount_cad)} par véhicule` : `Fixed: ${_fmt(broker.fee_structure.fixed_amount_cad)} per vehicle`)
                    : (lang === 'fr' ? `Pourcentage : ${(broker.fee_structure?.percentage_rate * 100).toFixed(2)} % du prix final` : `Percentage: ${(broker.fee_structure?.percentage_rate * 100).toFixed(2)}% of hammer price`)}
                </p>
              </CardContent></Card>

              {subscription && (
                <Card data-testid="broker-subscription-card"><CardContent className="p-5">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div>
                      <h3 className="font-semibold mb-1">
                        {lang === 'fr' ? 'Abonnement annuel' : 'Annual Subscription'}
                      </h3>
                      <p className="text-xs text-slate-500">{subscription.plan_name}</p>
                    </div>
                    {(subscription.status === 'free' || subscription.status === 'comp') ? (
                      <Badge className="bg-purple-100 text-purple-800" data-testid="broker-comp-badge">
                        <ShieldCheck className="h-3 w-3 mr-1" />
                        {lang === 'fr' ? 'Accès complimentaire — Partenaire BidVex' : 'Complimentary Access — BidVex Partner'}
                      </Badge>
                    ) : (
                      <Badge className="bg-emerald-100 text-emerald-800">{subscription.status}</Badge>
                    )}
                  </div>
                  <div className="mt-3 flex items-end gap-3 flex-wrap">
                    <span className="text-2xl font-bold" data-testid="broker-sub-final">{_fmt(subscription.final_cad)}</span>
                    {subscription.discount_pct > 0 && (
                      <span className="text-sm text-slate-400 line-through" data-testid="broker-sub-base">{_fmt(subscription.base_cad)}</span>
                    )}
                    <span className="text-xs text-slate-500">{lang === 'fr' ? '/ an' : '/ year'}</span>
                  </div>
                  {subscription.discount_label && subscription.discount_pct > 0 && (
                    <p className="text-xs text-amber-600 mt-1">{subscription.discount_label}</p>
                  )}
                  {subscription.expires_at && (
                    <p className="text-xs text-slate-500 mt-2">
                      {lang === 'fr' ? 'Renouvellement : ' : 'Renews: '}
                      {new Date(subscription.expires_at).toLocaleDateString(lang === 'fr' ? 'fr-CA' : 'en-CA')}
                    </p>
                  )}
                  {/* iter397 — Broker pays their own annual fee via Stripe */}
                  {!(subscription.status === 'active' || subscription.status === 'free' || subscription.status === 'comp') && (
                    <div className="mt-4 flex items-center gap-3 flex-wrap">
                      <Button
                        onClick={handlePayAnnualFee}
                        disabled={payingFee}
                        data-testid="broker-pay-annual-fee-btn"
                        className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      >
                        {payingFee
                          ? (lang === 'fr' ? 'Redirection…' : 'Redirecting…')
                          : (lang === 'fr' ? `Payer ${_fmt(subscription.final_cad)} maintenant` : `Pay ${_fmt(subscription.final_cad)} now`)}
                      </Button>
                      <span className="text-xs text-slate-500">
                        {lang === 'fr' ? 'Paiement sécurisé via Stripe' : 'Secure Stripe Checkout'}
                      </span>
                    </div>
                  )}
                </CardContent></Card>
              )}
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

          {tab === 'ledger'   && <BrokerReconciliationTab lang={lang} />}
          {tab === 'deals'    && <BrokerActiveDealsTab lang={lang} />}
          {tab === 'pipeline' && <BrokerPipelineTab lang={lang} />}
          {tab === 'revenue'  && <BrokerRevenueTab lang={lang} broker={broker} />}
          {tab === 'contract' && <BrokerCustomTermsTab lang={lang} broker={broker} onSaved={loadBroker} />}
          {tab === 'settings' && <BrokerSettingsTab lang={lang} broker={broker} onSaved={loadBroker} />}
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

// ── v6 — Active Deals Kanban ───────────────────────────────────────────
function BrokerActiveDealsTab({ lang }) {
  const [deals, setDeals] = React.useState([]);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    try {
      const t = localStorage.getItem('access_token') || localStorage.getItem('token');
      const r = await axios.get(`${API_BASE}/broker-relationships/active-deals`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      setDeals(r.data?.data || []);
    } catch {
      setDeals([]);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { load(); const i = setInterval(load, 30000); return () => clearInterval(i); }, [load]);

  const columns = [
    { id: 'bidding',  en: 'Watching',  fr: 'Surveille', color: 'bg-slate-100' },
    { id: 'winning',  en: 'Winning',   fr: 'Gagne',     color: 'bg-emerald-100' },
    { id: 'outbid',   en: 'Outbid',    fr: 'Dépassé',   color: 'bg-rose-100' },
    { id: 'won',      en: 'Won',       fr: 'Gagné',     color: 'bg-blue-100' },
  ];

  if (loading) return <div className="text-center text-slate-500 py-12">Loading…</div>;

  return (
    <section data-testid="broker-active-deals">
      <h2 className="text-xl font-semibold mb-4">{lang === 'fr' ? 'Affaires actives' : 'Active Deals'}</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {columns.map(col => {
          const items = deals.filter(d => d.column === col.id);
          return (
            <div key={col.id} className={`${col.color} rounded-lg p-3 min-h-[200px]`} data-testid={`deals-col-${col.id}`}>
              <h3 className="font-semibold text-sm mb-3 flex items-center justify-between">
                <span>{lang === 'fr' ? col.fr : col.en}</span>
                <span className="text-xs bg-white rounded-full px-2 py-0.5">{items.length}</span>
              </h3>
              <div className="space-y-2">
                {items.map(d => (
                  <Card key={d.bid_id} className="p-3 text-xs" data-testid={`deal-${d.bid_id}`}>
                    <div className="font-semibold truncate">{d.vehicle_label}</div>
                    <div className="text-slate-500 truncate">{d.buyer_name || d.buyer_email}</div>
                    <div className="mt-1 flex items-center justify-between">
                      <span>{lang === 'fr' ? 'Notre' : 'Ours'}: ${Number(d.our_bid_amount_cad).toFixed(0)}</span>
                      <span className="text-slate-500">${Number(d.current_bid_cad || 0).toFixed(0)}</span>
                    </div>
                  </Card>
                ))}
                {items.length === 0 && (
                  <div className="text-xs text-slate-500 italic">{lang === 'fr' ? 'Aucun' : 'None'}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ── v6 — Pipeline + Invoices ───────────────────────────────────────────
function BrokerPipelineTab({ lang }) {
  const [invoices, setInvoices] = React.useState([]);
  const [loading, setLoading]   = React.useState(true);
  const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

  const load = React.useCallback(async () => {
    try {
      const r = await axios.get(`${API_BASE}/broker-invoices`, { headers: { Authorization: `Bearer ${_token()}` } });
      setInvoices(r.data?.data || []);
    } catch { setInvoices([]); }
    finally { setLoading(false); }
  }, []);
  React.useEffect(() => { load(); }, [load]);

  const STEPS = ['won', 'invoice_sent', 'paid', 'ready', 'released', 'delivered'];
  const STEP_LABEL = {
    won:          { en: 'Won',           fr: 'Gagné' },
    invoice_sent: { en: 'Invoice Sent',  fr: 'Facture envoyée' },
    paid:         { en: 'Payment Received', fr: 'Paiement reçu' },
    ready:        { en: 'Ready',         fr: 'Prêt' },
    released:     { en: 'Released',      fr: 'Libéré' },
    delivered:    { en: 'Delivered',     fr: 'Livré' },
  };

  const stepIndex = (inv) => {
    if (inv.vehicle_release_status === 'delivered') return 5;
    if (inv.vehicle_release_status === 'released')  return 4;
    if (inv.buyer_payment_status === 'paid')        return 3;
    if (inv.id)                                     return 1;
    return 0;
  };

  const downloadPdf = async (id) => {
    const r = await fetch(`${API_BASE}/broker-invoices/${id}/pdf`, {
      headers: { Authorization: `Bearer ${_token()}` },
    });
    const blob = await r.blob();
    const url  = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `invoice-${id}.pdf`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 500);
  };
  const markPaid = async (id) => {
    // v7 — broker manually confirms direct hammer payment received
    const ok = window.confirm(
      lang === 'fr'
        ? 'Confirmez-vous avoir reçu le prix marteau directement de l\'acheteur (virement / chèque certifié / compte en fiducie) ?'
        : 'Do you confirm you received the hammer payment directly from the buyer (wire / certified cheque / trust account)?'
    );
    if (!ok) return;
    await axios.patch(`${API_BASE}/broker-invoices/${id}/mark-paid`, {
      hammer_received_confirmed: true,
      payment_method: 'wire',
    }, { headers: { Authorization: `Bearer ${_token()}` } });
    load();
  };
  const release  = async (id) => {
    await axios.post(`${API_BASE}/broker-invoices/${id}/release-vehicle`, {}, { headers: { Authorization: `Bearer ${_token()}` } });
    load();
  };

  // ── v8 — Title transfer logging ─────────────────────────────────
  const [ttOpen, setTtOpen] = React.useState(null);   // invoice obj or null
  const [ttForm, setTtForm] = React.useState({ registry_tx_number: '', province: 'QC', transfer_date: new Date().toISOString().slice(0, 10) });
  const [ttSaving, setTtSaving] = React.useState(false);
  const REGISTRY_BY_PROVINCE = {
    QC: 'SAAQ', ON: 'ServiceOntario', AB: 'AMVIC / Alberta Registries',
    BC: 'ICBC', MB: 'Manitoba Public Insurance', SK: 'SGI',
    NS: 'Service Nova Scotia', NB: 'Service New Brunswick',
    NL: 'Motor Registration Division', PE: 'Access PEI', OTHER: 'Provincial Registry',
  };
  const submitTitleTransfer = async () => {
    if (!ttOpen || !ttForm.registry_tx_number.trim()) return;
    setTtSaving(true);
    try {
      await axios.patch(`${API_BASE}/broker-invoices/${ttOpen.id}/log-title-transfer`, {
        registry_tx_number: ttForm.registry_tx_number.trim(),
        province:           ttForm.province,
        transfer_date:      new Date(ttForm.transfer_date).toISOString(),
      }, { headers: { Authorization: `Bearer ${_token()}` } });
      setTtOpen(null);
      setTtForm({ registry_tx_number: '', province: 'QC', transfer_date: new Date().toISOString().slice(0, 10) });
      load();
    } finally {
      setTtSaving(false);
    }
  };
  const releasedAt = (inv) => inv.released_at ? new Date(inv.released_at) : null;
  const daysSinceRelease = (inv) => {
    const d = releasedAt(inv);
    return d ? Math.floor((Date.now() - d.getTime()) / 86400000) : null;
  };

  if (loading) return <div className="text-center text-slate-500 py-12">Loading…</div>;

  return (
    <section data-testid="broker-pipeline">
      <h2 className="text-xl font-semibold mb-4">{lang === 'fr' ? 'Pipeline post-enchère' : 'Post-Auction Pipeline'}</h2>
      {invoices.length === 0 ? (
        <Card><CardContent className="p-8 text-center text-slate-500">{lang === 'fr' ? 'Aucune facture pour le moment.' : 'No invoices yet.'}</CardContent></Card>
      ) : (
        <div className="space-y-3">
          {invoices.map(inv => {
            const idx = stepIndex(inv);
            return (
              <Card key={inv.id} data-testid={`invoice-row-${inv.id}`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-3 flex-wrap mb-3">
                    <div>
                      <div className="font-semibold">{inv.invoice_number}</div>
                      <div className="text-xs text-slate-500">{lang === 'fr' ? 'Véhicule' : 'Vehicle'}: {inv.vehicle_listing_id}</div>
                      <div className="text-xs text-slate-500">{lang === 'fr' ? 'Code de retrait' : 'Pickup code'}: <code>{inv.pickup_code}</code></div>
                    </div>
                    <div className="text-right">
                      <div className="text-lg font-bold">${Number(inv.total_cad).toFixed(2)} CAD</div>
                      <Badge>{inv.buyer_payment_status}</Badge>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 mb-3 overflow-x-auto">
                    {STEPS.map((s, i) => (
                      <React.Fragment key={s}>
                        <div className={`px-2 py-1 rounded text-[10px] whitespace-nowrap ${i <= idx ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-slate-500'}`}>
                          {lang === 'fr' ? STEP_LABEL[s].fr : STEP_LABEL[s].en}
                        </div>
                        {i < STEPS.length - 1 && <div className={`h-0.5 w-3 ${i < idx ? 'bg-emerald-500' : 'bg-slate-200'}`} />}
                      </React.Fragment>
                    ))}
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <Button size="sm" variant="outline" onClick={() => downloadPdf(inv.id)} data-testid={`invoice-pdf-${inv.id}`}>
                      📄 {lang === 'fr' ? 'PDF' : 'PDF'}
                    </Button>
                    {inv.buyer_payment_status !== 'paid' && (
                      <Button size="sm" onClick={() => markPaid(inv.id)} data-testid={`invoice-mark-paid-${inv.id}`}>
                        ✓ {lang === 'fr' ? 'Marquer payé' : 'Mark Paid'}
                      </Button>
                    )}
                    {inv.buyer_payment_status === 'paid' && inv.vehicle_release_status !== 'released' && (
                      <Button size="sm" onClick={() => release(inv.id)} data-testid={`invoice-release-${inv.id}`}>
                        🚚 {lang === 'fr' ? 'Libérer véhicule' : 'Release Vehicle'}
                      </Button>
                    )}
                    {/* v8 — Title transfer logger (post-release) */}
                    {inv.released_at && !inv.title_transfer_logged_at && (
                      <Button
                        size="sm"
                        variant={daysSinceRelease(inv) > 14 ? 'destructive' : 'default'}
                        className={daysSinceRelease(inv) > 14 ? '' : 'bg-amber-500 hover:bg-amber-600 text-white'}
                        onClick={() => setTtOpen(inv)}
                        data-testid={`invoice-log-title-${inv.id}`}
                      >
                        📋 {daysSinceRelease(inv) > 14
                          ? (lang === 'fr' ? 'Transfert en retard — consigner' : 'Title overdue — log now')
                          : (lang === 'fr' ? 'Consigner le transfert de propriété' : 'Log Title Transfer')}
                      </Button>
                    )}
                    {inv.title_transfer_logged_at && (
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-emerald-100 text-emerald-800" data-testid={`title-filed-${inv.id}`}>
                        ✅ {lang === 'fr' ? 'Transfert déposé' : 'Title Transfer Filed'} · {inv.title_transfer_registry} {inv.title_transfer_tx_number}
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* v8 — Title transfer modal */}
      {ttOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => !ttSaving && setTtOpen(null)} data-testid="title-transfer-modal">
          <div className="bg-white dark:bg-slate-900 rounded-lg max-w-md w-full p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold">
              {lang === 'fr' ? 'Consigner le transfert de propriété' : 'Log Title Transfer'}
            </h3>
            <p className="text-xs text-slate-500">
              {lang === 'fr'
                ? 'Doit être consigné dans les 14 jours suivant la remise du véhicule (obligation OPC / SAAQ / OMVIC).'
                : 'Required within 14 days of vehicle release (OPC / SAAQ / OMVIC obligation).'}
            </p>
            <div>
              <label className="text-xs text-slate-500">{lang === 'fr' ? 'Province' : 'Province'}</label>
              <select
                value={ttForm.province}
                onChange={(e) => setTtForm(f => ({ ...f, province: e.target.value }))}
                className="w-full mt-1 px-3 py-2 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm"
                data-testid="title-transfer-province"
              >
                {Object.keys(REGISTRY_BY_PROVINCE).map(p => (
                  <option key={p} value={p}>{p} — {REGISTRY_BY_PROVINCE[p]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-500">{lang === 'fr' ? 'Numéro de transaction du registre' : 'Provincial Registry Transaction #'} *</label>
              <input
                value={ttForm.registry_tx_number}
                onChange={(e) => setTtForm(f => ({ ...f, registry_tx_number: e.target.value }))}
                placeholder="e.g. SAAQ-2026-12345"
                className="w-full mt-1 px-3 py-2 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm"
                data-testid="title-transfer-tx-number"
              />
            </div>
            <div>
              <label className="text-xs text-slate-500">{lang === 'fr' ? 'Date du transfert' : 'Transfer Date'} *</label>
              <input
                type="date"
                value={ttForm.transfer_date}
                onChange={(e) => setTtForm(f => ({ ...f, transfer_date: e.target.value }))}
                className="w-full mt-1 px-3 py-2 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm"
                data-testid="title-transfer-date"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setTtOpen(null)} disabled={ttSaving}>
                {lang === 'fr' ? 'Annuler' : 'Cancel'}
              </Button>
              <Button
                onClick={submitTitleTransfer}
                disabled={ttSaving || !ttForm.registry_tx_number.trim()}
                className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white"
                data-testid="title-transfer-submit"
              >
                {ttSaving ? (lang === 'fr' ? 'Envoi…' : 'Saving…') : (lang === 'fr' ? 'Consigner' : 'File Transfer')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

// ── v8.1 — Revenue + Settings (Stripe Connect onboarding live) ────────
function BrokerRevenueTab({ lang, broker }) {
  const [invoices, setInvoices]       = React.useState([]);
  const [stripeStatus, setStripeStatus] = React.useState(null);
  const [linking, setLinking]         = React.useState(false);
  const [linkError, setLinkError]     = React.useState(null);

  const t = () => localStorage.getItem('access_token') || localStorage.getItem('token');
  const auth = { headers: { Authorization: `Bearer ${t()}` } };

  React.useEffect(() => {
    axios.get(`${API_BASE}/broker-invoices`, auth).then(r => setInvoices(r.data?.data || [])).catch(() => {});
    axios.get(`${API_BASE}/stripe/broker-connect-status`, auth).then(r => setStripeStatus(r.data)).catch(() => setStripeStatus({ onboarded: false }));
  }, []);

  const startOnboarding = async () => {
    setLinking(true); setLinkError(null);
    try {
      const r = await axios.get(`${API_BASE}/stripe/connect-onboarding-link`, auth);
      if (r.data?.onboarding_url) {
        window.location.href = r.data.onboarding_url;
      } else {
        setLinkError('Failed to obtain onboarding URL.');
      }
    } catch (e) {
      setLinkError(e?.response?.data?.detail?.error || e?.response?.data?.detail?.message_en || 'Stripe link unavailable.');
    } finally {
      setLinking(false);
    }
  };

  const totals = invoices.reduce((acc, i) => ({
    hammer: acc.hammer + Number(i.hammer_price_cad || 0),
    broker: acc.broker + Number(i.broker_fee_cad || 0),
    bidvex: acc.bidvex + Number(i.bidvex_platform_fee_cad || 0),
  }), { hammer: 0, broker: 0, bidvex: 0 });

  return (
    <section data-testid="broker-revenue">
      <h2 className="text-xl font-semibold mb-4">{lang === 'fr' ? 'Revenus et paiements' : 'Revenue & Payouts'}</h2>

      {/* Stripe Connect onboarding */}
      {stripeStatus && !stripeStatus.onboarded && (
        <Card className="mb-4 border-2 border-amber-300 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-950/30 dark:to-orange-950/30" data-testid="stripe-connect-cta">
          <CardContent className="p-5">
            <div className="flex items-start gap-3 flex-wrap">
              <div className="text-3xl">💰</div>
              <div className="flex-1 min-w-[200px]">
                <h3 className="font-semibold text-lg mb-1">
                  {lang === 'fr' ? 'Monétisez votre licence' : 'Monetize Your License'}
                </h3>
                <p className="text-sm text-slate-700 dark:text-slate-200">
                  {lang === 'fr'
                    ? 'Connectez votre compte bancaire via Stripe pour recevoir des paiements automatiques des frais de service de BidVex.'
                    : 'Connect your bank account via Stripe to receive automated service fee payouts from BidVex.'}
                </p>
                {linkError && <p className="text-xs text-rose-600 mt-2">{String(linkError)}</p>}
              </div>
              <Button
                onClick={startOnboarding}
                disabled={linking}
                className="bg-amber-500 hover:bg-amber-600 text-white"
                data-testid="stripe-connect-start"
              >
                {linking ? '...' : (lang === 'fr' ? 'Connecter Stripe' : 'Connect Stripe Account')}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {stripeStatus && stripeStatus.onboarded && (
        <Card className="mb-4 border-emerald-200 bg-emerald-50 dark:bg-emerald-950/30" data-testid="stripe-connect-status">
          <CardContent className="p-4 flex items-center justify-between gap-3 flex-wrap">
            <div>
              <p className="font-semibold text-sm text-emerald-800 dark:text-emerald-200 flex items-center gap-1.5">
                ✅ {lang === 'fr' ? 'Stripe Connect connecté' : 'Stripe Connect connected'}
              </p>
              <p className="text-xs text-emerald-700 dark:text-emerald-300">{stripeStatus.connect_account_id}</p>
            </div>
            {stripeStatus.balance && (
              <div className="text-right">
                <p className="text-[11px] uppercase text-slate-500">{lang === 'fr' ? 'Solde disponible' : 'Available balance'}</p>
                <p className="text-lg font-bold text-emerald-700 dark:text-emerald-300">${Number(stripeStatus.balance.available_cad || 0).toFixed(2)} CAD</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-3 gap-3 mb-4">
        <KPI label={lang === 'fr' ? 'Total prix final' : 'Total Hammer'}        value={`$${totals.hammer.toFixed(0)}`} testid="rev-hammer" />
        <KPI label={lang === 'fr' ? 'Frais courtier' : 'Broker Fees'}            value={`$${totals.broker.toFixed(0)}`} testid="rev-broker" />
        <KPI label={lang === 'fr' ? 'Commission BidVex' : 'BidVex Commission'}  value={`$${totals.bidvex.toFixed(0)}`} testid="rev-bidvex" />
      </div>
      <Card><CardContent className="p-4">
        <h3 className="font-semibold mb-2">{lang === 'fr' ? 'Historique des paiements' : 'Payout History'}</h3>
        {invoices.length === 0 ? (
          <p className="text-sm text-slate-500">{lang === 'fr' ? 'Aucun paiement encore.' : 'No payouts yet.'}</p>
        ) : (
          <table className="w-full text-sm" data-testid="payout-history-table">
            <thead><tr className="text-left text-xs text-slate-500 border-b"><th className="py-2">#</th><th>{lang === 'fr' ? 'Date' : 'Date'}</th><th>{lang === 'fr' ? 'Prix final' : 'Hammer'}</th><th>{lang === 'fr' ? 'Frais' : 'Fee'}</th><th>{lang === 'fr' ? 'Statut' : 'Status'}</th></tr></thead>
            <tbody>
              {invoices.map(i => (
                <tr key={i.id} className="border-b">
                  <td className="py-2">{i.invoice_number}</td>
                  <td>{i.created_at ? new Date(i.created_at).toLocaleDateString() : '—'}</td>
                  <td>${Number(i.hammer_price_cad).toFixed(0)}</td>
                  <td>${Number(i.broker_fee_cad).toFixed(0)}</td>
                  <td><Badge>{i.buyer_payment_status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent></Card>
    </section>
  );
}

function BrokerSettingsTab({ lang, broker, onSaved }) {
  const [feeType, setFeeType] = React.useState(broker.fee_structure?.type || 'fixed');
  const [fixed, setFixed]     = React.useState(broker.fee_structure?.fixed_amount_cad || 0);
  const [pct, setPct]         = React.useState((broker.fee_structure?.percentage_rate || 0) * 100);
  const [minF, setMinF]       = React.useState(broker.fee_structure?.min_fee_cad ?? '');
  const [maxF, setMaxF]       = React.useState(broker.fee_structure?.max_fee_cad ?? '');
  const [deposit, setDeposit] = React.useState(broker.default_deposit_amount_cad || 500);
  const [saving, setSaving]   = React.useState(false);
  const [msg, setMsg]         = React.useState(null);

  const sample = 15000;
  const preview = (() => {
    let raw = feeType === 'fixed' ? Number(fixed) : sample * (Number(pct) / 100);
    if (minF !== '' && !Number.isNaN(Number(minF))) raw = Math.max(raw, Number(minF));
    if (maxF !== '' && !Number.isNaN(Number(maxF))) raw = Math.min(raw, Number(maxF));
    return raw;
  })();

  const save = async () => {
    setSaving(true); setMsg(null);
    try {
      const t = localStorage.getItem('access_token') || localStorage.getItem('token');
      await axios.patch(`${API_BASE}/brokers/settings`, {
        fee_structure: {
          type: feeType,
          fixed_amount_cad: Number(fixed) || 0,
          percentage_rate:  feeType === 'percentage' ? (Number(pct) || 0) / 100 : 0,
          min_fee_cad:      minF === '' ? null : Number(minF),
          max_fee_cad:      maxF === '' ? null : Number(maxF),
        },
        default_deposit_amount_cad: Number(deposit) || 500,
      }, { headers: { Authorization: `Bearer ${t}` } });
      setMsg({ kind: 'ok', text: lang === 'fr' ? '✅ Enregistré' : '✅ Saved' });
      if (onSaved) onSaved();
    } catch (e) {
      setMsg({ kind: 'err', text: e?.response?.data?.detail?.error || 'Failed' });
    } finally { setSaving(false); }
  };

  return (
    <section className="space-y-4" data-testid="broker-settings">
      <h2 className="text-xl font-semibold">{lang === 'fr' ? 'Paramètres' : 'Settings'}</h2>
      <Card><CardContent className="p-5 space-y-4">
        <div>
          <label className="text-sm font-medium">{lang === 'fr' ? 'Type de frais' : 'Fee Type'}</label>
          <div className="flex gap-2 mt-1">
            <button onClick={() => setFeeType('fixed')} className={`flex-1 p-2 rounded border-2 text-sm ${feeType === 'fixed' ? 'border-blue-600 bg-blue-50' : 'border-slate-200'}`} data-testid="settings-fee-fixed">
              {lang === 'fr' ? 'Fixe' : 'Fixed'}
            </button>
            <button onClick={() => setFeeType('percentage')} className={`flex-1 p-2 rounded border-2 text-sm ${feeType === 'percentage' ? 'border-blue-600 bg-blue-50' : 'border-slate-200'}`} data-testid="settings-fee-pct">
              {lang === 'fr' ? 'Pourcentage' : 'Percentage'}
            </button>
          </div>
        </div>
        {feeType === 'fixed' ? (
          <div>
            <label className="text-sm">{lang === 'fr' ? 'Montant fixe ($)' : 'Fixed Amount ($)'}</label>
            <input type="number" value={fixed} onChange={(e) => setFixed(e.target.value)} className="w-full px-3 py-2 rounded border" data-testid="settings-fixed-input" />
          </div>
        ) : (
          <div>
            <label className="text-sm">{lang === 'fr' ? 'Pourcentage (%)' : 'Percentage (%)'}</label>
            <input type="number" value={pct} onChange={(e) => setPct(e.target.value)} className="w-full px-3 py-2 rounded border" data-testid="settings-pct-input" />
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <div><label className="text-sm">{lang === 'fr' ? 'Frais min.' : 'Min Fee'}</label><input type="number" value={minF} onChange={(e) => setMinF(e.target.value)} className="w-full px-3 py-2 rounded border" data-testid="settings-min-input" /></div>
          <div><label className="text-sm">{lang === 'fr' ? 'Frais max.' : 'Max Fee'}</label><input type="number" value={maxF} onChange={(e) => setMaxF(e.target.value)} className="w-full px-3 py-2 rounded border" data-testid="settings-max-input" /></div>
        </div>
        <div>
          <label className="text-sm">{lang === 'fr' ? 'Dépôt par défaut ($)' : 'Default Deposit ($)'}</label>
          <input type="number" min="100" value={deposit} onChange={(e) => setDeposit(e.target.value)} className="w-full px-3 py-2 rounded border" data-testid="settings-deposit-input" />
        </div>
        <Alert className="bg-blue-50 border-blue-200">
          <AlertDescription data-testid="settings-preview">
            {lang === 'fr' ? `Sur un véhicule de 15 000 $, vos frais seraient : $${preview.toFixed(2)}` : `On a $15,000 vehicle your fee would be: $${preview.toFixed(2)}`}
          </AlertDescription>
        </Alert>
        {msg && (
          <div className={msg.kind === 'ok' ? 'text-emerald-600 text-sm' : 'text-rose-600 text-sm'} data-testid="settings-msg">{msg.text}</div>
        )}
        <Button onClick={save} disabled={saving} className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white" data-testid="settings-save">
          {saving ? '…' : (lang === 'fr' ? 'Enregistrer' : 'Save Changes')}
        </Button>
      </CardContent></Card>
    </section>
  );
}

// ── iter225 Task 1 — Buyer Reconciliation Matrix Tab ──────────────────
function BrokerReconciliationTab({ lang }) {
  const [data, setData]       = React.useState({ rows: [], totals: null });
  const [loading, setLoading] = React.useState(true);
  const [error, setError]     = React.useState(null);
  const [q, setQ]             = React.useState('');
  const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

  const load = React.useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await axios.get(`${API_BASE}/broker-relationships/buyer-ledger`, {
        headers: { Authorization: `Bearer ${_token()}` },
      });
      setData({ rows: r.data?.data || [], totals: r.data?.totals || null });
    } catch (e) {
      setError(e?.response?.data?.detail?.error || 'failed_to_load_ledger');
    } finally {
      setLoading(false);
    }
  }, []);
  React.useEffect(() => { load(); const i = setInterval(load, 60000); return () => clearInterval(i); }, [load]);

  const filtered = (data.rows || []).filter(r => {
    if (!q.trim()) return true;
    const needle = q.toLowerCase();
    return (
      (r.buyer_email     || '').toLowerCase().includes(needle) ||
      (r.buyer_full_name || '').toLowerCase().includes(needle)
    );
  });

  if (loading) return <div className="text-center text-slate-500 py-12">Loading…</div>;
  if (error)   return <div className="text-center text-rose-500 py-12" data-testid="ledger-error">{String(error)}</div>;

  return (
    <section className="space-y-4" data-testid="broker-reconciliation">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-semibold">{lang === 'fr' ? 'Matrice de réconciliation' : 'Reconciliation Matrix'}</h2>
          <p className="text-xs text-slate-500">
            {lang === 'fr'
              ? 'Ledger isolé : pour chaque acheteur géré, voyez ses enchères actives, gagnées et perdues.'
              : 'Isolated ledger: for every managed buyer, see their Active, Won, and Lost auctions.'}
          </p>
        </div>
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={lang === 'fr' ? 'Filtrer par e-mail / nom…' : 'Filter by email / name…'}
          className="px-3 py-2 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm w-full sm:w-64"
          data-testid="ledger-filter-input"
        />
      </div>

      {data.totals && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3" data-testid="ledger-totals">
          <KPI label={lang === 'fr' ? 'Acheteurs' : 'Buyers'} value={data.totals.buyers} testid="ledger-kpi-buyers" />
          <KPI label={lang === 'fr' ? 'Actives' : 'Active'} value={data.totals.active} testid="ledger-kpi-active" />
          <KPI label={lang === 'fr' ? 'Gagnées' : 'Won'} value={data.totals.won} testid="ledger-kpi-won" />
          <KPI label={lang === 'fr' ? 'Perdues' : 'Lost'} value={data.totals.lost} testid="ledger-kpi-lost" />
          <KPI label={lang === 'fr' ? 'Total enchéri (CAD)' : 'Total Bid (CAD)'} value={_fmt(data.totals.total_bid_cad)} testid="ledger-kpi-amount" />
        </div>
      )}

      {filtered.length === 0 ? (
        <Card data-testid="ledger-empty"><CardContent className="p-8 text-center text-slate-500">
          {lang === 'fr' ? 'Aucun acheteur correspondant.' : 'No matching buyers.'}
        </CardContent></Card>
      ) : (
        <Card><CardContent className="p-0 overflow-x-auto">
          <table className="w-full text-sm" data-testid="ledger-table">
            <thead>
              <tr className="text-left text-xs text-slate-500 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800">
                <th className="py-2 px-3">{lang === 'fr' ? 'Acheteur' : 'Buyer'}</th>
                <th className="px-3">{lang === 'fr' ? 'Statut' : 'Status'}</th>
                <th className="px-3">{lang === 'fr' ? 'Dépôt' : 'Deposit'}</th>
                <th className="px-3 text-center text-amber-700">{lang === 'fr' ? 'Actives' : 'Active'}</th>
                <th className="px-3 text-center text-emerald-700">{lang === 'fr' ? 'Gagnées' : 'Won'}</th>
                <th className="px-3 text-center text-rose-700">{lang === 'fr' ? 'Perdues' : 'Lost'}</th>
                <th className="px-3 text-right">{lang === 'fr' ? 'Total $' : 'Total $'}</th>
                <th className="px-3">{lang === 'fr' ? 'Contrat' : 'Contract'}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.relationship_id} className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40" data-testid={`ledger-row-${r.relationship_id}`}>
                  <td className="py-3 px-3">
                    <div className="font-medium text-slate-900 dark:text-white">{r.buyer_full_name || r.buyer_email}</div>
                    <div className="text-[11px] text-slate-500">{r.buyer_email}</div>
                  </td>
                  <td className="px-3"><Badge className="bg-slate-100 text-slate-700">{r.status}</Badge></td>
                  <td className="px-3"><Badge variant="outline">{r.deposit_status}</Badge></td>
                  <td className="px-3 text-center font-mono font-semibold text-amber-700" data-testid={`ledger-active-${r.relationship_id}`}>{r.active_auctions}</td>
                  <td className="px-3 text-center font-mono font-semibold text-emerald-700" data-testid={`ledger-won-${r.relationship_id}`}>{r.won_auctions}</td>
                  <td className="px-3 text-center font-mono font-semibold text-rose-700" data-testid={`ledger-lost-${r.relationship_id}`}>{r.lost_auctions}</td>
                  <td className="px-3 text-right font-mono">{_fmt(r.total_bid_amount_cad)}</td>
                  <td className="px-3">
                    {r.custom_terms_accepted_at ? (
                      <span className="inline-flex items-center gap-1 text-emerald-700 text-[11px]">
                        <CheckCircle2 className="w-3 h-3" />
                        {lang === 'fr' ? 'Accepté' : 'Accepted'}
                      </span>
                    ) : (
                      <span className="text-[11px] text-slate-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent></Card>
      )}
    </section>
  );
}

// ── iter225 Task 4 — Custom Broker-Buyer Contract Editor Tab ───────────
function BrokerCustomTermsTab({ lang, broker, onSaved }) {
  const initialHtml = broker?.custom_terms_html || '';
  const [html, setHtml]       = React.useState(initialHtml);
  const [enabled, setEnabled] = React.useState(Boolean(broker?.custom_terms_enabled));
  const [saving, setSaving]   = React.useState(false);
  const [msg, setMsg]         = React.useState(null);
  const editorRef = React.useRef(null);

  React.useEffect(() => {
    if (editorRef.current && editorRef.current.innerHTML !== initialHtml) {
      editorRef.current.innerHTML = initialHtml;
    }
  }, []);  // eslint-disable-line

  const cmd = (action, value = null) => {
    document.execCommand(action, false, value);
    if (editorRef.current) {
      setHtml(editorRef.current.innerHTML);
    }
  };

  const onInput = (e) => setHtml(e.currentTarget.innerHTML);

  const save = async () => {
    setSaving(true); setMsg(null);
    try {
      const token = localStorage.getItem('access_token') || localStorage.getItem('token');
      const tmp = document.createElement('div');
      tmp.innerHTML = html;
      const plain = (tmp.textContent || tmp.innerText || '').trim();
      await axios.patch(`${API_BASE}/brokers/custom-terms`, {
        custom_terms_html: html,
        custom_terms_plain: plain,
        enabled,
      }, { headers: { Authorization: `Bearer ${token}` } });
      setMsg({ kind: 'ok', text: lang === 'fr' ? '✅ Enregistré' : '✅ Saved' });
      if (onSaved) onSaved();
    } catch (e) {
      setMsg({ kind: 'err', text: e?.response?.data?.detail?.error || 'Save failed' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="space-y-4" data-testid="broker-custom-terms-tab">
      <div>
        <h2 className="text-xl font-semibold">{lang === 'fr' ? 'Contrat sur mesure courtier-acheteur' : 'Custom Broker-Buyer Contract'}</h2>
        <p className="text-xs text-slate-500 mt-1 max-w-2xl">
          {lang === 'fr'
            ? 'Rédigez les conditions qui s\'appliquent aux acheteurs qui se lient à vous. Lorsque cette option est activée, les acheteurs doivent accepter explicitement ce contrat avant de pouvoir enchérir sous votre licence.'
            : 'Draft the rules that apply to buyers linked to you. When enabled, buyers must explicitly accept this contract before they can bid under your license.'}
        </p>
      </div>

      <Card><CardContent className="p-4 space-y-3">
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            className="h-5 w-5 accent-amber-600"
            data-testid="custom-terms-enabled-toggle"
          />
          <span className="text-sm font-medium">
            {lang === 'fr'
              ? 'Exiger que chaque acheteur accepte ce contrat avant d\'enchérir'
              : 'Require every buyer to accept this contract before bidding'}
          </span>
        </label>

        <div className="flex flex-wrap items-center gap-1 px-2 py-1.5 border border-slate-200 dark:border-slate-700 rounded-t-md bg-slate-50 dark:bg-slate-800">
          <button type="button" onClick={() => cmd('bold')} className="px-2 py-1 text-xs font-bold rounded hover:bg-slate-200 dark:hover:bg-slate-700" data-testid="rte-bold">B</button>
          <button type="button" onClick={() => cmd('italic')} className="px-2 py-1 text-xs italic rounded hover:bg-slate-200 dark:hover:bg-slate-700" data-testid="rte-italic">I</button>
          <button type="button" onClick={() => cmd('underline')} className="px-2 py-1 text-xs underline rounded hover:bg-slate-200 dark:hover:bg-slate-700" data-testid="rte-underline">U</button>
          <span className="w-px h-4 bg-slate-300 dark:bg-slate-600 mx-1" />
          <button type="button" onClick={() => cmd('formatBlock', 'H3')} className="px-2 py-1 text-xs rounded hover:bg-slate-200 dark:hover:bg-slate-700" data-testid="rte-h3">H3</button>
          <button type="button" onClick={() => cmd('formatBlock', 'P')} className="px-2 py-1 text-xs rounded hover:bg-slate-200 dark:hover:bg-slate-700" data-testid="rte-p">P</button>
          <button type="button" onClick={() => cmd('insertUnorderedList')} className="px-2 py-1 text-xs rounded hover:bg-slate-200 dark:hover:bg-slate-700" data-testid="rte-ul">• List</button>
          <button type="button" onClick={() => cmd('insertOrderedList')} className="px-2 py-1 text-xs rounded hover:bg-slate-200 dark:hover:bg-slate-700" data-testid="rte-ol">1. List</button>
          <span className="w-px h-4 bg-slate-300 dark:bg-slate-600 mx-1" />
          <button
            type="button"
            onClick={() => {
              const url = window.prompt(lang === 'fr' ? 'Lien :' : 'Link URL:');
              if (url) cmd('createLink', url);
            }}
            className="px-2 py-1 text-xs rounded hover:bg-slate-200 dark:hover:bg-slate-700"
            data-testid="rte-link"
          >
            🔗
          </button>
          <button type="button" onClick={() => cmd('removeFormat')} className="px-2 py-1 text-xs rounded hover:bg-slate-200 dark:hover:bg-slate-700" data-testid="rte-clear">↺</button>
        </div>

        <div
          ref={editorRef}
          contentEditable
          suppressContentEditableWarning
          onInput={onInput}
          className="min-h-[280px] max-h-[480px] overflow-y-auto px-4 py-3 border-x border-b border-slate-200 dark:border-slate-700 rounded-b-md bg-white dark:bg-slate-900 prose prose-sm dark:prose-invert max-w-none focus:outline-none focus:ring-2 focus:ring-blue-500"
          data-testid="custom-terms-editor"
        />
        <p className="text-[11px] text-slate-500">
          {lang === 'fr'
            ? 'Maximum 50 000 caractères. Le contenu HTML est conservé tel quel ; rédigez clairement.'
            : 'Maximum 50,000 characters. HTML is preserved verbatim; keep the wording clear and legally precise.'}
        </p>
        {msg && (
          <div className={msg.kind === 'ok' ? 'text-emerald-600 text-sm' : 'text-rose-600 text-sm'} data-testid="custom-terms-msg">{msg.text}</div>
        )}
        <div className="flex justify-end">
          <Button
            onClick={save}
            disabled={saving}
            className="bg-gradient-to-r from-amber-500 to-orange-500 text-white"
            data-testid="custom-terms-save"
          >
            <Save className="w-4 h-4 mr-1.5" />
            {saving ? '…' : (lang === 'fr' ? 'Enregistrer le contrat' : 'Save Contract')}
          </Button>
        </div>
      </CardContent></Card>
    </section>
  );
}


