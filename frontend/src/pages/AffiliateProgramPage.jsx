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
    title: "Affiliate Center",
    subtitle: "Share, refer, and earn commissions.",
    heroCta: "Join the program",
    dashboardCta: "Open my Affiliate Center",
    lifetimeChip: "Lifetime attribution — no 12-month cutoff",
    commissionHeadline: "3% of BidVex's net platform profit — for life.",
    commissionExplain: "You earn 3% of BidVex's net platform profit generated from every transaction (auction fees and subscriptions) made by users you refer, for life.",
    trackingCookie: "Attribution cookie: 30 days",
    whyTitle: "Why partner with BidVex",
    perks: [
      { icon: DollarSign, title: "3% net profit share, for life", body: "You earn 3% of BidVex's net platform profit generated from every transaction (auction fees + subscriptions) made by users you refer. No 12-month expiry — it's for life." },
      { icon: TrendingUp, title: "Real-time tracking", body: "Live earnings dashboard, monthly + lifetime views, projected next-month payout, downloadable commission ledger, and instant referral analytics." },
      { icon: ShieldCheck, title: "Stripe Connect payouts", body: "Monthly Stripe Connect payouts direct to your bank. Minimum $25 CAD; anything below rolls forward. Manage bank info from the dashboard." },
      { icon: BarChart3, title: "Marketing kit", body: "Branded banners, unique short-links (/r/{code}), deep-link generators for TikTok / Instagram / Twitter, and a dedicated partner Slack." },
    ],
    howTitle: "How it works — 3 steps",
    steps: [
      { title: "Share", body: "Send your unique referral link. The tracking cookie stays active on visitors' devices for 30 days after the first click." },
      { title: "They buy", body: "Your referred users purchase BidVex subscriptions or complete auctions." },
      { title: "Get paid", body: "Receive 3% of BidVex's net platform profit generated from every transaction completed by your referrals — for life." },
    ],
    faqTitle: "Frequently asked questions",
    faqs: [
      { q: "Who can join?", a: "Anyone with an audience — content creators, industry blogs, dealer associations, brokers, and regional influencers. We manually approve applications to keep the network high-quality." },
      { q: "When do I get paid?", a: "Monthly, on the 1st, via Stripe Connect direct deposit. Minimum payout is $25 CAD; unpaid amounts roll to the next month." },
      { q: "How long does attribution last?", a: "For life. There is no 12-month cutoff. Every referred user is attributed to you permanently, and you earn on every transaction they ever complete." },
      { q: "What exactly does '3% of net platform profit' mean?", a: "For each transaction your referral completes (an auction win or a paid subscription), we take BidVex's platform fee, deduct payment-processor costs and refunds, and pay you 3% of what remains. The commission event and calculation are visible in your dashboard ledger." },
      { q: "Is there an exclusivity clause?", a: "No. You can promote competing platforms; we only ask that you disclose the BidVex partnership per FTC/Canadian consumer-protection rules." },
    ],
    trustedBy: "Trusted by 400+ Canadian affiliates already earning with BidVex",
  },
  fr: {
    title: "Centre d'affiliation",
    subtitle: "Partagez, référez et gagnez des commissions.",
    heroCta: "Rejoindre le programme",
    dashboardCta: "Ouvrir mon centre d'affiliation",
    lifetimeChip: "Attribution à vie — aucune limite de 12 mois",
    commissionHeadline: "3% du profit net de BidVex — à vie.",
    commissionExplain: "Vous gagnez 3% du profit net de la plateforme BidVex généré sur chaque transaction (frais d'enchères et abonnements) réalisée par les utilisateurs que vous référez, à vie.",
    trackingCookie: "Témoin d'attribution : 30 jours",
    whyTitle: "Pourquoi devenir partenaire BidVex",
    perks: [
      { icon: DollarSign, title: "3% du profit net, à vie", body: "Vous gagnez 3% du profit net de la plateforme BidVex généré sur chaque transaction (frais d'enchères + abonnements) réalisée par vos utilisateurs référés. Sans limite de 12 mois — c'est à vie." },
      { icon: TrendingUp, title: "Suivi en temps réel", body: "Tableau de bord en direct, vues mensuelles et à vie, versement projeté du mois prochain, registre de commissions téléchargeable et analyses instantanées." },
      { icon: ShieldCheck, title: "Versements Stripe Connect", body: "Versements mensuels par Stripe Connect directement à votre banque. Minimum 25 $ CAD; le reste se reporte. Gérez votre banque depuis le tableau de bord." },
      { icon: BarChart3, title: "Trousse marketing", body: "Bannières de marque, liens courts uniques (/r/{code}), générateur de liens profonds (TikTok / Instagram / X) et canal Slack dédié aux partenaires." },
    ],
    howTitle: "Comment ça fonctionne — 3 étapes",
    steps: [
      { title: "Partagez", body: "Envoyez votre lien de référence unique. Le témoin de suivi reste actif sur les appareils des visiteurs pendant 30 jours après le premier clic." },
      { title: "Ils achètent", body: "Vos utilisateurs référés achètent des abonnements BidVex ou remportent des enchères." },
      { title: "Vous êtes payé", body: "Recevez 3% du profit net de BidVex généré sur chaque transaction complétée par vos référés — à vie." },
    ],
    faqTitle: "Foire aux questions",
    faqs: [
      { q: "Qui peut se joindre?", a: "Toute personne avec une audience — créateurs, blogues industriels, associations de concessionnaires, courtiers et influenceurs régionaux. Nous approuvons manuellement pour garantir la qualité." },
      { q: "Quand suis-je payé(e)?", a: "Mensuellement, le 1er, par Stripe Connect (dépôt direct). Le seuil minimal est 25 CAD; les montants inférieurs se reportent." },
      { q: "Quelle est la durée d'attribution?", a: "À vie. Aucune coupure à 12 mois. Chaque utilisateur référé vous est attribué de façon permanente et vous gagnez sur chacune de ses transactions futures." },
      { q: "Que signifie exactement « 3% du profit net de la plateforme »?", a: "Pour chaque transaction complétée par votre référé (une enchère remportée ou un abonnement payé), nous prenons les frais de plateforme de BidVex, déduisons les coûts de traitement et les remboursements, et vous versons 3% du reste. Chaque événement de commission et son calcul sont visibles dans le registre du tableau de bord." },
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
            {c.lifetimeChip}
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-slate-900 dark:text-white mb-4" data-testid="affiliate-title">
            {c.title}
          </h1>
          <p className="text-lg text-slate-600 dark:text-slate-300 mb-3 max-w-3xl" data-testid="affiliate-subtitle">
            {c.subtitle}
          </p>
          <p className="text-2xl sm:text-3xl font-bold text-cyan-700 dark:text-cyan-300 mb-2" data-testid="affiliate-commission-headline">
            {c.commissionHeadline}
          </p>
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-8 max-w-3xl" data-testid="affiliate-commission-explain">
            {c.commissionExplain}
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
              {c.trackingCookie} · {c.trustedBy}
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

      {/* How it works — 3 steps with title + body */}
      <section className="py-16 px-4 bg-white dark:bg-slate-900/40 border-y border-slate-200 dark:border-slate-800">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white mb-8">{c.howTitle}</h2>
          <ol className="space-y-6">
            {c.steps.map((step, i) => (
              <li key={i} className="flex items-start gap-4" data-testid={`affiliate-step-${i}`}>
                <div className="flex-shrink-0 w-9 h-9 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 text-white flex items-center justify-center font-bold text-sm">
                  {i + 1}
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-white mb-1">{step.title}</h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">{step.body}</p>
                </div>
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
