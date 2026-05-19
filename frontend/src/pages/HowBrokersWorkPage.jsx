/**
 * iter217 Phase 5 Hotfix v7 — Public "How Brokers Work" landing page.
 *
 * Routes (mounted in App.js):
 *   • /how-brokers-work               (EN default)
 *   • /comment-fonctionnent-les-courtiers  (FR default)
 * Both routes render the same component; the user's i18n language
 * decides the rendered copy and the language toggle swaps between
 * them.  JSON-LD FAQ schema is injected for Google SEO.
 *
 * Live calculator powers off  POST /api/brokers/{id}/fee-preview
 * with a synthetic "no broker yet" fallback that mirrors the engine
 * locally so the page works without an account.
 */
import React, { useEffect, useState, useMemo } from 'react';
import { Helmet } from 'react-helmet-async';
import { useTranslation } from 'react-i18next';
import { useNavigate, useLocation } from 'react-router-dom';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../components/ui/select';
import { Slider } from '../components/ui/slider';
import {
  Accordion, AccordionItem, AccordionTrigger, AccordionContent,
} from '../components/ui/accordion';
import {
  ShieldCheck, FileCheck2, Sparkles, UserCheck, Handshake, Gavel,
  Award, Receipt, CreditCard, KeyRound, ArrowRight, Scale,
} from 'lucide-react';

const _fmt = (n) => new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(n || 0));

// Local copy of the v7 fee engine — pure, no API needed
const PLATFORM_FEE_RATE = 0.025;
const GST_RATE          = 0.05;
const QST_RATE          = 0.09975;
const STRIPE_PCT        = 0.029;
const STRIPE_FIXED      = 0.30;

function computeBreakdown({ hammer, province, feeType, feeValue }) {
  const h           = Math.max(0, Number(hammer) || 0);
  const platform    = h * PLATFORM_FEE_RATE;
  const broker      = feeType === 'percentage'
    ? h * (Number(feeValue) || 0) / 100
    : Number(feeValue) || 0;
  const subtotal    = platform + broker;
  const gst         = subtotal * GST_RATE;
  const qst         = (province === 'QC') ? subtotal * QST_RATE : 0;
  const stripeSub   = subtotal + gst + qst;
  const stripeGross = stripeSub > 0 ? (stripeSub + STRIPE_FIXED) / (1 - STRIPE_PCT) : 0;
  const stripeFee   = stripeGross - stripeSub;
  return {
    hammer:        +h.toFixed(2),
    platform:      +platform.toFixed(2),
    broker:        +broker.toFixed(2),
    subtotal:      +subtotal.toFixed(2),
    gst:           +gst.toFixed(2),
    qst:           +qst.toFixed(2),
    stripeFee:     +stripeFee.toFixed(2),
    stripeTotal:   +stripeGross.toFixed(2),
    totalCost:     +(stripeGross + h).toFixed(2),
    deposit:       500,
  };
}

const STEPS = [
  { icon: FileCheck2,  key: 'broker_joins' },
  { icon: ShieldCheck, key: 'admin_verifies' },
  { icon: UserCheck,   key: 'you_find' },
  { icon: Handshake,   key: 'you_request' },
  { icon: Award,       key: 'broker_accepts' },
  { icon: Gavel,       key: 'you_authorize' },
  { icon: Receipt,     key: 'auction_closes' },
  { icon: CreditCard,  key: 'two_payments' },
  { icon: KeyRound,    key: 'vehicle_release' },
];

