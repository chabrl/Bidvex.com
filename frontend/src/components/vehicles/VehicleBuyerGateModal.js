/**
 * iter201 — Phase 3 / 3A — Vehicle Buyer Gate Modal.
 *
 * Provincial-aware gate that fires before a buyer can place a bid or "Buy
 * It Now" on any vehicle listing (parts_accessories category is exempt).
 *
 * The component self-fetches /api/vehicles/buyer-verification/me?listing_id=…
 * and renders the correct UI per the gate_state returned by the backend:
 *   • province_required   → "Set your province" prompt
 *   • open                → green ✓ session-dismissable notice
 *   • territory_advisory  → advisory banner, allow proceed
 *   • qc_disclosure       → LPC ack checkbox
 *   • restricted_gate     → 3-option radio (dealer / dealer_rep / individual=BLOCK)
 *   • pending_review      → "Under review" notice
 *   • rejected            → rejection reason + resubmit
 *   • verified            → call onVerified(); auto-dismiss
 *
 * Props:
 *   open, onClose, listingId, listingProvince, vehicleProvince — pickup province
 *   onVerified() — called when the user is cleared to bid; parent can then
 *     trigger the actual bid flow.
 */
import API_BASE from '../../config';
import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Loader2, Shield, AlertTriangle, CheckCircle2, MapPin, X, ExternalLink } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { toast } from 'sonner';

const API = API_BASE;

const SESSION_DISMISS_KEY = (province) => `bidvex.buyer_gate.dismissed.${province}`;

const RESTRICTED = ['ON', 'NB', 'NS', 'PE', 'NL'];

