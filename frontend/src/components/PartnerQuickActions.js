import React, { useState, useMemo } from 'react';
import { Calendar, FileText, Zap } from 'lucide-react';
import { Button } from './ui/button';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Calendar as CalendarPicker } from './ui/calendar';
import { useCookieConsent } from '../hooks/useCookieConsent';

/**
 * PartnerQuickActions — VIP / Partner Pro exclusive messaging tools.
 * Bilingual (FR/EN) quick replies, inspection scheduler, and auction terms shortcut.
 * Visible only when `isPartnerOrVip` is true.
 *
 * Props:
 *   onSendMessage(text: string) — sends a message into the chat
 *   lang — 'fr' or 'en'
 *   isPartnerOrVip — boolean gate
 */

const QUICK_REPLIES = {
  en: [
    'Still available?',
    'Price is firm',
    'Check photos',
    'When can I see it?',
    'Is there a reserve price?',
    'Delivery options?',
  ],
  fr: [
    'Toujours disponible ?',
    'Prix ferme',
    'Voir les photos',
    'Quand puis-je le voir ?',
    'Y a-t-il un prix de reserve ?',
    'Options de livraison ?',
  ],
};

const AUCTION_TERMS = {
  en: `Auction Terms:
- All sales are final. No returns or exchanges.
- Buyer's premium of 5% applies to the hammer price.
- Payment is due within 48 hours of auction close.
- Vehicle must be picked up within 7 business days.
- BidVex acts as a platform only and is not a party to the transaction.`,
  fr: `Conditions de l'enchere :
- Toutes les ventes sont finales. Aucun retour ni echange.
- Une prime acheteur de 5 % s'applique au prix de vente.
- Le paiement est exigible dans les 48 heures suivant la fin de l'enchere.
- Le vehicule doit etre recupere dans les 7 jours ouvrables.
- BidVex agit a titre de plateforme seulement et n'est pas partie a la transaction.`,
};

const LABELS = {
  en: {
    quickReplies: 'Quick Replies',
    scheduleInspection: 'Schedule Inspection',
    auctionTerms: 'Auction Terms',
    selectDate: 'Pick a date for the inspection',
    inspectionMessage: (date) => `I'd like to schedule an inspection on ${date}. Does that work for you?`,
  },
  fr: {
    quickReplies: 'Reponses rapides',
    scheduleInspection: 'Planifier une inspection',
    auctionTerms: "Conditions de l'enchere",
    selectDate: "Choisissez une date pour l'inspection",
    inspectionMessage: (date) => `J'aimerais planifier une inspection le ${date}. Est-ce que cela vous convient ?`,
  },
};

const PartnerQuickActions = ({ onSendMessage, lang = 'en', isPartnerOrVip = false }) => {
  const [calendarOpen, setCalendarOpen] = useState(false);
  const { isAllowed } = useCookieConsent();
  const L = LABELS[lang] || LABELS.en;
  const replies = QUICK_REPLIES[lang] || QUICK_REPLIES.en;
  const terms = AUCTION_TERMS[lang] || AUCTION_TERMS.en;

  // Gate: only visible to VIP / Partner Pro
  if (!isPartnerOrVip) return null;

  const handleQuickReply = (text) => {
    onSendMessage(text);
  };

  const handleDateSelect = (date) => {
    if (!date) return;
    const formatted = date.toLocaleDateString(lang === 'fr' ? 'fr-CA' : 'en-CA', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
    onSendMessage(L.inspectionMessage(formatted));
    setCalendarOpen(false);
  };

  const handleAuctionTerms = () => {
    onSendMessage(terms);
  };

  return (
    <div
      className="border-t border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900"
      data-testid="partner-quick-actions"
    >
      {/* Quick Replies — horizontally scrollable */}
      <div className="px-3 pt-2 pb-1">
        <div
          className="flex gap-1.5 overflow-x-auto scrollbar-hide pb-1"
          data-testid="quick-replies-row"
        >
          <span className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400 shrink-0 pr-1">
            <Zap className="h-3 w-3" />
          </span>
          {replies.map((reply, i) => (
            <button
              key={i}
              onClick={() => handleQuickReply(reply)}
              className="shrink-0 px-3 py-1.5 text-xs font-medium rounded-full border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-[#06B6D4]/10 hover:border-[#06B6D4]/40 hover:text-[#06B6D4] transition-all whitespace-nowrap"
              data-testid={`quick-reply-${i}`}
            >
              {reply}
            </button>
          ))}
        </div>
      </div>

      {/* Action Buttons: Inspection Scheduler + Auction Terms */}
      <div className="px-3 pb-2 flex gap-2">
        <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
          <PopoverTrigger asChild>
            <button
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-[#06B6D4]/10 hover:text-[#06B6D4] transition-all border border-slate-200 dark:border-slate-700"
              data-testid="schedule-inspection-btn"
            >
              <Calendar className="h-3.5 w-3.5" />
              {L.scheduleInspection}
            </button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start" side="top">
            <div className="p-2 text-xs text-slate-500 text-center border-b">
              {L.selectDate}
            </div>
            <CalendarPicker
              mode="single"
              onSelect={handleDateSelect}
              disabled={(date) => date < new Date()}
              data-testid="inspection-calendar"
            />
          </PopoverContent>
        </Popover>

        <button
          onClick={handleAuctionTerms}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-[#06B6D4]/10 hover:text-[#06B6D4] transition-all border border-slate-200 dark:border-slate-700"
          data-testid="auction-terms-btn"
        >
          <FileText className="h-3.5 w-3.5" />
          {L.auctionTerms}
        </button>
      </div>
    </div>
  );
};

export default PartnerQuickActions;