const STEP_COPY = {
  en: {
    broker_joins:    { t: 'Broker Joins BidVex',                d: 'A licensed dealer or broker subscribes to BidVex, uploads their license documents, and sets their service fee structure.' },
    admin_verifies:  { t: 'Admin Verification',                 d: 'BidVex admin verifies the broker\'s license within 24-48 hours. Verified brokers appear in our public directory with a green checkmark.' },
    you_find:        { t: 'You Find a Broker',                  d: 'Browse verified brokers in your province. See their fee structure, star rating, and number of completed transactions before you choose.' },
    you_request:     { t: 'You Request a Partnership',          d: 'Click "Request Partnership." A $500 security deposit is held (not charged) on your card as a good-faith commitment. It is released after your vehicle is handed over.' },
    broker_accepts:  { t: 'Broker Accepts You',                 d: 'Your broker reviews and accepts your request. The partnership is now active. Your broker can bid on your behalf.' },
    you_authorize:   { t: 'You Authorize a Bid',                d: 'Tell your broker the maximum amount you\'re willing to pay. The broker places a proxy bid on your behalf. They are the legal bidder of record.' },
    auction_closes:  { t: 'Auction Closes — You Win',           d: 'The hammer falls. BidVex instantly generates a detailed invoice showing exactly what you owe and to whom.' },
    two_payments:    { t: 'Two Separate Payments',              d: 'You pay BidVex\'s platform fee + your broker\'s service fee via Stripe (one secure checkout). You pay the vehicle hammer price directly to your broker via bank wire or certified cheque. BidVex never touches the vehicle price.' },
    vehicle_release: { t: 'Vehicle Release',                    d: 'Once your broker confirms full payment, you receive an 8-character pickup code. Show it at the seller\'s location with your ID. The car is yours.' },
  },
  fr: {
    broker_joins:    { t: 'Le courtier rejoint BidVex',         d: 'Un concessionnaire ou courtier licencié s\'abonne à BidVex, téléverse ses documents de permis et définit sa structure de frais.' },
    admin_verifies:  { t: 'Vérification administrative',        d: 'L\'équipe BidVex vérifie le permis du courtier dans les 24 à 48 heures. Les courtiers vérifiés apparaissent dans notre répertoire public avec un crochet vert.' },
    you_find:        { t: 'Vous trouvez un courtier',           d: 'Parcourez les courtiers vérifiés de votre province. Consultez leur structure de frais, leur note et leur nombre de transactions complétées avant de choisir.' },
    you_request:     { t: 'Vous demandez un partenariat',       d: 'Cliquez sur « Demander un partenariat ». Une caution de 500 $ est retenue (non débitée) sur votre carte en gage de bonne foi. Elle est libérée après la remise du véhicule.' },
    broker_accepts:  { t: 'Le courtier vous accepte',           d: 'Votre courtier examine votre demande et l\'accepte. Le partenariat est maintenant actif. Votre courtier peut enchérir en votre nom.' },
    you_authorize:   { t: 'Vous autorisez une enchère',         d: 'Indiquez à votre courtier le montant maximal que vous êtes prêt à payer. Le courtier place une enchère par procuration en votre nom. Il est l\'enchérisseur officiel.' },
    auction_closes:  { t: 'L\'enchère ferme — Vous gagnez',     d: 'Le marteau tombe. BidVex génère instantanément une facture détaillée indiquant exactement ce que vous devez et à qui.' },
    two_payments:    { t: 'Deux paiements distincts',           d: 'Vous payez les frais de plateforme BidVex + les frais de service de votre courtier via Stripe (un seul paiement sécurisé). Vous payez le prix marteau du véhicule directement à votre courtier par virement bancaire ou chèque certifié. BidVex ne touche jamais au prix du véhicule.' },
    vehicle_release: { t: 'Remise du véhicule',                 d: 'Une fois que votre courtier a confirmé le paiement complet, vous recevez un code de retrait de 8 caractères. Présentez-le sur le lieu de remise avec votre pièce d\'identité. La voiture est à vous.' },
  },
};

