/**
 * iter258 Mission 4 — Partner Promotion Program landing page.
 *
 * Public-facing `/promotions/partners`. Three partner tiers
 * (dealer / broker / storage) with their respective free-trial offers,
 * a comparison table, and a final CTA. Each "Activate" CTA leads to
 * the registration flow (or directly to POST /api/promotions/partner-trial
 * for already-authenticated users).
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Helmet } from 'react-helmet-async';
import { Button } from '../components/ui/button';
import { Sparkles, Car, Award, Warehouse, Check, X } from 'lucide-react';
import { LangLink } from '../components/LangLink';

const PartnerPromotionsPage = () => {
  const { i18n } = useTranslation();
  const isFr = (i18n.language || 'en').startsWith('fr');
  const navigate = useNavigate();
  const t = (en, fr) => (isFr ? fr : en);

  const goActivate = (partnerType) => {
    navigate(`/auth?mode=register&ref=partner&type=${partnerType}`);
  };

  return (
    <div className="min-h-screen bg-slate-50" data-testid="partner-promotions-page">
      <Helmet>
        <title>{t(
          'Partner Program — Free Trial for Dealers, Brokers & Storage | BidVex',
          'Programme Partenaires — Essai gratuit pour concessionnaires, courtiers et entrepôts | BidVex',
        )}</title>
        <meta name="description" content={t(
          "Join BidVex as a vehicle dealer, licensed broker, or storage facility operator. Start your free trial today. No credit card required.",
          "Rejoignez BidVex en tant que concessionnaire automobile, courtier licencié ou exploitant d'entrepôt. Démarrez votre essai gratuit dès aujourd'hui. Aucune carte de crédit requise.",
        )} />
        <meta name="keywords" content="auction broker Canada, vehicle dealer auction platform, storage auction software, BidVex partner program" />
        <link rel="canonical" href="https://bidvex.com/promotions/partners" />
        <meta property="og:title" content={t('Partner Program | BidVex', 'Programme Partenaires | BidVex')} />
        <meta property="og:description" content={t(
          'Free trial for vehicle dealers, brokers and storage operators on Canada\'s #1 auction marketplace.',
          'Essai gratuit pour les concessionnaires, courtiers et entrepôts sur la marketplace d\'enchères #1 au Canada.',
        )} />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://bidvex.com/promotions/partners" />
        <meta property="og:image" content="https://bidvex.com/og-partners.jpg" />
        <meta property="og:locale" content={isFr ? 'fr_CA' : 'en_CA'} />
        <meta name="twitter:card" content="summary_large_image" />
      </Helmet>

      {/* Hero */}
      <section
        className="relative overflow-hidden"
        style={{ background: 'linear-gradient(135deg, #0a1628 0%, #1e3a5f 100%)' }}
        data-testid="partner-promotions-hero"
      >
        <div className="max-w-6xl mx-auto px-6 py-16 sm:py-24 text-white">
          <p className="text-amber-300 text-sm font-bold tracking-[0.2em] uppercase mb-4">
            🚀 {t('Partner Launch Program', 'Programme de lancement des partenaires')}
          </p>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black leading-tight mb-4">
            {t('Grow Your Business on BidVex', 'Faites croître votre entreprise sur BidVex')}
          </h1>
          <p className="text-xl text-blue-100 mb-3 font-semibold">
            {t("Canada's #1 Online Auction Marketplace for Pros", "La marketplace d'enchères #1 au Canada pour les professionnels")}
          </p>
          <p className="text-base text-blue-100/90 max-w-2xl mb-8">
            {t(
              'Reach thousands of verified buyers across Canada. Promote your inventory, listings, and brand — starting 100% FREE with our Partner Launch Program.',
              "Rejoignez des milliers d'acheteurs vérifiés à travers le Canada. Promouvez votre inventaire, vos annonces et votre marque — démarrez 100% gratuitement avec notre programme.",
            )}
          </p>
          <div className="flex flex-wrap gap-3">
            <Button
              className="bg-amber-500 hover:bg-amber-600 text-slate-900 font-bold px-6 py-6 text-base"
              onClick={() => navigate('/auth?mode=register&ref=partner')}
              data-testid="partner-hero-cta-start"
            >
              {t('Start My Free Trial', 'Démarrer mon essai gratuit')} →
            </Button>
            <Button
              variant="outline"
              className="border-white text-white hover:bg-white/10 font-bold px-6 py-6 text-base"
              onClick={() => document.getElementById('partner-tiers')?.scrollIntoView({ behavior: 'smooth' })}
              data-testid="partner-hero-cta-plans"
            >
              {t('View Plans', 'Voir les forfaits')}
            </Button>
          </div>
        </div>
      </section>

      {/* Three partner cards */}
      <section id="partner-tiers" className="max-w-7xl mx-auto px-6 py-12 sm:py-16">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Vehicle Dealers */}
          <article
            className="rounded-2xl p-6 shadow-md border border-blue-100"
            style={{ background: 'linear-gradient(180deg, #e3edff 0%, #ffffff 60%)' }}
            data-testid="partner-card-dealer"
          >
            <div className="flex items-center gap-2 mb-2">
              <Car className="h-8 w-8 text-blue-700" />
              <span className="text-xs font-bold tracking-widest uppercase text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full">
                🎁 {t('FREE 30-Day Trial', "Essai gratuit 30 jours")}
              </span>
            </div>
            <h3 className="text-xl font-extrabold text-slate-900 mb-3">
              {t('Vehicle Dealers & Brokers', 'Concessionnaires et courtiers automobiles')}
            </h3>
            <ul className="space-y-2 text-sm text-slate-700 mb-4">
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('3 Featured Vehicle Listings (top placement)', '3 annonces véhicule en vedette (en haut de page)')}</li>
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Verified Dealer Badge on all your listings', "Badge concessionnaire vérifié sur toutes vos annonces")}</li>
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Access to 10,000+ registered Canadian buyers', "Accès à plus de 10 000 acheteurs enregistrés au Canada")}</li>
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Real-time bid analytics dashboard', "Tableau de bord d'analyse des enchères en temps réel")}</li>
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Geo-targeted buyer matching by province', "Mise en relation par province")}</li>
            </ul>
            <p className="text-xs text-slate-500 mb-3">
              {t('After trial — Dealer Pro Plan:', "Après l'essai — Forfait Dealer Pro :")}
              <br />
              <strong className="text-slate-800">$149 CAD/mo</strong> {t('(up to 50 active listings)', '(jusqu\'à 50 annonces actives)')}
              <br />
              <span className="text-emerald-700">$99 CAD/mo</span> {t('(yearly commitment)', '(engagement annuel)')}
            </p>
            <Button
              className="w-full font-bold"
              style={{ backgroundColor: '#0055FF', color: 'white' }}
              onClick={() => goActivate('dealer')}
              data-testid="partner-cta-dealer"
            >
              {t('Activate Free Dealer Trial', 'Activer l\'essai concessionnaire')}
            </Button>
            <p className="text-[11px] text-slate-500 text-center mt-2">
              {t('No credit card required. Cancel anytime.', "Aucune carte de crédit requise. Annulez à tout moment.")}
            </p>
          </article>

          {/* Licensed Brokers */}
          <article
            className="rounded-2xl p-6 shadow-md border border-amber-200"
            style={{ background: 'linear-gradient(180deg, #fff8e0 0%, #ffffff 60%)' }}
            data-testid="partner-card-broker"
          >
            <div className="flex items-center gap-2 mb-2">
              <Award className="h-8 w-8 text-amber-600" />
              <span className="text-xs font-bold tracking-widest uppercase text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
                ⭐ {t('EXCLUSIVE — Broker Partner Program', 'EXCLUSIF — Programme Partenaire Courtier')}
              </span>
            </div>
            <h3 className="text-xl font-extrabold text-slate-900 mb-3">
              {t('Licensed Auction Brokers', "Courtiers licenciés d'enchères")}
            </h3>
            <ul className="space-y-2 text-sm text-slate-700 mb-4">
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Unlimited listings during trial', "Annonces illimitées pendant l'essai")}</li>
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Priority "Verified Broker" badge + directory listing', 'Badge "Courtier vérifié" + annuaire prioritaire')}</li>
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Dedicated broker profile page (public, SEO-indexed)', "Page courtier dédiée (publique, indexée SEO)")}</li>
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Client referral tools + co-branded auction pages', 'Outils de référencement client + pages co-marquées')}</li>
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Early access to Multi-Lot & Storage auction modules', "Accès anticipé aux modules Multi-Lots et Entrepôts")}</li>
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Direct buyer messaging system', "Messagerie directe acheteur")}</li>
            </ul>
            <p className="text-xs text-slate-500 mb-3">
              {t('After trial — Broker Pro Plan:', "Après l'essai — Forfait Broker Pro :")}
              <br />
              <strong className="text-slate-800">$249 CAD/mo</strong> {t('(unlimited listings)', '(annonces illimitées)')}
              <br />
              <span className="text-emerald-700">$199 CAD/mo</span> {t('(yearly commitment)', '(engagement annuel)')}
            </p>
            <Button
              className="w-full font-bold"
              style={{ backgroundColor: '#0055FF', color: 'white' }}
              onClick={() => goActivate('broker')}
              data-testid="partner-cta-broker"
            >
              {t('Apply for Broker Partnership', 'Postuler au partenariat courtier')}
            </Button>
            <p className="text-[11px] text-slate-500 text-center mt-2">
              {t('Regulated broker licence required for approval.', "Licence de courtier réglementée requise.")}
            </p>
          </article>

          {/* Storage Facilities */}
          <article
            className="rounded-2xl p-6 shadow-md border border-emerald-200"
            style={{ background: 'linear-gradient(180deg, #defaf2 0%, #ffffff 60%)' }}
            data-testid="partner-card-storage"
          >
            <div className="flex items-center gap-2 mb-2">
              <Warehouse className="h-8 w-8 text-emerald-700" />
              <span className="text-xs font-bold tracking-widest uppercase text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                🎁 {t('FREE 45-Day Trial', "Essai gratuit 45 jours")}
              </span>
            </div>
            <h3 className="text-xl font-extrabold text-slate-900 mb-3">
              {t('Storage Facility Operators', "Exploitants d'entrepôts")}
            </h3>
            <ul className="space-y-2 text-sm text-slate-700 mb-4">
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('5 Featured Storage Unit Auction listings', "5 annonces d'enchères d'unités d'entreposage en vedette")}</li>
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Facility profile page with photos + address map', "Page d'entrepôt avec photos + carte d'adresse")}</li>
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Automated tenant notification tools', "Outils de notification automatique des locataires")}</li>
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Legal-compliant abandoned property auction workflow', "Flux d'enchères conforme aux lois sur les biens abandonnés")}</li>
              <li className="flex gap-2"><Check className="h-4 w-4 text-emerald-600 mt-0.5" /> {t('Geo-targeted bidder reach within your region', "Portée géociblée des enchérisseurs dans votre région")}</li>
            </ul>
            <p className="text-xs text-slate-500 mb-3">
              {t('After trial — Storage Pro Plan:', "Après l'essai — Forfait Storage Pro :")}
              <br />
              <strong className="text-slate-800">$99 CAD/mo</strong> {t('(up to 20 active unit auctions)', '(jusqu\'à 20 enchères actives)')}
              <br />
              <span className="text-emerald-700">$69 CAD/mo</span> {t('(yearly commitment)', '(engagement annuel)')}
            </p>
            <Button
              className="w-full font-bold"
              style={{ backgroundColor: '#0055FF', color: 'white' }}
              onClick={() => goActivate('storage')}
              data-testid="partner-cta-storage"
            >
              {t('Start Storage Free Trial', "Démarrer l'essai entrepôt")}
            </Button>
            <p className="text-[11px] text-slate-500 text-center mt-2">
              {t('No credit card required. 45-day full access.', "Aucune carte de crédit requise. Accès complet 45 jours.")}
            </p>
          </article>
        </div>

        {/* Comparison table */}
        <div className="mt-12 bg-white border border-slate-200 rounded-2xl overflow-hidden" data-testid="partner-comparison-table">
          <table className="w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="text-left p-3 font-bold text-slate-700">{t('Feature', 'Fonctionnalité')}</th>
                <th className="p-3 font-bold text-blue-700">{t('Dealer', 'Concessionnaire')}</th>
                <th className="p-3 font-bold text-amber-700">{t('Broker', 'Courtier')}</th>
                <th className="p-3 font-bold text-emerald-700">{t('Storage', 'Entrepôt')}</th>
              </tr>
            </thead>
            <tbody>
              {[
                [t('Free Trial Duration', 'Durée essai gratuit'), '30 days', '60 days', '45 days'],
                [t('Featured Listings', 'Annonces en vedette'), '3', t('Unlim.', 'Illim.'), '5'],
                [t('Verified Badge', 'Badge vérifié'), '✅', '✅', '✅'],
                [t('Analytics Dashboard', "Tableau d'analyse"), '✅', '✅', '✅'],
                [t('Broker Directory', 'Annuaire de courtiers'), '❌', '✅', '❌'],
                [t('Storage Workflow', "Flux d'entrepôt"), '❌', '❌', '✅'],
                [t('Multi-Lot Auctions', 'Enchères Multi-Lots'), '❌', '✅', '✅'],
                [t('Credit Card Required', 'Carte de crédit requise'), '❌', '❌', '❌'],
              ].map((row, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="p-3 text-slate-700">{row[0]}</td>
                  <td className="p-3 text-center font-semibold">{row[1]}</td>
                  <td className="p-3 text-center font-semibold">{row[2]}</td>
                  <td className="p-3 text-center font-semibold">{row[3]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Final CTA */}
        <div className="mt-12 text-center bg-gradient-to-r from-amber-50 to-rose-50 border border-amber-200 rounded-2xl p-8" data-testid="partner-final-cta">
          <p className="text-lg sm:text-xl font-bold text-slate-900 mb-2">
            ⏳ {t('Limited Spots Available', 'Places limitées disponibles')}
          </p>
          <p className="text-sm text-slate-600 mb-5">
            {t('Partner slots fill quickly. Reserve your free trial today.', 'Les places se remplissent vite. Réservez votre essai gratuit aujourd\'hui.')}
          </p>
          <LangLink
            to="/auth?mode=register&ref=partner"
            className="inline-flex items-center gap-2 px-6 py-3 bg-[#0055FF] hover:opacity-90 text-white font-bold rounded-lg text-base"
            data-testid="partner-final-cta-btn"
          >
            <Sparkles className="h-4 w-4" />
            {t('Get Started Free', 'Démarrer gratuitement')}
          </LangLink>
        </div>
      </section>
    </div>
  );
};

export default PartnerPromotionsPage;
