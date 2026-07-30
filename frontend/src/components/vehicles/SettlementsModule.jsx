/**
 * iter437 — Settlements Module
 *
 * Mounts inside `/vehicle-dashboard` below <SalesPerformanceModule />.
 *
 * Data source (audit-only, no invented data or endpoints):
 *   GET /api/vehicles/dealer/pending-settlements
 *
 * The backend already returns `vehicle_settlements` for this dealer
 * enriched with vehicle + buyer info. This module transforms the raw
 * `settlement_status` enum into three dealer-friendly buckets
 * (pending / processing / paid) and computes summary totals.
 *
 * Fee-model reminder — BidVex only charges the BUYER a 2.5% platform
 * fee; the seller keeps 100% of the hammer price. This is displayed
 * as a footnote so dealers understand why "Seller Commission = $0".
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import {
  Wallet, Clock, RefreshCw, CheckCircle2, AlertTriangle, Info, Car,
} from 'lucide-react';

import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage } from '../../utils/errorHandler';
import { Card } from '../ui/card';
import { Badge } from '../ui/badge';

const API = API_BASE;

/* ── status mapping (server enum → dealer-facing bucket) ─────────── */

const BUCKET_META = {
  pending: {
    Icon: Clock,
    color: 'bg-amber-500',
    labelKey: 'settlements.statusPending',
    ring: 'border-amber-200 bg-amber-50 dark:bg-amber-950/30',
  },
  processing: {
    Icon: RefreshCw,
    color: 'bg-blue-500',
    labelKey: 'settlements.statusProcessing',
    ring: 'border-blue-200 bg-blue-50 dark:bg-blue-950/30',
  },
  paid: {
    Icon: CheckCircle2,
    color: 'bg-emerald-500',
    labelKey: 'settlements.statusPaid',
    ring: 'border-emerald-200 bg-emerald-50 dark:bg-emerald-950/30',
  },
  disputed: {
    Icon: AlertTriangle,
    color: 'bg-rose-500',
    labelKey: 'settlements.statusDisputed',
    ring: 'border-rose-200 bg-rose-50 dark:bg-rose-950/30',
  },
};

const STATUS_TO_BUCKET = {
  FEE_PROCESSING:               'pending',
  FEE_PAID:                     'pending',
  AWAITING_DEALER_CONFIRMATION: 'pending',
  DEALER_CONFIRMED:             'processing',
  DISPUTED:                     'disputed',
  FULLY_SETTLED:                'paid',
  ADMIN_RESOLVED:               'paid',
};

const bucketOf = (status) => STATUS_TO_BUCKET[status] || 'pending';

/* ── formatters ──────────────────────────────────────────────────── */

const fmtCurrency = (v, lang) =>
  new Intl.NumberFormat(lang === 'fr' ? 'fr-CA' : 'en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Number(v) || 0);

const fmtDate = (iso, lang) => {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat(lang === 'fr' ? 'fr-CA' : 'en-CA', {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
    }).format(new Date(iso));
  } catch {
    return '—';
  }
};

/* ── status pill ──────────────────────────────────────────────── */

const StatusPill = ({ status, t }) => {
  const bucket = bucketOf(status);
  const meta = BUCKET_META[bucket];
  const Icon = meta.Icon;
  return (
    <Badge
      className={`${meta.color} gap-1 text-white whitespace-nowrap`}
      data-testid={`settlement-status-pill-${bucket}`}
    >
      <Icon className="h-3 w-3" />
      {t(meta.labelKey)}
    </Badge>
  );
};

/* ── module ────────────────────────────────────────────────────── */