const FAQS = {
  en: [
    { q: 'Why can\'t I bid directly on vehicles?',
      a: 'Provincial laws (OPC/SAAQ in Quebec, OMVIC in Ontario, AMVIC in Alberta, VSA in BC) restrict wholesale and restricted vehicle auctions to licensed dealers. An individual buyer cannot legally close such a transaction. A licensed broker is the legally compliant solution.' },
    { q: 'Is my $500 deposit refundable?',
      a: 'Yes — the $500 is an authorization hold, not a charge. It is automatically released after your vehicle handoff (5-7 business days). The only cases where it is captured are documented buyer abandonment, non-payment of broker fees within 72 hours, or fraud.' },
    { q: 'How is the broker\'s fee set?',
      a: 'Each broker sets their own fee in their profile — either a flat amount (e.g., $500 per vehicle) or a percentage (e.g., 3% of the hammer price). The exact amount is shown to you BEFORE you request the partnership, with full taxes itemized.' },
    { q: 'Does BidVex handle the vehicle\'s money?',
      a: 'No. BidVex is a software marketplace, not a financial intermediary. The hammer price is paid directly from you to the broker via bank wire, certified cheque, or broker trust account. BidVex\'s Stripe only processes the service fees (platform + broker fee + taxes).' },
    { q: 'What happens if I win but change my mind?',
      a: 'You have a binding obligation once your authorized bid wins. If you fail to pay your broker\'s service fees within 72 hours, your $500 deposit is captured as liquidated damages and the listing may be re-auctioned. We recommend setting realistic max-bid amounts.' },
    { q: 'Which provinces does BidVex operate in?',
      a: 'BidVex is a Canadian marketplace headquartered in Sherbrooke, Quebec. We work with brokers licensed by OMVIC (Ontario), OPC/SAAQ (Quebec), AMVIC (Alberta), VSA (British Columbia), and equivalent regulators in other provinces. Each broker only serves the province(s) they are licensed in.' },
  ],
  fr: [
    { q: 'Pourquoi ne puis-je pas enchérir directement sur les véhicules ?',
      a: 'Les lois provinciales (OPC/SAAQ au Québec, OMVIC en Ontario, AMVIC en Alberta, VSA en Colombie-Britannique) réservent les enchères de véhicules en gros aux concessionnaires licenciés. Un acheteur individuel ne peut légalement conclure une telle transaction. Un courtier licencié est la solution légalement conforme.' },
    { q: 'Ma caution de 500 $ est-elle remboursable ?',
      a: 'Oui — les 500 $ sont une retenue d\'autorisation, pas un débit. Elle est libérée automatiquement après la remise du véhicule (5 à 7 jours ouvrables). Les seuls cas de prélèvement sont l\'abandon documenté de l\'acheteur, le non-paiement des frais du courtier dans les 72 heures ou la fraude.' },
    { q: 'Comment les frais du courtier sont-ils fixés ?',
      a: 'Chaque courtier fixe ses propres frais dans son profil — soit un montant fixe (p. ex. 500 $ par véhicule), soit un pourcentage (p. ex. 3 % du prix marteau). Le montant exact vous est présenté AVANT que vous ne demandiez le partenariat, avec toutes les taxes détaillées.' },
    { q: 'BidVex gère-t-il l\'argent du véhicule ?',
      a: 'Non. BidVex est une plateforme logicielle, pas un intermédiaire financier. Le prix marteau est payé directement de vous au courtier par virement bancaire, chèque certifié ou compte en fiducie. Le Stripe de BidVex ne traite que les frais de service (plateforme + courtier + taxes).' },
    { q: 'Que se passe-t-il si je gagne mais change d\'avis ?',
      a: 'Vous avez une obligation contractuelle dès que votre enchère gagne. Si vous ne payez pas les frais de service du courtier dans les 72 heures, votre caution de 500 $ est prélevée à titre de dommages-intérêts et l\'annonce peut être remise aux enchères. Nous recommandons de fixer des montants maximaux réalistes.' },
    { q: 'Dans quelles provinces BidVex opère-t-il ?',
      a: 'BidVex est une plateforme canadienne dont le siège est à Sherbrooke, au Québec. Nous travaillons avec des courtiers licenciés par OMVIC (Ontario), OPC/SAAQ (Québec), AMVIC (Alberta), VSA (Colombie-Britannique) et leurs équivalents dans les autres provinces. Chaque courtier ne dessert que la ou les provinces où il est licencié.' },
  ],
};

