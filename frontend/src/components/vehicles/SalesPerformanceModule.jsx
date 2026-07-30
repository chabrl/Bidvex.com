/**
 * iter432 — Sales & Performance Module
 *
 * Mounts inside `/vehicle-dashboard` below <MyVehiclesModule />.
 *
 * Data source (audit-only, no invented data):
 *   GET /api/vehicles/my/analytics?window_days=30|60|90
 *
 * The backend aggregates over the two collections the dealer already
 * populates — `vehicle_listings` (views_count, final_price, sold_at)
 * and `vehicle_bids` (created_at). Views are summed lifetime for
 * listings whose `created_at` falls in the window because per-day view
 * timestamps are not tracked.
 *
 * Renders:
 *   1. 30 / 60 / 90 day window toggle
 *   2. Four metric cards — Views · Bids · Revenue · Conversion Rate
 *   3. Recharts responsive bar chart of bids + sold per day/week
 *   4. Empty state when `has_data === false`
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import {
  Eye, TrendingUp, DollarSign, Percent, BarChart3, Info,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';

import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage } from '../../utils/errorHandler';
import { Card } from '../ui/card';

const API = API_BASE;

const WINDOWS = [
  { days: 30, labelKey: 'salesPerformance.window30', shortKey: 'salesPerformance.windowShort30' },
  { days: 60, labelKey: 'salesPerformance.window60', shortKey: 'salesPerformance.windowShort60' },
  { days: 90, labelKey: 'salesPerformance.window90', shortKey: 'salesPerformance.windowShort90' },
];

const formatCurrency = (v, lang) =>
  new Intl.NumberFormat(lang === 'fr' ? 'fr-CA' : 'en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(Number(v) || 0);

const formatNumber = (v, lang) =>
  new Intl.NumberFormat(lang === 'fr' ? 'fr-CA' : 'en-CA').format(Number(v) || 0);

const formatPercent = (v, lang) =>
  new Intl.NumberFormat(lang === 'fr' ? 'fr-CA' : 'en-CA', {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(Number(v) || 0);

const formatChartTick = (isoDate, lang) => {
  if (!isoDate) return '';
  const parts = isoDate.split('-');
  if (parts.length !== 3) return isoDate;
  const monthLabels = lang === 'fr'
    ? ['jan', 'fév', 'mar', 'avr', 'mai', 'juin', 'juil', 'aoû', 'sep', 'oct', 'nov', 'déc']
    : ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const monthIdx = parseInt(parts[1], 10) - 1;
  return `${monthLabels[monthIdx] || parts[1]} ${parseInt(parts[2], 10)}`;
};

/* ---------------------------- metric card ------------------------------- */

const MetricCard = ({ icon: Icon, label, value, helpText, tone, testId }) => (
  <Card
    className="p-4 flex flex-col gap-2 hover:shadow-md transition-shadow"
    data-testid={testId}
  >
    <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
      <span
        className={`inline-flex items-center justify-center h-8 w-8 rounded-lg ${tone.bg} ${tone.fg}`}
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="text-xs sm:text-sm font-medium uppercase tracking-wide">{label}</span>
    </div>
    <div
      className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100 leading-tight"
      data-testid={`${testId}-value`}
    >
      {value}
    </div>
    {helpText && (
      <p className="text-[11px] sm:text-xs text-slate-500 dark:text-slate-400 leading-snug">
        {helpText}
      </p>
    )}
  </Card>
);

/* ---------------------------- module ----------------------------------- */