const SettlementsModule = () => {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language || 'en').startsWith('fr') ? 'fr' : 'en';
  const { token } = useAuth();

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const resp = await axios.get(
        `${API}/vehicles/dealer/pending-settlements`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setRows(resp.data?.settlements || []);
    } catch (err) {
      toast.error(extractErrorMessage(err) || t('settlements.loadFailed'));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const summary = useMemo(() => {
    let pending = 0;
    let paid = 0;
    for (const r of rows) {
      const bucket = bucketOf(r.settlement_status);
      const price = Number(r.hammer_price) || 0;
      if (bucket === 'paid') paid += price;
      else if (bucket === 'pending' || bucket === 'processing') pending += price;
    }
    return { pending, paid };
  }, [rows]);

  const isEmpty = !loading && rows.length === 0;

  /* ── render ─────────────────────────────────────────────────── */

  if (loading) {
    return (
      <div
        className="flex flex-col items-center justify-center py-12"
        data-testid="settlements-loading"
      >
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mb-3" />
        <p className="text-sm text-slate-500">{t('settlements.loading')}</p>
      </div>
    );
  }

  if (isEmpty) {
    return (
      <Card className="p-10 text-center" data-testid="settlements-empty">
        <Wallet className="h-14 w-14 text-slate-300 mx-auto mb-4" />
        <h3 className="text-lg sm:text-xl font-semibold mb-2">
          {t('settlements.emptyTitle')}
        </h3>
        <p className="text-sm text-slate-500 max-w-md mx-auto">
          {t('settlements.emptyBody')}
        </p>
      </Card>
    );
  }

  return (
    <section data-testid="settlements-module">
      {/* Summary bar */}
      <div
        className="grid gap-4 grid-cols-1 sm:grid-cols-2 mb-5"
        data-testid="settlements-summary"
      >
        <Card
          className="p-4 flex items-start gap-3 border-amber-200/60 bg-amber-50/50 dark:bg-amber-950/20 dark:border-amber-900/40"
          data-testid="settlement-summary-pending"
        >
          <span className="inline-flex items-center justify-center h-10 w-10 rounded-lg bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 flex-shrink-0">
            <Clock className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <div className="text-xs sm:text-sm font-medium uppercase tracking-wide text-amber-800 dark:text-amber-300">
              {t('settlements.summaryPending')}
            </div>
            <div
              className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100 leading-tight mt-0.5"
              data-testid="settlement-summary-pending-value"
            >
              {fmtCurrency(summary.pending, lang)}
            </div>
            <p className="text-[11px] text-amber-700/80 dark:text-amber-400/80 mt-1">
              {t('settlements.summaryPendingHelp')}
            </p>
          </div>
        </Card>

        <Card
          className="p-4 flex items-start gap-3 border-emerald-200/60 bg-emerald-50/50 dark:bg-emerald-950/20 dark:border-emerald-900/40"
          data-testid="settlement-summary-paid"
        >
          <span className="inline-flex items-center justify-center h-10 w-10 rounded-lg bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 flex-shrink-0">
            <CheckCircle2 className="h-5 w-5" />
          </span>
          <div className="min-w-0">
            <div className="text-xs sm:text-sm font-medium uppercase tracking-wide text-emerald-800 dark:text-emerald-300">
              {t('settlements.summaryPaid')}
            </div>
            <div
              className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100 leading-tight mt-0.5"
              data-testid="settlement-summary-paid-value"
            >
              {fmtCurrency(summary.paid, lang)}
            </div>
            <p className="text-[11px] text-emerald-700/80 dark:text-emerald-400/80 mt-1">
              {t('settlements.summaryPaidHelp')}
            </p>
          </div>
        </Card>
      </div>

      {/* Desktop table */}
      <Card className="hidden md:block overflow-hidden" data-testid="settlements-table-card">
        <div className="overflow-x-auto">
          <table
            className="w-full text-sm border-collapse"
            data-testid="settlements-table"
          >
            <thead className="bg-slate-50 dark:bg-slate-900/60 text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
              <tr>
                <th className="px-4 py-3 font-medium">{t('settlements.colVehicle')}</th>
                <th className="px-4 py-3 font-medium text-right">{t('settlements.colSalePrice')}</th>
                <th className="px-4 py-3 font-medium text-right">{t('settlements.colBuyerPremium')}</th>
                <th className="px-4 py-3 font-medium text-right">{t('settlements.colSellerCommission')}</th>
                <th className="px-4 py-3 font-medium text-right">{t('settlements.colNetPayout')}</th>
                <th className="px-4 py-3 font-medium text-center">{t('settlements.colStatus')}</th>
                <th className="px-4 py-3 font-medium text-right whitespace-nowrap">{t('settlements.colDate')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {rows.map((r) => {
                const v = r.vehicle || {};
                const salePrice = Number(r.hammer_price) || 0;
                const buyerPremium = Number(r.net_commission_amount) || 0;
                const sellerCommission = 0; // BidVex fee model — buyer pays, seller keeps 100%
                const netPayout = salePrice - sellerCommission;
                const testId = `settlement-row-${r.auction_id}`;
                return (
                  <tr
                    key={r.auction_id}
                    className="hover:bg-slate-50/60 dark:hover:bg-slate-900/40"
                    data-testid={testId}
                  >
                    <td className="px-4 py-3 min-w-[180px]">
                      <div className="font-medium text-slate-900 dark:text-slate-100">
                        {v.year} {v.make} {v.model}
                      </div>
                      {r.buyer?.name && (
                        <div className="text-[11px] text-slate-500 mt-0.5">
                          {t('settlements.buyerLabel')}: {r.buyer.name}
                        </div>
                      )}
                    </td>
                    <td
                      className="px-4 py-3 text-right tabular-nums whitespace-nowrap"
                      data-testid={`${testId}-sale-price`}
                    >
                      {fmtCurrency(salePrice, lang)}
                    </td>
                    <td
                      className="px-4 py-3 text-right tabular-nums text-slate-600 dark:text-slate-400 whitespace-nowrap"
                      data-testid={`${testId}-buyer-premium`}
                    >
                      {fmtCurrency(buyerPremium, lang)}
                    </td>
                    <td
                      className="px-4 py-3 text-right tabular-nums text-slate-600 dark:text-slate-400 whitespace-nowrap"
                      data-testid={`${testId}-seller-commission`}
                    >
                      {fmtCurrency(sellerCommission, lang)}
                    </td>
                    <td
                      className="px-4 py-3 text-right tabular-nums font-semibold text-slate-900 dark:text-slate-100 whitespace-nowrap"
                      data-testid={`${testId}-net-payout`}
                    >
                      {fmtCurrency(netPayout, lang)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <StatusPill status={r.settlement_status} t={t} />
                    </td>
                    <td
                      className="px-4 py-3 text-right text-slate-500 whitespace-nowrap"
                      data-testid={`${testId}-date`}
                    >
                      {fmtDate(r.fee_paid_at || r.updated_at || r.created_at, lang)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Mobile card list */}
      <div className="md:hidden space-y-3" data-testid="settlements-mobile-list">
        {rows.map((r) => {
          const v = r.vehicle || {};
          const salePrice = Number(r.hammer_price) || 0;
          const buyerPremium = Number(r.net_commission_amount) || 0;
          const sellerCommission = 0;
          const netPayout = salePrice - sellerCommission;
          const testId = `settlement-row-${r.auction_id}`;
          return (
            <Card key={r.auction_id} className="p-4" data-testid={testId}>
              <div className="flex items-start justify-between gap-2 mb-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 font-semibold text-slate-900 dark:text-slate-100">
                    <Car className="h-4 w-4 text-slate-400" />
                    <span>{v.year} {v.make} {v.model}</span>
                  </div>
                  {r.buyer?.name && (
                    <div className="text-[11px] text-slate-500 mt-1 truncate">
                      {t('settlements.buyerLabel')}: {r.buyer.name}
                    </div>
                  )}
                </div>
                <StatusPill status={r.settlement_status} t={t} />
              </div>

              <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                <dt className="text-slate-500">{t('settlements.colSalePrice')}</dt>
                <dd
                  className="text-right tabular-nums font-medium"
                  data-testid={`${testId}-sale-price`}
                >
                  {fmtCurrency(salePrice, lang)}
                </dd>

                <dt className="text-slate-500">{t('settlements.colBuyerPremium')}</dt>
                <dd
                  className="text-right tabular-nums"
                  data-testid={`${testId}-buyer-premium`}
                >
                  {fmtCurrency(buyerPremium, lang)}
                </dd>

                <dt className="text-slate-500">{t('settlements.colSellerCommission')}</dt>
                <dd
                  className="text-right tabular-nums"
                  data-testid={`${testId}-seller-commission`}
                >
                  {fmtCurrency(sellerCommission, lang)}
                </dd>

                <dt className="text-slate-700 dark:text-slate-300 font-semibold">
                  {t('settlements.colNetPayout')}
                </dt>
                <dd
                  className="text-right tabular-nums font-bold text-slate-900 dark:text-slate-100"
                  data-testid={`${testId}-net-payout`}
                >
                  {fmtCurrency(netPayout, lang)}
                </dd>

                <dt className="text-slate-500">{t('settlements.colDate')}</dt>
                <dd
                  className="text-right text-slate-500"
                  data-testid={`${testId}-date`}
                >
                  {fmtDate(r.fee_paid_at || r.updated_at || r.created_at, lang)}
                </dd>
              </dl>
            </Card>
          );
        })}
      </div>

      {/* Fee-model footnote — honesty about why seller_commission = $0 */}
      <p
        className="mt-3 text-[11px] text-slate-500 dark:text-slate-400 flex items-start gap-1.5"
        data-testid="settlements-fee-note"
      >
        <Info className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
        {t('settlements.feeModelNote')}
      </p>
    </section>
  );
};

export default SettlementsModule;
