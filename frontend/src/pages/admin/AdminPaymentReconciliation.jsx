/**
 * iter482 P6 — Admin Payment Reconciliation Dashboard
 * ====================================================
 *
 * Read-only audit surface for BidVex operations. Backed by
 *   /api/admin/stripe-reconciliation
 *   /api/admin/stripe-reconciliation/summary
 *   /api/admin/stripe-reconciliation/{payment_intent_id}
 *
 * Design invariants:
 *   • Backend is authoritative — this page never recalculates money.
 *   • Cent totals arrive as integers from the backend; formatting is
 *     the ONLY frontend responsibility.
 *   • Status vocabulary is the P6-canonical set
 *     RECONCILED / VARIANCE / SHORTFALL / PENDING / ERROR
 *     (mirrored in ``services/stripe_reconciliation_service.public_status``).
 *   • Bilingual EN/FR via i18next key `adminReconciliation`.
 *   • No sensitive card fields — the backend never persists card numbers
 *     or CVVs; only `card_country` is stored.
 */
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import API_BASE from '../../config';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter,
} from '../../components/ui/dialog';
import { Loader2, Search, X, AlertTriangle, CheckCircle2, Clock, XCircle } from 'lucide-react';

const API = API_BASE;

// ─── helpers ───
const centsToMoney = (cents, currency = 'CAD', locale = 'en-CA') => {
  const n = Number.isFinite(cents) ? cents : 0;
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(n / 100);
};

const statusBadgeStyle = (status) => {
  switch ((status || '').toUpperCase()) {
    case 'RECONCILED':  return { className: 'bg-emerald-100 text-emerald-900', Icon: CheckCircle2 };
    case 'VARIANCE':    return { className: 'bg-amber-100  text-amber-900',   Icon: AlertTriangle };
    case 'SHORTFALL':   return { className: 'bg-rose-100   text-rose-900',    Icon: AlertTriangle };
    case 'PENDING':     return { className: 'bg-slate-100  text-slate-700',   Icon: Clock };
    case 'ERROR':       return { className: 'bg-red-200    text-red-900',     Icon: XCircle };
    default:            return { className: 'bg-slate-100  text-slate-700',   Icon: Clock };
  }
};

const StatusBadge = ({ status, label }) => {
  const { className, Icon } = statusBadgeStyle(status);
  return (
    <Badge className={`gap-1 ${className}`} data-testid={`recon-status-badge-${status}`}>
      <Icon className="h-3 w-3" />
      {label}
    </Badge>
  );
};

