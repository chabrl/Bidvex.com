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
  { id: 'deals',     icon: Car,             label_en: 'Active Deals', label_fr: 'Affaires actives' },
  { id: 'pipeline',  icon: ClipboardList,   label_en: 'Pipeline',     label_fr: 'Pipeline' },
  { id: 'revenue',   icon: DollarSign,      label_en: 'Revenue',      label_fr: 'Revenus' },
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

          {tab === 'deals'    && <BrokerActiveDealsTab lang={lang} />}
          {tab === 'pipeline' && <BrokerPipelineTab lang={lang} />}
          {tab === 'revenue'  && <BrokerRevenueTab lang={lang} broker={broker} />}
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
      const r = await axios.get(`${API_BASE}/api/broker-relationships/active-deals`, {
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
      const r = await axios.get(`${API_BASE}/api/broker-invoices`, { headers: { Authorization: `Bearer ${_token()}` } });
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
    const r = await fetch(`${API_BASE}/api/broker-invoices/${id}/pdf`, {
      headers: { Authorization: `Bearer ${_token()}` },
    });
    const blob = await r.blob();
    const url  = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `invoice-${id}.pdf`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 500);
  };
  const markPaid = async (id) => {
    await axios.patch(`${API_BASE}/api/broker-invoices/${id}/mark-paid`, {}, { headers: { Authorization: `Bearer ${_token()}` } });
    load();
  };
  const release  = async (id) => {
    await axios.post(`${API_BASE}/api/broker-invoices/${id}/release-vehicle`, {}, { headers: { Authorization: `Bearer ${_token()}` } });
    load();
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
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </section>
  );
}

// ── v6 — Revenue + Settings ────────────────────────────────────────────
function BrokerRevenueTab({ lang, broker }) {
  const [invoices, setInvoices] = React.useState([]);
  React.useEffect(() => {
    const t = localStorage.getItem('access_token') || localStorage.getItem('token');
    axios.get(`${API_BASE}/api/broker-invoices`, { headers: { Authorization: `Bearer ${t}` } })
      .then(r => setInvoices(r.data?.data || [])).catch(() => {});
  }, []);
  const totals = invoices.reduce((acc, i) => ({
    hammer: acc.hammer + Number(i.hammer_price_cad || 0),
    broker: acc.broker + Number(i.broker_fee_cad || 0),
    bidvex: acc.bidvex + Number(i.bidvex_platform_fee_cad || 0),
  }), { hammer: 0, broker: 0, bidvex: 0 });

  return (
    <section data-testid="broker-revenue">
      <h2 className="text-xl font-semibold mb-4">{lang === 'fr' ? 'Revenus et paiements' : 'Revenue & Payouts'}</h2>
      <Alert className="mb-4 border-blue-200 bg-blue-50 dark:bg-blue-950/30">
        <AlertDescription>
          {lang === 'fr'
            ? '🔗 Configuration Stripe Connect — bientôt disponible. Vos paiements seront transférés vers votre compte une fois Stripe Connect activé.'
            : '🔗 Stripe Connect onboarding — coming soon. Your payouts will transfer to your account once Stripe Connect is enabled.'}
        </AlertDescription>
      </Alert>
      <div className="grid grid-cols-3 gap-3 mb-4">
        <KPI label={lang === 'fr' ? 'Total prix final' : 'Total Hammer'} value={`$${totals.hammer.toFixed(0)}`} testid="rev-hammer" />
        <KPI label={lang === 'fr' ? 'Frais courtier' : 'Broker Fees'}     value={`$${totals.broker.toFixed(0)}`} testid="rev-broker" />
        <KPI label={lang === 'fr' ? 'Commission BidVex' : 'BidVex Commission'} value={`$${totals.bidvex.toFixed(0)}`} testid="rev-bidvex" />
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
      await axios.patch(`${API_BASE}/api/brokers/settings`, {
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

