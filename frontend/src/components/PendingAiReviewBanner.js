import React, { useState } from 'react';
import axios from 'axios';
import API_BASE from '../config';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { toast } from 'sonner';
import { ShieldAlert, CheckCircle2, XCircle, MessageCircle } from 'lucide-react';

const API = API_BASE;

/**
 * FEATURE PATCH v9 / Feature 3 — Seller dashboard banner shown when a
 * listing is in status="pending_ai_review". Offers 3 actions:
 *   1. Edit & Resubmit (correct the category inline)
 *   2. Withdraw
 *   3. Contact Support
 */
const PendingAiReviewBanner = ({ listing, onActionDone }) => {
  const { token } = useAuth();
  const { i18n } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const headers = { Authorization: `Bearer ${token}` };

  const [editing, setEditing] = useState(false);
  const [newCategory, setNewCategory] = useState(listing.ai_suggested_category || listing.category || '');
  const [working, setWorking] = useState(false);

  const isMulti = listing.listing_type === 'multi' || Array.isArray(listing.lots);

  const handleResubmit = async () => {
    if (!newCategory.trim()) {
      toast.error(isFr ? 'Veuillez choisir une catégorie' : 'Please choose a category');
      return;
    }
    setWorking(true);
    try {
      await axios.post(`${API}/listings/${listing.id}/correct-category`, {
        new_category: newCategory.trim(),
        listing_type: isMulti ? 'multi' : 'single',
      }, { headers });
      toast.success(isFr ? 'Annonce soumise à nouveau pour examen.' : 'Listing resubmitted for review.');
      setEditing(false);
      onActionDone?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail?.message_en || 'Failed to resubmit');
    } finally {
      setWorking(false);
    }
  };

  const handleWithdraw = async () => {
    if (!window.confirm(isFr ? 'Retirer cette annonce ?' : 'Withdraw this listing?')) return;
    setWorking(true);
    try {
      await axios.post(
        `${API}/listings/${listing.id}/withdraw-from-review?listing_type=${isMulti ? 'multi' : 'single'}`,
        null,
        { headers }
      );
      toast.success(isFr ? 'Annonce retirée.' : 'Listing withdrawn.');
      onActionDone?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail?.message_en || 'Failed to withdraw');
    } finally {
      setWorking(false);
    }
  };

  const isAdminReview = (listing.status || '') === 'pending_admin_review';

  return (
    <div
      className={`mb-2 rounded-md border p-3 text-xs ${isAdminReview ? 'border-slate-300 bg-slate-100' : 'border-amber-300 bg-amber-50'}`}
      data-testid={`pending-ai-review-banner-${listing.id}`}
    >
      <div className="flex items-start gap-2">
        <ShieldAlert className={`h-4 w-4 mt-0.5 flex-shrink-0 ${isAdminReview ? 'text-slate-600' : 'text-amber-600'}`} />
        <div className="min-w-0 flex-1">
          {isAdminReview ? (
            <>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="inline-flex items-center gap-1 rounded-full bg-amber-200 text-amber-900 border border-amber-300 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide" data-testid={`under-review-badge-${listing.id}`}>
                  {isFr ? '⏳ En cours de révision' : '⏳ Under Review'}
                </span>
                <span className="text-[10px] text-slate-500">{isFr ? '5 à 50 minutes' : '5 to 50 minutes'}</span>
              </div>
              <p className="text-slate-700 mt-1.5 leading-relaxed">
                {isFr
                  ? 'Cette annonce est actuellement vérifiée manuellement par notre équipe de conformité afin d\u2019assurer l\u2019alignement de la catégorie. La vérification prend de 5 à 50 minutes.'
                  : 'This listing is currently being manually verified by our compliance team to ensure category alignment. Verification takes 5 to 50 minutes.'}
              </p>
              <div className="flex flex-col lg:flex-row gap-2 mt-2 w-full">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs w-full lg:w-auto cursor-not-allowed opacity-70"
                  disabled
                  data-testid={`view-public-blocked-${listing.id}`}
                  title={isFr ? 'Vue publique bloquée pendant la révision' : 'Public view blocked while under review'}
                >
                  🔒 {isFr ? 'Vue publique bloquée' : 'Public view blocked'}
                </Button>
                <a
                  href="/contact-support"
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-slate-300 text-slate-700 hover:bg-slate-50 text-xs h-7 w-full lg:w-auto justify-center"
                  data-testid={`contact-support-${listing.id}`}
                >
                  <MessageCircle className="h-3.5 w-3.5" /> {isFr ? 'Contacter le support' : 'Contact Support'}
                </a>
              </div>
            </>
          ) : (
            <>
              <p className="font-semibold text-amber-900">
                {isFr ? 'En attente d\u2019examen IA' : 'Pending AI Review'}
              </p>
              <p className="text-amber-800 mt-0.5">
                {isFr
                  ? 'Notre système IA a soulev\u00E9 une possible incoh\u00E9rence de cat\u00E9gorie. Un administrateur examinera votre annonce sous peu. Vous pouvez aussi corriger la cat\u00E9gorie maintenant pour acc\u00E9l\u00E9rer l\u2019examen.'
                  : 'Our AI system flagged a possible category mismatch. An admin will review your listing shortly. You can also correct the category now to speed things up.'}
              </p>

              {listing.ai_suggested_category && (
                <div className="text-[11px] text-amber-700 mt-1">
                  {isFr ? 'Suggestion IA' : 'AI suggestion'}: <strong>{listing.ai_suggested_category}</strong>
                </div>
              )}

              {editing ? (
            <div className="mt-2 flex items-end gap-2 flex-wrap">
              <div className="flex-1 min-w-[180px]">
                <label className="text-[10px] text-amber-700">{isFr ? 'Nouvelle cat\u00E9gorie' : 'New category'}</label>
                <Input
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  className="h-7 text-xs"
                  data-testid={`new-category-input-${listing.id}`}
                />
              </div>
              <Button
                size="sm"
                className="bg-emerald-600 hover:bg-emerald-700 text-white h-7"
                onClick={handleResubmit}
                disabled={working}
                data-testid={`submit-resubmit-${listing.id}`}
              >
                <CheckCircle2 className="h-3.5 w-3.5 mr-1" /> {isFr ? 'Soumettre' : 'Resubmit'}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setEditing(false)}
                disabled={working}
              >
                {isFr ? 'Annuler' : 'Cancel'}
              </Button>
            </div>
          ) : (
            <div className="mt-2 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs"
                onClick={() => setEditing(true)}
                disabled={working}
                data-testid={`edit-resubmit-${listing.id}`}
              >
                {isFr ? 'Modifier et soumettre \u00E0 nouveau' : 'Edit & Resubmit'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs border-rose-300 text-rose-700 hover:bg-rose-50"
                onClick={handleWithdraw}
                disabled={working}
                data-testid={`withdraw-listing-${listing.id}`}
              >
                <XCircle className="h-3.5 w-3.5 mr-1" /> {isFr ? 'Retirer' : 'Withdraw'}
              </Button>
              <a
                href="/contact-support"
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-slate-300 text-slate-700 hover:bg-slate-50 text-xs h-7"
                data-testid={`contact-support-${listing.id}`}
              >
                <MessageCircle className="h-3.5 w-3.5" /> {isFr ? 'Contacter le support' : 'Contact Support'}
              </a>
            </div>
          )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default PendingAiReviewBanner;
