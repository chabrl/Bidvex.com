import API_BASE from '../../config';
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import {
  Loader2, Gavel, MapPin, Clock, ShieldCheck, AlertTriangle, Info,
  CreditCard, Banknote, Send,
} from 'lucide-react';
import StorageCountdown from './StorageCountdown';
import StorageFooterBanner from './StorageFooterBanner';
import StorageAutoBidModal from '../../components/StorageAutoBidModal';
import QuickBidButtons from '../../components/QuickBidButtons';

const API = API_BASE;

const StorageAuctionDetail = () => {
  const { id } = useParams();
  const { token } = useAuth();
  const { i18n } = useTranslation();
  const isFr = (i18n.language || '').startsWith('fr');

  const [auction, setAuction] = useState(null);
  const [history, setHistory] = useState([]);
  const [pricing, setPricing] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activePhoto, setActivePhoto] = useState(0);
  const [maxBid, setMaxBid] = useState('');
  const [submittingBid, setSubmittingBid] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [a, h, p] = await Promise.all([
        axios.get(`${API}/storage-auctions/${id}`),
        axios.get(`${API}/storage-auctions/${id}/bids`),
        axios.get(`${API}/storage-auctions/${id}/pricing?payment_method=stripe`),
      ]);
      setAuction(a.data);
      setHistory(h.data?.bids || []);
      setPricing(p.data);
    } catch (err) {
      toast.error(isFr ? 'Enchère introuvable' : 'Auction not found');
    } finally {
      setLoading(false);
    }
  }, [id, isFr]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Refresh every 15s for live bid updates
  useEffect(() => {
    const t = setInterval(fetchData, 15000);
    return () => clearInterval(t);
  }, [fetchData]);

  const handlePlaceBid = async (overrideAmount) => {
    const amt = parseFloat(overrideAmount ?? maxBid);
    if (!Number.isFinite(amt) || amt <= 0) {
      toast.error(isFr ? "Entrez une offre maximale valide" : 'Enter a valid max bid');
      return;
    }
    if (!token) {
      toast.error(isFr ? 'Connectez-vous pour enchérir' : 'Sign in to place a bid');
      return;
    }
    setSubmittingBid(true);
    try {
      const res = await axios.post(
        `${API}/storage-auctions/${id}/bid`,
        { max_bid: amt },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(
        res.data.you_are_winning
          ? (isFr ? `Vous êtes en tête à ${res.data.current_bid} $` : `You are winning at $${res.data.current_bid}`)
          : (isFr ? 'Offre placée — vous avez été surenchéri' : "Bid placed — you've been outbid by an existing proxy")
      );
      if (res.data.soft_close_extended) {
        toast.info(isFr ? 'Enchère prolongée de 10 minutes (soft close)' : 'Auction extended by 10 minutes (soft close)');
      }
      setMaxBid('');
      fetchData();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'object' ? (isFr ? detail.message_fr : detail.message_en) : (detail || 'Bid failed');
      toast.error(msg);
    } finally {
      setSubmittingBid(false);
    }
  };

  if (loading) return <div className="min-h-screen flex justify-center items-center"><Loader2 className="h-10 w-10 animate-spin text-blue-600" /></div>;
  if (!auction) return null;

  const photos = auction.photos || [];
  const minNext = (auction.current_bid || 0) + (auction.bid_increment || 10);
  const isLive = auction.live_status === 'active';
  const facility = auction.facility || {};

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-6" data-testid="storage-auction-detail">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <Link to="/storage-auctions/browse" className="text-sm text-blue-600 hover:underline">
          ← {isFr ? 'Retour aux enchères' : 'Back to auctions'}
        </Link>

        <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-6 mt-4">
          {/* LEFT — gallery + details */}
          <div className="space-y-4">
            {/* Photo gallery */}
            <Card className="overflow-hidden">
              <div className="relative bg-slate-200 dark:bg-slate-800 h-80 flex items-center justify-center">
                {photos.length > 0 ? (
                  <img src={photos[activePhoto]} alt={`Unit ${auction.unit_number}`} className="w-full h-full object-contain" />
                ) : (
                  <span className="text-7xl opacity-50">🔒</span>
                )}
              </div>
              {photos.length > 1 && (
                <div className="flex gap-2 p-3 overflow-x-auto">
                  {photos.map((p, i) => (
                    <button
                      key={i}
                      onClick={() => setActivePhoto(i)}
                      className={`w-16 h-16 rounded-md overflow-hidden border-2 shrink-0 ${i === activePhoto ? 'border-blue-600' : 'border-transparent'}`}
                    >
                      <img src={p} alt="" className="w-full h-full object-cover" />
                    </button>
                  ))}
                </div>
              )}
            </Card>

            {auction.video_url && (
              <Card className="p-4">
                <p className="font-semibold mb-2">{isFr ? 'Vidéo de l\'unité' : 'Unit video'}</p>
                <video src={auction.video_url} controls className="w-full rounded-lg" />
              </Card>
            )}

            {/* Unit details */}
            <Card className="p-5">
              <h1 className="text-2xl font-bold mb-2">
                Unit #{auction.unit_number} — {auction.unit_size}
              </h1>
              <div className="flex flex-wrap gap-2 mb-3">
                <Badge variant="outline" className="capitalize">{(auction.unit_type || '').replace(/_/g, ' ')}</Badge>
                {auction.is_lien_unit && (
                  <Badge variant="outline" className="border-amber-400 text-amber-700 bg-amber-50">
                    {isFr ? 'Sous droit de rétention' : 'Lien Unit'}
                  </Badge>
                )}
                <Badge variant="outline">📍 {auction.facility_city}, {auction.facility_province}</Badge>
              </div>
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <p><strong>EN:</strong> {auction.description_en}</p>
                <hr/>
                <p><strong>FR:</strong> {auction.description_fr}</p>
              </div>
              {auction.is_lien_unit && (
                <div className="mt-4 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/40 text-xs">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-amber-900 dark:text-amber-200 mb-1">⚠️ Lien Unit Notice / Avis d'unité sous droit de rétention</p>
                      <p className="text-amber-900 dark:text-amber-200 mb-1"><strong>EN:</strong> This unit contains the personal property of a delinquent tenant. The storage facility is solely responsible for compliance with provincial lien laws and proper tenant notification procedures. BidVex is a technology platform only and is not an auctioneer. All bids are final.</p>
                      <p className="text-amber-900 dark:text-amber-200"><strong>FR:</strong> Cette unité contient les biens personnels d'un locataire délinquant. La facilité d'entreposage est seule responsable. BidVex est une plateforme technologique uniquement et n'est pas un encanteur. Toutes les offres sont finales.</p>
                    </div>
                  </div>
                </div>
              )}
            </Card>

            {/* Facility info */}
            <Card className="p-5">
              <h3 className="font-semibold flex items-center gap-2 mb-2">
                <ShieldCheck className="h-4 w-4 text-emerald-600" />
                {facility.company_name || auction.facility_name}
                {facility.verified && (
                  <Badge className="bg-emerald-600 text-white text-[10px]">✓ {isFr ? 'Vérifiée' : 'Verified'}</Badge>
                )}
              </h3>
              <p className="text-sm text-muted-foreground flex items-center gap-1">
                <MapPin className="h-3 w-3" /> {auction.facility_city}, {auction.facility_province}
              </p>
            </Card>

            {/* Bid history */}
            <Card className="p-5">
              <h3 className="font-semibold mb-3">{isFr ? "Historique des offres" : 'Bid history'} ({history.length})</h3>
              {history.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">{isFr ? 'Aucune offre encore' : 'No bids yet'}</p>
              ) : (
                <div className="divide-y">
                  {history.slice().reverse().map((b, i) => (
                    <div key={i} className="flex justify-between text-sm py-2">
                      <span className="text-muted-foreground">{b.bidder_label}</span>
                      <span className="font-mono font-bold">${Number(b.amount).toFixed(2)}</span>
                      <span className="text-xs text-muted-foreground">{new Date(b.placed_at).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {/* RIGHT — sticky bid box */}
          <aside className="lg:sticky lg:top-4 self-start space-y-4">
            <Card className="p-5">
              {isLive ? (
                <Badge className="bg-emerald-500 text-white mb-3">
                  <span className="w-2 h-2 bg-white rounded-full animate-pulse inline-block mr-1.5" />
                  LIVE
                </Badge>
              ) : (
                <Badge variant="outline" className="mb-3">{auction.live_status?.toUpperCase()}</Badge>
              )}
              <p className="text-xs uppercase tracking-wider text-muted-foreground">{isFr ? 'Offre actuelle' : 'Current bid'}</p>
              <p className="text-4xl font-black text-blue-600 mb-1" data-testid="current-bid-display">
                ${Number(auction.current_bid || 0).toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground mb-3">
                {auction.bid_count || 0} {isFr ? 'offres' : 'bids'}
              </p>

              <div className="bg-slate-50 dark:bg-slate-900/50 rounded-lg p-3 text-center mb-4">
                <p className="text-[10px] uppercase text-muted-foreground mb-1 flex items-center justify-center gap-1">
                  <Clock className="h-3 w-3" /> {isFr ? 'Reste' : 'Time remaining'}
                </p>
                <StorageCountdown endTime={auction.end_time} />
              </div>

              {auction.soft_close_enabled && (
                <div className="text-[11px] bg-blue-50 dark:bg-blue-950/30 text-blue-800 dark:text-blue-300 p-2.5 rounded-md border border-blue-100 dark:border-blue-900/40 mb-4 flex items-start gap-1.5">
                  <Info className="h-3 w-3 mt-0.5 shrink-0" />
                  <span>{isFr ? "⏰ Une offre dans les 10 dernières minutes prolonge l'enchère de 10 minutes." : '⏰ A bid in the final 10 minutes extends the auction by 10 minutes.'}</span>
                </div>
              )}

              {isLive && (
                <>
                  {/* Quick Bid pills (iter175) — one-tap +$X / +$Y / +$Z scaled by bid_increment */}
                  <div className="mb-3">
                    <QuickBidButtons
                      currentBid={auction.current_bid || 0}
                      bidIncrement={auction.bid_increment || 10}
                      loading={submittingBid}
                      onConfirm={async (amount) => {
                        setMaxBid(String(amount));
                        await new Promise(r => setTimeout(r, 30));
                        await handlePlaceBid(amount);
                      }}
                      testidPrefix="storage-quick-bid"
                    />
                  </div>

                  <label className="text-xs font-medium mb-1 block">
                    {isFr ? 'Votre offre · Your bid' : 'Your bid · Votre offre'} (≥ ${minNext.toFixed(2)})
                  </label>
                  <div className="flex gap-2">
                    <Input
                      type="number"
                      inputMode="decimal"
                      min={minNext}
                      step={auction.bid_increment || 10}
                      value={maxBid}
                      onChange={e => setMaxBid(e.target.value)}
                      placeholder={`${minNext.toFixed(2)}`}
                      data-testid="max-bid-input"
                    />
                    <Button onClick={handlePlaceBid} disabled={submittingBid} className="bg-blue-600 hover:bg-blue-700 text-white" data-testid="place-bid-btn">
                      {submittingBid ? <Loader2 className="h-4 w-4 animate-spin" /> : <><Gavel className="h-4 w-4 mr-1" /> {isFr ? 'Enchérir · Bid' : 'Bid · Enchérir'}</>}
                    </Button>
                  </div>

                  {/* Setup Auto-Bid (mirrors marketplace) — purple Premium badge gates non-premium tiers */}
                  <div className="mt-3">
                    <StorageAutoBidModal
                      auctionId={auction.id}
                      currentBid={auction.current_bid || 0}
                      bidIncrement={auction.bid_increment || 10}
                      onActivated={() => { setMaxBid(''); fetchData(); }}
                    />
                  </div>
                </>
              )}
            </Card>

            {/* No buyer fees notice */}
            <Card className="p-4 bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 dark:border-emerald-900/40">
              <p className="text-sm font-bold text-emerald-800 dark:text-emerald-200 mb-1">
                ✅ {isFr ? 'Aucuns frais acheteur' : 'No Buyer Fees'}
              </p>
              <p className="text-xs text-emerald-800 dark:text-emerald-300">
                {isFr
                  ? "BidVex ne facture AUCUNS frais. Vous ne payez que le montant de l'offre gagnante à la facilité."
                  : 'BidVex charges ZERO fees. You only pay the winning bid amount to the facility.'}
              </p>
            </Card>

            {/* Payment methods */}
            <Card className="p-4">
              <p className="text-xs font-semibold mb-2 uppercase tracking-wider">{isFr ? 'Modes de paiement acceptés' : 'Payment methods accepted'}</p>
              <div className="flex flex-wrap gap-2 text-xs">
                {(auction.payment_methods_accepted || []).includes('stripe') && (
                  <Badge variant="outline"><CreditCard className="h-3 w-3 mr-1" />Stripe</Badge>
                )}
                {(auction.payment_methods_accepted || []).includes('cash') && (
                  <Badge variant="outline"><Banknote className="h-3 w-3 mr-1" />{isFr ? 'Comptant' : 'Cash'}</Badge>
                )}
                {(auction.payment_methods_accepted || []).includes('etransfer') && (
                  <Badge variant="outline"><Send className="h-3 w-3 mr-1" />E-Transfer</Badge>
                )}
              </div>
              {pricing && (
                <p className="text-[10px] text-muted-foreground mt-2">
                  {isFr ? 'Si Stripe : frais de traitement (~2,9% + 0,30 $) en plus.' : 'If Stripe: ~2.9% + $0.30 processing fee added on top.'}
                </p>
              )}
            </Card>

            <div className="text-[10px] text-center text-muted-foreground">
              <Link to="/storage-auctions/terms" className="underline">{isFr ? 'Conditions' : 'Terms'}</Link>
              {' • '}
              <Link to="/storage-auctions/how-it-works" className="underline">{isFr ? 'Comment ça marche' : 'How it works'}</Link>
            </div>
          </aside>
        </div>
      </div>
      <StorageFooterBanner />
    </div>
  );
};

export default StorageAuctionDetail;
