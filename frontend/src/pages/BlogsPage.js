/**
 * BidVex Blogs — SEO landing page (iter325).
 * Centralized repository for BidVex articles, operational definitions,
 * user hints, and technical explanations to drive organic traffic.
 *
 * Replaces the deprecated mailto Press link in the footer.
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { useTranslation } from 'react-i18next';
import { Newspaper, ArrowRight, BookOpen, Gavel, ShieldCheck, Truck, Warehouse, Sparkles } from 'lucide-react';

const ARTICLES = [
  {
    slug: 'how-bidvex-auction-engine-works',
    icon: Gavel,
    tag: 'platform',
    title_en: 'How the BidVex Auction Engine Works — Hammer Price, Buyer Premium & Settlement',
    title_fr: 'Comment fonctionne le moteur d’enchères BidVex — Prix marteau, prime acheteur et règlement',
    excerpt_en: 'A clear breakdown of how the final hammer price is determined, when the buyer\'s premium applies (3%–5% by tier), and the role of the 14.975% Quebec tax on platform service fees.',
    excerpt_fr: 'Comprendre comment le prix marteau final est déterminé, quand la prime acheteur s\'applique (3 % à 5 % selon le palier) et le rôle de la taxe québécoise de 14,975 % sur les frais de service.',
    read_min: 6,
  },
  {
    slug: 'broker-and-dealer-onboarding',
    icon: ShieldCheck,
    tag: 'compliance',
    title_en: 'Becoming a Certified Vehicle Dealer or Broker on BidVex',
    title_fr: 'Devenir concessionnaire de véhicules certifié ou courtier sur BidVex',
    excerpt_en: 'The full broker-gate verification pipeline: OMVIC, AMVIC, VSA and SAAQ license validation, $200/yr subscription with the LAUNCH50 coupon, and the buyer security deposit mechanics.',
    excerpt_fr: 'Le pipeline complet de vérification du portail courtier : validation des licences OMVIC, AMVIC, VSA et SAAQ, abonnement annuel de 200 $ avec le coupon LAUNCH50, et la mécanique du dépôt de sécurité acheteur.',
    read_min: 8,
  },
  {
    slug: 'storage-facility-liquidation-rules',
    icon: Warehouse,
    tag: 'storage',
    title_en: 'Commercial Storage Facility Auctions — Compliance & Buyer\'s Premium',
    title_fr: 'Enchères de centres d\'entreposage commercial — Conformité et prime acheteur',
    excerpt_en: 'How abandoned storage unit liquidations work under Quebec self-storage statutes, including the standard 5% buyer premium and notice-period requirements.',
    excerpt_fr: 'Le fonctionnement de la liquidation des unités d\'entreposage abandonnées en vertu des lois québécoises, y compris la prime acheteur standard de 5 % et les délais de préavis requis.',
    read_min: 5,
  },
  {
    slug: 'vehicle-hammer-direct-settlement',
    icon: Truck,
    tag: 'vehicles',
    title_en: 'Vehicle Hammer Price — Why BidVex Never Touches It',
    title_fr: 'Prix marteau du véhicule — Pourquoi BidVex n\'y touche jamais',
    excerpt_en: 'Direct buyer-to-broker settlement, Stripe Connect only processes service fees, GST/QST split, and SAAQ/OMVIC title transfer obligations.',
    excerpt_fr: 'Règlement direct acheteur-courtier, Stripe Connect ne traite que les frais de service, ventilation TPS/TVQ, et obligations de transfert de titre SAAQ/OMVIC.',
    read_min: 7,
  },
  {
    slug: 'contractor-commission-and-leaderboard',
    icon: Sparkles,
    tag: 'partners',
    title_en: 'Inside the Contractor Commission Engine — 5% Baseline, +1% per Week in the Top 5',
    title_fr: 'À l\'intérieur du moteur de commission contractant — 5 % de base, +1 % par semaine dans le Top 5',
    excerpt_en: 'How verified contractor acquisitions earn a structural 5% baseline commission, the Monday-reset Top-5 leaderboard +1% bonus, the -1% drop-out deduction, and the 20% effective ceiling.',
    excerpt_fr: 'Comment les acquisitions de contractants vérifiés gagnent une commission de base structurelle de 5 %, le bonus +1 % du tableau Top 5 réinitialisé chaque lundi, la déduction -1 % en cas de sortie et le plafond effectif de 20 %.',
    read_min: 6,
  },
  {
    slug: 'watchdog-fraud-engine',
    icon: ShieldCheck,
    tag: 'security',
    title_en: 'The Watchdog Fraud Engine — How BidVex AI Telemetry Protects Every Auction',
    title_fr: 'Le moteur antifraude Watchdog — Comment la télémétrie IA de BidVex protège chaque enchère',
    excerpt_en: 'Real-time photo-EXIF analysis, duplicate-listing detection, bid-velocity scoring, and the GenAI direct watchdog that scores every new listing before it goes live.',
    excerpt_fr: 'Analyse EXIF photo en temps réel, détection de listings dupliqués, score de vélocité d\'enchères et watchdog direct GenAI qui évalue chaque nouvelle annonce avant publication.',
    read_min: 9,
  },
];

const TAG_LABELS = {
  platform:   { en: 'Platform',   fr: 'Plateforme' },
  compliance: { en: 'Compliance', fr: 'Conformité' },
  storage:    { en: 'Storage',    fr: 'Entreposage' },
  vehicles:   { en: 'Vehicles',   fr: 'Véhicules' },
  partners:   { en: 'Partners',   fr: 'Partenaires' },
  security:   { en: 'Security',   fr: 'Sécurité' },
};

export default function BlogsPage() {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').toLowerCase().startsWith('fr');

  return (
    <div className="min-h-screen bg-slate-50" data-testid="blogs-page">
      <Helmet>
        <title>{fr ? 'Blog BidVex — Articles, guides et nouveautés' : 'BidVex Blog — Articles, Guides & Platform Insights'}</title>
        <meta
          name="description"
          content={fr
            ? 'Articles, guides et explications techniques pour vendeurs, courtiers, concessionnaires et acheteurs sur la plateforme d\'enchères BidVex.'
            : 'Articles, guides, and technical explanations for sellers, brokers, dealers, and buyers on the BidVex auction platform.'}
        />
        <link rel="canonical" href="https://bidvex.com/blogs" />
      </Helmet>

      {/* Hero */}
      <section className="relative overflow-hidden border-b border-slate-200" style={{ background: 'linear-gradient(135deg, #0B2545 0%, #1B3D6F 60%, #2186C6 100%)' }}>
        <div className="max-w-6xl mx-auto px-6 py-16 md:py-20 text-white">
          <div className="flex items-center gap-2 text-sm uppercase tracking-[0.2em] text-cyan-200 mb-4" data-testid="blogs-eyebrow">
            <Newspaper className="w-4 h-4" />
            <span>{fr ? 'Salle de presse & Blog' : 'Press Room & Blog'}</span>
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold leading-tight mb-4" data-testid="blogs-hero-title">
            {fr ? 'Articles, guides et nouveautés BidVex' : 'BidVex Articles, Guides & Platform Insights'}
          </h1>
          <p className="text-lg text-cyan-100 max-w-3xl">
            {fr
              ? 'Le dépôt centralisé de définitions opérationnelles, conseils pratiques et explications techniques pour faire grandir la communauté BidVex.'
              : 'The centralized repository of operational definitions, user hints, and technical explanations powering the BidVex community.'}
          </p>
          <p className="text-sm text-cyan-200 mt-6">
            {fr ? 'Vous représentez la presse ou les médias ? Écrivez à ' : 'Press or media inquiries? Email '}
            <a href="mailto:support@bidvex.com" className="underline hover:text-white" data-testid="blogs-press-email">support@bidvex.com</a>
            {fr ? ' — nous répondons sous 24 h ouvrables.' : ' — we respond within 1 business day.'}
          </p>
        </div>
      </section>

      {/* Article grid */}
      <section className="max-w-6xl mx-auto px-6 py-12 md:py-16">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="blogs-grid">
          {ARTICLES.map((a) => {
            const Icon = a.icon;
            const tagLabel = (TAG_LABELS[a.tag] || {})[fr ? 'fr' : 'en'] || a.tag;
            return (
              <article
                key={a.slug}
                data-testid={`blogs-article-${a.slug}`}
                className="group bg-white rounded-xl border border-slate-200 hover:border-cyan-400 hover:shadow-xl transition-all duration-300 overflow-hidden flex flex-col"
              >
                <div className="px-6 pt-6 flex items-start justify-between">
                  <div className="w-12 h-12 rounded-lg flex items-center justify-center" style={{ background: '#F0F8FF' }}>
                    <Icon className="w-6 h-6" style={{ color: '#2186C6' }} />
                  </div>
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-cyan-700 bg-cyan-50 px-2 py-1 rounded-full">
                    {tagLabel}
                  </span>
                </div>
                <div className="px-6 pt-4 pb-6 flex-1 flex flex-col">
                  <h2 className="text-lg font-bold text-slate-900 mb-2 leading-snug group-hover:text-cyan-700 transition-colors">
                    {fr ? a.title_fr : a.title_en}
                  </h2>
                  <p className="text-sm text-slate-600 leading-relaxed flex-1">
                    {fr ? a.excerpt_fr : a.excerpt_en}
                  </p>
                  <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between text-xs">
                    <span className="text-slate-500">
                      {a.read_min} {fr ? 'min de lecture' : 'min read'}
                    </span>
                    <span className="inline-flex items-center gap-1 text-cyan-700 font-semibold group-hover:gap-2 transition-all">
                      {fr ? 'Lire la suite' : 'Read more'}
                      <ArrowRight className="w-3 h-3" />
                    </span>
                  </div>
                </div>
              </article>
            );
          })}
        </div>

        {/* CTA */}
        <div className="mt-16 rounded-2xl p-8 md:p-12 text-center" style={{ background: '#0B2545', color: 'white' }} data-testid="blogs-cta-card">
          <BookOpen className="w-10 h-10 mx-auto mb-3 text-cyan-300" />
          <h2 className="text-2xl md:text-3xl font-bold mb-3">
            {fr ? 'Un sujet à creuser ? Suggérez un article.' : 'Have a topic you\'d like us to cover?'}
          </h2>
          <p className="text-cyan-100 max-w-xl mx-auto mb-6">
            {fr
              ? 'Notre équipe éditoriale publie chaque semaine. Soumettez vos idées et nous y répondrons par un article ou un guide.'
              : 'Our editorial team publishes weekly. Submit topic ideas and we\'ll respond with an article or how-to guide.'}
          </p>
          <Link
            to="/contact-us"
            data-testid="blogs-suggest-topic-link"
            className="inline-flex items-center gap-2 px-6 py-3 bg-cyan-400 text-slate-900 font-semibold rounded-lg hover:bg-cyan-300 transition-colors"
          >
            {fr ? 'Proposer un sujet' : 'Suggest a Topic'}
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>
    </div>
  );
}
