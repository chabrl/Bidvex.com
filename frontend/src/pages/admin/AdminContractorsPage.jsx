/**
 * iter316 Phase B — Mission B5
 * Admin Contractors page + Commission Rate Editor modal.
 *
 * Lists all dialer_contractors with their accrued earnings + Stripe state.
 * Admin can:
 *   • Edit per-account-type commission rates (vehicle_dealer, partner,
 *     broker, liquidator, individual_seller) + the default fallback.
 *     Inline percentage input → converted to decimal on save.
 *   • Remove referral attribution for a specific referred account
 *     (kills FUTURE accruals; history stays intact).
 *
 * Backend endpoints used:
 *   • GET    /api/twilio/admin/contractors/{id}/commission-rates
 *   • PATCH  /api/twilio/admin/contractors/{id}/commission-rates
 *   • POST   /api/twilio/admin/accounts/{account_id}/remove-referral-attribution
 *   • GET    /api/twilio/contractor/dashboard?contractor_id={id} (admin override)
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  DollarSign, Loader2, Pencil, Trash2, Save, X, Search,
  CheckCircle2, AlertTriangle, ShieldCheck, UserPlus, Eye, Copy,
} from 'lucide-react';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../components/ui/dialog';

const ACCOUNT_TYPES = [
  { id: 'vehicle_dealer',     en: 'Vehicle Dealer',     fr: 'Concessionnaire' },
  { id: 'partner',            en: 'Partner',            fr: 'Partenaire' },
  { id: 'broker',             en: 'Broker',             fr: 'Courtier' },
  { id: 'liquidator',         en: 'Liquidator',         fr: 'Liquidateur' },
  { id: 'individual_seller',  en: 'Individual Seller',  fr: 'Vendeur individuel' },
];

function pctToDecimal(v) {
  if (v === '' || v === null || v === undefined) return null;
  const n = Number(v);
  if (Number.isNaN(n)) return null;
  return Math.max(0, Math.min(1, n / 100));
}

function decimalToPct(d) {
  if (d === null || d === undefined || d === '') return '';
  return (Number(d) * 100).toFixed(2);
}

function formatMoney(amount) {
  return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(amount || 0));
}

// ─── Main page ────────────────────────────────────────────────────────

export default function AdminContractorsPage() {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').startsWith('fr');
  const { token } = useAuth();
  const navigate = useNavigate();

  const [contractors, setContractors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [editingContractor, setEditingContractor] = useState(null);
  const [removingAttribution, setRemovingAttribution] = useState(null);
  const [creatingOpen, setCreatingOpen] = useState(false);
  const [demotingContractor, setDemotingContractor] = useState(null);

  const fetchContractors = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/twilio/admin/contractors`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setContractors(r.data?.items || []);
    } catch {
      setContractors([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchContractors();
  }, [fetchContractors]);

  const filtered = contractors.filter((c) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (c.email || '').toLowerCase().includes(q)
      || (c.name || '').toLowerCase().includes(q)
      || (c.id || '').toLowerCase().includes(q)
    );
  });

  return (
    <div className="container mx-auto max-w-7xl py-4 px-3" data-testid="admin-contractors-page">
      <header className="mb-4 flex items-start justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2" data-testid="admin-contractors-title">
            <ShieldCheck className="h-7 w-7 text-indigo-600" />
            {fr ? 'Gestion des contractants' : 'Contractor Management'}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            {fr
              ? 'Configurez les taux de commission, vérifiez les versements Stripe et gérez les attributions.'
              : 'Configure commission rates, review Stripe payouts, and manage attributions.'}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            className="bg-indigo-600 hover:bg-indigo-700 text-white"
            onClick={() => setCreatingOpen(true)}
            data-testid="new-contractor-btn"
          >
            <UserPlus className="h-4 w-4 mr-1" />
            {fr ? 'Nouveau contractant' : 'New Contractor'}
          </Button>
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder={fr ? 'Rechercher…' : 'Search…'}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-7 w-64"
              data-testid="admin-contractors-search"
            />
          </div>
        </div>
      </header>

      {loading ? (
        <div className="flex items-center justify-center py-20" data-testid="admin-contractors-loading">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-600 mr-2" />
          <span>{fr ? 'Chargement…' : 'Loading…'}</span>
        </div>
      ) : filtered.length === 0 ? (
        <Card className="border-2 border-dashed">
          <CardContent className="p-8 text-center text-sm text-slate-500" data-testid="admin-contractors-empty">
            {fr
              ? 'Aucun contractant trouvé. Promouvez un utilisateur au rôle « dialer_contractor » pour commencer.'
              : 'No contractors found. Promote a user to the "dialer_contractor" role to get started.'}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="admin-contractors-table">
                <thead>
                  <tr className="text-xs text-slate-500 border-b bg-slate-50">
                    <th className="text-left py-2 px-3">{fr ? 'Contractant' : 'Contractor'}</th>
                    <th className="text-left py-2 px-3">{fr ? 'Poste' : 'Extension'}</th>
                    <th className="text-left py-2 px-3">{fr ? 'Stripe' : 'Stripe'}</th>
                    <th className="text-left py-2 px-3">{fr ? 'Code parrainage' : 'Referral'}</th>
                    <th className="text-right py-2 px-3">{fr ? 'Accumulé' : 'Accrued'}</th>
                    <th className="text-right py-2 px-3">{fr ? 'Versé' : 'Paid'}</th>
                    <th className="text-right py-2 px-3">{fr ? 'Actions' : 'Actions'}</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => (
                    <ContractorRow
                      key={c.id}
                      contractor={c}
                      token={token}
                      fr={fr}
                      onEditRates={() => setEditingContractor(c)}
                      onRemoveAttribution={(acc) => setRemovingAttribution({ contractor: c, account: acc })}
                      onViewProfile={() => navigate(`/admin/contractors/${c.id}`)}
                      onDemote={() => setDemotingContractor(c)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Modal — edit rates */}
      {editingContractor && (
        <CommissionRateEditorModal
          contractor={editingContractor}
          fr={fr}
          token={token}
          onClose={() => setEditingContractor(null)}
          onSaved={() => {
            setEditingContractor(null);
            fetchContractors();
            toast.success(fr ? 'Taux mis à jour.' : 'Rates updated.');
          }}
        />
      )}

      {/* Modal — remove attribution */}
      {removingAttribution && (
        <RemoveAttributionDialog
          ctx={removingAttribution}
          fr={fr}
          token={token}
          onClose={() => setRemovingAttribution(null)}
          onDone={() => {
            setRemovingAttribution(null);
            fetchContractors();
          }}
        />
      )}

      {/* Modal — create new contractor */}
      {creatingOpen && (
        <NewContractorDialog
          fr={fr}
          token={token}
          onClose={() => setCreatingOpen(false)}
          onCreated={(result) => {
            setCreatingOpen(false);
            fetchContractors();
            // Show invite link so admin can share it.
            const inviteUrl = `${window.location.origin}/reset-password?token=${result.invite_token}`;
            toast.success(
              fr ? 'Contractant créé. Lien d\u2019invitation copié.' : 'Contractor created. Invite link copied.',
            );
            try { navigator.clipboard.writeText(inviteUrl); } catch { /* noop */ }
          }}
        />
      )}

      {/* Modal — confirm demote contractor */}
      {demotingContractor && (
        <DemoteContractorDialog
          contractor={demotingContractor}
          fr={fr}
          token={token}
          onClose={() => setDemotingContractor(null)}
          onDone={() => {
            setDemotingContractor(null);
            fetchContractors();
          }}
        />
      )}
    </div>
  );
}

