/**
 * iter211 — Commission Payout Method toggle (user-facing).
 *
 * Lives in the Seller Dashboard → Payment Settings.
 * Lets partners, vehicle dealers, and storage facilities choose between:
 *   • Auto (Stripe) — saved card auto-charged immediately on close
 *   • Manual (e-Transfer/Cheque) — admin settles after off-platform payment
 *
 * Also shows the current outstanding balance + threshold so the user knows
 * when they're about to be gated.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { CreditCard, Banknote, Loader2, AlertTriangle, CheckCircle2 } from 'lucide-react';
import API_BASE from '../config';

const API = API_BASE;

const CommissionPayoutMethodCard = ({ user }) => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || 'en').startsWith('fr');
  const [method, setMethod] = useState(null);
  const [outstanding, setOutstanding] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const isEligible = !!(user?.is_partner || user?.is_vehicle_dealer || user?.is_storage_facility);

  useEffect(() => {
    if (!isEligible) { setLoading(false); return; }
    Promise.all([
      axios.get(`${API}/users/me/commission-payout-method`).catch(() => ({ data: { method: 'auto' } })),
      axios.get(`${API}/users/me/outstanding-commission`).catch(() => ({ data: { outstanding_cad: 0, blocked: false, threshold_cad: 500 } })),
    ]).then(([m, o]) => {
      setMethod(m.data?.method || 'auto');
      setOutstanding(o.data || { outstanding_cad: 0, blocked: false });
    }).finally(() => setLoading(false));
  }, [isEligible]);

  const save = async (next) => {
    if (next === method || saving) return;
    setSaving(true);
    try {
      await axios.put(`${API}/users/me/commission-payout-method`, { method: next });
      setMethod(next);
      toast.success(
        next === 'auto'
          ? (isFr ? 'Mode automatique activé' : 'Automatic mode enabled')
          : (isFr ? 'Mode manuel activé' : 'Manual mode enabled')
      );
    } catch (err) {
      toast.error(err.response?.data?.detail || (isFr ? 'Échec de la sauvegarde' : 'Save failed'));
    } finally {
      setSaving(false);
    }
  };

  if (!isEligible) return null;
  if (loading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-500 flex items-center gap-2" data-testid="commission-payout-loading">
        <Loader2 className="w-3 h-3 animate-spin" />
        {isFr ? 'Chargement…' : 'Loading…'}
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4" data-testid="commission-payout-card">
      <div>
        <h3 className="text-base font-semibold text-slate-900">
          {isFr ? 'Mode de paiement des commissions' : 'Commission Payout Method'}
        </h3>
        <p className="text-xs text-slate-500 mt-1">
          {isFr
            ? "Choisissez comment BidVex perçoit votre commission de 3–5 % après la clôture d'une enchère."
            : 'Choose how BidVex collects your 3–5% commission after an auction closes.'}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => save('auto')}
          disabled={saving}
          data-testid="commission-method-auto"
          className={`text-left rounded-lg border-2 p-4 transition-colors ${
            method === 'auto'
              ? 'border-emerald-500 bg-emerald-50'
              : 'border-slate-200 hover:border-slate-300 bg-white'
          } ${saving ? 'opacity-50' : ''}`}
        >
          <div className="flex items-start gap-3">
            <CreditCard className={`w-5 h-5 mt-0.5 ${method === 'auto' ? 'text-emerald-600' : 'text-slate-400'}`} />
            <div className="flex-1">
              <p className="font-medium text-slate-900 text-sm flex items-center gap-2">
                {isFr ? 'Automatique (Stripe)' : 'Automatic (Stripe)'}
                {method === 'auto' && <CheckCircle2 className="w-4 h-4 text-emerald-600" />}
              </p>
              <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                {isFr
                  ? 'BidVex débite la carte enregistrée immédiatement à la clôture de l\'enchère. Recommandé.'
                  : 'BidVex auto-charges your saved card immediately on auction close. Recommended.'}
              </p>
            </div>
          </div>
        </button>

        <button
          type="button"
          onClick={() => save('manual')}
          disabled={saving}
          data-testid="commission-method-manual"
          className={`text-left rounded-lg border-2 p-4 transition-colors ${
            method === 'manual'
              ? 'border-amber-500 bg-amber-50'
              : 'border-slate-200 hover:border-slate-300 bg-white'
          } ${saving ? 'opacity-50' : ''}`}
        >
          <div className="flex items-start gap-3">
            <Banknote className={`w-5 h-5 mt-0.5 ${method === 'manual' ? 'text-amber-600' : 'text-slate-400'}`} />
            <div className="flex-1">
              <p className="font-medium text-slate-900 text-sm flex items-center gap-2">
                {isFr ? 'Manuel (virement Interac / chèque)' : 'Manual (e-Transfer / Cheque)'}
                {method === 'manual' && <CheckCircle2 className="w-4 h-4 text-amber-600" />}
              </p>
              <p className="text-[11px] text-slate-500 mt-1 leading-relaxed">
                {isFr
                  ? 'Vous payez BidVex hors plateforme. Solde élevé impayé = blocage de nouvelles annonces.'
                  : 'You pay BidVex off-platform. High unpaid balance will block new listings.'}
              </p>
            </div>
          </div>
        </button>
      </div>

      {/* Outstanding balance / safety gate state */}
      {outstanding && (
        <div
          data-testid="commission-outstanding"
          className={`rounded-lg p-3 text-xs flex items-start gap-2 ${
            outstanding.blocked
              ? 'bg-rose-50 border border-rose-200 text-rose-900'
              : outstanding.outstanding_cad > 0
                ? 'bg-amber-50 border border-amber-200 text-amber-900'
                : 'bg-slate-50 border border-slate-200 text-slate-600'
          }`}
        >
          {outstanding.blocked ? <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" /> : <Banknote className="w-4 h-4 mt-0.5 flex-shrink-0" />}
          <div>
            <p className="font-medium">
              {isFr
                ? `Solde impayé : ${outstanding.outstanding_cad.toFixed(2)} $ CAD`
                : `Outstanding balance: $${outstanding.outstanding_cad.toFixed(2)} CAD`}
            </p>
            <p className="text-[11px] mt-0.5 leading-relaxed">
              {outstanding.blocked
                ? (isFr
                    ? `Vous avez dépassé le seuil de ${outstanding.threshold_cad.toFixed(2)} $. Vos nouvelles annonces sont bloquées jusqu'au règlement.`
                    : `You have exceeded the $${outstanding.threshold_cad.toFixed(2)} threshold. New listings are blocked until settled.`)
                : (isFr
                    ? `Seuil de blocage : ${outstanding.threshold_cad.toFixed(2)} $ CAD`
                    : `Block threshold: $${outstanding.threshold_cad.toFixed(2)} CAD`)}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default CommissionPayoutMethodCard;
export { CommissionPayoutMethodCard };
