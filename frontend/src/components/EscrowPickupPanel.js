import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import API_BASE from '../config';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { toast } from 'sonner';
import {
  Shield, Lock, CheckCircle2, Clock, AlertTriangle,
  Key, Send, Loader2, Package, DollarSign, XCircle,
  CreditCard, Truck, UserCheck, ArrowRight
} from 'lucide-react';

const API = API_BASE;

const STATUS_CONFIG = {
  held: { label_en: 'Funds Held', label_fr: 'Fonds détenus', color: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300', icon: Lock },
  released: { label_en: 'Released', label_fr: 'Libérés', color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300', icon: CheckCircle2 },
  auto_released: { label_en: 'Auto-Released', label_fr: 'Auto-libérés', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300', icon: Clock },
  disputed: { label_en: 'Disputed', label_fr: 'En litige', color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300', icon: AlertTriangle },
  refunded: { label_en: 'Refunded', label_fr: 'Remboursé', color: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300', icon: XCircle },
};

const timeRemaining = (expiresAt) => {
  if (!expiresAt) return null;
  const exp = new Date(expiresAt);
  const diff = exp - Date.now();
  if (diff <= 0) return null;
  const hrs = Math.floor(diff / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  return `${hrs}h ${mins}m`;
};

// ──────────── BUYER TIMELINE ────────────
const BuyerTimeline = ({ escrow, fr }) => {
  const steps = [
    { id: 'payment', icon: CreditCard, label_en: 'Payment Received', label_fr: 'Paiement reçu', done: true, time: escrow.created_at },
    { id: 'escrow', icon: Lock, label_en: 'Escrow Created', label_fr: 'Séquestre créé', done: true, time: escrow.created_at },
    { id: 'code', icon: Key, label_en: 'Pickup Code Issued', label_fr: 'Code de retrait émis', done: true, time: escrow.created_at },
    { id: 'pickup', icon: Truck, label_en: 'Pickup Meeting', label_fr: 'Rencontre de retrait', done: !!escrow.pickup_confirmed_at || escrow.escrow_status === 'released', time: escrow.pickup_confirmed_at },
    { id: 'released', icon: CheckCircle2, label_en: 'Funds Released', label_fr: 'Fonds libérés', done: ['released', 'auto_released'].includes(escrow.escrow_status), time: escrow.funds_released_at },
  ];

  return (
    <div className="flex items-center gap-1 overflow-x-auto py-3" data-testid="buyer-timeline">
      {steps.map((step, i) => {
        const Icon = step.icon;
        return (
          <React.Fragment key={step.id}>
            <div className={`flex flex-col items-center min-w-[80px] ${step.done ? 'text-green-600' : 'text-slate-300 dark:text-slate-600'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${step.done ? 'bg-green-100 dark:bg-green-900/40' : 'bg-slate-100 dark:bg-slate-800'}`}>
                <Icon className="h-4 w-4" />
              </div>
              <p className="text-[10px] mt-1 text-center leading-tight font-medium">{fr ? step.label_fr : step.label_en}</p>
              {step.time && <p className="text-[9px] text-muted-foreground">{new Date(step.time).toLocaleDateString(fr ? 'fr-CA' : 'en-CA', { month: 'short', day: 'numeric' })}</p>}
            </div>
            {i < steps.length - 1 && <ArrowRight className={`h-3 w-3 flex-shrink-0 ${step.done ? 'text-green-400' : 'text-slate-200 dark:text-slate-700'}`} />}
          </React.Fragment>
        );
      })}
    </div>
  );
};

// ──────────── SELLER VIEW ────────────
export function SellerEscrowPanel() {
  const { i18n } = useTranslation();
  const { token } = useAuth();
  const fr = i18n.language?.startsWith('fr');
  const [escrows, setEscrows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [codeInputs, setCodeInputs] = useState({});
  const [submitting, setSubmitting] = useState({});

  const fetchEscrows = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/escrow/seller/status`, { headers: { Authorization: `Bearer ${token}` } });
      setEscrows(res.data);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchEscrows(); }, [fetchEscrows]);

  const handleConfirmPickup = async (auctionId) => {
    // iter455 — Accept the canonical BVX-XXXXXXXX code (or a legacy 6-char
    // code) with any casing / hyphens / spaces. Normalize before sending
    // so the backend receives the exact same string in every case.
    const raw = codeInputs[auctionId] || '';
    const normalized = raw.toUpperCase().replace(/[^A-Z0-9]/g, '');
    if (normalized.length < 6) {
      toast.error(fr
        ? 'Entrez le code complet figurant sur le reçu de l\u2019acheteur (ex. BVX-XXXXXXXX).'
        : 'Enter the full pickup code from the buyer\u2019s receipt (e.g. BVX-XXXXXXXX).');
      return;
    }
    // If the buyer's code has the BVX prefix, restore the canonical
    // hyphen so the backend audit trail records the exact-format value.
    const code = normalized.startsWith('BVX') && normalized.length === 11
      ? `BVX-${normalized.slice(3)}`
      : normalized;
    setSubmitting(prev => ({ ...prev, [auctionId]: true }));
    try {
      const res = await axios.post(`${API}/escrow/seller/confirm-pickup`, { auction_id: auctionId, code }, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(fr ? res.data.message_fr : res.data.message_en);
      fetchEscrows();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'object' ? (fr ? detail.message_fr : detail.message_en) : detail || 'Error');
    } finally { setSubmitting(prev => ({ ...prev, [auctionId]: false })); }
  };

  if (loading) return <div className="text-center py-8"><Loader2 className="h-5 w-5 animate-spin mx-auto text-muted-foreground" /></div>;

  if (escrows.length === 0) {
    return (
      <Card data-testid="seller-escrow-empty">
        <CardContent className="py-12 text-center">
          <Shield className="h-10 w-10 text-slate-300 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">{fr ? 'Aucune transaction de dépôt fiduciaire pour le moment.' : 'No escrow transactions yet.'}</p>
          <p className="text-xs text-muted-foreground mt-1">{fr ? 'Quand un acheteur paie pour votre article, les fonds seront détenus ici.' : 'When a buyer pays for your item, funds will be held here until pickup confirmation.'}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4" data-testid="seller-escrow-panel">
      {escrows.map(escrow => {
        const config = STATUS_CONFIG[escrow.escrow_status] || STATUS_CONFIG.held;
        const StatusIcon = config.icon;
        const remaining = escrow.escrow_status === 'held' ? timeRemaining(escrow.pickup_code_expires_at) : null;
        const isHeld = escrow.escrow_status === 'held';
        const isDisputed = escrow.escrow_status === 'disputed';
        const isSubmitting = submitting[escrow.auction_id];

        return (
          <Card key={escrow.auction_id} className={`overflow-hidden ${isDisputed ? 'border-red-400 dark:border-red-600' : ''}`} data-testid={`escrow-card-${escrow.auction_id}`}>
            <CardContent className="p-5">
              {/* Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-slate-100 dark:bg-slate-800 rounded-lg"><Package className="h-5 w-5 text-slate-600 dark:text-slate-400" /></div>
                  <div>
                    <p className="text-sm font-semibold">{fr ? 'Enchère' : 'Auction'} #{escrow.auction_id?.slice(0, 8)}</p>
                    <p className="text-xs text-muted-foreground">{new Date(escrow.created_at).toLocaleDateString(fr ? 'fr-CA' : 'en-CA', { month: 'short', day: 'numeric', year: 'numeric' })}</p>
                  </div>
                </div>
                <Badge className={config.color} data-testid={`escrow-status-${escrow.auction_id}`}><StatusIcon className="h-3 w-3 mr-1" />{fr ? config.label_fr : config.label_en}</Badge>
              </div>

              {/* Amounts */}
              <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
                <div><p className="text-xs text-muted-foreground">{fr ? 'Montant total' : 'Total Amount'}</p><p className="font-semibold">${((escrow.total_charged_cents || 0) / 100).toFixed(2)} CAD</p></div>
                <div><p className="text-xs text-muted-foreground">{fr ? 'Votre paiement' : 'Your Payout'}</p><p className="font-semibold text-green-600">${(((escrow.total_charged_cents || 0) - (escrow.application_fee_cents || 0)) / 100).toFixed(2)} CAD</p></div>
              </div>

              {/* HELD: Pickup Code Entry */}
              {isHeld && (
                <div className="border-t pt-4 mt-2" data-testid={`pickup-entry-${escrow.auction_id}`}>
                  <div className="flex items-center gap-2 mb-3">
                    <Key className="h-4 w-4 text-amber-500" />
                    <p className="text-sm font-medium">{fr ? "Entrez le code de retrait complet de l'acheteur (ex. BVX-XXXXXXXX)" : "Enter the buyer's full pickup code (e.g. BVX-XXXXXXXX)"}</p>
                    {remaining && <Badge variant="outline" className="text-xs ml-auto"><Clock className="h-3 w-3 mr-1" />{remaining} {fr ? 'restant' : 'left'}</Badge>}
                  </div>
                  <div className="flex gap-2">
                    <Input
                      value={codeInputs[escrow.auction_id] || ''}
                      onChange={e => setCodeInputs(prev => ({
                        ...prev,
                        // iter455 — Accept BVX-XXXXXXXX and legacy 6-char.
                        // Uppercase everything, keep letters, digits, and
                        // one hyphen. Cap length at 20 to defensively
                        // absorb pasted whitespace / stray characters.
                        [escrow.auction_id]: e.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, '').slice(0, 20),
                      }))}
                      placeholder="BVX-XXXXXXXX"
                      maxLength={20}
                      className="font-mono text-lg tracking-[0.15em] text-center uppercase w-64"
                      disabled={isSubmitting}
                      data-testid={`pickup-code-input-${escrow.auction_id}`}
                    />
                    <Button
                      onClick={() => handleConfirmPickup(escrow.auction_id)}
                      disabled={isSubmitting || (codeInputs[escrow.auction_id] || '').replace(/[^A-Z0-9]/gi, '').length < 6}
                      className="gap-2"
                      data-testid={`confirm-pickup-btn-${escrow.auction_id}`}
                    >
                      {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}{fr ? 'Confirmer' : 'Confirm'}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">{fr ? "Demandez à l'acheteur son code de retrait complet (ex. BVX-XXXXXXXX) et collez-le ici pour libérer vos fonds. La casse, les tirets et les espaces sont ignorés." : "Ask the buyer for their full pickup code (e.g. BVX-XXXXXXXX) and paste it here to release your funds. Case, hyphens, and spaces are ignored."}</p>
                </div>
              )}

              {/* DISPUTED: Red block - disable everything */}
              {isDisputed && (
                <div className="border-t pt-4 mt-2 bg-red-50 dark:bg-red-950/20 -mx-5 -mb-5 px-5 pb-5 rounded-b-lg" data-testid={`dispute-notice-seller-${escrow.auction_id}`}>
                  <div className="flex items-center gap-2 text-red-700 dark:text-red-400">
                    <AlertTriangle className="h-5 w-5" />
                    <p className="text-sm font-semibold">{fr ? 'Cet escrow est en litige. Les fonds sont temporairement bloqués.' : 'This escrow is under dispute. Funds are temporarily locked.'}</p>
                  </div>
                  <p className="text-xs text-red-600 dark:text-red-400 mt-1">{fr ? 'L\'équipe BidVex examine ce dossier. Aucune action n\'est possible pendant la résolution.' : 'The BidVex team is reviewing this case. No actions are possible during resolution.'}</p>
                </div>
              )}

              {/* RELEASED */}
              {escrow.escrow_status === 'released' && (
                <div className="border-t pt-3 mt-2 flex items-center gap-2 text-green-600"><CheckCircle2 className="h-4 w-4" /><p className="text-sm font-medium">{fr ? 'Fonds libérés sur votre compte' : 'Funds released to your account'}{escrow.funds_released_at && ` — ${new Date(escrow.funds_released_at).toLocaleString(fr ? 'fr-CA' : 'en-CA')}`}</p></div>
              )}

              {/* AUTO-RELEASED */}
              {escrow.escrow_status === 'auto_released' && (
                <div className="border-t pt-3 mt-2 flex items-center gap-2 text-blue-600"><Clock className="h-4 w-4" /><p className="text-sm">{fr ? 'Fonds auto-libérés après 48 heures' : 'Funds auto-released after 48 hours'}</p></div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

// ──────────── BUYER VIEW ────────────
export function BuyerEscrowPanel() {
  const { i18n } = useTranslation();
  const { token } = useAuth();
  const fr = i18n.language?.startsWith('fr');
  const [escrows, setEscrows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await axios.get(`${API}/escrow/buyer/status`, { headers: { Authorization: `Bearer ${token}` } });
        setEscrows(res.data);
      } catch { /* silent */ }
      finally { setLoading(false); }
    };
    fetch();
  }, [token]);

  if (loading) return <div className="text-center py-8"><Loader2 className="h-5 w-5 animate-spin mx-auto text-muted-foreground" /></div>;

  if (escrows.length === 0) {
    return (
      <Card data-testid="buyer-escrow-empty">
        <CardContent className="py-12 text-center">
          <Shield className="h-10 w-10 text-slate-300 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">{fr ? 'Aucune transaction de dépôt fiduciaire.' : 'No escrow transactions yet.'}</p>
          <p className="text-xs text-muted-foreground mt-1">{fr ? 'Quand vous gagnez une enchère, vos fonds seront détenus en dépôt.' : 'When you win an auction, your funds will be held in escrow until pickup.'}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4" data-testid="buyer-escrow-panel">
      {escrows.map(escrow => {
        const config = STATUS_CONFIG[escrow.escrow_status] || STATUS_CONFIG.held;
        const StatusIcon = config.icon;
        const isDisputed = escrow.escrow_status === 'disputed';

        return (
          <Card key={escrow.auction_id} className={isDisputed ? 'border-red-400 dark:border-red-600' : ''} data-testid={`buyer-escrow-${escrow.auction_id}`}>
            <CardContent className="p-5">
              {/* Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-slate-100 dark:bg-slate-800 rounded-lg"><DollarSign className="h-5 w-5 text-slate-600 dark:text-slate-400" /></div>
                  <div>
                    <p className="text-sm font-semibold">{fr ? 'Enchère' : 'Auction'} #{escrow.auction_id?.slice(0, 8)}</p>
                    <p className="text-xs text-muted-foreground">{new Date(escrow.created_at).toLocaleDateString(fr ? 'fr-CA' : 'en-CA', { month: 'short', day: 'numeric', year: 'numeric' })}</p>
                  </div>
                </div>
                <Badge className={config.color}><StatusIcon className="h-3 w-3 mr-1" />{fr ? config.label_fr : config.label_en}</Badge>
              </div>

              {/* Amounts */}
              <div className="grid grid-cols-2 gap-3 mb-3 text-sm">
                <div><p className="text-xs text-muted-foreground">{fr ? 'Montant payé' : 'Amount Paid'}</p><p className="font-semibold">${((escrow.total_charged_cents || 0) / 100).toFixed(2)} CAD</p></div>
                <div><p className="text-xs text-muted-foreground">{fr ? 'Statut' : 'Status'}</p><p className="font-medium">{fr ? config.label_fr : config.label_en}</p></div>
              </div>

              {/* Timeline */}
              <BuyerTimeline escrow={escrow} fr={fr} />

              {/* HELD: Instructions */}
              {escrow.escrow_status === 'held' && (
                <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-4 mt-3" data-testid="buyer-escrow-instructions">
                  <div className="flex items-center gap-2 mb-2"><Key className="h-4 w-4 text-amber-600" /><p className="text-sm font-semibold text-amber-800 dark:text-amber-300">{fr ? 'Votre code de retrait' : 'Your Pickup Code'}</p></div>
                  <p className="text-xs text-amber-700 dark:text-amber-400">{fr ? 'Votre code a été envoyé à votre adresse courriel. Présentez-le au vendeur lors du retrait.' : 'Your code was sent to your email. Show it to the seller at pickup to release the funds.'}</p>
                </div>
              )}

              {/* DISPUTED: Red banner - disable everything */}
              {isDisputed && (
                <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mt-3" data-testid={`dispute-notice-buyer-${escrow.auction_id}`}>
                  <div className="flex items-center gap-2 text-red-700 dark:text-red-400">
                    <AlertTriangle className="h-5 w-5" />
                    <p className="text-sm font-semibold">{fr ? 'Cet escrow est actuellement en litige.' : 'This escrow is currently under dispute.'}</p>
                  </div>
                  <p className="text-xs text-red-600 dark:text-red-400 mt-1">{fr ? 'Notre équipe examine votre dossier. Les fonds sont temporairement bloqués.' : 'Our team is reviewing your case. Funds are temporarily locked.'}</p>
                </div>
              )}

              {/* RELEASED */}
              {escrow.escrow_status === 'released' && (
                <div className="flex items-center gap-2 text-green-600 mt-3"><CheckCircle2 className="h-4 w-4" /><p className="text-sm">{fr ? 'Transaction complétée. Le vendeur a confirmé le retrait.' : 'Transaction complete. Seller confirmed pickup.'}</p></div>
              )}

              {/* AUTO-RELEASED */}
              {escrow.escrow_status === 'auto_released' && (
                <div className="flex items-center gap-2 text-blue-600 mt-3"><Clock className="h-4 w-4" /><p className="text-sm">{fr ? 'Fonds automatiquement libérés après 48 heures.' : 'Funds automatically released after 48 hours.'}</p></div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
