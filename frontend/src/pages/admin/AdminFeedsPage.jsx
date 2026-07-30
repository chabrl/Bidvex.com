import { extractErrorMessage } from '../../utils/errorHandler';
/**
 * Phase 5 — Admin Feed Health dashboard.
 *
 * Surfaces the same /api/feeds/facebook-local/meta payload alongside
 * a "Force Cache Refresh" button and an inline JSON preview so the
 * admin can wire Meta Business Manager → Catalog → Scheduled Feed.
 */
import API_BASE from '../../config';
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  RefreshCw, Copy, ExternalLink, AlertCircle, CheckCircle2, Eye, Image as ImageIcon,
  MapPin, Ban, ShieldAlert, Clock,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { useAuth } from '../../contexts/AuthContext';

const API = API_BASE;

const StatRow = ({ icon: Icon, label, count, accent }) => (
  <div
    className="flex items-center justify-between py-3 border-b last:border-b-0"
    style={{ borderColor: '#e2e8f0' }}
  >
    <div className="flex items-center gap-3">
      <Icon className="h-4 w-4" style={{ color: accent || '#64748b' }} />
      <span className="text-sm" style={{ color: '#334155' }}>{label}</span>
    </div>
    <span className="text-base font-semibold tabular-nums" style={{ color: accent || '#0f172a' }}>
      {count ?? 0}
    </span>
  </div>
);