const VehicleBuyerGateModal = ({ open, onClose, listingId, onVerified }) => {
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');

  const [loading, setLoading] = useState(true);
  const [state, setState] = useState(null);   // gate_state JSON from backend
  const [provinceRule, setProvinceRule] = useState(null); // province_regulations doc
  const [submitting, setSubmitting] = useState(false);

  // Restricted-gate form state
  const [option, setOption] = useState(null); // "dealer" | "dealer_representative" | "individual"
  const [licenseNumber, setLicenseNumber] = useState('');
  const [businessName, setBusinessName] = useState('');
  const [docFile, setDocFile] = useState(null);

  // QC LPC ack state
  const [qcAcked, setQcAcked] = useState(false);

  const fetchState = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const headers = { Authorization: `Bearer ${token}` };
      const r = await axios.get(
        `${API}/vehicles/buyer-verification/me${listingId ? `?listing_id=${encodeURIComponent(listingId)}` : ''}`,
        { headers }
      );
      setState(r.data);
      // Load province regulation
      if (r.data?.province) {
        try {
          const pr = await axios.get(`${API}/vehicles/province-regulations/${r.data.province}`);
          setProvinceRule(pr.data);
        } catch (_) { /* ignore */ }
      }
    } catch (e) {
      toast.error(isFr ? 'Erreur de chargement' : 'Failed to load gate state');
    } finally {
      setLoading(false);
    }
  }, [listingId, isFr]);

  useEffect(() => {
    if (open) fetchState();
  }, [open, fetchState]);

  const provinceLabel = useMemo(() => {
    if (!provinceRule) return state?.province || '';
    return isFr ? provinceRule.province_name_fr : provinceRule.province_name_en;
  }, [provinceRule, state, isFr]);

  // ───────── Auto-dismiss flows: open + verified + territory advisory ─────────
  useEffect(() => {
    if (!open || !state) return;
    if (state.gate_state === 'open' || state.gate_state === 'verified' || state.gate_state === 'qc_disclosure_acked') {
      // Already cleared — call onVerified once
      onVerified?.();
      onClose?.();
    }
  }, [open, state, onVerified, onClose]);

  // ───────── Submission handlers ─────────
  const handleSetProvince = (code) => {
    navigate('/settings');
  };

  const handleQcAck = async () => {
    if (!qcAcked) {
      toast.error(isFr ? 'Veuillez cocher la case' : 'Please check the box to continue');
      return;
    }
    setSubmitting(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(
        `${API}/vehicles/buyer-verification/qc-ack`,
        { listing_id: listingId },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(isFr ? 'Reconnaissance enregistrée' : 'Acknowledged');
      onVerified?.();
      onClose?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail?.[isFr ? 'message_fr' : 'message_en'] || 'Failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRestrictedSubmit = async () => {
    if (option === 'individual') return; // hard-block — should never reach here
    if (!licenseNumber.trim()) {
      toast.error(isFr ? 'Numéro de licence requis' : 'Licence number required');
      return;
    }
    if (option === 'dealer_representative' && !businessName.trim()) {
      toast.error(isFr ? "Nom de l'entreprise requis" : 'Business name required');
      return;
    }
    setSubmitting(true);
    try {
      const token = localStorage.getItem('token');
      const fd = new FormData();
      fd.append('type', option);
      fd.append('license_number', licenseNumber);
      if (option === 'dealer_representative') fd.append('dealer_business_name', businessName);
      if (docFile) fd.append('document', docFile);
      await axios.post(`${API}/vehicles/buyer-verification/submit`, fd, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(isFr
        ? "Vérification soumise. Réponse sous 24 h."
        : 'Verification submitted. Response within 24 h.', { duration: 7000 });
      await fetchState();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error((detail && (detail.message_fr || detail.message_en)) || 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSessionDismiss = () => {
    if (state?.province) {
      try { sessionStorage.setItem(SESSION_DISMISS_KEY(state.province), '1'); } catch (_) {}
    }
    onVerified?.();
    onClose?.();
  };

  // ───────── Render gate by state ─────────
  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose?.()}>
      <DialogContent className="max-w-lg" data-testid="vehicle-buyer-gate-modal">
        {loading ? (
          <div className="flex items-center justify-center py-8 gap-2 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> {isFr ? 'Chargement…' : 'Loading…'}
          </div>
        ) : state?.gate_state === 'province_required' ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <MapPin className="h-5 w-5 text-amber-600" />
                {isFr ? 'Province requise' : 'Province required'}
              </DialogTitle>
              <DialogDescription>
                {isFr
                  ? 'Veuillez définir votre province dans les paramètres de profil pour confirmer votre admissibilité aux enchères de véhicules.'
                  : 'Please set your province in Profile Settings to confirm your eligibility to bid on vehicles.'}
              </DialogDescription>
            </DialogHeader>
            <div className="flex justify-end gap-2 mt-4">
              <Button variant="outline" onClick={onClose}>{isFr ? 'Annuler' : 'Cancel'}</Button>
              <Button onClick={handleSetProvince} data-testid="buyer-gate-go-to-profile">
                {isFr ? 'Aller aux paramètres' : 'Go to Profile Settings'}
              </Button>
            </div>
          </>
        ) : state?.gate_state === 'restricted_gate' ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-600" />
                {isFr ? `Vérification requise — ${provinceLabel}` : `Dealer Verification Required — ${provinceLabel}`}
              </DialogTitle>
              <DialogDescription className="text-sm leading-relaxed">
                {isFr
                  ? (provinceRule?.buyer_gate_message_fr || provinceRule?.seller_notice_fr)
                  : (provinceRule?.buyer_gate_message_en || provinceRule?.seller_notice_en)}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 mt-2" data-testid="buyer-gate-options">
              {[
                { key: 'dealer', label_en: `I am a licensed dealer in ${provinceLabel}`, label_fr: `Je suis un concessionnaire licencié en ${provinceLabel}` },
                { key: 'dealer_representative', label_en: 'I am purchasing on behalf of a licensed dealer', label_fr: "J'achète pour le compte d'un concessionnaire licencié" },
                { key: 'individual', label_en: 'I am an individual buyer (not a dealer)', label_fr: "Je suis un acheteur individuel (non concessionnaire)" },
              ].map((opt) => (
                <label
                  key={opt.key}
                  className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition ${option === opt.key ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30' : 'border-slate-200 hover:border-slate-300'}`}
                  data-testid={`buyer-gate-option-${opt.key}`}
                >
                  <input
                    type="radio"
                    checked={option === opt.key}
                    onChange={() => setOption(opt.key)}
                    className="mt-0.5"
                  />
                  <span className="text-sm font-medium">{isFr ? opt.label_fr : opt.label_en}</span>
                </label>
              ))}
            </div>

            {option === 'dealer' && (
              <div className="space-y-2 mt-3">
                <Label className="text-sm">{isFr ? 'Numéro de licence du concessionnaire' : 'Dealer Licence Number'} *</Label>
                <Input value={licenseNumber} onChange={(e) => setLicenseNumber(e.target.value)} data-testid="buyer-gate-license-input" />
                <Label className="text-sm">{isFr ? "Document de licence (PDF/JPG/PNG, max 10 Mo)" : 'Licence Document (PDF/JPG/PNG, max 10 MB)'}</Label>
                <Input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setDocFile(e.target.files?.[0] || null)} data-testid="buyer-gate-doc-input" />
              </div>
            )}
            {option === 'dealer_representative' && (
              <div className="space-y-2 mt-3">
                <Label className="text-sm">{isFr ? 'Numéro de licence du concessionnaire' : "Dealer's Licence Number"} *</Label>
                <Input value={licenseNumber} onChange={(e) => setLicenseNumber(e.target.value)} data-testid="buyer-gate-license-input" />
                <Label className="text-sm">{isFr ? "Nom de l'entreprise du concessionnaire" : 'Dealer Business Name'} *</Label>
                <Input value={businessName} onChange={(e) => setBusinessName(e.target.value)} data-testid="buyer-gate-business-input" />
              </div>
            )}
            {option === 'individual' && (
              <div className="rounded-lg border-2 border-red-200 bg-red-50 dark:bg-red-950/30 p-4 mt-3 text-sm" data-testid="buyer-gate-individual-block">
                <p className="font-semibold text-red-700 dark:text-red-300">
                  {isFr ? 'Achat bloqué' : 'Purchase blocked'}
                </p>
                <p className="text-red-700 dark:text-red-200 mt-1">
                  {isFr
                    ? `Les acheteurs individuels en ${provinceLabel} ne sont pas autorisés à acheter de véhicules aux enchères de concessionnaires selon les règlements de ${provinceRule?.regulatory_body || 'l\'autorité provinciale'}. Pour acheter un véhicule, contactez un concessionnaire licencié en ${provinceLabel}.`
                    : `Individual buyers in ${provinceLabel} are not permitted to purchase from dealer vehicle auctions under ${provinceRule?.regulatory_body || 'provincial regulator'} regulations. To purchase a vehicle, contact a licensed ${provinceLabel} dealer who can bid on your behalf.`}
                </p>
                <a
                  href={`https://www.google.com/maps/search/${encodeURIComponent((provinceLabel || '') + ' car dealers')}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-flex items-center gap-1 text-red-800 dark:text-red-300 underline-offset-2 hover:underline"
                  data-testid="buyer-gate-find-dealer-link"
                >
                  {isFr ? 'Trouver un concessionnaire' : 'Find a dealer'} <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}

            <div className="flex justify-end gap-2 mt-4">
              <Button variant="outline" onClick={onClose}>{isFr ? 'Fermer' : 'Close'}</Button>
              <Button
                disabled={!option || option === 'individual' || submitting}
                onClick={handleRestrictedSubmit}
                data-testid="buyer-gate-submit-btn"
              >
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : (isFr ? 'Continuer' : 'Continue')}
              </Button>
            </div>
          </>
        ) : state?.gate_state === 'qc_disclosure' ? (
          <>
            <DialogHeader>
              <DialogTitle data-testid="buyer-gate-qc-title">
                {isFr ? 'Avis de protection du consommateur — Québec' : 'Quebec Consumer Protection Notice'}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-3 text-sm leading-relaxed mt-1">
              <p data-testid="buyer-gate-qc-fr-body">
                <strong className="text-blue-700 dark:text-blue-300">FR :</strong>{' '}
                En vertu de la <em>Loi sur la protection du consommateur</em> du Québec (LPC), le vendeur (concessionnaire) est tenu de vous fournir une divulgation complète de l'état du véhicule, de son historique d'accidents, de tout privilège existant et de son utilisation antérieure avant la clôture de la vente. En enchérissant, vous reconnaissez avoir reçu ou avoir eu accès à ces informations dans la fiche de l'article.
              </p>
              <p data-testid="buyer-gate-qc-en-body">
                <strong className="text-blue-700 dark:text-blue-300">EN:</strong>{' '}
                Under Quebec's Consumer Protection Act (LPC), the seller (dealer) is required to provide you with full disclosure of vehicle condition, accident history, existing liens, and prior use before the sale closes. By bidding, you acknowledge having received or having had access to this information in the listing.
              </p>
              <label className="flex items-start gap-2 mt-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={qcAcked}
                  onChange={(e) => setQcAcked(e.target.checked)}
                  className="mt-0.5"
                  data-testid="buyer-gate-qc-ack-checkbox"
                />
                <span className="text-sm">
                  {isFr
                    ? "Je comprends et j'accepte les conditions de divulgation LPC applicables à cet achat."
                    : 'I understand and acknowledge the LPC disclosure requirements applicable to this purchase.'}
                </span>
              </label>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <Button variant="outline" onClick={onClose}>{isFr ? 'Annuler' : 'Cancel'}</Button>
              <Button disabled={!qcAcked || submitting} onClick={handleQcAck} data-testid="buyer-gate-qc-continue-btn">
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : (isFr ? 'Continuer pour enchérir' : 'Continue to Bid')}
              </Button>
            </div>
          </>
        ) : state?.gate_state === 'pending_review' ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-blue-600" />
                {isFr ? 'Vérification en cours' : 'Verification under review'}
              </DialogTitle>
              <DialogDescription>
                {isFr
                  ? "Votre vérification de concessionnaire est en cours d'examen. Vous serez notifié dans les 24 heures."
                  : 'Your dealer verification is under review. You will be notified within 24 hours.'}
              </DialogDescription>
            </DialogHeader>
            <div className="flex justify-end mt-4">
              <Button onClick={onClose}>{isFr ? 'Fermer' : 'Close'}</Button>
            </div>
          </>
        ) : state?.gate_state === 'rejected' ? (
          <>
            <DialogHeader>
              <DialogTitle className="text-red-700 dark:text-red-300">
                {isFr ? 'Vérification rejetée' : 'Verification rejected'}
              </DialogTitle>
              <DialogDescription>
                <strong>{isFr ? 'Raison :' : 'Reason:'}</strong> {state?.rejection_reason || '—'}
              </DialogDescription>
            </DialogHeader>
            <p className="text-sm mt-2">
              {isFr
                ? 'Vous pouvez resoumettre votre vérification avec des documents mis à jour ci-dessous.'
                : 'You can resubmit your verification with updated documents below.'}
            </p>
            <Button onClick={() => setState({ ...state, gate_state: 'restricted_gate' })} className="mt-3" data-testid="buyer-gate-resubmit-btn">
              {isFr ? 'Resoumettre' : 'Resubmit'}
            </Button>
          </>
        ) : state?.gate_state === 'territory_advisory' ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-600" />
                {isFr ? `Avis — ${provinceLabel}` : `Advisory — ${provinceLabel}`}
              </DialogTitle>
              <DialogDescription>
                {isFr
                  ? `Les règlements d'enchères de véhicules dans les territoires varient. Assurez-vous de respecter les exigences de ${provinceLabel} avant de finaliser votre achat.`
                  : `Vehicle auction regulations in territories vary. Ensure you comply with ${provinceLabel} motor vehicle requirements before completing your purchase.`}
              </DialogDescription>
            </DialogHeader>
            <div className="flex justify-end gap-2 mt-4">
              <Button onClick={() => { onVerified?.(); onClose?.(); }} data-testid="buyer-gate-territory-continue">
                {isFr ? 'Continuer' : 'Continue'}
              </Button>
            </div>
          </>
        ) : state?.gate_state === 'open' ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300">
                <CheckCircle2 className="h-5 w-5" />
                {isFr ? `Vous êtes admissible — ${provinceLabel}` : `You're eligible — ${provinceLabel}`}
              </DialogTitle>
              <DialogDescription>
                {isFr
                  ? `Les acheteurs individuels peuvent acheter des véhicules aux enchères en ${provinceLabel}. Vous êtes prêt.`
                  : `Individual buyers may purchase vehicles at auction in ${provinceLabel}. You're good to go.`}
              </DialogDescription>
            </DialogHeader>
            <div className="flex justify-end mt-4">
              <Button onClick={handleSessionDismiss} data-testid="buyer-gate-open-continue">
                {isFr ? 'Continuer pour enchérir' : 'Continue to Bid'}
              </Button>
            </div>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>{isFr ? 'État inconnu' : 'Unknown state'}</DialogTitle>
              <DialogDescription>{state?.gate_state}</DialogDescription>
            </DialogHeader>
            <div className="flex justify-end mt-4">
              <Button onClick={onClose}>{isFr ? 'Fermer' : 'Close'}</Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default VehicleBuyerGateModal;