const SalesPerformanceModule = () => {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language || 'en').startsWith('fr') ? 'fr' : 'en';
  const { token } = useAuth();

  const [windowDays, setWindowDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async (days) => {
    if (!token) return;
    setLoading(true);
    try {
      const resp = await axios.get(
        `${API}/vehicles/my/analytics?window_days=${days}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setData(resp.data);
    } catch (err) {
      toast.error(extractErrorMessage(err) || t('salesPerformance.loadFailed'));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => { fetchData(windowDays); }, [windowDays, fetchData]);

  const chartData = useMemo(() => {
    if (!data?.daily_series) return [];
    return data.daily_series.map((row) => ({
      ...row,
      tick: formatChartTick(row.date, lang),
    }));
  }, [data, lang]);

  const totals = data?.totals || { views: 0, bids: 0, revenue: 0, sold_count: 0, conversion_rate: 0 };
  const isEmpty = !loading && data && !data.has_data;
  const granularity = data?.granularity === 'week' ? 'weekly' : 'daily';

  return (
    <section data-testid="sales-performance-module">
      {/* Window toggle */}
      <div
        className="flex items-center gap-2 mb-5 flex-wrap"
        role="tablist"
        data-testid="sales-performance-window-toggle"
      >
        {WINDOWS.map((w) => {
          const isActive = windowDays === w.days;
          return (
            <button
              key={w.days}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setWindowDays(w.days)}
              className={`px-3 py-2 rounded-lg text-xs sm:text-sm font-semibold whitespace-nowrap transition-colors min-h-[40px] ${
                isActive
                  ? 'bg-[#0055FF] text-white shadow-sm'
                  : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800'
              }`}
              data-testid={`sales-performance-window-${w.days}`}
            >
              {t(w.labelKey)}
            </button>
          );
        })}
      </div>

      {loading ? (
        <div
          className="flex flex-col items-center justify-center py-12"
          data-testid="sales-performance-loading"
        >
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mb-3" />
          <p className="text-sm text-slate-500">{t('salesPerformance.loading')}</p>
        </div>
      ) : isEmpty ? (
        <Card className="p-10 text-center" data-testid="sales-performance-empty">
          <BarChart3 className="h-14 w-14 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg sm:text-xl font-semibold mb-2">
            {t('salesPerformance.emptyTitle')}
          </h3>
          <p className="text-sm text-slate-500 max-w-md mx-auto">
            {t('salesPerformance.emptyBody')}
          </p>
        </Card>
      ) : (
        <>
          {/* Metric cards */}
          <div
            className="grid gap-4 grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 mb-6"
            data-testid="sales-performance-metrics"
          >
            <MetricCard
              icon={Eye}
              label={t('salesPerformance.metricViews')}
              value={formatNumber(totals.views, lang)}
              helpText={t('salesPerformance.metricViewsHelp')}
              tone={{ bg: 'bg-blue-100 dark:bg-blue-950/40', fg: 'text-blue-600' }}
              testId="metric-views"
            />
            <MetricCard
              icon={TrendingUp}
              label={t('salesPerformance.metricBids')}
              value={formatNumber(totals.bids, lang)}
              helpText={t('salesPerformance.metricBidsHelp')}
              tone={{ bg: 'bg-emerald-100 dark:bg-emerald-950/40', fg: 'text-emerald-600' }}
              testId="metric-bids"
            />
            <MetricCard
              icon={DollarSign}
              label={t('salesPerformance.metricRevenue')}
              value={formatCurrency(totals.revenue, lang)}
              helpText={t('salesPerformance.metricRevenueHelp')}
              tone={{ bg: 'bg-purple-100 dark:bg-purple-950/40', fg: 'text-purple-600' }}
              testId="metric-revenue"
            />
            <MetricCard
              icon={Percent}
              label={t('salesPerformance.metricConversion')}
              value={formatPercent(totals.conversion_rate, lang)}
              helpText={t('salesPerformance.metricConversionHelp')}
              tone={{ bg: 'bg-amber-100 dark:bg-amber-950/40', fg: 'text-amber-600' }}
              testId="metric-conversion"
            />
          </div>

          {/* Chart */}
          <Card className="p-4 sm:p-5" data-testid="sales-performance-chart-card">
            <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
              <h3 className="font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-blue-600" />
                {t('salesPerformance.chartTitle')}
              </h3>
              <span
                className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide"
                data-testid="sales-performance-granularity"
              >
                {t(`salesPerformance.chartGranularity${granularity === 'weekly' ? 'Weekly' : 'Daily'}`)}
              </span>
            </div>

            <div style={{ width: '100%', height: 280 }} data-testid="sales-performance-chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={chartData}
                  margin={{ top: 8, right: 8, left: -12, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis
                    dataKey="tick"
                    tick={{ fontSize: 11 }}
                    interval="preserveStartEnd"
                    minTickGap={20}
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    allowDecimals={false}
                    width={36}
                  />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 8,
                      border: '1px solid #e2e8f0',
                    }}
                    labelFormatter={(l) => l}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar
                    dataKey="bids"
                    name={t('salesPerformance.chartLegendBids')}
                    fill="#10b981"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey="sold"
                    name={t('salesPerformance.chartLegendSold')}
                    fill="#8b5cf6"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Views-are-lifetime note */}
            <p
              className="mt-3 text-[11px] text-slate-500 dark:text-slate-400 flex items-start gap-1.5"
              data-testid="sales-performance-views-note"
            >
              <Info className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
              {t('salesPerformance.chartViewsNote')}
            </p>
          </Card>
        </>
      )}
    </section>
  );
};

export default SalesPerformanceModule;
