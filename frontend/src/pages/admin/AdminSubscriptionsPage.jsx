/**
 * iter217 Phase 5 Hotfix v6.5 — Admin Subscription Management.
 *
 * Route: /admin/subscriptions  (also mounted as a tab under /admin)
 *
 * Four tabs:
 *   1. Global Settings       — base price, discount type/value/label, dates
 *   2. Per-User Override     — search broker by name/email, apply discounts,
 *                              grant free access, extend, suspend, reactivate
 *   3. Subscription List     — table of all broker subscriptions with filters
 *                              and CSV export
 *   4. Revenue Summary       — ARR / MRR / discounted-vs-full / revenue lost
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import API_BASE from '../../config';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Switch } from '../../components/ui/switch';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../../components/ui/tabs';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../components/ui/select';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../components/ui/dialog';
import { Alert, AlertDescription } from '../../components/ui/alert';
import {
  CreditCard, Search, Download, DollarSign, Users,
  Sparkles, Settings, AlertTriangle, Loader2, CheckCircle2,
} from 'lucide-react';

const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');
const _authHeaders = () => ({ Authorization: `Bearer ${_token()}` });
const _fmt = (n) => new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(n || 0));
const _fmtDate = (v) => {
  if (!v) return '—';
  try { return new Date(v).toLocaleDateString('en-CA'); } catch { return '—'; }
};

const STATUS_BADGE = {
  active:    { color: 'bg-emerald-100 text-emerald-800',  label_en: 'Active',     label_fr: 'Actif' },
  free:      { color: 'bg-purple-100 text-purple-800',    label_en: 'Free',       label_fr: 'Gratuit' },
  comp:      { color: 'bg-purple-100 text-purple-800',    label_en: 'Comp',       label_fr: 'Complimentaire' },
  expired:   { color: 'bg-slate-200 text-slate-700',      label_en: 'Expired',    label_fr: 'Expiré' },
  suspended: { color: 'bg-rose-100 text-rose-800',        label_en: 'Suspended',  label_fr: 'Suspendu' },
  unpaid:    { color: 'bg-amber-100 text-amber-900',      label_en: 'Unpaid',     label_fr: 'Impayé' },
};

function StatusBadge({ status, lang }) {
  const cfg = STATUS_BADGE[status] || STATUS_BADGE.unpaid;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${cfg.color}`} data-testid={`sub-status-${status}`}>
      {lang === 'fr' ? cfg.label_fr : cfg.label_en}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────
// TAB 1 — Global Settings
// ─────────────────────────────────────────────────────────────────────
function GlobalSettingsTab({ lang }) {
  const [settings, setSettings] = useState(null);
  const [saving, setSaving]     = useState(false);
  const [saved, setSaved]       = useState(false);
  const [error, setError]       = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await axios.get(`${API_BASE}/admin/subscriptions/settings`, { headers: _authHeaders() });
      setSettings(r.data);
    } catch (e) {
      setError(e?.response?.data?.detail?.error || e?.message || 'Failed to load settings');
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const set = (k, v) => setSettings(prev => ({ ...prev, [k]: v }));

  const save = async () => {
    setSaving(true); setError(null); setSaved(false);
    try {
      const r = await axios.patch(`${API_BASE}/admin/subscriptions/settings`, {
        plan_name:        settings.plan_name,
        base_cad:         Number(settings.base_cad),
        currency:         settings.currency,
        discount_active:  !!settings.discount_active,
        discount_type:    settings.discount_type,
        discount_value:   Number(settings.discount_value),
        discount_label:   settings.discount_label,
        discount_starts_at: settings.discount_starts_at || null,
        discount_ends_at:   settings.discount_ends_at   || null,
        period_days:      Number(settings.period_days),
        auto_renew:       !!settings.auto_renew,
      }, { headers: _authHeaders() });
      setSettings(r.data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      setError(e?.response?.data?.detail?.error || e?.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (!settings) return <div className="py-8 text-center text-slate-500"><Loader2 className="inline animate-spin mr-2" />Loading…</div>;

  const effectiveFinal = (() => {
    const base = Number(settings.base_cad) || 0;
    if (!settings.discount_active) return base;
    const v = Number(settings.discount_value) || 0;
    if (settings.discount_type === 'fixed') return Math.max(0, base - v);
    return Math.max(0, base * (1 - Math.max(0, Math.min(100, v)) / 100));
  })();

  return (
    <div className="space-y-4">
      {error  && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertDescription>{String(error)}</AlertDescription></Alert>}
      {saved  && <Alert className="bg-emerald-50 border-emerald-200"><CheckCircle2 className="h-4 w-4 text-emerald-600" /><AlertDescription className="text-emerald-700">{lang==='fr'?'Paramètres mis à jour. Les changements s\'appliquent immédiatement aux nouvelles inscriptions.':'Settings updated. Changes apply immediately to new sign-ups.'}</AlertDescription></Alert>}

      <Card>
        <CardHeader><CardTitle className="text-base">{lang === 'fr' ? 'Forfait annuel courtier' : 'Broker Annual Plan'}</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label>{lang === 'fr' ? 'Nom du forfait' : 'Plan name'}</Label>
              <Input value={settings.plan_name} onChange={(e) => set('plan_name', e.target.value)} data-testid="settings-plan-name" />
            </div>
            <div>
              <Label>{lang === 'fr' ? 'Devise' : 'Currency'}</Label>
              <Input value={settings.currency} onChange={(e) => set('currency', e.target.value.toUpperCase())} data-testid="settings-currency" />
            </div>
            <div>
              <Label>{lang === 'fr' ? 'Prix de base (par an)' : 'Base price (per year)'}</Label>
              <Input type="number" min="0" step="0.01" value={settings.base_cad} onChange={(e) => set('base_cad', e.target.value)} data-testid="settings-base-cad" />
            </div>
            <div>
              <Label>{lang === 'fr' ? 'Durée (jours)' : 'Period (days)'}</Label>
              <Input type="number" min="1" value={settings.period_days} onChange={(e) => set('period_days', e.target.value)} data-testid="settings-period-days" />
            </div>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <Switch checked={!!settings.auto_renew} onCheckedChange={(v) => set('auto_renew', !!v)} data-testid="settings-auto-renew" />
            <Label className="text-sm">{lang === 'fr' ? 'Renouvellement automatique (avis par courriel 30 jours avant)' : 'Auto-renewal (email notification 30 days before renewal)'}</Label>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-amber-500" />
            {lang === 'fr' ? 'Rabais promotionnel' : 'Promotional Discount'}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <Switch checked={!!settings.discount_active} onCheckedChange={(v) => set('discount_active', !!v)} data-testid="settings-discount-active" />
            <Label className="text-sm">{lang === 'fr' ? 'Rabais activé' : 'Discount enabled'}</Label>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <Label>{lang === 'fr' ? 'Type' : 'Type'}</Label>
              <Select value={settings.discount_type} onValueChange={(v) => set('discount_type', v)}>
                <SelectTrigger data-testid="settings-discount-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="percentage">{lang === 'fr' ? 'Pourcentage (%)' : 'Percentage (%)'}</SelectItem>
                  <SelectItem value="fixed">{lang === 'fr' ? 'Montant fixe ($)' : 'Fixed Amount ($)'}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>{lang === 'fr' ? 'Valeur' : 'Value'}</Label>
              <Input type="number" min="0" step="0.01" value={settings.discount_value} onChange={(e) => set('discount_value', e.target.value)} data-testid="settings-discount-value" />
            </div>
            <div>
              <Label>{lang === 'fr' ? 'Étiquette affichée' : 'Display label'}</Label>
              <Input value={settings.discount_label} onChange={(e) => set('discount_label', e.target.value)} data-testid="settings-discount-label" />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Label>{lang === 'fr' ? 'Début (optionnel)' : 'Effective from (optional)'}</Label>
              <Input type="datetime-local"
                     value={settings.discount_starts_at ? String(settings.discount_starts_at).slice(0,16) : ''}
                     onChange={(e) => set('discount_starts_at', e.target.value || null)}
                     data-testid="settings-discount-starts" />
            </div>
            <div>
              <Label>{lang === 'fr' ? 'Fin (optionnel)' : 'Expires on (optional)'}</Label>
              <Input type="datetime-local"
                     value={settings.discount_ends_at ? String(settings.discount_ends_at).slice(0,16) : ''}
                     onChange={(e) => set('discount_ends_at', e.target.value || null)}
                     data-testid="settings-discount-ends" />
            </div>
          </div>

          <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
            <p className="text-xs text-slate-500 uppercase tracking-wide font-semibold">{lang==='fr'?'Aperçu':'Live preview'}</p>
            <div className="mt-2 flex items-end gap-3 flex-wrap">
              <span className="text-2xl font-bold" data-testid="settings-preview-final">{_fmt(effectiveFinal)}</span>
              {effectiveFinal !== Number(settings.base_cad) && (
                <span className="text-sm text-slate-400 line-through">{_fmt(settings.base_cad)}</span>
              )}
              <span className="text-xs text-slate-500">/ {lang==='fr'?'an':'year'}</span>
            </div>
            {settings.discount_active && settings.discount_label && (
              <p className="text-xs text-amber-600 mt-1">{settings.discount_label}</p>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={save} disabled={saving} data-testid="settings-save-btn"
                className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white">
          {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
          {lang === 'fr' ? 'Enregistrer les modifications' : 'Save Changes'}
        </Button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// TAB 2 — Per-User Override
// ─────────────────────────────────────────────────────────────────────
function PerUserOverrideTab({ lang }) {
  const [search, setSearch] = useState('');
  const [rows, setRows]     = useState([]);
  const [loading, setLoading] = useState(false);
  const [picked, setPicked] = useState(null);   // { broker_id, ... }
  const [override, setOverride] = useState(null);
  const [error, setError]   = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved]   = useState(false);

  const doSearch = useCallback(async (q) => {
    if (!q || q.length < 2) { setRows([]); return; }
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/admin/subscriptions/list?search=${encodeURIComponent(q)}`, { headers: _authHeaders() });
      setRows(r.data?.data || []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => doSearch(search), 400);
    return () => clearTimeout(t);
  }, [search, doSearch]);

  const openOverride = (row) => {
    setPicked(row);
    setOverride({
      base_cad:           row.base_cad,
      discount_pct:       row.discount_pct,
      status:             row.subscription_status,
      expires_at:         row.subscription_expires_at,
      extend_days:        '',
      note:               row.subscription_note || '',
      free_access:        row.subscription_status === 'free',
    });
    setSaved(false); setError(null);
  };

  const applyOverride = async () => {
    if (!picked) return;
    setSaving(true); setError(null); setSaved(false);
    try {
      const payload = {};
      if (override.base_cad !== undefined && override.base_cad !== null && override.base_cad !== '') payload.base_cad = Number(override.base_cad);
      if (override.discount_pct !== undefined && override.discount_pct !== null && override.discount_pct !== '') payload.discount_pct = Number(override.discount_pct);
      if (override.status) payload.status = override.status;
      if (override.expires_at) payload.expires_at = override.expires_at;
      if (override.extend_days) payload.extend_days = Number(override.extend_days);
      if (override.note !== undefined) payload.note = override.note;
      if (override.free_access) payload.free_access = true;

      await axios.patch(
        `${API_BASE}/admin/brokers/${picked.broker_id}/subscription`,
        payload,
        { headers: _authHeaders() }
      );
      setSaved(true);
      await doSearch(search);
      setTimeout(() => { setPicked(null); setSaved(false); }, 1200);
    } catch (e) {
      setError(e?.response?.data?.detail?.error || e?.message || 'Override failed');
    } finally {
      setSaving(false);
    }
  };

  const setOv = (k, v) => setOverride(prev => ({ ...prev, [k]: v }));

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-4">
          <Label className="text-xs text-slate-500">{lang === 'fr' ? 'Rechercher un courtier par nom ou courriel' : 'Search broker by name or email'}</Label>
          <div className="relative mt-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={lang === 'fr' ? 'p. ex. john@... ou Auctioneer Inc' : 'e.g. john@... or Auctioneer Inc'}
              className="pl-10"
              data-testid="override-search-input"
            />
          </div>
        </CardContent>
      </Card>

      {loading && <p className="text-center py-4 text-slate-500"><Loader2 className="inline animate-spin mr-2" />Searching…</p>}

      {!loading && rows.length === 0 && search.length >= 2 && (
        <p className="text-center py-6 text-slate-500">{lang === 'fr' ? 'Aucun courtier trouvé.' : 'No brokers found.'}</p>
      )}

      <div className="space-y-2">
        {rows.map(r => (
          <Card key={r.broker_id} className="cursor-pointer hover:shadow-md transition" onClick={() => openOverride(r)} data-testid={`override-row-${r.broker_id}`}>
            <CardContent className="p-3 flex items-center justify-between gap-3 flex-wrap">
              <div className="min-w-[200px]">
                <p className="font-semibold text-sm">{r.legal_business_name}</p>
                <p className="text-xs text-slate-500">{r.user_email} · {r.operating_province}</p>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={r.subscription_status} lang={lang} />
                <span className="text-sm font-medium">{_fmt(r.final_cad)}</span>
                {r.discount_pct > 0 && <span className="text-xs text-amber-600">−{r.discount_pct}%</span>}
                <Button size="sm" variant="outline">{lang === 'fr' ? 'Modifier' : 'Override'}</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Override Modal */}
      <Dialog open={!!picked} onOpenChange={(o) => { if (!o) setPicked(null); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{lang === 'fr' ? 'Modifier l\'abonnement' : 'Override Subscription'}</DialogTitle>
          </DialogHeader>
          {picked && override && (
            <div className="space-y-3">
              <p className="text-sm text-slate-600 dark:text-slate-300">
                <strong>{picked.legal_business_name}</strong> · {picked.user_email}
              </p>
              {error && <Alert variant="destructive"><AlertDescription>{String(error)}</AlertDescription></Alert>}
              {saved && <Alert className="bg-emerald-50 border-emerald-200"><AlertDescription className="text-emerald-700">{lang==='fr'?'Modifications enregistrées.':'Override saved.'}</AlertDescription></Alert>}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">{lang === 'fr' ? 'Prix de base ($)' : 'Base price ($)'}</Label>
                  <Input type="number" min="0" step="0.01" value={override.base_cad || ''} onChange={(e) => setOv('base_cad', e.target.value)} data-testid="override-base-cad" />
                </div>
                <div>
                  <Label className="text-xs">{lang === 'fr' ? 'Rabais (%)' : 'Discount (%)'}</Label>
                  <Input type="number" min="0" max="100" step="1" value={override.discount_pct || 0} onChange={(e) => setOv('discount_pct', e.target.value)} data-testid="override-discount-pct" />
                </div>
              </div>

              <div>
                <Label className="text-xs">{lang === 'fr' ? 'Statut' : 'Status'}</Label>
                <Select value={override.status || 'unpaid'} onValueChange={(v) => setOv('status', v)}>
                  <SelectTrigger data-testid="override-status"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="unpaid">{lang === 'fr' ? 'Impayé' : 'Unpaid'}</SelectItem>
                    <SelectItem value="active">{lang === 'fr' ? 'Actif' : 'Active'}</SelectItem>
                    <SelectItem value="free">{lang === 'fr' ? 'Gratuit' : 'Free'}</SelectItem>
                    <SelectItem value="comp">{lang === 'fr' ? 'Complimentaire' : 'Comp'}</SelectItem>
                    <SelectItem value="suspended">{lang === 'fr' ? 'Suspendu' : 'Suspended'}</SelectItem>
                    <SelectItem value="expired">{lang === 'fr' ? 'Expiré' : 'Expired'}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">{lang === 'fr' ? 'Date d\'expiration' : 'Expires at'}</Label>
                  <Input
                    type="datetime-local"
                    value={override.expires_at ? String(override.expires_at).slice(0,16) : ''}
                    onChange={(e) => setOv('expires_at', e.target.value || null)}
                    data-testid="override-expires-at"
                  />
                </div>
                <div>
                  <Label className="text-xs">{lang === 'fr' ? 'Prolonger (jours)' : 'Extend by (days)'}</Label>
                  <Input type="number" min="0" value={override.extend_days || ''} onChange={(e) => setOv('extend_days', e.target.value)} placeholder="0" data-testid="override-extend-days" />
                </div>
              </div>

              <label className="flex items-start gap-2 cursor-pointer">
                <input type="checkbox" checked={!!override.free_access} onChange={(e) => setOv('free_access', e.target.checked)} className="mt-1" data-testid="override-free-access" />
                <span className="text-sm">{lang === 'fr' ? 'Accorder un accès gratuit (rabais 100 % + statut "Gratuit"). Note interne obligatoire ci-dessous.' : 'Grant free access (100% discount + status="free"). Admin note required below.'}</span>
              </label>

              <div>
                <Label className="text-xs">{lang === 'fr' ? 'Note interne (non visible à l\'utilisateur)' : 'Internal admin note (not shown to user)'}{override.free_access && ' *'}</Label>
                <Input value={override.note || ''} onChange={(e) => setOv('note', e.target.value)} placeholder={lang === 'fr' ? 'Raison de l\'ajustement…' : 'Reason for adjustment…'} data-testid="override-note" />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setPicked(null)} disabled={saving}>{lang === 'fr' ? 'Annuler' : 'Cancel'}</Button>
            <Button onClick={applyOverride} disabled={saving || (override?.free_access && !override?.note?.trim())} data-testid="override-apply-btn"
                    className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] text-white">
              {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              {lang === 'fr' ? 'Appliquer' : 'Apply'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// TAB 3 — Subscription List
// ─────────────────────────────────────────────────────────────────────
function SubscriptionListTab({ lang }) {
  const [rows, setRows]       = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter]   = useState('all');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = filter !== 'all' ? `?status=${filter}` : '';
      const r = await axios.get(`${API_BASE}/admin/subscriptions/list${qs}`, { headers: _authHeaders() });
      setRows(r.data?.data || []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [filter]);
  useEffect(() => { load(); }, [load]);

  const exportCSV = () => {
    if (!rows.length) return;
    const headers = [
      'broker_id','user_name','user_email','legal_business_name','operating_province',
      'plan_name','subscription_status','base_cad','discount_pct','final_cad',
      'subscription_started_at','subscription_expires_at','created_at',
    ];
    const lines = [headers.join(',')];
    for (const r of rows) {
      const cell = (v) => {
        if (v === null || v === undefined) return '';
        const s = String(v).replace(/"/g, '""');
        return /[",\n]/.test(s) ? `"${s}"` : s;
      };
      lines.push(headers.map(h => cell(r[h])).join(','));
    }
    const blob = new Blob([lines.join('\r\n')], { type: 'text/csv' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `bidvex-broker-subscriptions-${new Date().toISOString().slice(0,10)}.csv`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-end gap-3 flex-wrap">
        <div>
          <Label className="text-xs">{lang === 'fr' ? 'Filtrer' : 'Filter'}</Label>
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-[200px]" data-testid="list-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{lang === 'fr' ? 'Tous' : 'All'}</SelectItem>
              <SelectItem value="active">{lang === 'fr' ? 'Actif' : 'Active'}</SelectItem>
              <SelectItem value="expired">{lang === 'fr' ? 'Expiré' : 'Expired'}</SelectItem>
              <SelectItem value="free">{lang === 'fr' ? 'Gratuit' : 'Free'}</SelectItem>
              <SelectItem value="suspended">{lang === 'fr' ? 'Suspendu' : 'Suspended'}</SelectItem>
              <SelectItem value="unpaid">{lang === 'fr' ? 'Impayé' : 'Unpaid'}</SelectItem>
              <SelectItem value="comp">{lang === 'fr' ? 'Complimentaire' : 'Comp'}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button variant="outline" onClick={exportCSV} disabled={!rows.length} data-testid="list-export-csv">
          <Download className="w-4 h-4 mr-2" />{lang === 'fr' ? 'Exporter CSV' : 'Export CSV'}
        </Button>
        <span className="text-xs text-slate-500 ml-auto">{rows.length} {lang === 'fr' ? 'enregistrements' : 'records'}</span>
      </div>

      {loading ? <p className="text-center py-8 text-slate-500"><Loader2 className="inline animate-spin mr-2" />Loading…</p> : (
        <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/60 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left">{lang === 'fr' ? 'Nom' : 'Name'}</th>
                <th className="px-3 py-2 text-left">{lang === 'fr' ? 'Courriel' : 'Email'}</th>
                <th className="px-3 py-2 text-left">{lang === 'fr' ? 'Forfait' : 'Plan'}</th>
                <th className="px-3 py-2 text-left">{lang === 'fr' ? 'Statut' : 'Status'}</th>
                <th className="px-3 py-2 text-right">{lang === 'fr' ? 'Prix payé' : 'Price'}</th>
                <th className="px-3 py-2 text-right">{lang === 'fr' ? 'Rabais' : 'Discount'}</th>
                <th className="px-3 py-2 text-left">{lang === 'fr' ? 'Débuté' : 'Started'}</th>
                <th className="px-3 py-2 text-left">{lang === 'fr' ? 'Renouvellement' : 'Renewal'}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.broker_id} className="border-t border-slate-100 dark:border-slate-700" data-testid={`list-row-${r.broker_id}`}>
                  <td className="px-3 py-2">{r.legal_business_name}</td>
                  <td className="px-3 py-2 text-slate-500">{r.user_email}</td>
                  <td className="px-3 py-2">{r.plan_name}</td>
                  <td className="px-3 py-2"><StatusBadge status={r.subscription_status} lang={lang} /></td>
                  <td className="px-3 py-2 text-right font-semibold">{_fmt(r.final_cad)}</td>
                  <td className="px-3 py-2 text-right text-amber-600">{r.discount_pct > 0 ? `−${r.discount_pct}%` : '—'}</td>
                  <td className="px-3 py-2 text-slate-500">{_fmtDate(r.subscription_started_at || r.created_at)}</td>
                  <td className="px-3 py-2 text-slate-500">{_fmtDate(r.subscription_expires_at)}</td>
                </tr>
              ))}
              {!rows.length && (
                <tr><td colSpan="8" className="px-3 py-8 text-center text-slate-500">{lang === 'fr' ? 'Aucun abonnement.' : 'No subscriptions.'}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// TAB 4 — Revenue Summary
// ─────────────────────────────────────────────────────────────────────
function RevenueSummaryTab({ lang }) {
  const [data, setData]   = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/admin/subscriptions/revenue`, { headers: _authHeaders() });
        if (mounted) setData(r.data);
      } catch { /* noop */ }
      finally { if (mounted) setLoading(false); }
    })();
    return () => { mounted = false; };
  }, []);

  if (loading) return <p className="text-center py-8 text-slate-500"><Loader2 className="inline animate-spin mr-2" />Loading…</p>;
  if (!data)   return <p className="text-center py-8 text-slate-500">{lang === 'fr' ? 'Aucune donnée.' : 'No data available.'}</p>;

  const Kpi = ({ label, value, accent, testId }) => (
    <Card><CardContent className="p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${accent || ''}`} data-testid={testId}>{value}</p>
    </CardContent></Card>
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi label={lang === 'fr' ? 'Abonnements actifs' : 'Active subscribers'} value={data.active + data.comp + data.free} testId="kpi-active-count" />
        <Kpi label="ARR" value={_fmt(data.arr_cad)} accent="text-emerald-600" testId="kpi-arr" />
        <Kpi label="MRR" value={_fmt(data.mrr_cad)} accent="text-emerald-600" testId="kpi-mrr" />
        <Kpi label={lang === 'fr' ? 'Revenus perdus (rabais)' : 'Revenue lost to discounts'} value={_fmt(data.revenue_lost_cad)} accent="text-rose-600" testId="kpi-lost" />
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">{lang === 'fr' ? 'Répartition' : 'Breakdown'}</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
            <div><span className="text-slate-500">{lang === 'fr' ? 'Plein tarif' : 'Full price'}: </span><strong>{data.full_price_count}</strong></div>
            <div><span className="text-slate-500">{lang === 'fr' ? 'Rabais appliqué' : 'Discounted'}: </span><strong>{data.discounted_count}</strong></div>
            <div><span className="text-slate-500">{lang === 'fr' ? 'Gratuit' : 'Free'}: </span><strong>{data.free}</strong></div>
            <div><span className="text-slate-500">{lang === 'fr' ? 'Complimentaire' : 'Comp'}: </span><strong>{data.comp}</strong></div>
            <div><span className="text-slate-500">{lang === 'fr' ? 'Suspendu' : 'Suspended'}: </span><strong>{data.suspended}</strong></div>
            <div><span className="text-slate-500">{lang === 'fr' ? 'Expiré' : 'Expired'}: </span><strong>{data.expired}</strong></div>
            <div><span className="text-slate-500">{lang === 'fr' ? 'Impayé' : 'Unpaid'}: </span><strong>{data.unpaid}</strong></div>
            <div><span className="text-slate-500">{lang === 'fr' ? 'Total des courtiers' : 'Total brokers'}: </span><strong>{data.total_brokers}</strong></div>
            <div><span className="text-slate-500">{lang === 'fr' ? 'ARR potentiel' : 'Potential ARR'}: </span><strong>{_fmt(data.potential_arr_cad)}</strong></div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Page shell
// ─────────────────────────────────────────────────────────────────────
export default function AdminSubscriptionsPage() {
  const { i18n } = useTranslation();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';

  return (
    <div className="container mx-auto max-w-7xl py-6 px-4">
      <header className="mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2" data-testid="admin-subscriptions-title">
          <CreditCard className="h-7 w-7" />
          {lang === 'fr' ? 'Gestion des abonnements' : 'Subscription Management'}
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          {lang === 'fr'
            ? 'Tarification du forfait BidVex Broker Annual, rabais globaux, abonnements par utilisateur et revenus.'
            : 'Pricing for the BidVex Broker Annual plan, global discounts, per-user subscriptions and revenue.'}
        </p>
      </header>

      <Tabs defaultValue="global" className="w-full" data-testid="admin-subscriptions-tabs">
        <TabsList className="mb-4 flex-wrap h-auto">
          <TabsTrigger value="global" data-testid="tab-global">
            <Settings className="h-4 w-4 mr-1.5" /> {lang === 'fr' ? 'Paramètres globaux' : 'Global Settings'}
          </TabsTrigger>
          <TabsTrigger value="override" data-testid="tab-override">
            <Users className="h-4 w-4 mr-1.5" /> {lang === 'fr' ? 'Modifier par utilisateur' : 'Per-User Override'}
          </TabsTrigger>
          <TabsTrigger value="list" data-testid="tab-list">
            <Sparkles className="h-4 w-4 mr-1.5" /> {lang === 'fr' ? 'Liste des abonnements' : 'Subscription List'}
          </TabsTrigger>
          <TabsTrigger value="revenue" data-testid="tab-revenue">
            <DollarSign className="h-4 w-4 mr-1.5" /> {lang === 'fr' ? 'Résumé des revenus' : 'Revenue Summary'}
          </TabsTrigger>
        </TabsList>
        <TabsContent value="global"><GlobalSettingsTab lang={lang} /></TabsContent>
        <TabsContent value="override"><PerUserOverrideTab lang={lang} /></TabsContent>
        <TabsContent value="list"><SubscriptionListTab lang={lang} /></TabsContent>
        <TabsContent value="revenue"><RevenueSummaryTab lang={lang} /></TabsContent>
      </Tabs>
    </div>
  );
}
