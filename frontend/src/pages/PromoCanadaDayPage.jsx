/**
 * iter340 P2 — Canada Day promo landing page (/promo/canada-day).
 * Bilingual EN/FR. CTA deep-links to /auth?promo=canada-day which
 * pre-fills the promo code on the registration form.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Car, Store, Package, Lock, ShieldCheck, Timer, Languages, Percent, ArrowRight } from 'lucide-react';
import SEO from '../components/SEO';
import { Button } from '../components/ui/button';

const FEATURES = [
  {
    icon: Car,
    en: { title: 'Vehicle Auctions', text: 'Licensed dealer network, provincial compliance built-in' },
    fr: { title: 'Encans de véhicules', text: 'Réseau de concessionnaires licenciés, conformité provinciale intégrée' },
  },
  {
    icon: Store,
    en: { title: 'Marketplace', text: 'Individual sellers and businesses, any item' },
    fr: { title: 'Marché', text: 'Vendeurs individuels et entreprises, tout article' },
  },
  {
    icon: Package,
    en: { title: 'Lots Auctions', text: 'Liquidators and auctioneers, multi-item events' },
    fr: { title: 'Encans de lots', text: 'Liquidateurs et encanteurs, événements multi-articles' },
  },
  {
    icon: Lock,
    en: { title: 'Storage Auctions', text: 'Facility operators, easy setup' },
    fr: { title: 'Encans d\'entreposage', text: 'Exploitants d\'installations, configuration facile' },
  },
];

const TRUST = [
  { icon: ShieldCheck, en: 'Verified Canadian Dealers', fr: 'Concessionnaires canadiens vérifiés' },
  { icon: Timer, en: 'Soft-Close Protection', fr: 'Protection anti-sniping' },
  { icon: Languages, en: 'Bilingual EN/FR', fr: 'Bilingue EN/FR' },
  { icon: Percent, en: '2.5% Platform Fee', fr: 'Frais de plateforme de 2,5 %' },
];

export default function PromoCanadaDayPage() {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const fr = i18n.language?.startsWith('fr');

  return (
    <div className="min-h-screen bg-[#0B2545] text-white" data-testid="promo-canada-day-page">
      <SEO
        title={fr ? 'Fête du Canada — Première annonce et premier mois GRATUITS' : 'Canada Day — First Listing & First Month FREE'}
        description={fr
          ? 'Fêtez la fête du Canada avec BidVex : votre première annonce et votre premier mois sont 100 % gratuits sur le marché d\'encans bilingue du Canada.'
          : "Celebrate Canada Day with BidVex: your first listing and first month are 100% free on Canada's bilingual auction marketplace."}
        path="/promo/canada-day"
      />

      {/* Hero */}
      <div className="max-w-5xl mx-auto px-4 pt-16 pb-10 text-center">
        <p className="text-lg sm:text-xl font-semibold text-red-300" data-testid="promo-hero">
          🇨🇦 {fr ? 'Fêtez la fête du Canada avec BidVex' : 'Celebrate Canada Day with BidVex'}
        </p>
        <h1 className="mt-4 text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-tight text-white" data-testid="promo-headline">
          {fr ? (
            <>Votre première annonce et premier mois — <span className="text-red-400">100 % GRATUIT</span></>
          ) : (
            <>Your First Listing & First Month — <span className="text-red-400">100% FREE</span></>
          )}
        </h1>
        <p className="mt-5 text-base md:text-lg text-slate-300 max-w-2xl mx-auto" data-testid="promo-subheadline">
          {fr
            ? 'Le marché d\'encans bilingue du Canada pour les véhicules, les liquidations, l\'entreposage et les articles de marché.'
            : "Canada's bilingual auction marketplace for vehicles, liquidations, storage, and marketplace items."}
        </p>
        <Button
          size="lg"
          className="mt-8 bg-red-600 hover:bg-red-700 text-white text-base font-bold px-8 py-6 rounded-full"
          onClick={() => navigate('/auth?promo=canada-day')}
          data-testid="promo-cta-btn"
        >
          {fr ? 'Réclamer votre mois gratuit' : 'Claim Your Free Month'}
          <ArrowRight className="ml-2 h-5 w-5" />
        </Button>
        <p className="mt-3 text-xs text-slate-400">
          {fr ? 'Offre valide jusqu\'au 31 juillet 2026.' : 'Offer valid through July 31, 2026.'}
        </p>
      </div>

      {/* Feature blocks */}
      <div className="max-w-5xl mx-auto px-4 py-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {FEATURES.map((f, i) => {
          const c = fr ? f.fr : f.en;
          const Icon = f.icon;
          return (
            <div key={i} className="rounded-xl bg-white/5 border border-white/10 p-5 backdrop-blur-sm" data-testid={`promo-feature-${i}`}>
              <Icon className="h-7 w-7 text-[#2B8FD0]" />
              <h3 className="mt-3 font-bold text-white">{c.title}</h3>
              <p className="mt-1 text-sm text-slate-300">{c.text}</p>
            </div>
          );
        })}
      </div>

      {/* Trust badges */}
      <div className="max-w-5xl mx-auto px-4 pb-16">
        <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 border-t border-white/10 pt-8" data-testid="promo-trust-badges">
          {TRUST.map((b, i) => {
            const Icon = b.icon;
            return (
              <span key={i} className="flex items-center gap-2 text-sm text-slate-300">
                <Icon className="h-4 w-4 text-red-400" />
                {fr ? b.fr : b.en}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
