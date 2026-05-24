/**
 * iter229 — Vehicle Compliance Gateway Bid Panel.
 *
 * Renders status-based banners or a System-Proxy Bid form by calling
 * GET /api/broker-relationships/compliance-check?listing_id=...
 *
 * Status verdicts handled:
 *   • eligible             → render the System-Proxy Bid form
 *   • no_broker            → "Find a Broker →" warning
 *   • relationship_pending → "Awaiting broker approval" notice
 *   • no_deposit           → "Authorize $500 Deposit →" notice
 *   • province_mismatch    → "Broker not licensed in {listingProvince}"
 *   • not_a_vehicle        → returns null (let parent render its own bid form)
 *
 * The first time a buyer bids under a broker, a LegalAgreementModal
 * presents the proxy-bid rider. Once accepted, all subsequent bids
 * flow straight through.
 *
 * Bid submission goes through POST /api/auctions/{listing_id}/bid
 * (the existing endpoint), which now enforces bid_cap +
 * proxy_bid_agreement_accepted server-side.
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import API_BASE from '../../config';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card, CardContent } from '../ui/card';
import { Alert, AlertDescription } from '../ui/alert';
import {
  Lock, ShieldCheck, AlertTriangle, MapPin, Banknote, CheckCircle2,
  Gavel, Hourglass, Loader2, ExternalLink, X,
} from 'lucide-react';

const _fmt = (n) =>
  (n == null || Number.isNaN(Number(n)))
    ? '$0'
    : new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(n));

export default function VehicleBidPanel({ listingId, vehicleProvince, currentHighestBid, lang = 'en', onBidSuccess }) {
  const [gatewayStatus, setGatewayStatus] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [bidAmount, setBidAmount] = useState('');
  const [showLegalModal, setShowLegalModal] = useState(false);
  const [errorMsg, setErrorMsg]   = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  const _token = () => localStorage.getItem('access_token') || localStorage.getItem('token');

  const load = useCallback(async () => {
    setLoading(true); setErrorMsg('');
    try {
      const r = await axios.get(
        `${API_BASE}/broker-relationships/compliance-check?listing_id=${encodeURIComponent(listingId)}`,
        { headers: { Authorization: `Bearer ${_token()}` } },
      );
      setGatewayStatus(r.data);
    } catch (e) {
      if (e?.response?.status === 401) setGatewayStatus({ status: 'no_broker' });
      else setGatewayStatus({ status: 'error', message: e?.response?.data?.detail?.error || 'failed_to_load' });
    } finally {
      setLoading(false);
    }
  }, [listingId]);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="border border-slate-200 rounded-xl p-6 bg-white animate-pulse" data-testid="vehicle-bid-panel-loading">
        <div className="h-4 bg-slate-100 rounded w-1/3 mb-4" />
        <div className="h-10 bg-slate-100 rounded mb-3" />
        <div className="h-10 bg-slate-100 rounded" />
      </div>
    );
  }

  // Non-vehicle listings: render nothing so the parent renders the standard bid form.
  if (gatewayStatus?.status === 'not_a_vehicle') return null;

  const handleBidSubmit = (e) => {
    if (e?.preventDefault) e.preventDefault();
    setErrorMsg('');

    const amt = parseFloat(bidAmount);
    if (!amt || amt <= 0) {
      setErrorMsg(lang === 'fr' ? 'Veuillez saisir un montant valide.' : 'Please enter a valid bid amount.');
      return;
    }
    if (gatewayStatus.bid_cap && amt > Number(gatewayStatus.bid_cap)) {
      setErrorMsg(
        lang === 'fr'
          ? `Cette enchère dépasse votre plafond pré-autorisé de ${_fmt(gatewayStatus.bid_cap)}.`
          : `This bid exceeds your pre-authorized broker bid cap of ${_fmt(gatewayStatus.bid_cap)}.`
      );
      return;
    }
    if (currentHighestBid && amt <= Number(currentHighestBid)) {
      setErrorMsg(
        lang === 'fr'
          ? `Votre enchère doit être supérieure à l'enchère actuelle de ${_fmt(currentHighestBid)}.`
          : `Your bid must be higher than the current bid of ${_fmt(currentHighestBid)}.`
      );
      return;
    }
    if (!gatewayStatus.proxy_bid_agreement_accepted) {
      setShowLegalModal(true);
    } else {
      executeSystemProxyBid(amt);
    }
  };

  const executeSystemProxyBid = async (amt) => {
    setSubmitting(true); setErrorMsg(''); setSuccessMsg('');
    try {
      const r = await axios.post(
        `${API_BASE}/auctions/${encodeURIComponent(listingId)}/bid`,
        { listing_id: listingId, amount: Number(amt), bid_amount: Number(amt) },
        { headers: { Authorization: `Bearer ${_token()}` } },
      );
      setSuccessMsg(
        lang === 'fr'
          ? `✓ Enchère placée à ${_fmt(amt)} sous la licence de ${gatewayStatus.broker_name}.`
          : `✓ Bid of ${_fmt(amt)} placed under ${gatewayStatus.broker_name}'s licence.`
      );
      setBidAmount('');
      if (onBidSuccess) onBidSuccess(r.data);
      // Refresh compliance state in case the agreement was accepted by this flow
      load();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setErrorMsg(
        (typeof detail === 'object'
          ? (detail[lang === 'fr' ? 'message_fr' : 'message_en'] || detail.message || detail.error)
          : detail)
        || (lang === 'fr' ? 'Échec du placement de l\'enchère.' : 'Bid placement failed.')
      );
    } finally {
      setSubmitting(false);
    }
  };

  const confirmLegalAgreement = async () => {
    setSubmitting(true); setErrorMsg('');
    try {
      await axios.post(
        `${API_BASE}/broker-relationships/accept-proxy-agreement`, {},
        { headers: { Authorization: `Bearer ${_token()}` } },
      );
      setShowLegalModal(false);
      // Reflect locally so we don't need a round-trip
      setGatewayStatus({ ...gatewayStatus, proxy_bid_agreement_accepted: true });
      await executeSystemProxyBid(parseFloat(bidAmount));
    } catch (e) {
      setErrorMsg(
        e?.response?.data?.detail?.message_en
        || e?.response?.data?.detail?.error
        || 'Failed to sign legal document rider.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  switch (gatewayStatus?.status) {
    case 'eligible':
      return (
        <Card className="border-2 border-slate-200 dark:border-slate-700 shadow-sm" data-testid="vehicle-bid-panel-eligible">
          <CardContent className="p-5 space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
              <Gavel className="w-4 h-4 text-blue-600" />
              {lang === 'fr' ? 'Placer une enchère via le système-procuration' : 'Place System-Proxy Bid'}
            </div>
            <form onSubmit={handleBidSubmit} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">
                  {lang === 'fr' ? 'Votre enchère' : 'Your bid'} (CAD)
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <span className="text-slate-500 sm:text-sm">$</span>
                  </div>
                  <Input
                    type="number"
                    required
                    min={(currentHighestBid || 0) + 1}
                    value={bidAmount}
                    onChange={(e) => setBidAmount(e.target.value)}
                    className="pl-7"
                    placeholder={lang === 'fr' ? 'Saisir le montant' : 'Enter bid value'}
                    data-testid="vehicle-bid-amount-input"
                  />
                </div>
                {gatewayStatus.bid_cap && (
                  <p className="text-[11px] text-slate-500 mt-1 flex items-center gap-1">
                    <Banknote className="w-3 h-3" />
                    {lang === 'fr'
                      ? `Plafond convenu : ${_fmt(gatewayStatus.bid_cap)}`
                      : `Agreed bid cap: ${_fmt(gatewayStatus.bid_cap)}`}
                  </p>
                )}
              </div>
              {errorMsg && (
                <Alert variant="destructive" data-testid="vehicle-bid-error">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{errorMsg}</AlertDescription>
                </Alert>
              )}
              {successMsg && (
                <Alert className="border-emerald-300 bg-emerald-50" data-testid="vehicle-bid-success">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  <AlertDescription className="text-emerald-800">{successMsg}</AlertDescription>
                </Alert>
              )}
              <Button
                type="submit"
                disabled={submitting}
                className="w-full bg-blue-600 text-white hover:bg-blue-700"
                data-testid="vehicle-bid-submit"
              >
                {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Gavel className="w-4 h-4 mr-2" />}
                {submitting
                  ? (lang === 'fr' ? 'Placement…' : 'Placing…')
                  : (lang === 'fr' ? 'Placer l\'enchère' : 'Place Bid')}
              </Button>
              <p className="text-[11px] text-center text-slate-500 flex items-center justify-center gap-1">
                <Lock className="w-3 h-3" />
                {lang === 'fr' ? 'Enchère exécutée sous la licence de' : 'Bid executed under'}{' '}
                <strong>{gatewayStatus.broker_name}</strong>{' '}
                ({gatewayStatus.broker_registry} — {gatewayStatus.broker_province || vehicleProvince})
              </p>
            </form>
          </CardContent>
          {showLegalModal && (
            <LegalAgreementModal
              brokerData={gatewayStatus}
              bidCap={gatewayStatus.bid_cap}
              submitting={submitting}
              lang={lang}
              onConfirm={confirmLegalAgreement}
              onCancel={() => setShowLegalModal(false)}
            />
          )}
        </Card>
      );

    case 'no_broker':
      return (
        <Card className="border-2 border-amber-300 bg-amber-50 dark:bg-amber-950/30" data-testid="vehicle-bid-panel-no-broker">
          <CardContent className="p-4 text-amber-800 dark:text-amber-200 text-sm flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">
                {lang === 'fr'
                  ? 'Un courtier agréé est obligatoire pour enchérir sur des véhicules au Canada.'
                  : 'A licensed broker is required to bid on vehicles in Canada.'}
              </p>
              <a href="/brokers" className="underline font-semibold text-amber-900 dark:text-amber-200 inline-flex items-center gap-1 mt-1.5" data-testid="vehicle-bid-find-broker">
                {lang === 'fr' ? 'Trouver un courtier' : 'Find a Broker'} <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </CardContent>
        </Card>
      );

    case 'province_mismatch':
      return (
        <Card className="border-2 border-rose-300 bg-rose-50 dark:bg-rose-950/30" data-testid="vehicle-bid-panel-province-mismatch">
          <CardContent className="p-4 text-rose-800 dark:text-rose-200 text-sm flex items-start gap-2">
            <MapPin className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">
                {lang === 'fr'
                  ? `Votre courtier (${gatewayStatus.broker_name}) est licencié en ${gatewayStatus.broker_province} mais ce véhicule se trouve en ${gatewayStatus.listing_province}.`
                  : `Your active broker (${gatewayStatus.broker_name}) is licensed in ${gatewayStatus.broker_province} but this vehicle is located in ${gatewayStatus.listing_province}.`}
              </p>
              <a
                href={`/brokers?province=${gatewayStatus.listing_province}`}
                className="underline font-semibold text-rose-900 dark:text-rose-200 inline-flex items-center gap-1 mt-1.5"
                data-testid="vehicle-bid-find-province-broker"
              >
                {lang === 'fr' ? `Trouver un courtier en ${gatewayStatus.listing_province}` : `Find a broker in ${gatewayStatus.listing_province}`}
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </CardContent>
        </Card>
      );

    case 'no_deposit':
      return (
        <Card className="border-2 border-amber-300 bg-amber-50 dark:bg-amber-950/30" data-testid="vehicle-bid-panel-no-deposit">
          <CardContent className="p-4 text-amber-800 dark:text-amber-200 text-sm flex items-start gap-2">
            <Lock className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">
                {lang === 'fr'
                  ? 'Un dépôt remboursable de 500 $ est requis avant de pouvoir placer une enchère sur un véhicule.'
                  : 'A $500 refundable security deposit is required before placing a vehicle bid.'}
              </p>
              <a href="/account?tab=broker" className="underline font-semibold text-amber-900 dark:text-amber-200 inline-flex items-center gap-1 mt-1.5" data-testid="vehicle-bid-authorize-deposit">
                {lang === 'fr' ? 'Autoriser le dépôt' : 'Authorize Deposit'} <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </CardContent>
        </Card>
      );

    case 'relationship_pending':
      return (
        <Card className="border-2 border-blue-300 bg-blue-50 dark:bg-blue-950/30" data-testid="vehicle-bid-panel-pending">
          <CardContent className="p-4 text-blue-800 dark:text-blue-200 text-sm flex items-start gap-2">
            <Hourglass className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <p>
              {lang === 'fr'
                ? 'Votre partenariat avec le courtier est en attente d\'approbation. Vous pourrez enchérir dès qu\'il accepte votre demande.'
                : 'Your broker partnership is pending approval. You can place bids once your broker accepts your request.'}
            </p>
          </CardContent>
        </Card>
      );

    case 'error':
      return (
        <Card className="border-2 border-rose-300 bg-rose-50" data-testid="vehicle-bid-panel-error">
          <CardContent className="p-4 text-rose-800 text-sm flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <p>{gatewayStatus.message || 'Compliance gateway failed to load.'}</p>
          </CardContent>
        </Card>
      );

    default:
      return null;
  }
}

// ── Legal Agreement Modal ──────────────────────────────────────────────
function LegalAgreementModal({ brokerData, bidCap, submitting, onConfirm, onCancel, lang }) {
  const [ack, setAck] = useState(false);
  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4"
      onClick={onCancel}
      data-testid="legal-agreement-modal"
      role="dialog"
      aria-modal="true"
    >
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-xl max-w-md w-full overflow-hidden border border-slate-100 dark:border-slate-700" onClick={(e) => e.stopPropagation()}>
        <div className="p-5 border-b border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 flex items-center justify-between gap-2">
          <h3 className="text-md font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-blue-600" />
            {lang === 'fr' ? 'Avant d\'enchérir — Avis juridique important' : 'Before You Bid — Important Legal Notice'}
          </h3>
          <button onClick={onCancel} className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700" data-testid="legal-modal-close">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5 space-y-4 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
          <p>
            {lang === 'fr' ? 'En plaçant cette enchère, vous autorisez ' : 'By placing this bid, you authorize '}
            <strong>{brokerData.broker_name}</strong>
            {lang === 'fr'
              ? ` à exécuter cette enchère instantanément sous leur licence ${brokerData.broker_registry} et leur pleine autorité légale.`
              : ` to execute this bid instantly under their ${brokerData.broker_registry} dealer license and full legal authority.`}
          </p>
          <p>
            <strong>{brokerData.broker_name}</strong>
            {lang === 'fr'
              ? ' devient l\'enchérisseur légal de référence. Vous restez financièrement responsable du paiement si cette enchère est gagnante.'
              : ' becomes the legal bidder of record. You remain financially responsible for payment if this bid wins.'}
          </p>
          <div className="bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 p-3 rounded-lg font-medium text-slate-800 dark:text-slate-200">
            {lang === 'fr' ? 'Votre plafond d\'enchère pré-autorisé : ' : 'Your pre-authorized bid cap: '}
            <span className="text-blue-700 dark:text-cyan-300 font-bold" data-testid="legal-modal-bidcap">
              {bidCap ? _fmt(bidCap) : (lang === 'fr' ? 'Aucun plafond' : 'No cap set')}
            </span>
          </div>
          <label className="flex items-start gap-3 mt-2 text-xs font-medium cursor-pointer text-slate-700 dark:text-slate-300">
            <input
              type="checkbox"
              checked={ack}
              onChange={(e) => setAck(e.target.checked)}
              className="mt-0.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-4 w-4"
              data-testid="legal-modal-checkbox"
            />
            <span>
              {lang === 'fr'
                ? 'Je comprends et autorise cette enchère à être placée via le routage système-procuration.'
                : 'I understand and authorize this bid to be placed via proxy system routing.'}
            </span>
          </label>
        </div>
        <div className="p-4 border-t border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={submitting}
            className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-700 text-sm font-medium disabled:opacity-50"
            data-testid="legal-modal-cancel"
          >
            {lang === 'fr' ? 'Annuler' : 'Cancel'}
          </button>
          <button
            onClick={() => { if (ack) onConfirm(); }}
            disabled={!ack || submitting}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
            data-testid="legal-modal-confirm"
          >
            {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {lang === 'fr' ? 'Confirmer et placer l\'enchère' : 'Confirm & Place Bid'}
          </button>
        </div>
      </div>
    </div>
  );
}
