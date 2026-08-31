/**
 * iter501 — Admin Affiliate Manager
 *
 * Two responsibilities in one page:
 *   1. Approve payout requests (unchanged from iter499).
 *   2. Manage per-affiliate STATUS (active / revoked) and per-affiliate
 *      custom commission rate (0–20% override; null = fall back to the
 *      global 3% default).
 *
 * Backend contract:
 *   GET  /api/affiliate/admin/all           — list all affiliates + candidates
 *   POST /api/affiliate/admin/set-status    — {user_id, status, commission_rate?}
 *   POST /api/affiliate/admin/set-rate      — {user_id, commission_rate|null}
 */
import API_BASE from '../../config';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import {
  DollarSign, CheckCircle, Users, Ban, Save, Loader2,
} from 'lucide-react';
import { formatCurrency } from '../../utils/currencyFormatter';

const API = API_BASE;

// Convert a rate stored as a fraction (e.g. 0.05) to a percentage string
// suitable for the input field. Uses at most 4 decimal places so both
// "3" (integer) and "7.5" (fractional) round-trip cleanly.
const fractionToPct = (rate) =>
  rate === null || rate === undefined || Number.isNaN(Number(rate))
    ? ''
    : String(+(Number(rate) * 100).toFixed(4));

const pctToFraction = (pctStr) => {
  const n = Number(pctStr);
  if (Number.isNaN(n)) return NaN;
  return +(n / 100).toFixed(6);
};

const RATE_MIN_PCT = 0;
const RATE_MAX_PCT_DEFAULT = 75; // iter502 — mirrors backend MAX_AFFILIATE_COMMISSION_RATE=0.75

const STATUS_BADGE = {
  active:  { cls: 'bg-emerald-100 text-emerald-800 border-emerald-300', en: 'Active',  fr: 'Actif' },
  pending: { cls: 'bg-amber-100 text-amber-800 border-amber-300',       en: 'Pending', fr: 'En attente' },
  revoked: { cls: 'bg-rose-100 text-rose-800 border-rose-300',          en: 'Revoked', fr: 'Révoqué' },
  none:    { cls: 'bg-slate-100 text-slate-700 border-slate-300',       en: 'None',    fr: 'Aucun' },
};

/**
 * Row for a single affiliate — pill status + rate input + action button(s).
 * Keeps its own local state for the rate input so a validation error
 * doesn't wipe the parent's list re-fetch.
 */