export default function HowBrokersWorkPage() {
  const { i18n, t: tt } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const isFR = location.pathname.startsWith('/comment-fonctionnent') || i18n.language?.startsWith('fr');
  const lang = isFR ? 'fr' : 'en';

  // Sync URL with i18n language on first load
  useEffect(() => {
    if (isFR && i18n.language !== 'fr') i18n.changeLanguage('fr');
    if (!isFR && i18n.language === 'fr' && location.pathname === '/how-brokers-work') {
      // intentional — let user stay on EN URL even if global lang is FR
    }
  }, []);   // run once on mount

  // ── Calculator state ────────────────────────────────────────────
  const [hammer,   setHammer]   = useState(15000);
  const [province, setProvince] = useState('QC');
  const [feeType,  setFeeType]  = useState('fixed');
  const [feeValue, setFeeValue] = useState(500);
  const breakdown = useMemo(
    () => computeBreakdown({ hammer, province, feeType, feeValue }),
    [hammer, province, feeType, feeValue],
  );

  // ── JSON-LD for SEO ────────────────────────────────────────────
  const faqLd = {
    "@context": "https://schema.org",
    "@type":    "FAQPage",
    "mainEntity": FAQS[lang].map((f) => ({
      "@type": "Question",
      "name": f.q,
      "acceptedAnswer": { "@type": "Answer", "text": f.a },
    })),
  };

  const T = {
    title:       isFR ? 'Comment fonctionnent les courtiers — BidVex' : 'How Brokers Work — BidVex',
    description: isFR
      ? 'Au Canada, l\'achat d\'un véhicule aux enchères restreintes nécessite un courtier licencié. Voici comment BidVex vous y aide légalement.'
      : 'In Canada, buying a vehicle from restricted auctions requires a licensed broker. Here\'s how BidVex helps you do it legally and transparently.',
    heroH1:      isFR ? 'Achetez aux enchères sans permis de concessionnaire' : 'Buy at Auction Without a Dealer License',
    heroSub:     isFR
      ? 'Au Canada, l\'achat d\'un véhicule aux enchères restreintes nécessite un permis de concessionnaire. BidVex vous met en contact avec des courtiers licenciés vérifiés qui enchérissent en votre nom — légalement, en toute transparence et à bon prix.'
      : 'In Canada, purchasing a vehicle from a wholesale or restricted auction requires a licensed dealer. BidVex connects you with verified, licensed brokers who bid on your behalf — legally, transparently, and affordably.',
    findBroker:  isFR ? 'Trouver un courtier' : 'Find a Broker',
    becomeBroker:isFR ? 'Devenir courtier' : 'Become a Broker',

    why_title:   isFR ? 'Pourquoi un courtier est-il requis' : 'Why a Broker Is Required',
    why_law_t:   isFR ? 'La loi' : 'The Law',
    why_law_d:   isFR ? 'Les lois provinciales (OPC/SAAQ au Québec, OMVIC en Ontario, AMVIC en Alberta) exigent que seuls les concessionnaires licenciés puissent acheter aux enchères en gros. Les acheteurs individuels ne peuvent pas enchérir directement.'
                      : 'Provincial laws (OPC/SAAQ in Quebec, OMVIC in Ontario, AMVIC in Alberta) require that only licensed dealers may buy from wholesale auctions. Individual buyers cannot bid directly.',
    why_prot_t:  isFR ? 'Votre protection' : 'Your Protection',
    why_prot_d:  isFR ? 'Votre courtier est licencié, réglementé et redevable à son organisme provincial. Il est légalement responsable de la transaction — pas BidVex, ni vous seul.'
                      : 'Your broker is licensed, regulated, and accountable to their provincial regulator. They are legally responsible for the transaction — not BidVex, and not you alone.',
    why_trans_t: isFR ? 'Transparence totale' : 'Full Transparency',
    why_trans_d: isFR ? 'Tous les frais du courtier sont affichés avant que vous ne vous engagiez. Aucune surprise à la conclusion. BidVex génère une facture PDF signée pour chaque transaction.'
                      : 'All broker fees are displayed before you commit. No surprises at closing. BidVex generates a signed PDF invoice for every transaction.',

    steps_title: isFR ? 'Le parcours en 9 étapes' : 'The 9-Step Visual Flow',
    calc_title:  isFR ? 'Calculateur de frais en direct' : 'Live Fee Calculator',
    calc_disclaimer: isFR
      ? 'Le prix marteau du véhicule est toujours réglé directement entre vous et votre courtier. BidVex ne traite que les frais de service affichés ci-dessus. Cela maintient votre transaction conforme aux règlements provinciaux canadiens sur les concessionnaires.'
      : 'The vehicle hammer price is always settled directly between you and your broker. BidVex only processes the service fees shown above. This keeps your transaction compliant with Canadian provincial dealer regulations.',
    becomeCta_h: isFR ? 'Êtes-vous un courtier ou un concessionnaire licencié ?' : 'Are You a Licensed Broker or Dealer?',
    becomeCta_d: isFR
      ? 'Rejoignez BidVex pour 100 $/an (tarification de lancement) et entrez en contact avec des acheteurs individuels qui ont besoin d\'un professionnel licencié pour les représenter aux enchères. Fixez vos propres frais. Bâtissez votre réputation. Développez votre entreprise.'
      : 'Join BidVex for $100/year (launch pricing) and connect with individual buyers who need a licensed professional to represent them at auction. Set your own fees. Build your reputation. Grow your business.',
    becomeCta_btn: isFR ? 'Devenir courtier — 100 $/an' : 'Become a Broker — $100/year',
    faq_title:    isFR ? 'Foire aux questions' : 'Frequently Asked Questions',
  };

  return (
    <div className="bg-gradient-to-b from-[#0F172A] via-[#1E293B] to-[#0F172A] text-white min-h-screen pb-16">
      <Helmet>
        <title>{T.title}</title>
        <meta name="description" content={T.description} />
        <link rel="canonical" href={isFR
          ? "https://bidvex.com/comment-fonctionnent-les-courtiers"
          : "https://bidvex.com/how-brokers-work"} />
        <link rel="alternate" hrefLang="en" href="https://bidvex.com/how-brokers-work" />
        <link rel="alternate" hrefLang="fr" href="https://bidvex.com/comment-fonctionnent-les-courtiers" />
        <script type="application/ld+json">{JSON.stringify(faqLd)}</script>
      </Helmet>

      {/* Language toggle in top right */}
      <div className="container mx-auto max-w-6xl px-4 pt-6 flex justify-end">
        <div className="flex gap-2 bg-white/5 backdrop-blur rounded-full p-1 border border-white/10" data-testid="hbw-lang-toggle">
          <button
            className={`px-3 py-1 rounded-full text-xs font-semibold ${!isFR ? 'bg-cyan-500 text-slate-900' : 'text-slate-300'}`}
            onClick={() => navigate('/how-brokers-work')}
            data-testid="hbw-lang-en"
          >EN</button>
          <button
            className={`px-3 py-1 rounded-full text-xs font-semibold ${isFR ? 'bg-cyan-500 text-slate-900' : 'text-slate-300'}`}
            onClick={() => navigate('/comment-fonctionnent-les-courtiers')}
            data-testid="hbw-lang-fr"
          >FR</button>
        </div>
      </div>

      {/* ── HERO ─────────────────────────────────────────────── */}
      <section className="container mx-auto max-w-5xl px-4 pt-10 pb-16 text-center" data-testid="hbw-hero">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-300 text-xs font-semibold border border-cyan-500/30 mb-6">
          <Scale className="h-3.5 w-3.5" />
          {isFR ? 'Plateforme conforme — Québec, Ontario, Alberta, C.-B.' : 'Compliant Platform — Quebec, Ontario, Alberta, BC'}
        </div>
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight" data-testid="hbw-h1">
          {T.heroH1}
        </h1>
        <p className="mt-6 text-base sm:text-lg text-slate-300 max-w-3xl mx-auto leading-relaxed">
          {T.heroSub}
        </p>
        <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
          <Button
            size="lg"
            onClick={() => navigate('/brokers')}
            className="bg-gradient-to-r from-cyan-400 to-blue-500 text-slate-900 font-semibold hover:opacity-90"
            data-testid="hbw-cta-find"
          >
            {T.findBroker} <ArrowRight className="h-4 w-4 ml-1.5" />
          </Button>
          <Button
            size="lg"
            variant="outline"
            onClick={() => navigate('/become-a-broker')}
            className="border-white/30 text-white hover:bg-white/10"
            data-testid="hbw-cta-become"
          >
            {T.becomeBroker}
          </Button>
        </div>
      </section>

      {/* ── WHY (3 cards) ────────────────────────────────────── */}
      <section className="container mx-auto max-w-6xl px-4 pb-16">
        <h2 className="text-2xl sm:text-3xl font-bold text-center mb-10">{T.why_title}</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {[
            { Icon: Scale,       t: T.why_law_t,   d: T.why_law_d   },
            { Icon: ShieldCheck, t: T.why_prot_t,  d: T.why_prot_d  },
            { Icon: Sparkles,    t: T.why_trans_t, d: T.why_trans_d },
          ].map((c, i) => (
            <Card key={i} className="bg-white/5 border-white/10 hover:border-cyan-500/40 transition-colors">
              <CardContent className="p-6">
                <c.Icon className="h-7 w-7 text-cyan-400 mb-3" />
                <h3 className="font-semibold text-lg mb-2">{c.t}</h3>
                <p className="text-sm text-slate-300 leading-relaxed">{c.d}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* ── 9 STEPS timeline ─────────────────────────────────── */}
      <section className="container mx-auto max-w-4xl px-4 pb-20" data-testid="hbw-steps">
        <h2 className="text-2xl sm:text-3xl font-bold text-center mb-12">{T.steps_title}</h2>
        <div className="relative">
          <div className="absolute left-7 top-2 bottom-2 w-0.5 bg-gradient-to-b from-cyan-500/50 via-blue-500/30 to-transparent hidden sm:block"></div>
          <ol className="space-y-6">
            {STEPS.map(({ icon: Icon, key }, i) => (
              <li key={key} className="relative flex gap-4" data-testid={`hbw-step-${i+1}`}>
                <div className="flex-shrink-0 w-14 h-14 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-slate-900 font-bold shadow-lg shadow-cyan-500/30">
                  <Icon className="h-6 w-6" />
                </div>
                <div className="flex-1 pt-1">
                  <p className="text-xs font-semibold tracking-wider text-cyan-400 mb-1">
                    {isFR ? `ÉTAPE ${i+1}` : `STEP ${i+1}`}
                  </p>
                  <h3 className="font-semibold text-lg">{STEP_COPY[lang][key].t}</h3>
                  <p className="text-sm text-slate-300 mt-1 leading-relaxed">{STEP_COPY[lang][key].d}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ── LIVE CALCULATOR ──────────────────────────────────── */}
      <section className="container mx-auto max-w-5xl px-4 pb-16" data-testid="hbw-calc">
        <h2 className="text-2xl sm:text-3xl font-bold text-center mb-3">{T.calc_title}</h2>
        <p className="text-center text-sm text-slate-400 mb-8">
          {isFR ? 'Estimez votre coût total en temps réel' : 'Estimate your total cost in real time'}
        </p>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Inputs */}
          <Card className="bg-white/5 border-white/10">
            <CardContent className="p-6 space-y-5">
              <div>
                <Label className="text-sm text-slate-300">{isFR ? 'Prix du véhicule' : 'Vehicle price'}: <strong className="text-white">{_fmt(hammer)}</strong></Label>
                <Slider min={5000} max={100000} step={1000} value={[hammer]} onValueChange={(v) => setHammer(v[0])} className="mt-3" data-testid="calc-hammer-slider" />
              </div>
              <div>
                <Label className="text-sm text-slate-300">{isFR ? 'Province de l\'acheteur' : 'Buyer province'}</Label>
                <Select value={province} onValueChange={setProvince}>
                  <SelectTrigger className="bg-white/5 border-white/20 text-white mt-1" data-testid="calc-province"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="QC">Quebec / Québec</SelectItem>
                    <SelectItem value="ON">Ontario</SelectItem>
                    <SelectItem value="AB">Alberta</SelectItem>
                    <SelectItem value="BC">British Columbia / C.-B.</SelectItem>
                    <SelectItem value="OTHER">{isFR ? 'Autre' : 'Other'}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-sm text-slate-300">{isFR ? 'Type de frais' : 'Fee type'}</Label>
                  <Select value={feeType} onValueChange={(v) => { setFeeType(v); setFeeValue(v === 'fixed' ? 500 : 3); }}>
                    <SelectTrigger className="bg-white/5 border-white/20 text-white mt-1" data-testid="calc-fee-type"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="fixed">{isFR ? 'Fixe ($)' : 'Fixed ($)'}</SelectItem>
                      <SelectItem value="percentage">{isFR ? 'Pourcentage (%)' : 'Percentage (%)'}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-sm text-slate-300">{isFR ? 'Valeur' : 'Value'}</Label>
                  <Input type="number" min="0" step={feeType === 'percentage' ? 0.1 : 50} value={feeValue}
                         onChange={(e) => setFeeValue(Number(e.target.value) || 0)}
                         className="bg-white/5 border-white/20 text-white mt-1" data-testid="calc-fee-value" />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Output */}
          <Card className="bg-gradient-to-br from-cyan-500/10 to-blue-600/10 border-cyan-500/30">
            <CardContent className="p-6">
              <p className="text-xs uppercase tracking-wider text-cyan-300 font-semibold mb-3">
                {isFR ? 'Estimation détaillée' : 'Your Estimated Cost Breakdown'}
              </p>
              <Row label={isFR ? 'Prix marteau du véhicule (direct)' : 'Vehicle Hammer Price (direct)'} value={_fmt(breakdown.hammer)} accent />
              <hr className="border-white/10 my-2" />
              <Row label={isFR ? 'Frais de plateforme BidVex' : 'BidVex Platform Fee'}      value={_fmt(breakdown.platform)} />
              <Row label={isFR ? 'Frais de service du courtier' : 'Broker Service Fee'}     value={_fmt(breakdown.broker)} />
              <Row label="GST (5%)"                                                          value={_fmt(breakdown.gst)} />
              <Row label={`QST (9.975%) ${province === 'QC' ? '' : (isFR ? '(QC uniquement)' : '(QC only)')}`} value={_fmt(breakdown.qst)} muted={province !== 'QC'} />
              <Row label={isFR ? 'Frais Stripe' : 'Stripe Processing Fee'}                  value={_fmt(breakdown.stripeFee)} />
              <hr className="border-white/10 my-2" />
              <Row label={isFR ? 'Vous payez via Stripe' : 'You pay via Stripe'}             value={_fmt(breakdown.stripeTotal)} bold testId="calc-stripe-total" />
              <Row label={isFR ? 'Vous payez directement au courtier' : 'You pay broker directly'} value={_fmt(breakdown.hammer)} bold testId="calc-direct" />
              <hr className="border-cyan-500/40 my-2" />
              <Row label={isFR ? 'Coût total' : 'Total Cost'}                                value={_fmt(breakdown.totalCost)} big testId="calc-total" />
              <p className="text-[11px] text-slate-400 mt-3">
                + {_fmt(breakdown.deposit)} {isFR ? 'caution remboursable' : 'refundable security deposit'}
              </p>
            </CardContent>
          </Card>
        </div>
        <p className="text-xs text-slate-400 mt-5 max-w-3xl mx-auto text-center leading-relaxed">
          {T.calc_disclaimer}
        </p>
      </section>

      {/* ── BECOME A BROKER CTA ──────────────────────────────── */}
      <section className="container mx-auto max-w-4xl px-4 pb-16">
        <Card className="bg-gradient-to-r from-amber-500/10 to-orange-500/10 border-amber-500/30">
          <CardContent className="p-8 text-center">
            <h2 className="text-2xl sm:text-3xl font-bold">{T.becomeCta_h}</h2>
            <p className="text-sm text-slate-300 mt-4 max-w-2xl mx-auto leading-relaxed">{T.becomeCta_d}</p>
            <Button
              size="lg"
              onClick={() => navigate('/become-a-broker')}
              className="mt-6 bg-amber-400 text-slate-900 font-semibold hover:bg-amber-300"
              data-testid="hbw-cta-become-bottom"
            >
              {T.becomeCta_btn} <ArrowRight className="h-4 w-4 ml-1.5" />
            </Button>
          </CardContent>
        </Card>
      </section>

      {/* ── FAQ ──────────────────────────────────────────────── */}
      <section className="container mx-auto max-w-3xl px-4 pb-16" data-testid="hbw-faq">
        <h2 className="text-2xl sm:text-3xl font-bold text-center mb-8">{T.faq_title}</h2>
        <Accordion type="single" collapsible className="space-y-2">
          {FAQS[lang].map((f, i) => (
            <AccordionItem key={i} value={`faq-${i}`} className="bg-white/5 border border-white/10 rounded-lg px-4">
              <AccordionTrigger className="text-left text-base font-semibold hover:no-underline" data-testid={`hbw-faq-q-${i}`}>
                {f.q}
              </AccordionTrigger>
              <AccordionContent className="text-slate-300 text-sm leading-relaxed">
                {f.a}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </section>
    </div>
  );
}

function Row({ label, value, bold, big, accent, muted, testId }) {
  return (
    <div className="flex justify-between items-center py-1" data-testid={testId}>
      <span className={`text-sm ${muted ? 'text-slate-500' : 'text-slate-300'}`}>{label}</span>
      <span className={`tabular-nums ${big ? 'text-2xl font-bold text-white' : bold ? 'font-semibold text-white' : accent ? 'font-semibold text-amber-300' : muted ? 'text-slate-500' : 'text-white'}`}>
        {value}
      </span>
    </div>
  );
}