// ─── Contractor row ──────────────────────────────────────────────────

function ContractorRow({ contractor, token, fr, onEditRates, onRemoveAttribution, onViewProfile, onDemote }) {
  const [expanded, setExpanded] = useState(false);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadDashboard = useCallback(async () => {
    if (dashboard) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/twilio/contractor/dashboard?contractor_id=${contractor.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setDashboard(r.data);
    } catch {
      setDashboard({ earnings: { accrued_total: 0, paid_total: 0 }, referred_accounts: [] });
    } finally {
      setLoading(false);
    }
  }, [contractor.id, token, dashboard]);

  const handleExpand = async () => {
    if (!expanded) await loadDashboard();
    setExpanded((p) => !p);
  };

  const stripeOk = dashboard?.stripe_connected || contractor.stripe_connect_payouts_enabled;

  return (
    <>
      <tr className="border-b hover:bg-slate-50 cursor-pointer" onClick={handleExpand} data-testid={`contractor-row-${contractor.id}`}>
        <td className="py-2 px-3">
          <p className="font-medium">{contractor.name || contractor.email}</p>
          <p className="text-xs text-slate-500 font-mono">{contractor.id?.slice(0, 8)}</p>
        </td>
        <td className="py-2 px-3" data-testid={`ext-${contractor.id}`}>
          {contractor.extension_number ? (
            <span className="font-mono text-sm font-semibold text-slate-800">
              ext. {contractor.extension_number}
            </span>
          ) : (
            <Badge className="bg-amber-100 text-amber-800" data-testid={`ext-pending-${contractor.id}`}>
              <AlertTriangle className="h-3 w-3 mr-1" />
              {fr ? 'En attente' : 'Pending'}
            </Badge>
          )}
        </td>
        <td className="py-2 px-3">
          {stripeOk ? (
            <Badge className="bg-emerald-100 text-emerald-800" data-testid={`stripe-ok-${contractor.id}`}>
              <CheckCircle2 className="h-3 w-3 mr-1" />
              {fr ? 'Connecté' : 'Connected'}
            </Badge>
          ) : (
            <Badge className="bg-amber-100 text-amber-800" data-testid={`stripe-missing-${contractor.id}`}>
              <AlertTriangle className="h-3 w-3 mr-1" />
              {fr ? 'À configurer' : 'Setup needed'}
            </Badge>
          )}
        </td>
        <td className="py-2 px-3 text-xs font-mono">
          {dashboard?.referral_code || contractor.affiliate_code || '—'}
        </td>
        <td className="py-2 px-3 text-right font-semibold">
          {dashboard ? formatMoney(dashboard.earnings?.accrued_total) : '…'}
        </td>
        <td className="py-2 px-3 text-right font-semibold">
          {dashboard ? formatMoney(dashboard.earnings?.paid_total) : '…'}
        </td>
        <td className="py-2 px-3 text-right">
          <div className="flex items-center justify-end gap-1">
            <Button
              size="sm"
              variant="ghost"
              onClick={(e) => { e.stopPropagation(); onViewProfile(); }}
              data-testid={`view-profile-btn-${contractor.id}`}
              title={fr ? 'Voir le profil' : 'View profile'}
            >
              <Eye className="h-3.5 w-3.5 mr-1" />
              {fr ? 'Voir' : 'View'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={(e) => { e.stopPropagation(); onEditRates(); }}
              data-testid={`edit-rates-btn-${contractor.id}`}
            >
              <Pencil className="h-3.5 w-3.5 mr-1" />
              {fr ? 'Taux' : 'Rates'}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="text-rose-600 hover:bg-rose-50"
              onClick={(e) => { e.stopPropagation(); onDemote(); }}
              data-testid={`demote-btn-${contractor.id}`}
              title={fr ? 'Rétrograder' : 'Demote'}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </td>
      </tr>

      {expanded && (
        <tr className="bg-slate-50/60">
          <td colSpan={6} className="px-3 py-2" data-testid={`contractor-expanded-${contractor.id}`}>
            {loading ? (
              <div className="text-xs text-slate-500"><Loader2 className="inline h-3 w-3 animate-spin mr-1" />{fr ? 'Chargement…' : 'Loading…'}</div>
            ) : (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-slate-600">
                  {fr ? 'Comptes parrainés' : 'Referred accounts'} ({(dashboard?.referred_accounts || []).length})
                </p>
                {(dashboard?.referred_accounts || []).length === 0 ? (
                  <p className="text-xs text-slate-500">{fr ? 'Aucun.' : 'None.'}</p>
                ) : (
                  <ul className="text-xs space-y-1">
                    {dashboard.referred_accounts.slice(0, 10).map((acc) => (
                      <li key={acc.id} className="flex items-center justify-between gap-2">
                        <span className="font-mono truncate">
                          {acc.name || acc.id}
                          <Badge variant="outline" className="ml-2">{acc.account_type}</Badge>
                        </span>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-rose-600 hover:bg-rose-50 h-7"
                          onClick={() => onRemoveAttribution(acc)}
                          data-testid={`remove-attribution-btn-${acc.id}`}
                        >
                          <Trash2 className="h-3 w-3 mr-1" />
                          {fr ? 'Retirer' : 'Remove'}
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Commission Rate Editor Modal ─────────────────────────────────────

function CommissionRateEditorModal({ contractor, fr, token, onClose, onSaved }) {
  const [rates, setRates] = useState({});
  const [defaultRate, setDefaultRate] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function fetchRates() {
      try {
        const r = await axios.get(
          `${API_BASE}/twilio/admin/contractors/${contractor.id}/commission-rates`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (cancelled) return;
        const r2p = {};
        const src = r.data.rates_by_account_type || {};
        ACCOUNT_TYPES.forEach((t) => { r2p[t.id] = decimalToPct(src[t.id]); });
        setRates(r2p);
        setDefaultRate(decimalToPct(r.data.default_rate));
      } catch {
        // Default empty / use platform default (20%)
        const r2p = {};
        ACCOUNT_TYPES.forEach((t) => { r2p[t.id] = ''; });
        setRates(r2p);
        setDefaultRate('20.00');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchRates();
    return () => { cancelled = true; };
  }, [contractor.id, token]);

  const handleSave = async () => {
    setSaving(true);
    // Convert percentages to decimals, drop blanks (= keep as-is).
    const decimalRates = {};
    Object.entries(rates).forEach(([k, v]) => {
      const d = pctToDecimal(v);
      if (d !== null) decimalRates[k] = d;
    });
    const body = {
      rates_by_account_type: decimalRates,
      default_rate: pctToDecimal(defaultRate),
    };
    try {
      await axios.patch(
        `${API_BASE}/twilio/admin/contractors/${contractor.id}/commission-rates`,
        body,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || (fr ? 'Échec de la sauvegarde.' : 'Save failed.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl" data-testid="commission-rates-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            {fr ? 'Taux de commission' : 'Commission Rates'}
            <span className="text-xs font-mono ml-2 text-slate-500">{contractor.email}</span>
          </DialogTitle>
          <DialogDescription>
            {fr
              ? 'Configurez le pourcentage de commission par type de compte parrainé. Les changements ne s\u2019appliquent qu\u2019aux NOUVELLES transactions (l\u2019historique est immuable).'
              : 'Configure commission percentages per account type. Changes apply to NEW transactions only (history is immutable).'}
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="py-8 text-center text-sm text-slate-500">
            <Loader2 className="inline h-4 w-4 animate-spin mr-1" />
            {fr ? 'Chargement…' : 'Loading…'}
          </div>
        ) : (
          <div className="space-y-3">
            {ACCOUNT_TYPES.map((t) => (
              <div key={t.id} className="grid grid-cols-3 items-center gap-3">
                <label className="text-sm font-medium" data-testid={`rate-label-${t.id}`}>
                  {fr ? t.fr : t.en}
                </label>
                <div className="col-span-2 flex items-center gap-2">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    max="100"
                    value={rates[t.id] ?? ''}
                    onChange={(e) => setRates({ ...rates, [t.id]: e.target.value })}
                    placeholder={fr ? 'Par défaut' : 'Use default'}
                    data-testid={`rate-input-${t.id}`}
                  />
                  <span className="text-sm text-slate-500">%</span>
                </div>
              </div>
            ))}
            <div className="grid grid-cols-3 items-center gap-3 pt-3 border-t">
              <label className="text-sm font-bold">
                {fr ? 'Taux par défaut' : 'Default rate'}
              </label>
              <div className="col-span-2 flex items-center gap-2">
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={defaultRate}
                  onChange={(e) => setDefaultRate(e.target.value)}
                  placeholder="20.00"
                  data-testid="rate-input-default"
                />
                <span className="text-sm text-slate-500">%</span>
              </div>
            </div>
            <p className="text-xs text-slate-500 italic">
              {fr
                ? 'Plage : 0% à 100%. Les pourcentages sont convertis en décimales (ex. 25% → 0.25) avant d\u2019être enregistrés.'
                : 'Range: 0% to 100%. Percentages are converted to decimals (e.g. 25% → 0.25) on save.'}
            </p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={saving} data-testid="rates-cancel-btn">
            <X className="h-4 w-4 mr-1" />
            {fr ? 'Annuler' : 'Cancel'}
          </Button>
          <Button
            onClick={handleSave}
            disabled={loading || saving}
            className="bg-indigo-600 hover:bg-indigo-700 text-white"
            data-testid="rates-save-btn"
          >
            {saving ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Save className="h-4 w-4 mr-1" />}
            {fr ? 'Enregistrer' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Remove Attribution Dialog ────────────────────────────────────────

function RemoveAttributionDialog({ ctx, fr, token, onClose, onDone }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!reason.trim()) {
      toast.error(fr ? 'Veuillez fournir une raison.' : 'Please provide a reason.');
      return;
    }
    setBusy(true);
    try {
      await axios.post(
        `${API_BASE}/twilio/admin/accounts/${ctx.account.id}/remove-referral-attribution`,
        { reason },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(fr ? 'Attribution retirée.' : 'Attribution removed.');
      onDone();
    } catch (e) {
      toast.error(e?.response?.data?.detail || (fr ? 'Échec.' : 'Failed.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="remove-attribution-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-rose-600">
            <Trash2 className="h-5 w-5" />
            {fr ? 'Retirer l\u2019attribution' : 'Remove Referral Attribution'}
          </DialogTitle>
          <DialogDescription>
            {fr
              ? 'Cette action arrêtera toute commission FUTURE pour ce compte. L\u2019historique reste intact.'
              : 'This will stop FUTURE commissions for this account. Existing history is preserved.'}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <p className="text-xs text-slate-600">
            <span className="font-semibold">{fr ? 'Compte :' : 'Account:'}</span>{' '}
            <span className="font-mono">{ctx.account.name || ctx.account.id}</span>
          </p>
          <p className="text-xs text-slate-600">
            <span className="font-semibold">{fr ? 'Contractant :' : 'Contractor:'}</span>{' '}
            {ctx.contractor.email}
          </p>
          <Textarea
            rows={3}
            placeholder={fr ? 'Raison (obligatoire)…' : 'Reason (required)…'}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            data-testid="remove-attribution-reason"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy} data-testid="remove-attribution-cancel-btn">
            <X className="h-4 w-4 mr-1" />
            {fr ? 'Annuler' : 'Cancel'}
          </Button>
          <Button
            variant="destructive"
            onClick={submit}
            disabled={busy}
            data-testid="remove-attribution-confirm-btn"
          >
            {busy ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Trash2 className="h-4 w-4 mr-1" />}
            {fr ? 'Confirmer le retrait' : 'Confirm removal'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


// ─── New Contractor Dialog ────────────────────────────────────────────

function NewContractorDialog({ fr, token, onClose, onCreated }) {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [province, setProvince] = useState('QC');
  const [defaultRatePct, setDefaultRatePct] = useState('20');
  const [busy, setBusy] = useState(false);
  const [inviteUrl, setInviteUrl] = useState(null);

  const submit = async () => {
    if (!email || !email.includes('@')) {
      toast.error(fr ? 'Email valide requis.' : 'Valid email required.');
      return;
    }
    setBusy(true);
    try {
      const body = {
        email: email.trim().toLowerCase(),
        name: name.trim(),
        phone: phone.trim(),
        province,
        initial_default_rate: pctToDecimal(defaultRatePct),
      };
      const r = await axios.post(
        `${API_BASE}/twilio/admin/contractors`,
        body,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const url = `${window.location.origin}/reset-password?token=${r.data.invite_token}`;
      setInviteUrl(url);
      // Slightly delayed callback to let the admin copy the link.
      setTimeout(() => onCreated(r.data), 1500);
    } catch (e) {
      const d = e?.response?.data?.detail;
      const msg = (typeof d === 'object' ? (fr ? d?.message_fr : d?.message_en) : d) || e?.message;
      toast.error(msg || (fr ? 'Échec.' : 'Failed.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="new-contractor-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserPlus className="h-5 w-5" />
            {fr ? 'Nouveau contractant' : 'New Contractor'}
          </DialogTitle>
          <DialogDescription>
            {fr
              ? 'Crée un nouvel utilisateur avec le rôle dialer_contractor. Si l\u2019email existe déjà, l\u2019utilisateur est promu.'
              : 'Creates a new user with role=dialer_contractor. If the email already exists, that user is promoted instead.'}
          </DialogDescription>
        </DialogHeader>
        {inviteUrl ? (
          <div className="space-y-2" data-testid="new-contractor-success">
            <p className="text-sm text-emerald-700 font-semibold flex items-center gap-1">
              <CheckCircle2 className="h-4 w-4" />
              {fr ? 'Créé ! Lien d\u2019invitation :' : 'Created! Invite link:'}
            </p>
            <div className="flex items-center gap-2">
              <Input value={inviteUrl} readOnly className="font-mono text-xs" data-testid="invite-link-input" />
              <Button
                size="sm"
                onClick={() => { navigator.clipboard.writeText(inviteUrl); toast.success(fr ? 'Copié.' : 'Copied.'); }}
                data-testid="copy-invite-link-btn"
              >
                <Copy className="h-3.5 w-3.5" />
              </Button>
            </div>
            <p className="text-[11px] text-slate-500">
              {fr ? 'Valable 7 jours. Email d\u2019invitation envoyé automatiquement.' : 'Valid for 7 days. Invite email sent automatically.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold">{fr ? 'Email *' : 'Email *'}</label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="contractor@example.com"
                data-testid="new-contractor-email"
              />
            </div>
            <div>
              <label className="text-xs font-semibold">{fr ? 'Nom complet' : 'Full name'}</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={fr ? 'Jean Tremblay' : 'John Smith'}
                data-testid="new-contractor-name"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs font-semibold">{fr ? 'Téléphone' : 'Phone'}</label>
                <Input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+14155550100"
                  data-testid="new-contractor-phone"
                />
              </div>
              <div>
                <label className="text-xs font-semibold">{fr ? 'Province' : 'Province'}</label>
                <Input
                  value={province}
                  onChange={(e) => setProvince(e.target.value.toUpperCase())}
                  maxLength={2}
                  data-testid="new-contractor-province"
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold">
                {fr ? 'Taux de commission par défaut (%)' : 'Default commission rate (%)'}
              </label>
              <Input
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={defaultRatePct}
                onChange={(e) => setDefaultRatePct(e.target.value)}
                data-testid="new-contractor-default-rate"
              />
              <p className="text-[11px] text-slate-500 mt-1">
                {fr ? 'Converti en décimal au moment de l\u2019enregistrement (ex. 20 \u2192 0.20).' : 'Converted to decimal on save (e.g. 20 → 0.20).'}
              </p>
            </div>
          </div>
        )}
        <DialogFooter>
          {!inviteUrl && (
            <>
              <Button variant="outline" onClick={onClose} disabled={busy} data-testid="new-contractor-cancel-btn">
                <X className="h-4 w-4 mr-1" />
                {fr ? 'Annuler' : 'Cancel'}
              </Button>
              <Button
                onClick={submit}
                disabled={busy}
                className="bg-indigo-600 hover:bg-indigo-700 text-white"
                data-testid="new-contractor-submit-btn"
              >
                {busy ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <UserPlus className="h-4 w-4 mr-1" />}
                {fr ? 'Créer' : 'Create'}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Demote Contractor Dialog ─────────────────────────────────────────

function DemoteContractorDialog({ contractor, fr, token, onClose, onDone }) {
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      const r = await axios.post(
        `${API_BASE}/twilio/admin/users/${contractor.id}/demote-from-contractor`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(fr ? `Rétrogradé vers ${r.data.reverted_to_role}.` : `Demoted to ${r.data.reverted_to_role}.`);
      onDone();
    } catch (e) {
      const d = e?.response?.data?.detail;
      const msg = (typeof d === 'object' ? (fr ? d?.message_fr : d?.message_en) : d) || e?.message;
      toast.error(msg || (fr ? 'Échec.' : 'Failed.'));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="demote-contractor-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-rose-600">
            <Trash2 className="h-5 w-5" />
            {fr ? 'Rétrograder le contractant' : 'Demote Contractor'}
          </DialogTitle>
          <DialogDescription>
            {fr
              ? `Cette action retire le rôle de contractant de ${contractor.email}. L\u2019historique des commissions et l\u2019attribution des comptes référés sont préservés.`
              : `This removes the contractor role from ${contractor.email}. Commission history and referred-account attribution are PRESERVED.`}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy} data-testid="demote-cancel-btn">
            <X className="h-4 w-4 mr-1" />
            {fr ? 'Annuler' : 'Cancel'}
          </Button>
          <Button
            variant="destructive"
            onClick={submit}
            disabled={busy}
            data-testid="demote-confirm-btn"
          >
            {busy ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Trash2 className="h-4 w-4 mr-1" />}
            {fr ? 'Confirmer la rétrogradation' : 'Confirm demotion'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
