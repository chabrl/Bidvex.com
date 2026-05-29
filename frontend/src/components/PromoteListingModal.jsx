/**
 * iter239 Mission 5 — Promote Listing Modal
 *
 * Seller-facing dialog that posts to `POST /api/listings/{id}/promote` and
 * activates featured/promoted status across the selected sections. Phase 1
 * is FREE (no Stripe charge — backend simply flips the promotion fields);
 * Phase 2 will add Stripe Checkout per `promotion_tier`.
 */
import React, { useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Sparkles, Loader2 } from 'lucide-react';
import API_BASE from '../config';
import { useAuth } from '../contexts/AuthContext';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Button } from './ui/button';

const ALL_SECTIONS = [
  { id: 'marketplace', label_en: 'Marketplace', label_fr: 'Marketplace' },
  { id: 'lots',        label_en: 'Lots Auction', label_fr: 'Enchères par lots' },
  { id: 'storage',     label_en: 'Storage Auctions', label_fr: "Entreposage" },
  { id: 'vehicles',    label_en: 'Vehicle Auctions', label_fr: 'Véhicules' },
  { id: 'homepage',    label_en: 'Homepage', label_fr: "Page d'accueil" },
];

const TIERS = [
  { id: 'standard', label_en: 'Standard',  label_fr: 'Standard',  blurb_en: 'Featured tag + sort boost', blurb_fr: 'Étiquette + boost de tri' },
  { id: 'featured', label_en: 'Featured',  label_fr: 'En vedette', blurb_en: 'Inline grid placement + carousel', blurb_fr: 'Carrousel + injection dans la grille' },
  { id: 'top',      label_en: 'Top Pick',  label_fr: 'Top pick',  blurb_en: 'Top carousel slot + all sections', blurb_fr: 'Premier slot + toutes sections' },
];

const DURATIONS = [3, 7, 14, 30];

const PromoteListingModal = ({ open, onOpenChange, listing, onSuccess }) => {
  const { i18n } = useTranslation();
  const { token } = useAuth();
  const isFr = (i18n.language || 'en').startsWith('fr');
  const t = (en, fr) => (isFr ? fr : en);

  const [sections, setSections] = useState(['marketplace']);
  const [duration, setDuration] = useState(7);
  const [tier, setTier] = useState('featured');
  const [submitting, setSubmitting] = useState(false);

  const toggleSection = (id) => {
    setSections((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    );
  };

  const handlePromote = async () => {
    if (!listing?.id) return;
    if (sections.length === 0) {
      toast.error(t('Select at least one section', 'Sélectionnez au moins une section'));
      return;
    }
    setSubmitting(true);
    try {
      const res = await axios.post(
        `${API_BASE}/listings/${listing.id}/promote`,
        { sections, duration_days: duration, tier },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(
        t(
          `Listing promoted until ${new Date(res.data.promotion_expires_at).toLocaleDateString()}`,
          `Annonce promue jusqu'au ${new Date(res.data.promotion_expires_at).toLocaleDateString()}`
        )
      );
      onSuccess?.(res.data);
      onOpenChange(false);
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || 'Failed to promote';
      toast.error(typeof msg === 'string' ? msg : 'Promotion failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg" data-testid="promote-listing-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-amber-500" />
            {t('Promote this listing', 'Promouvoir cette annonce')}
          </DialogTitle>
          <DialogDescription>
            {t(
              'Boost visibility across the BidVex network. Activates instantly — no payment required during early access.',
              'Augmentez la visibilité sur le réseau BidVex. Activation immédiate — sans paiement durant l’accès anticipé.'
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {/* Tier picker */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
              {t('Promotion tier', 'Forfait')}
            </label>
            <div className="grid grid-cols-3 gap-2">
              {TIERS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => setTier(opt.id)}
                  className={`p-2 rounded-lg border text-left transition-all ${
                    tier === opt.id
                      ? 'border-amber-500 bg-amber-50 ring-2 ring-amber-200'
                      : 'border-slate-200 bg-white hover:border-amber-300'
                  }`}
                  data-testid={`promote-tier-${opt.id}`}
                >
                  <div className="text-sm font-bold text-slate-900">
                    {isFr ? opt.label_fr : opt.label_en}
                  </div>
                  <div className="text-[11px] text-slate-500">
                    {isFr ? opt.blurb_fr : opt.blurb_en}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Sections */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
              {t('Sections to feature on', 'Sections à mettre en avant')}
            </label>
            <div className="flex flex-wrap gap-2">
              {ALL_SECTIONS.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => toggleSection(s.id)}
                  className={`px-3 py-1.5 rounded-full text-xs font-semibold border-[1.5px] transition-all ${
                    sections.includes(s.id)
                      ? 'bg-[#2d6be4] text-white border-[#2d6be4]'
                      : 'bg-white text-slate-700 border-slate-200 hover:border-blue-300'
                  }`}
                  data-testid={`promote-section-${s.id}`}
                >
                  {isFr ? s.label_fr : s.label_en}
                </button>
              ))}
            </div>
          </div>

          {/* Duration */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
              {t('Duration (days)', 'Durée (jours)')}
            </label>
            <div className="flex gap-2">
              {DURATIONS.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDuration(d)}
                  className={`flex-1 py-2 rounded-md border-[1.5px] font-semibold text-sm transition-all ${
                    duration === d
                      ? 'bg-emerald-50 border-emerald-500 text-emerald-700'
                      : 'bg-white border-slate-200 text-slate-700 hover:border-emerald-300'
                  }`}
                  data-testid={`promote-duration-${d}`}
                >
                  {d}d
                </button>
              ))}
            </div>
          </div>

          {/* Summary */}
          <div className="rounded-lg bg-blue-50 border border-blue-200 p-3 text-xs text-blue-900" data-testid="promote-summary">
            <p>
              <strong>{listing?.title || t('This listing', 'Cette annonce')}</strong>{' '}
              {t('will be promoted as', 'sera promu en tant que')}{' '}
              <strong>{(TIERS.find((x) => x.id === tier) || TIERS[1])[isFr ? 'label_fr' : 'label_en']}</strong>{' '}
              {t('for', 'pendant')} <strong>{duration}d</strong> {t('across', 'sur')}{' '}
              <strong>{sections.length}</strong> {t('section(s)', 'section(s)')}.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting} data-testid="promote-cancel-btn">
            {t('Cancel', 'Annuler')}
          </Button>
          <Button
            onClick={handlePromote}
            disabled={submitting || sections.length === 0}
            className="bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white border-0"
            data-testid="promote-confirm-btn"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                {t('Promoting…', 'Promotion…')}
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" />
                {t('Activate promotion', 'Activer la promotion')}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default PromoteListingModal;
