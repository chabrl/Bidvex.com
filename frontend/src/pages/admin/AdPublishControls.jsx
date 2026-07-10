/**
 * iter339 — Per-campaign Meta / Google publish controls + performance pull.
 * Buttons are disabled with a tooltip when the platform API prerequisites
 * (env credentials) are not configured — feature-flag driven.
 */
import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Loader2, BarChart3, Send, X } from 'lucide-react';
import API_BASE from '../../config';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Label } from '../../components/ui/label';
import { Input } from '../../components/ui/input';

const selectCls = 'h-8 w-full rounded-md border border-input bg-background px-2 text-xs';

export const AdPublishControls = ({ campaign: c, token, config, onUpdated }) => {
  const [panel, setPanel] = useState(null); // 'meta' | 'google' | null
  const [publishing, setPublishing] = useState(false);
  const [language, setLanguage] = useState('en');
  // Meta
  const [metaCampaigns, setMetaCampaigns] = useState(null);
  const [metaCampaignId, setMetaCampaignId] = useState('');
  const [newMetaCampaignName, setNewMetaCampaignName] = useState('');
  // Google
  const [googleCampaigns, setGoogleCampaigns] = useState(null);
  const [googleCampaignId, setGoogleCampaignId] = useState('');
  const [googleAdGroups, setGoogleAdGroups] = useState([]);
  const [googleAdGroupId, setGoogleAdGroupId] = useState('');
  // Performance
  const [perf, setPerf] = useState(null);
  const [perfLoading, setPerfLoading] = useState(false);

  const headers = { Authorization: `Bearer ${token}` };
  const metaEnabled = !!config?.meta?.enabled;
  const googleEnabled = !!config?.google?.enabled;
  const isDraft = c.status === 'draft';
  const published = !!(c.meta_ad_id || c.google_ad_id);

  const disabledTip = (enabled, platform) => {
    if (!enabled) return `API not configured — ${platform === 'meta' ? 'Meta Business Manager verification + Marketing API approval required' : 'Google Ads developer token (standard access) + OAuth required'}`;
    if (isDraft) return 'Mark campaign ready first';
    return '';
  };

  const openMeta = async () => {
    setPanel(panel === 'meta' ? null : 'meta');
    if (metaCampaigns === null) {
      try {
        const r = await axios.get(`${API_BASE}/admin/ad-campaigns/meta/campaigns`, { headers });
        setMetaCampaigns(r.data?.items || []);
      } catch (e) {
        setMetaCampaigns([]);
        toast.error(e?.response?.data?.detail || 'Failed to load Meta campaigns');
      }
    }
  };

  const openGoogle = async () => {
    setPanel(panel === 'google' ? null : 'google');
    if (googleCampaigns === null) {
      try {
        const r = await axios.get(`${API_BASE}/admin/ad-campaigns/google/campaigns`, { headers });
        setGoogleCampaigns(r.data?.items || []);
      } catch (e) {
        setGoogleCampaigns([]);
        toast.error(e?.response?.data?.detail || 'Failed to load Google campaigns');
      }
    }
  };

  const pickGoogleCampaign = async (id) => {
    setGoogleCampaignId(id);
    setGoogleAdGroupId('');
    setGoogleAdGroups([]);
    if (!id) return;
    try {
      const r = await axios.get(`${API_BASE}/admin/ad-campaigns/google/ad-groups?campaign_id=${id}`, { headers });
      setGoogleAdGroups(r.data?.items || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load ad groups');
    }
  };

  const publishMeta = async () => {
    setPublishing(true);
    try {
      const r = await axios.post(
        `${API_BASE}/admin/ad-campaigns/${c.id}/publish/meta`,
        { meta_campaign_id: metaCampaignId || null, new_campaign_name: newMetaCampaignName || null, language },
        { headers },
      );
      toast.success(`Published to Meta — ad ${r.data.meta_ad_id} (${r.data.ad_status})`);
      onUpdated({ ...c, meta_ad_id: r.data.meta_ad_id, status: r.data.status });
      setPanel(null);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Meta publish failed');
    } finally { setPublishing(false); }
  };

  const publishGoogle = async () => {
    if (!googleCampaignId || !googleAdGroupId) {
      toast.error('Select a Google campaign and ad group.');
      return;
    }
    setPublishing(true);
    try {
      const r = await axios.post(
        `${API_BASE}/admin/ad-campaigns/${c.id}/publish/google`,
        { google_campaign_id: googleCampaignId, google_ad_group_id: googleAdGroupId, language },
        { headers },
      );
      toast.success(`Published to Google — RSA ${r.data.google_ad_id}`);
      onUpdated({ ...c, google_ad_id: r.data.google_ad_id, status: r.data.status });
      setPanel(null);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Google publish failed');
    } finally { setPublishing(false); }
  };

  const loadPerformance = async () => {
    setPerfLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/admin/ad-campaigns/${c.id}/performance`, { headers });
      setPerf(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Performance fetch failed');
    } finally { setPerfLoading(false); }
  };

  return (
    <div className="pt-2 border-t border-slate-100 space-y-2" data-testid={`ad-publish-controls-${c.id}`}>
      <div className="flex items-center gap-1.5 flex-wrap">
        <span title={disabledTip(metaEnabled, 'meta')}>
          <Button
            size="sm" variant="outline" className="h-7 text-[11px]"
            disabled={!metaEnabled || isDraft || !!c.meta_ad_id || publishing}
            onClick={openMeta}
            data-testid={`ad-publish-meta-btn-${c.id}`}
          >
            📘 {c.meta_ad_id ? 'On Meta' : 'Publish to Meta'}
          </Button>
        </span>
        <span title={disabledTip(googleEnabled, 'google')}>
          <Button
            size="sm" variant="outline" className="h-7 text-[11px]"
            disabled={!googleEnabled || isDraft || !!c.google_ad_id || publishing}
            onClick={openGoogle}
            data-testid={`ad-publish-google-btn-${c.id}`}
          >
            🔵 {c.google_ad_id ? 'On Google' : 'Publish to Google'}
          </Button>
        </span>
        {published && (
          <Button
            size="sm" variant="outline" className="h-7 text-[11px]"
            onClick={loadPerformance} disabled={perfLoading}
            data-testid={`ad-performance-btn-${c.id}`}
          >
            {perfLoading ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <BarChart3 className="h-3 w-3 mr-1" />}
            Performance
          </Button>
        )}
        {(!metaEnabled || !googleEnabled) && (
          <span className="text-[10px] text-slate-400" data-testid={`ad-publish-flag-note-${c.id}`}>
            {!metaEnabled && !googleEnabled ? 'Meta & Google APIs not configured' : !metaEnabled ? 'Meta API not configured' : 'Google API not configured'}
          </span>
        )}
      </div>

      {panel === 'meta' && (
        <div className="rounded-md border border-blue-200 bg-blue-50/50 p-2 space-y-2" data-testid={`ad-meta-panel-${c.id}`}>
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-semibold text-blue-900">Publish to Meta (Facebook / Instagram)</p>
            <button onClick={() => setPanel(null)} className="text-slate-400 hover:text-slate-600"><X className="h-3.5 w-3.5" /></button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <div>
              <Label className="text-[10px]">Meta Campaign</Label>
              <select value={metaCampaignId} onChange={(e) => setMetaCampaignId(e.target.value)} className={selectCls} data-testid={`ad-meta-campaign-select-${c.id}`}>
                <option value="">+ Create new campaign</option>
                {(metaCampaigns || []).map((mc) => (
                  <option key={mc.id} value={mc.id}>{mc.name} ({mc.status})</option>
                ))}
              </select>
            </div>
            {!metaCampaignId && (
              <div>
                <Label className="text-[10px]">New campaign name</Label>
                <Input className="h-8 text-xs" value={newMetaCampaignName} onChange={(e) => setNewMetaCampaignName(e.target.value)} placeholder="BidVex Listings — Jun 2026" />
              </div>
            )}
            <div>
              <Label className="text-[10px]">Ad language</Label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)} className={selectCls}>
                <option value="en">English</option>
                <option value="fr">Français</option>
              </select>
            </div>
          </div>
          <p className="text-[10px] text-slate-500">Targeting: Canada · 25-55 · auctions/vehicles/liquidation/real-estate. Ad is created PAUSED — activate in Ads Manager.</p>
          <Button size="sm" className="h-7 bg-blue-600 hover:bg-blue-700 text-white text-[11px]" onClick={publishMeta} disabled={publishing} data-testid={`ad-meta-confirm-btn-${c.id}`}>
            {publishing ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Send className="h-3 w-3 mr-1" />}
            Publish
          </Button>
        </div>
      )}

      {panel === 'google' && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50/50 p-2 space-y-2" data-testid={`ad-google-panel-${c.id}`}>
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-semibold text-emerald-900">Publish to Google Ads (Responsive Search Ad)</p>
            <button onClick={() => setPanel(null)} className="text-slate-400 hover:text-slate-600"><X className="h-3.5 w-3.5" /></button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <div>
              <Label className="text-[10px]">Google Campaign</Label>
              <select value={googleCampaignId} onChange={(e) => pickGoogleCampaign(e.target.value)} className={selectCls} data-testid={`ad-google-campaign-select-${c.id}`}>
                <option value="">Select campaign…</option>
                {(googleCampaigns || []).map((gc) => (
                  <option key={gc.id} value={gc.id}>{gc.name} ({gc.status})</option>
                ))}
              </select>
            </div>
            <div>
              <Label className="text-[10px]">Ad Group</Label>
              <select value={googleAdGroupId} onChange={(e) => setGoogleAdGroupId(e.target.value)} className={selectCls} disabled={!googleCampaignId} data-testid={`ad-google-adgroup-select-${c.id}`}>
                <option value="">Select ad group…</option>
                {googleAdGroups.map((ag) => (
                  <option key={ag.id} value={ag.id}>{ag.name} ({ag.status})</option>
                ))}
              </select>
            </div>
            <div>
              <Label className="text-[10px]">Ad language</Label>
              <select value={language} onChange={(e) => setLanguage(e.target.value)} className={selectCls}>
                <option value="en">English</option>
                <option value="fr">Français</option>
              </select>
            </div>
          </div>
          <p className="text-[10px] text-slate-500">Gemini generates 2 extra headline variants (≤30 chars) + 1 extra description (≤90 chars). RSA is created PAUSED.</p>
          <Button size="sm" className="h-7 bg-emerald-600 hover:bg-emerald-700 text-white text-[11px]" onClick={publishGoogle} disabled={publishing || !googleAdGroupId} data-testid={`ad-google-confirm-btn-${c.id}`}>
            {publishing ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Send className="h-3 w-3 mr-1" />}
            Publish RSA
          </Button>
        </div>
      )}

      {perf && (
        <div className="rounded-md border border-slate-200 bg-slate-50 p-2 space-y-1" data-testid={`ad-performance-panel-${c.id}`}>
          <p className="text-[10px] text-slate-500">
            Performance {perf.cached ? '(cached — refreshes hourly)' : ''} · {perf.fetched_at ? new Date(perf.fetched_at).toLocaleString() : ''}
          </p>
          {Object.entries(perf.platforms || {}).map(([platform, m]) => (
            <div key={platform} className="flex items-center gap-2 text-[11px] flex-wrap">
              <Badge variant="outline" className="text-[10px] uppercase">{platform === 'meta' ? '📘 Meta' : '🔵 Google'}</Badge>
              {m.error ? (
                <span className="text-rose-600">{m.error === 'api_not_configured' ? 'API not configured' : m.error}</span>
              ) : (
                <>
                  <span><b>{m.impressions ?? 0}</b> impressions</span>
                  <span><b>{m.clicks ?? 0}</b> clicks</span>
                  <span><b>${(m.spend ?? 0).toFixed ? (m.spend ?? 0).toFixed(2) : m.spend}</b> spend</span>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AdPublishControls;