const AdminFeedsPage = () => {
  const { token } = useAuth();
  const { t } = useTranslation();
  const [meta, setMeta] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadMeta = async () => {
    try {
      const { data } = await axios.get(`${API}/feeds/facebook-local/meta`);
      setMeta(data);
    } catch (e) {
      toast.error('Failed to load feed metadata');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMeta();
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const { data } = await axios.post(
        `${API}/feeds/facebook-local/refresh`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(`Feed cache refreshed — ${data.item_count} items`);
      await loadMeta();
    } catch (e) {
      toast.error(extractErrorMessage(e) || 'Refresh failed');
    } finally {
      setRefreshing(false);
    }
  };

  const handlePreview = async () => {
    try {
      const { data } = await axios.get(`${API}/feeds/facebook-local?limit=5`);
      setPreview(data);
    } catch (e) {
      toast.error('Failed to load preview');
    }
  };

  const handleCopy = () => {
    if (meta?.feed_url) {
      navigator.clipboard.writeText(meta.feed_url);
      toast.success('Feed URL copied to clipboard');
    }
  };

  if (loading) {
    return <div className="p-6 text-slate-400">Loading…</div>;
  }

  const isHealthy = (meta?.feed_total_items ?? meta?.feed_eligible_listings ?? 0) >= 5;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: '#0f172a' }}>
            <span style={{ fontSize: '1.25rem' }}>📡</span>
            {t('admin.adFeeds.title', 'Meta Ad Feeds')}
          </h1>
          <p className="text-sm mt-1" style={{ color: '#64748b' }}>
            {t('admin.adFeeds.subtitle', 'Public catalog feeds powering Meta Dynamic & Local Inventory Ads.')}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={handlePreview}
            variant="outline"
            data-testid="feed-preview-btn"
          >
            <Eye className="h-4 w-4 mr-1.5" />
            {t('admin.adFeeds.preview', 'Preview First 5')}
          </Button>
          <Button
            onClick={handleRefresh}
            disabled={refreshing}
            style={{ background: '#2563eb', color: 'white' }}
            data-testid="feed-refresh-btn"
          >
            <RefreshCw className={`h-4 w-4 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
            {t('admin.adFeeds.refresh', 'Force Cache Refresh')}
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {isHealthy ? (
              <Badge className="bg-emerald-100 text-emerald-700 border-0" data-testid="feed-status-badge">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                {t('admin.adFeeds.statusActive', 'Active')}
              </Badge>
            ) : (
              <Badge className="bg-rose-100 text-rose-700 border-0" data-testid="feed-status-badge">
                <AlertCircle className="h-3 w-3 mr-1" />
                {t('admin.adFeeds.statusEmpty', 'No eligible listings')}
              </Badge>
            )}
            <span className="text-base font-semibold">{t('admin.adFeeds.feedUrl', 'Feed URL')}</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 p-3 rounded-lg" style={{ background: '#f1f5f9', border: '1px solid #e2e8f0' }}>
            <code
              className="flex-1 text-sm break-all"
              style={{ color: '#0f172a', fontFamily: 'ui-monospace,monospace' }}
              data-testid="feed-url"
            >
              {meta?.feed_url}
            </code>
            <Button size="sm" variant="ghost" onClick={handleCopy} data-testid="feed-copy-btn">
              <Copy className="h-4 w-4" />
            </Button>
            <Button size="sm" variant="ghost" asChild>
              <a href={meta?.feed_url} target="_blank" rel="noreferrer">
                <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5">
            <div data-testid="kpi-total">
              <p className="text-xs uppercase tracking-wide" style={{ color: '#94a3b8' }}>
                {t('admin.adFeeds.totalActive', 'Active listings')}
              </p>
              <p className="text-2xl font-bold" style={{ color: '#0f172a' }}>
                {meta?.total_active_listings ?? 0}
              </p>
            </div>
            <div data-testid="kpi-eligible">
              <p className="text-xs uppercase tracking-wide" style={{ color: '#94a3b8' }}>
                {t('admin.adFeeds.eligible', 'In feed')}
              </p>
              <p className="text-2xl font-bold" style={{ color: '#16a34a' }}>
                {meta?.feed_eligible_listings ?? 0}
              </p>
            </div>
            <div data-testid="kpi-excluded">
              <p className="text-xs uppercase tracking-wide" style={{ color: '#94a3b8' }}>
                {t('admin.adFeeds.excluded', 'Excluded')}
              </p>
              <p className="text-2xl font-bold" style={{ color: '#dc2626' }}>
                {meta?.excluded_listings ?? 0}
              </p>
            </div>
            <div data-testid="kpi-pages">
              <p className="text-xs uppercase tracking-wide" style={{ color: '#94a3b8' }}>
                {t('admin.adFeeds.pages', 'Pages')}
              </p>
              <p className="text-2xl font-bold" style={{ color: '#0f172a' }}>
                {meta?.total_pages ?? 0}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('admin.adFeeds.exclusionReasons', 'Catalog health — Why are listings excluded?')}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          <StatRow icon={ImageIcon} label={t('admin.adFeeds.exNoImages', 'Missing valid https:// images')} count={meta?.exclusion_reasons?.no_images} accent="#dc2626" />
          <StatRow icon={MapPin} label={t('admin.adFeeds.exNoLocation', 'Missing city / region')} count={meta?.exclusion_reasons?.no_location} accent="#f59e0b" />
          <StatRow icon={Ban} label={t('admin.adFeeds.exDemo', 'Demo accounts (intentionally excluded)')} count={meta?.exclusion_reasons?.demo_account} accent="#94a3b8" />
          <StatRow icon={ShieldAlert} label={t('admin.adFeeds.exModeration', 'Pending moderation')} count={meta?.exclusion_reasons?.moderation_pending} accent="#f59e0b" />
          <StatRow icon={AlertCircle} label={t('admin.adFeeds.exNoTitle', 'Missing title')} count={meta?.exclusion_reasons?.no_title} accent="#dc2626" />
          <StatRow icon={ImageIcon} label={t('admin.adFeeds.placeholderUsed', 'Branded placeholder served (base64 listings)')} count={meta?.exclusion_reasons?.placeholder_used} accent="#2563eb" />
          <StatRow icon={ShieldAlert} label={t('admin.adFeeds.seedItemsPadded', 'Seed items padded (Meta 5-product minimum)')} count={meta?.seed_items_padded} accent="#2563eb" />
          <p className="text-xs mt-4" style={{ color: '#64748b' }}>
            <Clock className="inline h-3 w-3 mr-1" />
            {t('admin.adFeeds.lastCached', 'Last cached:')}{' '}
            <span style={{ fontFamily: 'ui-monospace,monospace' }}>
              {meta?.last_cached_at || '—'}
            </span>
            {' '}({meta?.cache_ttl_seconds || 0}s TTL)
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('admin.adFeeds.setupTitle', 'Meta Business Manager setup')}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm space-y-2" style={{ color: '#334155' }}>
          <p><strong>1.</strong> {t('admin.adFeeds.step1', 'Copy the feed URL above.')}</p>
          <p><strong>2.</strong> {t('admin.adFeeds.step2', 'Open Meta Business Manager → Catalog Manager → Add Data Source → Scheduled Feed.')}</p>
          <p><strong>3.</strong> {t('admin.adFeeds.step3', 'Paste the feed URL.')}</p>
          <p><strong>4.</strong> {t('admin.adFeeds.step4', 'Set refresh interval to 15 minutes.')}</p>
          <p><strong>5.</strong> {t('admin.adFeeds.step5', 'Connect your Pixel ID to the catalog so Dynamic Product Ads can retarget pixel viewers.')}</p>
        </CardContent>
      </Card>

      {preview && (
        <Card data-testid="feed-preview-panel">
          <CardHeader>
            <CardTitle className="text-sm">
              {t('admin.adFeeds.preview', 'Preview')} ({preview.data?.length || 0} items)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <pre
              className="p-3 rounded-lg overflow-auto text-xs"
              style={{ background: '#0f172a', color: '#94e2d5', maxHeight: 400 }}
            >
              {JSON.stringify(preview, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default AdminFeedsPage;
