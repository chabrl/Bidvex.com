/**
 * iter242 Mission 1 — Admin Promotions Engine
 *
 * Replaces the legacy per-listing promotion manager with the new
 * platform-wide offers control panel backed by `/api/admin/promotions`.
 *
 * Capabilities:
 *   • Management table with status badges, usage counters, action buttons
 *   • Multi-step create / edit dialog
 *   • Auto-generated BIDVEX-XXXXXX coupon codes + custom override
 *   • Target picker (all / tier / province / new_users / custom)
 *   • Audience pre-flight preview before saving
 *   • Pause / Activate / Duplicate / Delete / View Usage Report
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import API_BASE from '../../config';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { Switch } from '../../components/ui/switch';
import PromotionAnalyticsDashboard from '../../components/admin/PromotionAnalyticsDashboard';
import PartnerTrialsAdminSection from '../../components/admin/PartnerTrialsAdminSection';
// iter275 — Coupon conversion analytics tab (mint → click → redeem
// funnel per external campaign, side-by-side subject A/B comparison).
import CouponAnalyticsTab from '../../components/admin/CouponAnalyticsTab';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { Textarea } from '../../components/ui/textarea';
import {
  Plus,
  Copy,
  Trash2,
  Pause,
  Play,
  Sparkles,
  Users,
  RefreshCw,
  Eye,
  Wand2,
  Download,
  Rocket,
  X,
} from 'lucide-react';

const API = API_BASE;

const PROMOTION_TYPES = [
  { value: 'free_platform_fee',   label: 'Free Platform Fee',     blurb: 'Waive buyer premium or seller commission' },
  { value: 'free_first_listing',  label: 'Free First Listing',    blurb: '0% commission on first listing per category' },
  { value: 'reduced_commission',  label: 'Reduced Commission',    blurb: '% discount on platform commission' },
  { value: 'free_promotion_boost',label: 'Free Promotion Boost',  blurb: 'Free promotion credit (basic / standard / premium)' },
  { value: 'subscription_discount',label:'Subscription Discount', blurb: '% off subscription upgrade' },
  { value: 'partner_launch_offer',label: 'Partner Launch Offer',  blurb: 'Bundle for new partner sign-ups' },
];

const TARGET_OPTIONS = [
  { value: 'all',        label: 'All users' },
  { value: 'tier',       label: 'Specific subscription tier' },
  { value: 'province',   label: 'Specific province' },
  { value: 'new_users',  label: 'New users (last N days)' },
  { value: 'custom',     label: 'Manual user list' },
];

const STATUS_BADGE_STYLES = {
  active:    'bg-green-100 text-green-800 border-green-300',
  scheduled: 'bg-amber-100 text-amber-800 border-amber-300',
  expired:   'bg-rose-100 text-rose-800 border-rose-300',
  paused:    'bg-slate-200 text-slate-700 border-slate-300',
  draft:     'bg-blue-100 text-blue-800 border-blue-300',
  exhausted: 'bg-purple-100 text-purple-800 border-purple-300',
};
const STATUS_LABEL = {
  active:    '🟢 Active',
  scheduled: '🟡 Scheduled',
  expired:   '🔴 Expired',
  paused:    '⏸️ Paused',
  draft:     '✏️ Draft',
  exhausted: '✅ Exhausted',
};

const blankForm = () => ({
  id: null,
  name_en: '',
  name_fr: '',
  type: 'free_platform_fee',
  coupon_code: '',
  start_date: new Date().toISOString().slice(0, 10),
  end_date: new Date(Date.now() + 30 * 86_400_000).toISOString().slice(0, 10),
  max_uses: '',
  uses_per_user: 1,
  notify_users: false,
  show_banner: false,
  target_config: {
    target: 'all',
    target_tier: 'premium',
    target_province: 'QC',
    new_user_days: 30,
    custom_user_ids: [],
    custom_emails: [],
  },
  config: {
    discount_percent: 50,
    scope: ['all'],
    credit_tier: 'basic',
    credit_count: 1,
  },
  // iter257 — Optional multi-component composite. Empty array = single-
  // type campaign (back-compat). One+ entries = combined campaign.
  combined_components: [],
});

const PromotionManager = () => {
  const { token, user } = useAuth();
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const [promotions, setPromotions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(blankForm());
  const [editing, setEditing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewResult, setPreviewResult] = useState(null);
  const [usageOpen, setUsageOpen] = useState(null);
  const [usageRows, setUsageRows] = useState([]);

  const fetchPromotions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/admin/promotions`, { headers });
      setPromotions(res?.data?.items || []);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Failed to load promotions');
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => { fetchPromotions(); }, [fetchPromotions]);

  const openCreate = () => {
    setForm(blankForm());
    setEditing(false);
    setPreviewResult(null);
    setCreating(true);
  };

  const openEdit = (promo) => {
    setForm({
      id: promo.id,
      name_en: promo.name_en || '',
      name_fr: promo.name_fr || '',
      type: promo.type,
      coupon_code: promo.coupon_code || '',
      start_date: (promo.start_date || '').slice(0, 10),
      end_date: (promo.end_date || '').slice(0, 10),
      max_uses: promo.max_uses ?? '',
      uses_per_user: promo.uses_per_user || 1,
      notify_users: !!promo.notify_users,
      show_banner: !!promo.show_banner,
      target_config: {
        target: promo.target || promo.target_config?.target || 'all',
        target_tier: promo.target_config?.target_tier || 'premium',
        target_province: promo.target_config?.target_province || 'QC',
        new_user_days: promo.target_config?.new_user_days || 30,
        custom_user_ids: promo.target_config?.custom_user_ids || [],
        custom_emails: promo.target_config?.custom_emails || [],
      },
      config: {
        discount_percent: promo.config?.discount_percent ?? 50,
        scope: promo.config?.scope || ['all'],
        credit_tier: promo.config?.credit_tier || 'basic',
        credit_count: promo.config?.credit_count || 1,
      },
      combined_components: Array.isArray(promo.combined_components) ? promo.combined_components : [],
    });
    setEditing(true);
    setPreviewResult(null);
    setCreating(true);
  };

  const autoCoupon = () => {
    const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let suffix = '';
    for (let i = 0; i < 6; i += 1) suffix += alphabet[Math.floor(Math.random() * alphabet.length)];
    setForm((f) => ({ ...f, coupon_code: `BIDVEX-${suffix}` }));
  };

  const previewAudience = async () => {
    setPreviewLoading(true);
    setPreviewResult(null);
    try {
      const res = await axios.post(
        `${API}/admin/promotions/preview-audience`,
        form.target_config,
        { headers },
      );
      setPreviewResult(res.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Preview failed');
    } finally {
      setPreviewLoading(false);
    }
  };

  const savePromotion = async () => {
    if (!form.name_en?.trim()) { toast.error('Promotion name (EN) is required'); return; }
    setSubmitting(true);
    try {
      const payload = {
        name_en: form.name_en,
        name_fr: form.name_fr || form.name_en,
        type: form.type,
        target_config: form.target_config,
        config: form.config,
        coupon_code: form.coupon_code || undefined,
        start_date: new Date(form.start_date).toISOString(),
        end_date: new Date(form.end_date).toISOString(),
        max_uses: form.max_uses === '' ? null : Number(form.max_uses),
        uses_per_user: Number(form.uses_per_user) || 1,
        notify_users: !!form.notify_users,
        show_banner: !!form.show_banner,
        combined_components: (form.combined_components || []).length > 0
          ? form.combined_components.map((c) => ({ type: c.type, config: c.config || {} }))
          : undefined,
      };
      if (editing && form.id) {
        await axios.patch(`${API}/admin/promotions/${form.id}`, payload, { headers });
        toast.success('Promotion updated');
      } else {
        await axios.post(`${API}/admin/promotions`, payload, { headers });
        toast.success('Promotion created');
      }
      setCreating(false);
      fetchPromotions();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Save failed');
    } finally {
      setSubmitting(false);
    }
  };

  const togglePromotion = async (promo) => {
    const target = promo.status === 'active' ? 'pause' : 'activate';
    try {
      await axios.post(`${API}/admin/promotions/${promo.id}/${target}`, {}, { headers });
      toast.success(`Promotion ${target}d`);
      fetchPromotions();
    } catch (e) {
      toast.error(e?.response?.data?.detail || `${target} failed`);
    }
  };

  const duplicatePromotion = async (promo) => {
    try {
      await axios.post(`${API}/admin/promotions/${promo.id}/duplicate`, {}, { headers });
      toast.success('Duplicate created (status: draft)');
      fetchPromotions();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Duplicate failed');
    }
  };

  // iter251 — Launch broadcast workflow.
  const [launchTarget, setLaunchTarget] = useState(null);
  const [launchSubmitting, setLaunchSubmitting] = useState(false);
  // iter252 — Inbox QA toggle. When ON, the launch dispatches as a
  // self-preview to the admin instead of the live audience.
  const [launchTestSend, setLaunchTestSend] = useState(false);
  // iter254 Mission 3 — Forced language override for the blast.
  // 'auto' = use detect_partner_language(), 'en' / 'fr' = force.
  const [launchLang, setLaunchLang] = useState('auto');
  const openLaunch = (promo) => {
    setLaunchTarget(promo);
    setLaunchTestSend(false);  // always default OFF when opening
    setLaunchLang('auto');     // iter254 — reset language override
  };
  const confirmLaunchBroadcast = async () => {
    if (!launchTarget?.id) return;
    setLaunchSubmitting(true);
    try {
      // Partner-launch-offer promos route through the locked
      // partner-outreach PDF blast endpoint. Every other promo type
      // routes through the generic activation/broadcast pipeline.
      const isPartnerCampaign = launchTarget.type === 'partner_launch_offer';
      const endpoint = isPartnerCampaign
        ? `${API}/admin/promotions/partner-outreach/send`
        : `${API}/admin/promotions/${launchTarget.id}/activate`;
      const body = isPartnerCampaign ? { promotion_id: launchTarget.id } : {};
      // iter252 — Inbox QA: route to admin's own email when toggle is ON.
      if (launchTestSend && isPartnerCampaign) {
        const adminEmail = user?.email;
        if (!adminEmail) {
          toast.error('Could not resolve your session email');
          setLaunchSubmitting(false);
          return;
        }
        body.recipient_emails = [adminEmail];
      }
      // iter254 Mission 3 — Forced-language override.
      if (isPartnerCampaign && launchLang && launchLang !== 'auto') {
        body.forced_lang = launchLang;
      }
      const res = await axios.post(endpoint, body, { headers });
      const data = res?.data || {};
      const sent = data.sent ?? data.recipient_count ?? 0;
      const failed = data.failed ?? 0;
      if (launchTestSend && isPartnerCampaign) {
        toast.success('Test broadcast dispatched to your inbox!', {
          description: `Sent to ${user?.email} — uncheck the toggle to run the real blast.`,
        });
        // iter252 — Keep the modal open so the admin can uncheck and
        // immediately re-fire the real broadcast.
      } else {
        toast.success(`Broadcast launched — ${sent} sent${failed ? `, ${failed} failed` : ''}`, {
          description: `Coupon ${launchTarget.coupon_code} dispatched to the audience.`,
        });
        setLaunchTarget(null);
        fetchPromotions();
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Launch failed');
    } finally {
      setLaunchSubmitting(false);
    }
  };

  const deletePromotion = async (promo) => {
    if (!window.confirm(`Delete "${promo.name_en}" permanently?`)) return;
    try {
      await axios.delete(`${API}/admin/promotions/${promo.id}`, { headers });
      toast.success('Promotion deleted');
      fetchPromotions();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Delete failed');
    }
  };

  const openUsage = async (promo) => {
    setUsageOpen(promo);
    setUsageRows([]);
    try {
      const res = await axios.get(`${API}/admin/promotions/${promo.id}/usage`, { headers });
      setUsageRows(res?.data?.items || []);
    } catch (e) {
      toast.error('Could not load usage report');
    }
  };

  // iter244 Mission 3 — Trigger CSV download of the redemption log.
  const exportUsageCsv = async (promo) => {
    if (!promo?.id) return;
    try {
      const res = await axios.get(`${API}/admin/promotions/${promo.id}/usage.csv`, {
        headers,
        responseType: 'blob',
      });
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `promotion-${promo.coupon_code || promo.id}-usage.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'CSV export failed');
    }
  };

  return (
    <div className="space-y-4" data-testid="admin-promotions-engine">
      {/* iter245 Mission 2 — Promotion Performance Dashboard */}
      <PromotionAnalyticsDashboard />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-amber-500" />
            Admin Promotions Engine
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Platform-wide offers & coupons. Backed by <code className="text-xs bg-slate-100 px-1 rounded">/api/admin/promotions</code>.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchPromotions} data-testid="promotions-refresh-btn">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={openCreate} data-testid="promotions-new-btn" className="bg-gradient-to-r from-amber-500 to-orange-500 text-white border-0">
            <Plus className="h-4 w-4 mr-2" />
            New Promotion
          </Button>
        </div>
      </div>

      {/* Table */}
      <PartnerTrialsAdminSection token={token} />

      {/* iter275 — Coupon conversion analytics (mint → redeem funnel) */}
      <CouponAnalyticsTab token={token} />

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">All Promotions ({promotions.length})</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {loading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : promotions.length === 0 ? (
            <div className="p-12 text-center text-sm text-slate-500" data-testid="promotions-empty-state">
              No promotions yet. Click <strong>New Promotion</strong> to create your first offer.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-3 py-2 text-left">Name</th>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-left">Target</th>
                  <th className="px-3 py-2 text-left">Coupon</th>
                  <th className="px-3 py-2 text-left">Uses</th>
                  <th className="px-3 py-2 text-left">Period</th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {promotions.map((p) => (
                  <tr key={p.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`promotion-row-${p.id}`}>
                    <td className="px-3 py-2 align-top">
                      <div className="font-semibold text-slate-900">{p.name_en}</div>
                      {p.name_fr && <div className="text-xs text-slate-500">{p.name_fr}</div>}
                    </td>
                    <td className="px-3 py-2 align-top">
                      <Badge variant="outline" className="text-xs">{p.type}</Badge>
                    </td>
                    <td className="px-3 py-2 align-top text-xs text-slate-700">
                      {p.target}
                      {p.target_config?.target_tier && ` · ${p.target_config.target_tier}`}
                      {p.target_config?.target_province && ` · ${p.target_config.target_province}`}
                    </td>
                    <td className="px-3 py-2 align-top">
                      <code className="text-[11px] bg-slate-100 px-1.5 py-0.5 rounded font-mono">{p.coupon_code || '—'}</code>
                    </td>
                    <td className="px-3 py-2 align-top text-xs">
                      <strong>{p.current_uses ?? 0}</strong>
                      {p.max_uses ? ` / ${p.max_uses}` : ' / ∞'}
                    </td>
                    <td className="px-3 py-2 align-top text-xs">
                      {(p.start_date || '').slice(0, 10)} → {(p.end_date || '').slice(0, 10)}
                    </td>
                    <td className="px-3 py-2 align-top">
                      <Badge className={`text-xs ${STATUS_BADGE_STYLES[p.status] || ''}`} variant="outline">
                        {STATUS_LABEL[p.status] || p.status}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 align-top text-right whitespace-nowrap">
                      <div className="inline-flex gap-1">
                        <Button size="icon" variant="ghost" title={p.status === 'active' ? 'Pause' : 'Activate'} onClick={() => togglePromotion(p)} data-testid={`promotion-toggle-${p.id}`}>
                          {p.status === 'active' ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                        </Button>
                        <Button size="icon" variant="ghost" title="Edit" onClick={() => openEdit(p)} data-testid={`promotion-edit-${p.id}`}>
                          <Wand2 className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          title="🚀 Launch Broadcast"
                          onClick={() => openLaunch(p)}
                          className="text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50"
                          data-testid={`promotion-launch-${p.id}`}
                        >
                          <Rocket className="h-3.5 w-3.5" />
                        </Button>
                        <Button size="icon" variant="ghost" title="Duplicate" onClick={() => duplicatePromotion(p)} data-testid={`promotion-duplicate-${p.id}`}>
                          <Copy className="h-3.5 w-3.5" />
                        </Button>
                        <Button size="icon" variant="ghost" title="Usage report" onClick={() => openUsage(p)} data-testid={`promotion-usage-${p.id}`}>
                          <Eye className="h-3.5 w-3.5" />
                        </Button>
                        <Button size="icon" variant="ghost" title="Delete" onClick={() => deletePromotion(p)} className="hover:text-rose-600" data-testid={`promotion-delete-${p.id}`}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit dialog */}
      <Dialog open={creating} onOpenChange={(v) => !v && setCreating(false)}>
        <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="promotion-form-dialog">
          <DialogHeader>
            <DialogTitle>{editing ? 'Edit Promotion' : 'Create Promotion'}</DialogTitle>
            <DialogDescription>
              Configure type, target audience, validity window, and coupon code.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            {/* Names */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold">Name (EN)</Label>
                <Input value={form.name_en} onChange={(e) => setForm({ ...form, name_en: e.target.value })} placeholder="Free Partner Promotion" data-testid="promotion-name-en" />
              </div>
              <div>
                <Label className="text-xs font-semibold">Name (FR)</Label>
                <Input value={form.name_fr} onChange={(e) => setForm({ ...form, name_fr: e.target.value })} placeholder="Promotion Partenaire Gratuite" data-testid="promotion-name-fr" />
              </div>
            </div>

            {/* Type */}
            <div>
              <Label className="text-xs font-semibold">Promotion Type</Label>
              <Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v })}>
                <SelectTrigger data-testid="promotion-type-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PROMOTION_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value} data-testid={`promotion-type-${t.value}`}>
                      <div className="flex flex-col py-0.5">
                        <span className="font-semibold">{t.label}</span>
                        <span className="text-[10px] text-slate-500">{t.blurb}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Type-specific config */}
            {(form.type === 'reduced_commission' || form.type === 'subscription_discount') && (
              <div>
                <Label className="text-xs font-semibold">Discount %</Label>
                <Input type="number" min="1" max="100" value={form.config.discount_percent}
                  onChange={(e) => setForm({ ...form, config: { ...form.config, discount_percent: Number(e.target.value) } })}
                  data-testid="promotion-discount-percent"
                />
              </div>
            )}
            {form.type === 'free_promotion_boost' && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs font-semibold">Credit Tier</Label>
                  <Select value={form.config.credit_tier} onValueChange={(v) => setForm({ ...form, config: { ...form.config, credit_tier: v } })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="basic">basic ($9.99)</SelectItem>
                      <SelectItem value="standard">standard ($24.99)</SelectItem>
                      <SelectItem value="premium">premium ($49.99)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs font-semibold">Credits</Label>
                  <Input type="number" min="1" value={form.config.credit_count}
                    onChange={(e) => setForm({ ...form, config: { ...form.config, credit_count: Number(e.target.value) } })}
                  />
                </div>
              </div>
            )}

            {/* iter257 — Multi-component composite editor. Stack any number
                of promotion types inside ONE campaign. The runtime engine
                picks the component giving the biggest CAD saving for each
                transaction_type. Each component carries its own config:
                  • free_platform_fee / free_first_listing / free_promotion_boost /
                    partner_launch_offer  → always 100% off the eligible bucket
                  • reduced_commission / subscription_discount → custom %
                  • Optional config.flat_amount_cad / config.max_discount_cad
                    apply on top of the % math.                */}
            <div
              className="border border-violet-200 bg-violet-50/50 rounded-lg p-3 space-y-2"
              data-testid="combined-components-section"
            >
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-xs font-bold text-violet-900">
                    🧬 Combined Components (Multi-Promotion Engine)
                  </Label>
                  <p className="text-[11px] text-violet-700 mt-0.5">
                    Stack 2+ promotion types in a single campaign. Optional —
                    leave empty for a single-type campaign.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="border-violet-400 text-violet-800 hover:bg-violet-100"
                  data-testid="add-combined-component-btn"
                  onClick={() => setForm((f) => ({
                    ...f,
                    combined_components: [
                      ...(f.combined_components || []),
                      { type: 'reduced_commission', config: { discount_percent: 25 } },
                    ],
                  }))}
                >
                  + Add Component
                </Button>
              </div>

              {(form.combined_components || []).length === 0 ? (
                <p className="text-[11px] text-violet-700 italic" data-testid="no-combined-components">
                  No components yet — this campaign will use the single
                  &quot;Promotion Type&quot; above.
                </p>
              ) : (
                <div className="space-y-2">
                  {(form.combined_components || []).map((comp, idx) => (
                    <div
                      key={idx}
                      className="grid grid-cols-12 gap-2 items-end bg-white border border-violet-200 rounded-md p-2"
                      data-testid={`combined-component-row-${idx}`}
                    >
                      <div className="col-span-5">
                        <Label className="text-[10px] uppercase tracking-wide text-slate-500">Type</Label>
                        <Select
                          value={comp.type}
                          onValueChange={(v) => setForm((f) => ({
                            ...f,
                            combined_components: f.combined_components.map((c, i) =>
                              i === idx ? { ...c, type: v } : c
                            ),
                          }))}
                        >
                          <SelectTrigger data-testid={`combined-component-type-${idx}`}><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {PROMOTION_TYPES.map((t) => (
                              <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="col-span-3">
                        <Label className="text-[10px] uppercase tracking-wide text-slate-500">% off</Label>
                        <Input
                          type="number" min="0" max="100"
                          value={comp.config?.discount_percent ?? ''}
                          placeholder={['partner_launch_offer','free_platform_fee','free_first_listing','free_promotion_boost'].includes(comp.type) ? '100' : '25'}
                          onChange={(e) => setForm((f) => ({
                            ...f,
                            combined_components: f.combined_components.map((c, i) =>
                              i === idx ? { ...c, config: { ...(c.config || {}), discount_percent: e.target.value === '' ? undefined : Number(e.target.value) } } : c
                            ),
                          }))}
                          data-testid={`combined-component-percent-${idx}`}
                        />
                      </div>
                      <div className="col-span-3">
                        <Label className="text-[10px] uppercase tracking-wide text-slate-500">+ Flat $CAD</Label>
                        <Input
                          type="number" min="0"
                          value={comp.config?.flat_amount_cad ?? ''}
                          placeholder="0"
                          onChange={(e) => setForm((f) => ({
                            ...f,
                            combined_components: f.combined_components.map((c, i) =>
                              i === idx ? { ...c, config: { ...(c.config || {}), flat_amount_cad: e.target.value === '' ? undefined : Number(e.target.value) } } : c
                            ),
                          }))}
                          data-testid={`combined-component-flat-${idx}`}
                        />
                      </div>
                      <div className="col-span-1 flex justify-end">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="text-rose-600 hover:bg-rose-50 h-8 w-8"
                          onClick={() => setForm((f) => ({
                            ...f,
                            combined_components: f.combined_components.filter((_, i) => i !== idx),
                          }))}
                          data-testid={`combined-component-remove-${idx}`}
                          aria-label="Remove component"
                        >
                          ✕
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {(form.combined_components || []).length > 0 && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full border-violet-400 text-violet-800 hover:bg-violet-100 mt-1"
                  data-testid="preview-combined-btn"
                  onClick={async () => {
                    try {
                      const res = await axios.post(
                        `${API}/admin/promotions/preview-combined`,
                        {
                          components: form.combined_components.map((c) => ({
                            type: c.type, config: c.config || {},
                          })),
                          listing_type: 'vehicles',
                        },
                        { headers },
                      );
                      const lines = Object.entries(res.data?.preview || {}).map(([tx, m]) => {
                        if (!m.applies) return `${tx}: no match`;
                        const pct = m.discount_percent ?? 0;
                        return `${tx}: -$${Number(m.discount_amount_cad).toFixed(2)} (final $${Number(m.final_amount_cad).toFixed(2)} • ${pct}%)`;
                      });
                      toast.success(lines.join('\n'), { duration: 8000 });
                    } catch (e) {
                      toast.error(e?.response?.data?.detail || 'Preview failed');
                    }
                  }}
                >
                  🧮 Preview Combined Math
                </Button>
              )}
            </div>

            {/* Target */}
            <div>
              <Label className="text-xs font-semibold">Target Audience</Label>
              <Select value={form.target_config.target} onValueChange={(v) => setForm({ ...form, target_config: { ...form.target_config, target: v } })}>
                <SelectTrigger data-testid="promotion-target-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TARGET_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value} data-testid={`promotion-target-${o.value}`}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {form.target_config.target === 'tier' && (
              <div>
                <Label className="text-xs font-semibold">Tier</Label>
                <Select value={form.target_config.target_tier} onValueChange={(v) => setForm({ ...form, target_config: { ...form.target_config, target_tier: v } })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="standard">Standard</SelectItem>
                    <SelectItem value="premium">Premium</SelectItem>
                    <SelectItem value="vip_elite">VIP Elite</SelectItem>
                    <SelectItem value="partner">Partner</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            {form.target_config.target === 'province' && (
              <div>
                <Label className="text-xs font-semibold">Province</Label>
                <Select value={form.target_config.target_province} onValueChange={(v) => setForm({ ...form, target_config: { ...form.target_config, target_province: v } })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="QC">Quebec</SelectItem>
                    <SelectItem value="ON">Ontario</SelectItem>
                    <SelectItem value="BC">British Columbia</SelectItem>
                    <SelectItem value="AB">Alberta</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            {form.target_config.target === 'new_users' && (
              <div>
                <Label className="text-xs font-semibold">New within last (days)</Label>
                <Input type="number" min="1" value={form.target_config.new_user_days}
                  onChange={(e) => setForm({ ...form, target_config: { ...form.target_config, new_user_days: Number(e.target.value) } })}
                />
              </div>
            )}
            {form.target_config.target === 'custom' && (
              <div>
                <Label className="text-xs font-semibold">User emails (one per line)</Label>
                <Textarea rows={3}
                  value={(form.target_config.custom_emails || []).join('\n')}
                  onChange={(e) => setForm({
                    ...form,
                    target_config: {
                      ...form.target_config,
                      custom_emails: e.target.value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean),
                    },
                  })}
                  placeholder="partner1@example.com&#10;partner2@example.com"
                />
              </div>
            )}

            {/* Audience preview */}
            <div className="border rounded-lg bg-slate-50 p-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-700">Pre-flight audience preview</span>
                <Button size="sm" variant="outline" onClick={previewAudience} disabled={previewLoading} data-testid="promotion-preview-audience-btn">
                  <Users className="h-3.5 w-3.5 mr-1.5" />
                  {previewLoading ? 'Counting…' : 'Preview audience'}
                </Button>
              </div>
              {previewResult && (
                <div className="mt-2 text-xs text-slate-700" data-testid="promotion-preview-result">
                  <strong>{previewResult.count ?? 0}</strong> eligible users.
                  {previewResult.sample?.length > 0 && (
                    <div className="mt-1 text-[11px] text-slate-500">
                      Sample: {previewResult.sample.slice(0, 5).join(', ')}{previewResult.sample.length > 5 && '…'}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Coupon */}
            <div>
              <Label className="text-xs font-semibold">Coupon Code</Label>
              <div className="flex gap-2">
                <Input value={form.coupon_code} onChange={(e) => setForm({ ...form, coupon_code: e.target.value.toUpperCase() })} placeholder="Auto-generated if blank" data-testid="promotion-coupon-input" />
                <Button type="button" variant="outline" onClick={autoCoupon} data-testid="promotion-coupon-autogen-btn">
                  <Wand2 className="h-3.5 w-3.5 mr-1.5" />
                  Auto
                </Button>
              </div>
            </div>

            {/* Validity */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold">Start date</Label>
                <Input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} data-testid="promotion-start-date" />
              </div>
              <div>
                <Label className="text-xs font-semibold">End date</Label>
                <Input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} data-testid="promotion-end-date" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-semibold">Max uses (total)</Label>
                <Input type="number" min="0" value={form.max_uses} onChange={(e) => setForm({ ...form, max_uses: e.target.value })} placeholder="∞ unlimited" />
              </div>
              <div>
                <Label className="text-xs font-semibold">Uses per user</Label>
                <Input type="number" min="1" value={form.uses_per_user} onChange={(e) => setForm({ ...form, uses_per_user: e.target.value })} />
              </div>
            </div>

            {/* Notification toggles */}
            <div className="flex gap-4 pt-1">
              <label className="text-xs flex items-center gap-1.5 cursor-pointer">
                <input type="checkbox" checked={form.notify_users} onChange={(e) => setForm({ ...form, notify_users: e.target.checked })} data-testid="promotion-notify-users" />
                Email broadcast on activation
              </label>
              <label className="text-xs flex items-center gap-1.5 cursor-pointer">
                <input type="checkbox" checked={form.show_banner} onChange={(e) => setForm({ ...form, show_banner: e.target.checked })} data-testid="promotion-show-banner" />
                Show platform banner
              </label>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setCreating(false)} disabled={submitting}>Cancel</Button>
            <Button onClick={savePromotion} disabled={submitting} data-testid="promotion-save-btn">
              {submitting ? 'Saving…' : (editing ? 'Save changes' : 'Create promotion')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Usage report dialog */}
      <Dialog open={!!usageOpen} onOpenChange={(v) => !v && setUsageOpen(null)}>
        <DialogContent className="sm:max-w-xl max-h-[80vh] overflow-y-auto" data-testid="promotion-usage-dialog">
          <DialogHeader>
            <DialogTitle>Usage report — {usageOpen?.name_en}</DialogTitle>
            <DialogDescription>
              {usageOpen?.coupon_code} · {usageRows.length} redemption(s)
            </DialogDescription>
            {usageOpen && (
              <div className="flex justify-end pt-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => exportUsageCsv(usageOpen)}
                  data-testid="promotion-usage-export-csv-btn"
                  disabled={usageRows.length === 0}
                >
                  <Download className="h-3.5 w-3.5 mr-1.5" />
                  Export CSV
                </Button>
              </div>
            )}
          </DialogHeader>
          {usageRows.length === 0 ? (
            <div className="py-6 text-center text-sm text-slate-500">No redemptions yet.</div>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-2 py-1.5 text-left">User</th>
                  <th className="px-2 py-1.5 text-left">Tx Type</th>
                  <th className="px-2 py-1.5 text-right">Saved (CAD)</th>
                  <th className="px-2 py-1.5 text-left">When</th>
                </tr>
              </thead>
              <tbody>
                {usageRows.map((r) => (
                  <tr key={r.id || r.used_at} className="border-t border-slate-100">
                    <td className="px-2 py-1.5">{r.user_id?.slice(0, 8) || '—'}</td>
                    <td className="px-2 py-1.5">{r.transaction_type || '—'}</td>
                    <td className="px-2 py-1.5 text-right">${(r.saved_amount || 0).toFixed(2)}</td>
                    <td className="px-2 py-1.5">{(r.used_at || '').slice(0, 16).replace('T', ' ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </DialogContent>
      </Dialog>

      {/* iter251 — Launch Broadcast confirmation modal */}
      <Dialog
        open={!!launchTarget}
        onOpenChange={(o) => { if (!o) setLaunchTarget(null); }}
      >
        <DialogContent className="max-w-md" data-testid="launch-broadcast-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <Rocket className="h-4 w-4 text-indigo-600" />
              Launch Broadcast Now
            </DialogTitle>
            <DialogDescription>
              This will fire the campaign email <strong>immediately</strong> to the
              audience defined by this promotion's target configuration.
              Unsubscribed addresses are automatically excluded.
            </DialogDescription>
          </DialogHeader>
          {launchTarget && (
            <div className="bg-slate-50 border border-slate-200 rounded-md p-3 text-xs space-y-1.5">
              <div className="flex justify-between">
                <span className="text-slate-500">Campaign</span>
                <span className="text-slate-900 font-medium truncate ml-3">{launchTarget.name_en}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Coupon</span>
                <code className="font-mono text-slate-900">{launchTarget.coupon_code}</code>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Target</span>
                <span className="text-slate-900 font-medium">
                  {launchTarget.target_config?.target || launchTarget.target || 'all'}
                </span>
              </div>
              {launchTarget.target_config?.custom_emails?.length > 0 && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Manual list size</span>
                  <span className="text-slate-900 font-medium">
                    {launchTarget.target_config.custom_emails.length} email
                    {launchTarget.target_config.custom_emails.length === 1 ? '' : 's'}
                  </span>
                </div>
              )}
              {launchTarget.type === 'partner_launch_offer' && (
                <div className="mt-2 pt-2 border-t border-slate-200 text-[11px] text-indigo-700">
                  ⓘ Partner Outreach blast — includes the locked English/French
                  email body + Partner Program Evaluation Guide PDF flyer.
                </div>
              )}
            </div>
          )}

          {/* iter252 — Inbox QA safety toggle */}
          {launchTarget?.type === 'partner_launch_offer' && (
            <div
              className={`flex items-start gap-3 rounded-md border p-3 transition-colors ${
                launchTestSend
                  ? 'border-amber-300 bg-amber-50'
                  : 'border-slate-200 bg-slate-50'
              }`}
              data-testid="launch-test-send-toggle-row"
            >
              <Switch
                id="launch-test-send-toggle"
                checked={launchTestSend}
                onCheckedChange={setLaunchTestSend}
                disabled={launchSubmitting}
                data-testid="launch-test-send-toggle"
              />
              <label
                htmlFor="launch-test-send-toggle"
                className="text-xs leading-snug cursor-pointer flex-1"
              >
                <span className={`font-semibold ${launchTestSend ? 'text-amber-900' : 'text-slate-900'}`}>
                  🧪 Test Send to Myself (Inbox QA Pass)
                </span>
                <p className="mt-0.5 text-slate-600">
                  {launchTestSend
                    ? `The blast will be redirected to ${user?.email || 'your inbox'} only — the real audience will NOT receive this email.`
                    : 'When enabled, the broadcast routes only to your admin email so you can preview the live render before firing to the real audience.'}
                </p>
              </label>
            </div>
          )}

          {/* iter254 Mission 3 — Document language selector */}
          {launchTarget?.type === 'partner_launch_offer' && (
            <div className="space-y-1.5" data-testid="launch-lang-selector-row">
              <Label className="text-xs font-semibold text-slate-700">
                🌍 Document Language / Langue
              </Label>
              <Select value={launchLang} onValueChange={setLaunchLang}>
                <SelectTrigger className="h-9 text-xs" data-testid="launch-lang-selector">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto" data-testid="launch-lang-auto">
                    Automatic (Geo-detected)
                  </SelectItem>
                  <SelectItem value="en" data-testid="launch-lang-en">
                    Force English (EN)
                  </SelectItem>
                  <SelectItem value="fr" data-testid="launch-lang-fr">
                    Force French (FR)
                  </SelectItem>
                </SelectContent>
              </Select>
              <p className="text-[11px] text-slate-500">
                {launchLang === 'auto'
                  ? 'Each recipient gets the variant matching their province + preferred_language.'
                  : `All recipients will receive the ${launchLang === 'fr' ? 'French' : 'English'} variant regardless of their profile.`}
              </p>
            </div>
          )}
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              onClick={() => setLaunchTarget(null)}
              disabled={launchSubmitting}
              data-testid="launch-broadcast-cancel"
            >
              <X className="h-3.5 w-3.5 mr-1.5" />
              Cancel
            </Button>
            <Button
              type="button"
              onClick={confirmLaunchBroadcast}
              disabled={launchSubmitting}
              className={
                launchTestSend
                  ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white border-0'
                  : 'bg-gradient-to-r from-indigo-600 to-blue-600 text-white border-0'
              }
              data-testid="launch-broadcast-confirm"
            >
              <Rocket className={`h-3.5 w-3.5 mr-1.5 ${launchSubmitting ? 'animate-pulse' : ''}`} />
              {launchSubmitting
                ? (launchTestSend ? 'Sending test…' : 'Launching…')
                : (launchTestSend ? '✉️ Send Test to My Inbox' : '🚀 Launch Broadcast Now')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PromotionManager;
