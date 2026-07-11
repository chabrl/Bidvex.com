/**
 * iter341 P0 — Summer Grand Opening promo landing (/promo/summer-launch).
 * Replaces the retired Canada Day campaign (old route redirects here).
 * Bilingual EN/FR. CTA deep-links to /register?promo=SUMMER2026.
 */
import React from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Rocket, Car, Store, Package, Lock, ShieldCheck, Timer, Languages, Percent, ArrowRight } from 'lucide-react';
import SEO from '../components/SEO';
import { Button } from '../components/ui/button';

const OG_IMAGE = 'https://bidvex.com/static/og/summer-launch-promo.png';

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
  { icon: Timer, en: 'Soft-Close Bidding', fr: 'Enchères anti-sniping' },
  { icon: Languages, en: 'Bilingual EN/FR', fr: 'Bilingue EN/FR' },
  { icon: Percent, en: '2.5% Platform Fee', fr: 'Frais de plateforme de 2,5 %' },
];

export default function PromoSummerLaunchPage() {
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const fr = i18n.language?.startsWith('fr');

  return (
    <div className="min-h-screen bg-[#0B2545] text-white" data-testid="promo-summer-launch-page">
      <SEO
        title={fr ? 'Grand lancement de BidVex — Premier mois GRATUIT' : 'BidVex Grand Opening — First Month FREE'}
        description={fr
          ? 'Le nouveau marché d\'enchères bilingue du Canada est ouvert. Publiez gratuitement, enchérissez gratuitement, vendez mieux. Véhicules, Marché, Lots et Entreposage.'
          : "Canada's new bilingual auction marketplace is live. List free, bid free, sell smarter. Vehicles, Marketplace, Lots & Storage."}
        path="/promo/summer-launch"
        image={OG_IMAGE}
      />
      <Helmet>
        <meta property="og:image:width" content="1200" />
        <meta property="og:image:height" content="628" />
        <meta name="twitter:card" content="summary_large_image" />
      </Helmet>

      {/* Hero */}
      <div className="max-w-5xl mx-auto px-4 pt-16 pb-10 text-center">
        <p className="text-lg sm:text-xl font-semibold text-[#3FB4CB] flex items-center justify-center gap-2" data-testid="promo-hero">
          <Rocket className="h-5 w-5" />
          {fr ? 'Grand lancement de BidVex — Été 2026' : 'BidVex Grand Opening — Summer 2026'}
        </p>
        <h1 className="mt-4 text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-tight text-white" data-testid="promo-headline">
          {fr ? (
            <>BidVex est maintenant en ligne — et votre premier mois est <span className="text-[#2B8FD0]">offert</span></>
          ) : (
            <>BidVex Is Now Live — and Your First Month Is <span className="text-[#2B8FD0]">on Us</span></>
          )}
        </h1>
        <p className="mt-5 text-base md:text-lg text-slate-300 max-w-2xl mx-auto" data-testid="promo-subheadline">
          {fr
            ? 'Le nouveau marché d\'enchères bilingue du Canada est ouvert. Publiez votre première annonce gratuitement. Votre premier mois entier, sans frais.'
            : "Canada's new bilingual auction marketplace is open. List your first item free. Your entire first month, zero fees."}
        </p>
        <Button
          size="lg"
          className="mt-8 bg-[#2B8FD0] hover:bg-[#2478b0] text-white text-base font-bold px-8 py-6 rounded-full"
          onClick={() => navigate('/register?promo=SUMMER2026')}
          data-testid="promo-cta-btn"
        >
          {fr ? 'Réclamer votre mois gratuit' : 'Claim Your Free Month'}
          <ArrowRight className="ml-2 h-5 w-5" />
        </Button>
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

      {/* Trust badges + urgency */}
      <div className="max-w-5xl mx-auto px-4 pb-16">
        <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 border-t border-white/10 pt-8" data-testid="promo-trust-badges">
          {TRUST.map((b, i) => {
            const Icon = b.icon;
            return (
              <span key={i} className="flex items-center gap-2 text-sm text-slate-300">
                <Icon className="h-4 w-4 text-[#3FB4CB]" />
                {fr ? b.fr : b.en}
              </span>
            );
          })}
        </div>
        <p className="mt-8 text-center text-sm text-slate-400" data-testid="promo-urgency">
          {fr ? 'Offre valide jusqu\'au 31 août 2026' : 'Offer valid through August 31, 2026'}
        </p>
      </div>
    </div>
  );
}
