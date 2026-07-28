/**
 * iter369 — Real Auto-Bid setup modal (Premium/VIP-gated).
 *
 * Two states:
 *   • Subscribed (premium / vip_elite / partner / business): renders the
 *     configuration form — max bid + strategy + Update / Disable buttons
 *     if an auto-bid is already active on the lot.
 *   • Free tier: renders the upgrade dialog with two CTAs (Upgrade to
 *     Premium / Upgrade to VIP Elite) and a "Maybe Later" secondary.
 *
 * Backed by the multi-lot auto-bid endpoints introduced in iter369:
 *   GET  /api/multi-item-listings/:auction/lots/:lot/auto-bid
 *   POST /api/multi-item-listings/:auction/lots/:lot/auto-bid
 *   DEL  /api/multi-item-listings/:auction/lots/:lot/auto-bid
 *
 * No placeholders. No stubs. Talks to the real `auto_bids` collection.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Bot, CheckCircle2, XCircle, Zap, Loader2, TrendingUp } from 'lucide-react';
import API_BASE from '../config';
import { useAuth } from '../contexts/AuthContext';
import { usePlatformTermsGate } from '../contexts/PlatformTermsGateContext';
import { formatCurrency } from '../utils/currencyFormatter';

const ELIGIBLE_TIERS = new Set(['premium', 'vip', 'vip_elite', 'partner', 'business']);

export default function AutoBidModal({
  open,
  onOpenChange,
  auctionId,
  lot,               // full lot object { lot_number, title, current_price, ... }
  incrementInfo,     // { increment_option, schedule[], fixed_increment }
  onSaved,           // callback fired after save/disable so parent can refresh
}) {
  const { i18n, t } = useTranslation();
  const isFR = i18n.language?.startsWith('fr');
  const { user, token } = useAuth();
  const { runWithTermsGate } = usePlatformTermsGate();
  const navigate = useNavigate();

  const tier = (user?.subscription_tier || 'standard').toLowerCase();
  const eligible = ELIGIBLE_TIERS.has(tier);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [existing, setExisting] = useState(null);   // active auto-bid row from server
  const [maxBid, setMaxBid] = useState('');
  const [strategy, setStrategy] = useState('min_to_lead');
  const [err, setErr] = useState('');

  const currentPrice = Number(lot?.current_price ?? lot?.starting_price ?? 0);
  // Derive the minimum increment from the same server-side schedule the
  // BidIncrementTable + QuickBid pills use. Never hardcoded.
  const getIncrement = (bid) => {
    if (!incrementInfo) return 5;
    if (incrementInfo.increment_option === 'fixed' && incrementInfo.fixed_increment) {
      return Number(incrementInfo.fixed_increment);
    }
    const sched = incrementInfo.schedule || [];
    for (const row of sched) {
      const lo = Number(row.min ?? 0);
      const hi = row.max == null ? Infinity : Number(row.max);
      if (bid >= lo && bid < hi) return Number(row.step);
    }
    return sched.length ? Number(sched[sched.length - 1].step) : 5;
  };
  const step = getIncrement(currentPrice);
  const minValid = currentPrice + step;
  const strategyLabel = (incrementInfo?.increment_option || 'tiered');

  useEffect(() => {
    if (!open || !auctionId || !lot) return;
    let cancelled = false;
    setErr('');
    if (!eligible) return;   // skip fetch on free tier — upgrade UI takes over.
    setLoading(true);
    axios
      .get(`${API_BASE}/multi-item-listings/${auctionId}/lots/${lot.lot_number}/auto-bid`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        timeout: 8000,
      })
      .then((res) => {
        if (cancelled) return;
        const ab = res.data?.auto_bid;
        setExisting(ab);
        setMaxBid(ab?.max_bid != null ? String(ab.max_bid) : String(minValid));
        setStrategy(ab?.strategy || 'min_to_lead');
      })
      .catch((e) => { if (!cancelled) setErr(e?.response?.data?.detail || 'Unable to load auto-bid state'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, auctionId, lot?.lot_number, eligible, minValid, token]);

  const handleSave = async () => {
    setErr('');
    const amount = Number(maxBid);
    if (!amount || amount < minValid) {
      setErr(isFR
        ? `L'enchère maximum doit être d'au moins ${formatCurrency(minValid)}.`
        : `Max bid must be at least ${formatCurrency(minValid)}.`);
      return;
    }
    setSaving(true);
    try {
      await runWithTermsGate(() => axios.post(
        `${API_BASE}/multi-item-listings/${auctionId}/lots/${lot.lot_number}/auto-bid`,
        { max_bid: amount, strategy },
        { headers: { Authorization: `Bearer ${token}` } },
      ));
      toast.success(isFR ? 'Auto-enchère enregistrée' : 'Auto-Bid saved');
      onSaved && onSaved();
      onOpenChange(false);
    } catch (e) {
      // iter404 — silent no-op when the inline T&C modal is cancelled.
      if (e?.termsGateCancelled) { setSaving(false); return; }
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : (detail?.message || 'Failed to save Auto-Bid');
      setErr(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleDisable = async () => {
    setSaving(true);
    try {
      await axios.delete(
        `${API_BASE}/multi-item-listings/${auctionId}/lots/${lot.lot_number}/auto-bid`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(isFR ? 'Auto-enchère désactivée' : 'Auto-Bid disabled');
      onSaved && onSaved();
      onOpenChange(false);
    } catch (e) {
      setErr(e?.response?.data?.detail || 'Failed to disable Auto-Bid');
    } finally {
      setSaving(false);
    }
  };

  // ---------- Render ----------
  // iter369 fix — keep <Dialog> mounted even when `lot` is null so Radix
  // registers open-state transitions correctly (fixes grid-card open bug).
  const title = isFR ? "Configurer l'auto-enchère" : 'Setup Auto-Bid';

  return (
    <Dialog open={open && !!lot} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="auto-bid-modal">
        {!lot ? null : (
        <>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-cyan-600" />
            {eligible ? title : (isFR ? 'Auto-enchère — Premium' : 'Auto-Bid — Premium Feature')}
          </DialogTitle>
        </DialogHeader>

        {/* Upgrade gate: free-tier users see this dialog instead of the form. */}
        {!eligible && (
          <div className="space-y-4" data-testid="auto-bid-upgrade">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              {isFR
                ? "Ne manquez plus une enchère quand vous êtes absent."
                : "Never miss an auction while you're away."}
            </p>
            <ul className="space-y-2 text-sm">
              {[
                isFR ? 'Enchère automatique jusqu\'à votre maximum' : 'Automatic bidding up to your maximum',
                isFR ? 'Enchérissez pendant que vous dormez' : 'Compete while you sleep',
                isFR ? 'Ne payez jamais plus — votre max est protégé' : 'Never overpay — maximum bid protected',
                isFR ? 'Notifications de surenchère instantanées' : 'Instant outbid notifications',
              ].map((line, i) => (
                <li key={i} className="flex items-start gap-2 text-slate-700 dark:text-slate-300">
                  <CheckCircle2 className="h-4 w-4 mt-0.5 text-emerald-500 flex-shrink-0" />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
            <DialogFooter className="gap-2 sm:gap-2 flex-col sm:flex-row">
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                data-testid="auto-bid-maybe-later"
              >
                {isFR ? 'Plus tard' : 'Maybe Later'}
              </Button>
              <Button
                className="bg-cyan-600 hover:bg-cyan-700 text-white"
                onClick={() => { onOpenChange(false); navigate('/pricing?upgrade=premium'); }}
                data-testid="auto-bid-upgrade-premium"
              >
                {isFR ? 'Passer à Premium' : 'Upgrade to Premium'}
              </Button>
              <Button
                className="bg-gradient-to-r from-amber-500 to-rose-500 text-white"
                onClick={() => { onOpenChange(false); navigate('/pricing?upgrade=vip_elite'); }}
                data-testid="auto-bid-upgrade-vip"
              >
                {isFR ? 'Passer à VIP Elite' : 'Upgrade to VIP Elite'}
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Real form: eligible tiers only */}
        {eligible && (
          <div className="space-y-4" data-testid="auto-bid-form">
            {/* Lot summary block */}
            <div className="rounded-lg bg-slate-50 dark:bg-slate-800/60 p-3 text-sm space-y-1">
              <div className="font-semibold text-slate-900 dark:text-white">
                Lot #{lot.lot_number} · {lot.title || (isFR ? 'Article' : 'Item')}
              </div>
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>{isFR ? 'Enchère courante' : 'Current bid'}</span>
                <span className="font-mono">{formatCurrency(currentPrice)}</span>
              </div>
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>{isFR ? 'Prochaine enchère valide' : 'Next valid bid'}</span>
                <span className="font-mono">{formatCurrency(minValid)}</span>
              </div>
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>{isFR ? 'Incrément' : 'Bid increment'}</span>
                <span className="font-mono">
                  {formatCurrency(step)} ({strategyLabel})
                </span>
              </div>
              {existing && (
                <div className="mt-1 pt-1 border-t border-slate-200 dark:border-slate-700">
                  <Badge variant="outline" data-testid="auto-bid-active-status">
                    {isFR ? 'Auto-enchère active' : 'Auto-Bid active'}
                    {' · '}
                    {formatCurrency(existing.max_bid)}
                  </Badge>
                </div>
              )}
            </div>

            {loading && (
              <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                <Loader2 className="h-4 w-4 animate-spin" />
                {isFR ? 'Chargement…' : 'Loading…'}
              </div>
            )}

            {!loading && (
              <>
                <div className="space-y-1.5">
                  <Label htmlFor="autobid-max" className="text-sm font-semibold">
                    {isFR ? 'Enchère maximum (CAD)' : 'Maximum Bid (CAD)'}
                  </Label>
                  <Input
                    id="autobid-max"
                    type="number"
                    step="0.01"
                    min={minValid}
                    value={maxBid}
                    onChange={(e) => setMaxBid(e.target.value)}
                    placeholder={String(minValid)}
                    data-testid="auto-bid-max-input"
                  />
                  <p className="text-[11px] text-slate-500 dark:text-slate-400">
                    {isFR
                      ? "Vous ne serez jamais facturé plus que ce montant."
                      : 'You will never be charged more than this amount.'}
                  </p>
                </div>

                <div className="space-y-2">
                  <Label className="text-sm font-semibold">{isFR ? 'Stratégie' : 'Strategy'}</Label>
                  <label className="flex items-start gap-2 cursor-pointer p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <input
                      type="radio"
                      name="strategy"
                      value="min_to_lead"
                      checked={strategy === 'min_to_lead'}
                      onChange={() => setStrategy('min_to_lead')}
                      className="mt-1"
                      data-testid="auto-bid-strategy-min"
                    />
                    <div className="flex-1 text-sm">
                      <div className="font-medium flex items-center gap-1">
                        <TrendingUp className="h-3.5 w-3.5 text-emerald-600" />
                        {isFR ? "Enchérir le minimum pour rester en tête" : 'Bid minimum to stay leading'}
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400">
                        {isFR
                          ? "Le bot n'enchérit qu'un incrément à la fois."
                          : "Bot bids one increment at a time (conservative)."}
                      </div>
                    </div>
                  </label>
                  <label className="flex items-start gap-2 cursor-pointer p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <input
                      type="radio"
                      name="strategy"
                      value="max_immediate"
                      checked={strategy === 'max_immediate'}
                      onChange={() => setStrategy('max_immediate')}
                      className="mt-1"
                      data-testid="auto-bid-strategy-max"
                    />
                    <div className="flex-1 text-sm">
                      <div className="font-medium flex items-center gap-1">
                        <Zap className="h-3.5 w-3.5 text-rose-500" />
                        {isFR ? 'Enchérir le maximum immédiatement' : 'Bid full maximum immediately'}
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400">
                        {isFR
                          ? "Le bot place tout de suite votre montant max (agressif)."
                          : 'Bot places your max amount right away (aggressive).'}
                      </div>
                    </div>
                  </label>
                </div>

                {err && (
                  <div className="flex items-center gap-2 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 px-3 py-2 text-sm text-rose-700 dark:text-rose-300" data-testid="auto-bid-error">
                    <XCircle className="h-4 w-4" />
                    {err}
                  </div>
                )}

                <DialogFooter className="gap-2 sm:gap-2 flex-col sm:flex-row">
                  <Button
                    variant="outline"
                    onClick={() => onOpenChange(false)}
                    disabled={saving}
                    data-testid="auto-bid-cancel"
                  >
                    {isFR ? 'Annuler' : 'Cancel'}
                  </Button>
                  {existing && (
                    <Button
                      variant="destructive"
                      onClick={handleDisable}
                      disabled={saving}
                      data-testid="auto-bid-disable"
                    >
                      {isFR ? 'Désactiver' : 'Disable Auto-Bid'}
                    </Button>
                  )}
                  <Button
                    className="bg-cyan-600 hover:bg-cyan-700 text-white"
                    onClick={handleSave}
                    disabled={saving}
                    data-testid="auto-bid-save"
                  >
                    {saving && <Loader2 className="h-4 w-4 animate-spin mr-1.5" />}
                    {existing
                      ? (isFR ? 'Mettre à jour' : 'Update')
                      : (isFR ? "Activer l'auto-enchère" : 'Enable Auto-Bid')}
                  </Button>
                </DialogFooter>
              </>
            )}
          </div>
        )}
        </>
        )}
      </DialogContent>
    </Dialog>
  );
}