const AffiliateRow = ({ affiliate, defaultRate, maxRate, partnerDefaults, onSaved, isFr }) => {
  const initialPct = fractionToPct(affiliate.commission_rate);
  const [rateInput, setRateInput] = useState(initialPct);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // iter502 — Influencer Partner Program local state.  Only mutated on
  // explicit Save.  Pre-fills from the row; falls back to program
  // defaults when the row has never been enrolled.
  const [showPartner, setShowPartner] = useState(false);
  const [partnerEnabled, setPartnerEnabled] = useState(!!affiliate.partner_program);
  const [t1Rate, setT1Rate] = useState(
    fractionToPct(affiliate.tier_1_rate ?? partnerDefaults?.tier_1_rate),
  );
  const [t1Months, setT1Months] = useState(
    String(affiliate.tier_1_duration_months ?? partnerDefaults?.tier_1_duration_months ?? 6),
  );
  const [t2Rate, setT2Rate] = useState(
    fractionToPct(affiliate.tier_2_rate ?? partnerDefaults?.tier_2_rate),
  );
  const [partnerError, setPartnerError] = useState('');

  useEffect(() => {
    setRateInput(fractionToPct(affiliate.commission_rate));
    setError('');
    setPartnerEnabled(!!affiliate.partner_program);
    setT1Rate(fractionToPct(affiliate.tier_1_rate ?? partnerDefaults?.tier_1_rate));
    setT1Months(String(affiliate.tier_1_duration_months ?? partnerDefaults?.tier_1_duration_months ?? 6));
    setT2Rate(fractionToPct(affiliate.tier_2_rate ?? partnerDefaults?.tier_2_rate));
    setPartnerError('');
  }, [affiliate.commission_rate, affiliate.id, affiliate.partner_program,
      affiliate.tier_1_rate, affiliate.tier_1_duration_months,
      affiliate.tier_2_rate, partnerDefaults?.tier_1_rate,
      partnerDefaults?.tier_1_duration_months, partnerDefaults?.tier_2_rate]);

  const validate = () => {
    const trimmed = String(rateInput || '').trim();
    if (trimmed === '') {
      // Empty = clear the override → fall back to default. Valid.
      return { ok: true, rate: null };
    }
    const n = Number(trimmed);
    if (Number.isNaN(n)) {
      return { ok: false, msg: isFr ? 'Taux invalide' : 'Invalid rate' };
    }
    if (n < RATE_MIN_PCT || n > (maxRate * 100)) {
      return {
        ok: false,
        msg: isFr
          ? `Le taux doit être entre ${RATE_MIN_PCT}% et ${(maxRate * 100)}%`
          : `Rate must be between ${RATE_MIN_PCT}% and ${(maxRate * 100)}%`,
      };
    }
    return { ok: true, rate: pctToFraction(n) };
  };

  const status = (affiliate.affiliate_status || 'none').toLowerCase();
  const isActive = status === 'active';
  const isPendingOrNone = status === 'none' || status === 'pending';
  const isRevoked = status === 'revoked';

  const currentEffectivePct = fractionToPct(affiliate.effective_rate ?? defaultRate);
  const oldRatePctForToast = fractionToPct(affiliate.effective_rate ?? defaultRate);

  const doApprove = async () => {
    const v = validate();
    if (!v.ok) {
      setError(v.msg);
      toast.error(v.msg);
      return;
    }
    setSaving(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const body = { user_id: affiliate.id, status: 'active' };
      if (v.rate !== null) body.commission_rate = v.rate;
      const res = await axios.post(`${API}/affiliate/admin/set-status`, body, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const newRatePct = fractionToPct(res.data.effective_rate);
      const name = affiliate.name || affiliate.email || affiliate.id;
      toast.success(
        isFr
          ? `${name} approuvé — ${oldRatePctForToast}% → ${newRatePct}%`
          : `${name} approved — ${oldRatePctForToast}% → ${newRatePct}%`,
      );
      onSaved && onSaved();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg =
        typeof detail === 'string'
          ? detail
          : detail?.[isFr ? 'message_fr' : 'message_en']
            || detail?.message
            || (isFr ? 'Échec de l\u2019approbation' : 'Approval failed');
      setError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const doSaveRate = async () => {
    const v = validate();
    if (!v.ok) {
      setError(v.msg);
      toast.error(v.msg);
      return;
    }
    setSaving(true);
    setError('');
    try {
      const token = localStorage.getItem('token');
      const res = await axios.post(
        `${API}/affiliate/admin/set-rate`,
        { user_id: affiliate.id, commission_rate: v.rate },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const newRatePct = fractionToPct(res.data.effective_rate);
      const name = affiliate.name || affiliate.email || affiliate.id;
      if (res.data.changed) {
        toast.success(
          isFr
            ? `${name} : ${oldRatePctForToast}% → ${newRatePct}%`
            : `${name}: ${oldRatePctForToast}% → ${newRatePct}%`,
        );
      } else {
        toast(isFr ? 'Aucun changement' : 'No change', { duration: 1500 });
      }
      onSaved && onSaved();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg =
        typeof detail === 'string'
          ? detail
          : detail?.[isFr ? 'message_fr' : 'message_en']
            || detail?.message
            || (isFr ? 'Échec de la mise à jour' : 'Update failed');
      setError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  // iter502 — validate + save the Influencer Partner Program schedule.
  const validatePartner = () => {
    const parsePct = (s, label) => {
      const trimmed = String(s || '').trim();
      if (trimmed === '') return { rate: null };
      const n = Number(trimmed);
      if (Number.isNaN(n)) return { err: isFr ? `${label} invalide` : `Invalid ${label}` };
      if (n < RATE_MIN_PCT || n > (maxRate * 100)) {
        return {
          err: isFr
            ? `${label} doit être entre ${RATE_MIN_PCT}% et ${maxRate * 100}%`
            : `${label} must be between ${RATE_MIN_PCT}% and ${maxRate * 100}%`,
        };
      }
      return { rate: pctToFraction(n) };
    };
    const t1 = parsePct(t1Rate, isFr ? 'Tier 1' : 'Tier 1');
    if (t1.err) return { ok: false, msg: t1.err };
    const t2 = parsePct(t2Rate, isFr ? 'Tier 2' : 'Tier 2');
    if (t2.err) return { ok: false, msg: t2.err };
    const monthsN = Number(t1Months);
    if (!Number.isInteger(monthsN) || monthsN < 1 || monthsN > 120) {
      return {
        ok: false,
        msg: isFr
          ? 'La durée doit être un entier entre 1 et 120 mois'
          : 'Duration must be an integer between 1 and 120 months',
      };
    }
    return {
      ok: true,
      partner_program: partnerEnabled,
      tier_1_rate: t1.rate,
      tier_2_rate: t2.rate,
      tier_1_duration_months: monthsN,
    };
  };

  const doSavePartner = async () => {
    const v = validatePartner();
    if (!v.ok) {
      setPartnerError(v.msg);
      toast.error(v.msg);
      return;
    }
    setSaving(true);
    setPartnerError('');
    try {
      const token = localStorage.getItem('token');
      const body = {
        user_id: affiliate.id,
        partner_program: v.partner_program,
      };
      if (v.partner_program) {
        body.tier_1_rate = v.tier_1_rate;
        body.tier_2_rate = v.tier_2_rate;
        body.tier_1_duration_months = v.tier_1_duration_months;
      }
      const res = await axios.post(
        `${API}/affiliate/admin/set-rate`,
        body,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const name = affiliate.name || affiliate.email || affiliate.id;
      if (res.data.changed) {
        const label = v.partner_program
          ? (isFr
            ? `Partenaire activé (T1 ${fractionToPct(v.tier_1_rate)}% / T2 ${fractionToPct(v.tier_2_rate)}%)`
            : `Partner enabled (T1 ${fractionToPct(v.tier_1_rate)}% / T2 ${fractionToPct(v.tier_2_rate)}%)`)
          : (isFr ? 'Partenaire désactivé' : 'Partner disabled');
        toast.success(`${name}: ${label}`);
      } else {
        toast(isFr ? 'Aucun changement' : 'No change', { duration: 1500 });
      }
      onSaved && onSaved();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg =
        typeof detail === 'string'
          ? detail
          : detail?.[isFr ? 'message_fr' : 'message_en']
            || detail?.message
            || (isFr ? 'Échec de la mise à jour' : 'Update failed');
      setPartnerError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const badgeMeta = STATUS_BADGE[status] || STATUS_BADGE.none;

  return (
    <div
      className="grid grid-cols-1 md:grid-cols-12 gap-3 items-start md:items-center p-4 border rounded-lg bg-white dark:bg-slate-900"
      data-testid={`affiliate-row-${affiliate.id}`}
    >
      <div className="md:col-span-5 min-w-0">
        <p className="font-semibold truncate" data-testid={`affiliate-name-${affiliate.id}`}>
          {affiliate.name || (isFr ? 'Sans nom' : 'Unnamed')}
        </p>
        <p className="text-xs text-muted-foreground truncate">{affiliate.email}</p>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          <Badge
            className={`${badgeMeta.cls} text-[10px]`}
            data-testid={`affiliate-status-badge-${affiliate.id}`}
          >
            {isFr ? badgeMeta.fr : badgeMeta.en}
          </Badge>
          {affiliate.partner_program && (
            <Badge
              className="bg-purple-100 text-purple-800 border-purple-300 text-[10px]"
              data-testid={`affiliate-partner-badge-${affiliate.id}`}
            >
              {isFr ? 'Partenaire' : 'Partner'}
            </Badge>
          )}
          <span className="text-xs text-muted-foreground">
            {isFr ? 'Actuel:' : 'Current:'}{' '}
            <b data-testid={`affiliate-effective-rate-${affiliate.id}`}>
              {currentEffectivePct}%
            </b>
            {affiliate.commission_rate == null && !affiliate.partner_program && (
              <span className="text-[10px] italic ml-1 text-slate-500">
                ({isFr ? 'défaut' : 'default'})
              </span>
            )}
            {affiliate.commission_rate == null && affiliate.partner_program && (
              <span className="text-[10px] italic ml-1 text-purple-700 dark:text-purple-400">
                ({isFr ? 'tier programme' : 'program tier'})
              </span>
            )}
          </span>
          {affiliate.referred_count > 0 && (
            <span className="text-[10px] text-muted-foreground">
              · {affiliate.referred_count} {isFr ? 'référés' : 'referred'}
            </span>
          )}
          {(affiliate.total_credits_earned || 0) > 0 && (
            <span className="text-[10px] text-muted-foreground">
              · {formatCurrency(affiliate.total_credits_earned)} {isFr ? 'gagnés' : 'earned'}
            </span>
          )}
        </div>
      </div>

      <div className="md:col-span-3">
        <label className="block text-[10px] uppercase tracking-wide text-slate-500 mb-1">
          {isFr ? 'Taux (%)' : 'Rate (%)'}
        </label>
        <Input
          type="number"
          min={RATE_MIN_PCT}
          max={maxRate * 100}
          step="0.1"
          value={rateInput}
          onChange={(e) => { setRateInput(e.target.value); setError(''); }}
          placeholder={`${fractionToPct(defaultRate)}`}
          className={error ? 'border-rose-500' : ''}
          data-testid={`affiliate-rate-input-${affiliate.id}`}
        />
        {error && (
          <p className="text-xs text-rose-600 mt-1" data-testid={`affiliate-rate-error-${affiliate.id}`}>
            {error}
          </p>
        )}
      </div>

      <div className="md:col-span-4 flex flex-wrap gap-2 justify-end">
        {(isPendingOrNone || isRevoked) && (
          <Button
            size="sm"
            onClick={doApprove}
            disabled={saving}
            data-testid={`affiliate-approve-btn-${affiliate.id}`}
            className="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <CheckCircle className="h-3.5 w-3.5 mr-1.5" />}
            {isRevoked
              ? (isFr ? 'Réactiver' : 'Reactivate')
              : (isFr ? 'Approuver' : 'Approve')}
          </Button>
        )}
        {isActive && (
          <>
            <Button
              size="sm"
              onClick={doSaveRate}
              disabled={saving}
              data-testid={`affiliate-save-rate-btn-${affiliate.id}`}
              className="bg-blue-600 hover:bg-blue-700 text-white"
            >
              {saving ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Save className="h-3.5 w-3.5 mr-1.5" />}
              {isFr ? 'Enregistrer' : 'Save Rate'}
            </Button>
            <RevokeButton affiliate={affiliate} isFr={isFr} onSaved={onSaved} />
          </>
        )}
        <Button
          size="sm"
          variant="outline"
          onClick={() => setShowPartner((s) => !s)}
          data-testid={`affiliate-partner-toggle-${affiliate.id}`}
          className={affiliate.partner_program
            ? 'border-purple-400 text-purple-700 hover:bg-purple-50'
            : 'border-slate-300 text-slate-700 hover:bg-slate-50'}
        >
          {showPartner
            ? (isFr ? 'Masquer partenaire' : 'Hide Partner')
            : (isFr ? 'Programme partenaire' : 'Partner Program')}
        </Button>
      </div>

      {showPartner && (
        <div
          className="md:col-span-12 border-t border-slate-200 dark:border-slate-800 pt-4 mt-2 space-y-3"
          data-testid={`affiliate-partner-section-${affiliate.id}`}
        >
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={partnerEnabled}
                onChange={(e) => { setPartnerEnabled(e.target.checked); setPartnerError(''); }}
                data-testid={`affiliate-partner-enabled-${affiliate.id}`}
                className="h-4 w-4"
              />
              <span className="text-sm font-medium">
                {isFr
                  ? 'Inscrit au Programme Partenaire Influenceur'
                  : 'Enrolled in Influencer Partner Program'}
              </span>
            </label>
            {affiliate.partnership_start_date && (
              <span className="text-[10px] text-muted-foreground" data-testid={`affiliate-partner-start-${affiliate.id}`}>
                {isFr ? 'Début :' : 'Started:'}{' '}
                {new Date(affiliate.partnership_start_date).toLocaleDateString(isFr ? 'fr-CA' : 'en-CA')}
              </span>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block text-[10px] uppercase tracking-wide text-slate-500 mb-1">
                {isFr ? 'Tier 1 taux (%)' : 'Tier 1 rate (%)'}
              </label>
              <Input
                type="number"
                min={RATE_MIN_PCT}
                max={maxRate * 100}
                step="0.1"
                value={t1Rate}
                onChange={(e) => { setT1Rate(e.target.value); setPartnerError(''); }}
                disabled={!partnerEnabled}
                placeholder={String(fractionToPct(partnerDefaults?.tier_1_rate))}
                data-testid={`affiliate-tier1-rate-${affiliate.id}`}
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-wide text-slate-500 mb-1">
                {isFr ? 'Durée Tier 1 (mois)' : 'Tier 1 duration (months)'}
              </label>
              <Input
                type="number"
                min="1"
                max="120"
                step="1"
                value={t1Months}
                onChange={(e) => { setT1Months(e.target.value); setPartnerError(''); }}
                disabled={!partnerEnabled}
                placeholder={String(partnerDefaults?.tier_1_duration_months ?? 6)}
                data-testid={`affiliate-tier1-months-${affiliate.id}`}
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-wide text-slate-500 mb-1">
                {isFr ? 'Tier 2 taux (%)' : 'Tier 2 rate (%)'}
              </label>
              <Input
                type="number"
                min={RATE_MIN_PCT}
                max={maxRate * 100}
                step="0.1"
                value={t2Rate}
                onChange={(e) => { setT2Rate(e.target.value); setPartnerError(''); }}
                disabled={!partnerEnabled}
                placeholder={String(fractionToPct(partnerDefaults?.tier_2_rate))}
                data-testid={`affiliate-tier2-rate-${affiliate.id}`}
              />
            </div>
          </div>
          <p className="text-[11px] text-slate-500 italic">
            {isFr
              ? 'Le taux Tier 1 s\u2019applique automatiquement pendant la période initiale à partir de la date de début du partenariat, puis bascule vers le Tier 2. Un taux forfaitaire (Rate ci-dessus) remplace ce calendrier s\u2019il est défini.'
              : 'Tier 1 rate applies automatically for the initial window from the partnership start date, then falls through to Tier 2. A flat Rate (above) overrides this schedule when set.'}
          </p>
          {partnerError && (
            <p className="text-xs text-rose-600" data-testid={`affiliate-partner-error-${affiliate.id}`}>
              {partnerError}
            </p>
          )}
          <div className="flex justify-end">
            <Button
              size="sm"
              onClick={doSavePartner}
              disabled={saving}
              data-testid={`affiliate-save-partner-btn-${affiliate.id}`}
              className="bg-purple-600 hover:bg-purple-700 text-white"
            >
              {saving ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Save className="h-3.5 w-3.5 mr-1.5" />}
              {isFr ? 'Enregistrer le programme' : 'Save Program'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

const RevokeButton = ({ affiliate, isFr, onSaved }) => {
  const [confirm, setConfirm] = useState(null);

  const doRevoke = async () => {
    try {
      const token = localStorage.getItem('token');
      await axios.post(
        `${API}/affiliate/admin/set-status`,
        { user_id: affiliate.id, status: 'revoked' },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(
        isFr
          ? `${affiliate.name || affiliate.email} révoqué`
          : `${affiliate.name || affiliate.email} revoked`,
      );
      onSaved && onSaved();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg =
        typeof detail === 'string'
          ? detail
          : detail?.[isFr ? 'message_fr' : 'message_en']
            || detail?.message
            || (isFr ? 'Échec de la révocation' : 'Revoke failed');
      toast.error(msg);
    }
  };

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        onClick={() => setConfirm({
          title: isFr ? 'Révoquer cet affilié ?' : 'Revoke this affiliate?',
          description: isFr
            ? `${affiliate.name || affiliate.email} arrêtera d\u2019accumuler des commissions à partir de maintenant. Les gains passés ne sont pas affectés.`
            : `${affiliate.name || affiliate.email} will stop accruing new commissions immediately. Past earnings are not affected.`,
          confirmText: isFr ? 'Révoquer' : 'Revoke',
          successMessage: '',
          onConfirm: doRevoke,
        })}
        data-testid={`affiliate-revoke-btn-${affiliate.id}`}
        className="border-rose-300 text-rose-700 hover:bg-rose-50"
      >
        <Ban className="h-3.5 w-3.5 mr-1.5" />
        {isFr ? 'Révoquer' : 'Revoke'}
      </Button>
      <ConfirmDialog state={confirm} onClose={() => setConfirm(null)} />
    </>
  );
};


const AffiliateManager = () => {
  const { token } = useAuth();
  const { t, i18n } = useTranslation();
  const isFr = i18n.language?.startsWith('fr');
  const [rows, setRows] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [defaultRate, setDefaultRate] = useState(0.03);
  const [maxRate, setMaxRate] = useState(RATE_MAX_PCT_DEFAULT / 100);
  // iter502 — Partner Program defaults (pre-fill values for new enrolments)
  const [partnerDefaults, setPartnerDefaults] = useState({
    tier_1_rate: 0.50,
    tier_1_duration_months: 6,
    tier_2_rate: 0.05,
  });
  const [loading, setLoading] = useState(true);
  const [confirm, setConfirm] = useState(null);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const fetchData = useCallback(async () => {
    try {
      const [affRes, payRes] = await Promise.all([
        axios.get(`${API}/affiliate/admin/all`, { headers }),
        axios.get(`${API}/admin/affiliate/payouts`, { headers }).catch(() => ({ data: [] })),
      ]);
      const affData = affRes.data;
      setRows(Array.isArray(affData?.items) ? affData.items : []);
      setDefaultRate(affData?.default_rate ?? 0.03);
      setMaxRate(affData?.max_rate ?? (RATE_MAX_PCT_DEFAULT / 100));
      if (affData?.partner_program_defaults) {
        setPartnerDefaults(affData.partner_program_defaults);
      }
      const payData = payRes.data;
      setPayouts(Array.isArray(payData) ? payData : (payData?.payouts || []));
    } catch (_) {
      toast.error(isFr ? 'Échec du chargement des données' : 'Failed to load affiliate data');
    } finally {
      setLoading(false);
    }
  }, [headers, isFr]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleApprovePayout = (payoutId, amount) => {
    setConfirm({
      title: isFr ? 'Approuver ce paiement ?' : 'Approve this affiliate payout?',
      description: `${isFr ? 'Montant' : 'Amount'}: $${(amount ?? 0).toFixed(2)}.
${isFr ? 'Cela déclenchera le transfert Stripe.' : 'This will trigger the Stripe transfer.'}`,
      confirmText: isFr ? 'Approuver le paiement' : 'Approve Payout',
      successMessage: isFr ? 'Paiement approuvé' : 'Payout approved',
      onConfirm: async () => {
        await axios.put(`${API}/admin/affiliate/payouts/${payoutId}/approve`, {}, { headers });
        fetchData();
      },
    });
  };

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  const activeCount = rows.filter((r) => (r.affiliate_status || 'none').toLowerCase() === 'active').length;
  const totalCommissions = rows.reduce((s, r) => s + (r.total_credits_earned || 0), 0);
  const pendingPayoutCount = payouts.filter((p) => p.status === 'pending').length;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <DollarSign className="h-6 w-6" />
          {isFr ? 'Gestion du programme d\u2019affiliation' : 'Affiliate Program Management'}
        </h2>
        <p className="text-muted-foreground">
          {isFr
            ? `Approbations, paiements, taux personnalisés (défaut ${(defaultRate * 100).toFixed(2)}%, max ${(maxRate * 100).toFixed(0)}%), et Programme Partenaire Influenceur.`
            : `Approvals, payouts, custom rates (default ${(defaultRate * 100).toFixed(2)}%, cap ${(maxRate * 100).toFixed(0)}%), and Influencer Partner Program.`}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card><CardContent className="p-6"><div className="flex items-center gap-4"><Users className="h-8 w-8 text-blue-600" /><div><p className="text-2xl font-bold" data-testid="active-affiliate-count">{activeCount}</p><p className="text-sm text-muted-foreground">{isFr ? 'Affiliés actifs' : 'Active Affiliates'}</p></div></div></CardContent></Card>
        <Card><CardContent className="p-6"><div className="flex items-center gap-4"><DollarSign className="h-8 w-8 text-green-600" /><div><p className="text-2xl font-bold">{formatCurrency(totalCommissions)}</p><p className="text-sm text-muted-foreground">{isFr ? 'Commissions totales' : 'Total Commissions'}</p></div></div></CardContent></Card>
        <Card><CardContent className="p-6"><div className="flex items-center gap-4"><CheckCircle className="h-8 w-8 text-yellow-600" /><div><p className="text-2xl font-bold">{pendingPayoutCount}</p><p className="text-sm text-muted-foreground">{isFr ? 'Paiements en attente' : 'Pending Payouts'}</p></div></div></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle>{t('admin.payoutRequests', { defaultValue: isFr ? 'Demandes de paiement' : 'Payout Requests' })}</CardTitle></CardHeader>
        <CardContent>
          {payouts.length > 0 ? (
            <div className="space-y-2">
              {payouts.map((payout) => (
                <div key={payout.id} className="flex justify-between items-center p-4 border rounded-lg">
                  <div>
                    <p className="font-semibold">${payout.amount}</p>
                    <p className="text-sm text-muted-foreground">User: {payout.user_id}</p>
                    <p className="text-xs text-muted-foreground">{new Date(payout.created_at).toLocaleDateString()}</p>
                  </div>
                  <div className="flex gap-2">
                    <Badge className={payout.status === 'approved' ? 'bg-green-600 text-white' : 'bg-yellow-600 text-white'}>{payout.status}</Badge>
                    {payout.status === 'pending' && (
                      <Button size="sm" className="bg-green-600 hover:bg-green-700 text-white" onClick={() => handleApprovePayout(payout.id, payout.amount)} data-testid={`approve-payout-${payout.id}`}>
                        <CheckCircle className="h-4 w-4 mr-1" />{isFr ? 'Approuver' : 'Approve'}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">
              {isFr ? 'Aucune demande de paiement' : 'No payout requests'}
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            {t('admin.manageAffiliateStatus', {
              defaultValue: isFr
                ? 'Gérer le statut et le taux des affiliés'
                : 'Manage Affiliate Status & Rate',
            })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {rows.length === 0 ? (
            <p className="text-center text-muted-foreground py-8" data-testid="affiliates-empty">
              {isFr ? 'Aucun affilié pour le moment.' : 'No affiliates yet.'}
            </p>
          ) : (
            <div className="space-y-2" data-testid="affiliates-list">
              {rows.map((affiliate) => (
                <AffiliateRow
                  key={affiliate.id}
                  affiliate={affiliate}
                  defaultRate={defaultRate}
                  maxRate={maxRate}
                  partnerDefaults={partnerDefaults}
                  onSaved={fetchData}
                  isFr={isFr}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog state={confirm} onClose={() => setConfirm(null)} />
    </div>
  );
};

export default AffiliateManager;