const AdminPaymentReconciliation = () => {
  const { t, i18n } = useTranslation();
  const { token } = useAuth();
  const locale = i18n.language?.startsWith('fr') ? 'fr-CA' : 'en-CA';

  const [summary, setSummary]     = useState(null);
  const [rows, setRows]           = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);
  const [statusFilter, setStatusFilter]             = useState('all');
  const [jurisdictionFilter, setJurisdictionFilter] = useState('all');
  const [payerRoleFilter, setPayerRoleFilter]       = useState('all');
  const [dateFrom, setDateFrom]   = useState('');
  const [dateTo, setDateTo]       = useState('');
  const [search, setSearch]       = useState('');
  const [detailRow, setDetailRow] = useState(null);

  const authHeaders = useMemo(() => (
    token ? { Authorization: `Bearer ${token}` } : {}
  ), [token]);

  const buildParams = useCallback(() => {
    const p = {};
    if (statusFilter !== 'all')        p.status       = statusFilter;
    if (jurisdictionFilter !== 'all')  p.jurisdiction = jurisdictionFilter;
    if (payerRoleFilter !== 'all')     p.payer_role   = payerRoleFilter;
    if (dateFrom)                      p.date_from    = dateFrom;
    if (dateTo)                        p.date_to      = dateTo;
    if (search.trim())                 p.search       = search.trim();
    return p;
  }, [statusFilter, jurisdictionFilter, payerRoleFilter, dateFrom, dateTo, search]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, listRes] = await Promise.all([
        axios.get(`${API}/admin/stripe-reconciliation/summary`, { headers: authHeaders }),
        axios.get(`${API}/admin/stripe-reconciliation`, {
          headers: authHeaders,
          params: buildParams(),
        }),
      ]);
      setSummary(sumRes.data);
      setRows(listRes.data?.rows || []);
    } catch (e) {
      const status = e?.response?.status;
      if (status === 401 || status === 403) {
        setError(t('adminReconciliation.loadErrorAuth'));
      } else {
        setError(t('adminReconciliation.loadError'));
      }
      setSummary(null);
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [authHeaders, buildParams, t]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const clearFilters = () => {
    setStatusFilter('all');
    setJurisdictionFilter('all');
    setPayerRoleFilter('all');
    setDateFrom('');
    setDateTo('');
    setSearch('');
  };

  const openDetail = (row) => setDetailRow(row);
  const closeDetail = () => setDetailRow(null);

  // ─── render ───
  return (
    <div className="max-w-7xl mx-auto p-4 md:p-8 space-y-6" data-testid="admin-recon-page">
      <div>
        <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-slate-900" data-testid="recon-title">
          {t('adminReconciliation.title')}
        </h1>
        <p className="mt-1 text-sm text-slate-500 max-w-2xl">
          {t('adminReconciliation.subtitle')}
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3" data-testid="recon-summary">
        <SummaryCard label={t('adminReconciliation.cards.totalPayments')}
                     value={summary?.total_rows ?? '—'}
                     testid="card-total" />
        <SummaryCard label={t('adminReconciliation.cards.reconciled')}
                     value={summary?.reconciled ?? '—'}
                     tone="emerald"
                     testid="card-reconciled" />
        <SummaryCard label={t('adminReconciliation.cards.variance')}
                     value={summary?.variance ?? '—'}
                     tone="amber"
                     testid="card-variance" />
        <SummaryCard label={t('adminReconciliation.cards.shortfall')}
                     value={summary?.shortfall ?? '—'}
                     tone="rose"
                     testid="card-shortfall" />
        <SummaryCard label={t('adminReconciliation.cards.pending')}
                     value={summary?.pending ?? '—'}
                     tone="slate"
                     testid="card-pending" />
        <SummaryCard label={t('adminReconciliation.cards.error')}
                     value={summary?.error ?? '—'}
                     tone="red"
                     testid="card-error" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard label={t('adminReconciliation.cards.estimatedTotal')}
                     value={summary ? centsToMoney(summary.estimated_cents_total, 'CAD', locale) : '—'}
                     testid="card-estimated" />
        <SummaryCard label={t('adminReconciliation.cards.recoveryTotal')}
                     value={summary ? centsToMoney(summary.recovery_cents_total, 'CAD', locale) : '—'}
                     testid="card-recovery" />
        <SummaryCard label={t('adminReconciliation.cards.actualTotal')}
                     value={summary ? centsToMoney(summary.actual_cents_total, 'CAD', locale) : '—'}
                     testid="card-actual" />
        <SummaryCard label={t('adminReconciliation.cards.shortfallTotal')}
                     value={summary ? centsToMoney(Math.abs(summary.variance_cents_shortfall || 0), 'CAD', locale) : '—'}
                     tone="rose"
                     testid="card-shortfall-total" />
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">{t('adminReconciliation.filters.status')}</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-6 gap-3 items-end">
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">
              {t('adminReconciliation.filters.status')}
            </label>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger data-testid="filter-status"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('adminReconciliation.status.all')}</SelectItem>
                <SelectItem value="RECONCILED">{t('adminReconciliation.status.reconciled')}</SelectItem>
                <SelectItem value="VARIANCE">{t('adminReconciliation.status.variance')}</SelectItem>
                <SelectItem value="SHORTFALL">{t('adminReconciliation.status.shortfall')}</SelectItem>
                <SelectItem value="PENDING">{t('adminReconciliation.status.pending')}</SelectItem>
                <SelectItem value="ERROR">{t('adminReconciliation.status.error')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">
              {t('adminReconciliation.filters.jurisdiction')}
            </label>
            <Select value={jurisdictionFilter} onValueChange={setJurisdictionFilter}>
              <SelectTrigger data-testid="filter-jurisdiction"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('adminReconciliation.jurisdiction.all')}</SelectItem>
                <SelectItem value="domestic">{t('adminReconciliation.jurisdiction.domestic')}</SelectItem>
                <SelectItem value="international">{t('adminReconciliation.jurisdiction.international')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">
              {t('adminReconciliation.filters.payerRole')}
            </label>
            <Select value={payerRoleFilter} onValueChange={setPayerRoleFilter}>
              <SelectTrigger data-testid="filter-payer-role"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('adminReconciliation.payerRole.all')}</SelectItem>
                <SelectItem value="buyer">{t('adminReconciliation.payerRole.buyer')}</SelectItem>
                <SelectItem value="seller">{t('adminReconciliation.payerRole.seller')}</SelectItem>
                <SelectItem value="partner">{t('adminReconciliation.payerRole.partner')}</SelectItem>
                <SelectItem value="platform">{t('adminReconciliation.payerRole.platform')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">
              {t('adminReconciliation.filters.dateFrom')}
            </label>
            <Input type="date" value={dateFrom.slice(0, 10)}
                   onChange={(e) => setDateFrom(e.target.value)}
                   data-testid="filter-date-from" />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">
              {t('adminReconciliation.filters.dateTo')}
            </label>
            <Input type="date" value={dateTo.slice(0, 10)}
                   onChange={(e) => setDateTo(e.target.value)}
                   data-testid="filter-date-to" />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 block mb-1">
              {t('adminReconciliation.filters.search')}
            </label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
              <Input placeholder={t('adminReconciliation.filters.searchPlaceholder')}
                     value={search}
                     onChange={(e) => setSearch(e.target.value)}
                     className="pl-8"
                     data-testid="filter-search" />
            </div>
          </div>
          <div className="md:col-span-6 flex justify-end">
            <Button variant="ghost" onClick={clearFilters} data-testid="filter-clear">
              <X className="h-4 w-4 mr-1" />
              {t('adminReconciliation.filters.clear')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-24 text-sm text-slate-500 gap-2" data-testid="recon-loading">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t('adminReconciliation.loading')}
            </div>
          ) : error ? (
            <div className="flex items-center justify-center py-24 text-sm text-rose-600" data-testid="recon-error">
              {error}
            </div>
          ) : rows.length === 0 ? (
            <div className="flex items-center justify-center py-24 text-sm text-slate-500" data-testid="recon-empty">
              {t('adminReconciliation.empty')}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase text-slate-500 bg-slate-50">
                  <tr>
                    <th className="px-4 py-3">{t('adminReconciliation.columns.paymentIntent')}</th>
                    <th className="px-4 py-3">{t('adminReconciliation.columns.date')}</th>
                    <th className="px-4 py-3">{t('adminReconciliation.columns.payerRole')}</th>
                    <th className="px-4 py-3">{t('adminReconciliation.columns.cardJurisdiction')}</th>
                    <th className="px-4 py-3 text-right">{t('adminReconciliation.columns.estimated')}</th>
                    <th className="px-4 py-3 text-right">{t('adminReconciliation.columns.recovery')}</th>
                    <th className="px-4 py-3 text-right">{t('adminReconciliation.columns.actual')}</th>
                    <th className="px-4 py-3 text-right">{t('adminReconciliation.columns.variance')}</th>
                    <th className="px-4 py-3">{t('adminReconciliation.columns.status')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {rows.map((r) => {
                    const currency = r.currency || 'CAD';
                    const juri = (r.resolved_jurisdiction || '').toLowerCase();
                    const juriLabel = juri === 'domestic'
                      ? t('adminReconciliation.jurisdiction.domestic')
                      : (juri === 'international'
                          ? t('adminReconciliation.jurisdiction.international')
                          : '—');
                    const statusPublic = (r.reconciliation_status_ui
                      || r.reconciliation_status_public
                      || r.reconciliation_status
                      || 'PENDING').toUpperCase();
                    const statusLabelKey = {
                      RECONCILED: 'reconciled',
                      VARIANCE:   'variance',
                      SHORTFALL:  'shortfall',
                      PENDING:    'pending',
                      ERROR:      'error',
                    }[statusPublic] || 'pending';
                    return (
                      <tr key={r.payment_intent_id}
                          onClick={() => openDetail(r)}
                          className="cursor-pointer hover:bg-slate-50"
                          data-testid={`recon-row-${r.payment_intent_id}`}>
                        <td className="px-4 py-3 font-mono text-xs">
                          {r.payment_intent_id || '—'}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-slate-600">
                          {(r.updated_at || '').slice(0, 19).replace('T', ' ')}
                        </td>
                        <td className="px-4 py-3 capitalize">{r.payer_role || '—'}</td>
                        <td className="px-4 py-3">{juriLabel}</td>
                        <td className="px-4 py-3 text-right font-mono">
                          {centsToMoney(r.estimated_cents, currency, locale)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          {centsToMoney(r.recovery_cents, currency, locale)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          {centsToMoney(r.actual_cents, currency, locale)}
                        </td>
                        <td className={`px-4 py-3 text-right font-mono
                          ${((r.variance_cents || 0) < 0) ? 'text-rose-700' : ''}`}>
                          {centsToMoney(r.variance_cents, currency, locale)}
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={statusPublic}
                                       label={t(`adminReconciliation.status.${statusLabelKey}`)} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail dialog */}
      <Dialog open={!!detailRow} onOpenChange={(o) => (!o && closeDetail())}>
        <DialogContent className="max-w-2xl" data-testid="recon-detail-dialog">
          <DialogHeader>
            <DialogTitle>{t('adminReconciliation.detail.title')}</DialogTitle>
            <DialogDescription className="font-mono text-xs">
              {detailRow?.payment_intent_id || ''}
            </DialogDescription>
          </DialogHeader>
          {detailRow && (
            <ReconciliationDetail row={detailRow} locale={locale} t={t} />
          )}
          <DialogFooter>
            <Button variant="outline" onClick={closeDetail}
                    data-testid="recon-detail-close">
              {t('adminReconciliation.detail.close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

// ─── subcomponents ───
const SummaryCard = ({ label, value, tone, testid }) => {
  const toneClass = {
    emerald: 'text-emerald-700',
    amber:   'text-amber-700',
    rose:    'text-rose-700',
    slate:   'text-slate-700',
    red:     'text-red-700',
  }[tone] || 'text-slate-900';
  return (
    <Card data-testid={testid} className="shadow-sm">
      <CardContent className="p-4">
        <p className="text-[11px] uppercase tracking-wider text-slate-500 font-medium">
          {label}
        </p>
        <p className={`mt-1 text-xl font-semibold ${toneClass}`}>{value}</p>
      </CardContent>
    </Card>
  );
};

const KV = ({ label, value, mono = false, testid }) => (
  <div className="flex items-baseline justify-between gap-4 py-1" data-testid={testid}>
    <span className="text-xs text-slate-500">{label}</span>
    <span className={`text-sm text-slate-900 ${mono ? 'font-mono' : ''}`}>
      {value ?? '—'}
    </span>
  </div>
);

const ReconciliationDetail = ({ row, locale, t }) => {
  const currency = row.currency || 'CAD';
  const juri = (row.resolved_jurisdiction || '').toLowerCase();
  const juriLabel = juri === 'domestic'
    ? t('adminReconciliation.jurisdiction.domestic')
    : (juri === 'international'
        ? t('adminReconciliation.jurisdiction.international')
        : '—');
  const isShortfall = (row.variance_cents || 0) < 0;
  const varianceLabel = isShortfall
    ? t('adminReconciliation.detail.shortfall')
    : t('adminReconciliation.detail.variance');
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div>
        <KV label={t('adminReconciliation.detail.paymentIntent')}
            value={row.payment_intent_id} mono testid="detail-pi" />
        <KV label={t('adminReconciliation.detail.chargeId')}
            value={row.charge_id} mono testid="detail-charge" />
        <KV label={t('adminReconciliation.detail.balanceTxnId')}
            value={row.balance_transaction_id} mono testid="detail-btxn" />
        <KV label={t('adminReconciliation.detail.listing')}
            value={row.listing_id || row.invoice_id || '—'} mono testid="detail-listing" />
        <KV label={t('adminReconciliation.detail.cardCountry')}
            value={row.card_country || '—'} testid="detail-country" />
        <KV label={t('adminReconciliation.detail.cardJurisdiction')}
            value={juriLabel} testid="detail-juri" />
        <KV label={t('adminReconciliation.detail.detectedAt')}
            value={(row.updated_at || '').replace('T', ' ').slice(0, 19)} mono testid="detail-time" />
      </div>
      <div>
        <KV label={t('adminReconciliation.detail.estimatedFee')}
            value={centsToMoney(row.estimated_cents, currency, locale)} mono testid="detail-est" />
        <KV label={t('adminReconciliation.detail.recoveryFee')}
            value={centsToMoney(row.recovery_cents, currency, locale)} mono testid="detail-recov" />
        <KV label={t('adminReconciliation.detail.actualFee')}
            value={centsToMoney(row.actual_cents, currency, locale)} mono testid="detail-act" />
        <KV label={varianceLabel}
            value={centsToMoney(row.variance_cents, currency, locale)} mono testid="detail-var" />
        <KV label={t('adminReconciliation.detail.notificationStatus')}
            value={row.variance_notification_status || '—'} testid="detail-notify" />
        <KV label={t('adminReconciliation.detail.notificationSentAt')}
            value={(row.variance_notification_sent_at || '').replace('T', ' ').slice(0, 19) || '—'}
            mono testid="detail-notify-time" />
      </div>
    </div>
  );
};

export default AdminPaymentReconciliation;
