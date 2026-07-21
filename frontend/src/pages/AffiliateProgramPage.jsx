/**
 * iter367 P1 — Public Affiliate Program landing page.
 * Route: /affiliate-program (EN) / /fr/programme-affilies (FR).
 * Not to be confused with `/affiliate` which is the authenticated user
 * dashboard for enrolled affiliates. This page markets the program to
 * prospective partners and links to sign-up.
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Users, DollarSign, TrendingUp, Award, ArrowRight, CheckCircle2, ShieldCheck, BarChart3 } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { LangLink } from '../components/LangLink';
import PageHead from '../components/PageHead';

const COPY = {
  en: {
    title: "BidVex Affiliate Program",
    subtitle: "Earn 10% commission on every sale you refer for the first 12 months.",
    heroCta: "Join the program",
    dashboardCta: "Go to your Affiliate Dashboard",
    whyTitle: "Why partner with BidVex",
    perks: [
      { icon: DollarSign, title: "10% recurring commission", body: "You earn 10% of BidVex's platform fee on every winning bid your referred users make — for their first 12 months." },
      { icon: TrendingUp, title: "Real-time tracking", body: "Live earnings dashboard, downloadable CSV reports, and instant referral analytics powered by our internal ledger." },
      { icon: ShieldCheck, title: "Guaranteed payouts", body: "Monthly Stripe Connect payouts direct to your bank. No thresholds, no hoops. You get paid the 1st of every month." },
      { icon: BarChart3, title: "Marketing kit", body: "Branded banners, unique short-links, deep-link generators for TikTok / Instagram / Twitter, and a dedicated partner Slack." },
    ],
    howTitle: "How it works",
    steps: [
      "Apply in under 60 seconds — no minimum audience.",
      "Get your unique referral code + tracking link.",
      "Share on your channels (blog, YouTube, socials, email).",
      "Earn 10% of BidVex's fee for the first 12 months of every referred user's activity.",
    ],
    faqTitle: "Frequently asked questions",
    faqs: [
      { q: "Who can join?", a: "Anyone with an audience — content creators, industry blogs, dealer associations, brokers, and regional influencers. We manually approve applications to keep the network high-quality." },
      { q: "When do I get paid?", a: "Monthly, on the 1st, via Stripe Connect direct deposit. Minimum payout is $25 CAD; unpaid amounts roll to the next month." },
      { q: "How long does attribution last?", a: "A referred user is attributed to you for 12 full months from their first sign-up. All of their winning bids in that window pay you." },
      { q: "Is there an exclusivity clause?", a: "No. You can promote competing platforms; we only ask that you disclose the BidVex partnership per FTC/Canadian consumer-protection rules." },
    ],
    trustedBy: "Trusted by 400+ Canadian affiliates already earning with BidVex",
  },
  fr: {
    title: "Programme d'affiliation BidVex",
    subtitle: "Gagnez 10% de commission sur chaque vente référée pendant les 12 premiers mois.",
    heroCta: "Rejoindre le programme",
    dashboardCta: "Accédez à votre tableau d'affiliation",
    whyTitle: "Pourquoi devenir partenaire BidVex",
    perks: [
      { icon: DollarSign, title: "10% de commission récurrente", body: "Vous gagnez 10% des frais de plateforme BidVex sur chaque enchère remportée par vos utilisateurs référés — durant leurs 12 premiers mois." },
      { icon: TrendingUp, title: "Suivi en temps réel", body: "Tableau de bord en direct, rapports CSV téléchargeables et analyses instantanées via notre registre interne." },
      { icon: ShieldCheck, title: "Versements garantis", body: "Versements mensuels par Stripe Connect directement à votre banque. Sans seuil, sans embûche. Payé le 1er du mois." },
      { icon: BarChart3, title: "Trousse marketing", body: "Bannières de marque, liens courts uniques, générateur de liens profonds (TikTok / Instagram / X) et canal Slack dédié aux partenaires." },
    ],
    howTitle: "Comment ça fonctionne",
    steps: [
      "Postulez en moins de 60 secondes — aucune audience minimale requise.",
      "Recevez votre code de référence unique et votre lien de suivi.",
      "Partagez sur vos canaux (blogue, YouTube, réseaux sociaux, courriel).",
      "Gagnez 10% des frais de BidVex pendant les 12 premiers mois d'activité de chaque utilisateur référé.",
    ],
    faqTitle: "Foire aux questions",
    faqs: [
      { q: "Qui peut se joindre?", a: "Toute personne avec une audience — créateurs, blogues industriels, associations de concessionnaires, courtiers et influenceurs régionaux. Nous approuvons manuellement pour garantir la qualité." },
      { q: "Quand suis-je payé(e)?", a: "Mensuellement, le 1er, par Stripe Connect (dépôt direct). Le seuil minimal est 25 CAD; les montants inférieurs se reportent." },
      { q: "Quelle est la durée d'attribution?", a: "Un utilisateur référé vous est attribué pendant 12 mois complets à partir de son inscription. Toutes ses enchères remportées durant cette période vous rapportent." },
      { q: "Y a-t-il une exclusivité?", a: "Non. Vous pouvez promouvoir d'autres plateformes; nous demandons uniquement la divulgation du partenariat BidVex selon les règles FTC / Loi canadienne sur la protection du consommateur." },
    ],
    trustedBy: "Fait confiance à plus de 400 affiliés canadiens qui gagnent déjà avec BidVex",
  },
};

export default function AffiliateProgramPage() {
  const { i18n } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const lang = i18n.language === 'fr' ? 'fr' : 'en';
  const c = COPY[lang];

  const heroCtaTarget = user ? '/affiliate' : '/auth';
  const heroCtaLabel = user ? c.dashboardCta : c.heroCta;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-cyan-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950" data-testid="affiliate-program-page">
      <PageHead
        title={c.title + ' | BidVex'}
        description={c.subtitle}
        canonical={`/${lang === 'fr' ? 'fr/programme-affilies' : 'affiliate-program'}`}
      />

      {/* Hero */}
      <section className="relative overflow-hidden py-20 px-4">
        <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 via-blue-500/5 to-transparent pointer-events-none" />
        <div className="max-w-5xl mx-auto relative">
          <div className="inline-flex items-center gap-2 bg-cyan-100 dark:bg-cyan-900/40 text-cyan-800 dark:text-cyan-200 text-xs font-semibold px-3 py-1 rounded-full mb-4">
            <Award className="h-3.5 w-3.5" />
            {lang === 'fr' ? 'Nouveau — 10% récurrent' : 'New — 10% recurring'}
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-slate-900 dark:text-white mb-4" data-testid="affiliate-title">
            {c.title}
          </h1>
          <p className="text-lg text-slate-600 dark:text-slate-300 mb-8 max-w-3xl" data-testid="affiliate-subtitle">
            {c.subtitle}
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <Button
              size="lg"
              className="bg-gradient-to-r from-cyan-600 to-blue-600 text-white h-12 px-8 text-base font-bold"
              onClick={() => navigate(heroCtaTarget)}
              data-testid="affiliate-hero-cta"
            >
              {heroCtaLabel}
              <ArrowRight className="h-5 w-5 ml-2" />
            </Button>
            <div className="inline-flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400 px-3">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              {c.trustedBy}
            </div>
          </div>
        </div>
      </section>

      {/* Perks grid */}
      <section className="py-16 px-4">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white mb-8">{c.whyTitle}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {c.perks.map((p, i) => (
              <Card key={i} className="border-slate-200 dark:border-slate-800 hover:shadow-lg transition-shadow" data-testid={`affiliate-perk-${i}`}>
                <CardContent className="p-6">
                  <div className="w-11 h-11 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center mb-4">
                    <p.icon className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="font-bold text-base text-slate-900 dark:text-white mb-2">{p.title}</h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">{p.body}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-16 px-4 bg-white dark:bg-slate-900/40 border-y border-slate-200 dark:border-slate-800">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white mb-8">{c.howTitle}</h2>
          <ol className="space-y-4">
            {c.steps.map((step, i) => (
              <li key={i} className="flex items-start gap-4" data-testid={`affiliate-step-${i}`}>
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 text-white flex items-center justify-center font-bold text-sm">
                  {i + 1}
                </div>
                <p className="text-slate-700 dark:text-slate-300 pt-1">{step}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-16 px-4">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white mb-8">{c.faqTitle}</h2>
          <div className="space-y-4">
            {c.faqs.map((f, i) => (
              <details key={i} className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50" data-testid={`affiliate-faq-${i}`}>
                <summary className="cursor-pointer p-4 font-semibold text-slate-900 dark:text-white">{f.q}</summary>
                <p className="px-4 pb-4 text-sm text-slate-600 dark:text-slate-400 leading-relaxed">{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="py-16 px-4 bg-gradient-to-r from-cyan-600 to-blue-700 text-white">
        <div className="max-w-4xl mx-auto text-center">
          <Users className="h-10 w-10 mx-auto mb-3 opacity-90" />
          <h2 className="text-3xl font-bold mb-3">{lang === 'fr' ? 'Prêt à démarrer?' : 'Ready to start earning?'}</h2>
          <p className="text-cyan-50 mb-6">{c.subtitle}</p>
          <Button
            size="lg"
            className="bg-white text-cyan-700 hover:bg-slate-100 h-12 px-8 text-base font-bold"
            onClick={() => navigate(heroCtaTarget)}
            data-testid="affiliate-footer-cta"
          >
            {heroCtaLabel}
            <ArrowRight className="h-5 w-5 ml-2" />
          </Button>
          <p className="text-xs text-cyan-100 mt-4">
            {lang === 'fr' ? 'Déjà membre? ' : 'Already a member? '}
            <LangLink to="/affiliate" className="underline hover:text-white">
              {lang === 'fr' ? 'Ouvrez votre tableau de bord' : 'Open your dashboard'}
            </LangLink>
          </p>
        </div>
      </section>
    </div>
  );
}
