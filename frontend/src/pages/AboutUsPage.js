import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { useNavigate } from 'react-router-dom';
import {
  Globe, Zap, ShieldCheck, MapPin, Rocket, User, Building2,
  Mail, Phone, Hash, ChevronRight, Quote
} from 'lucide-react';

const FOUNDER_PHOTO = 'https://customer-assets.emergentagent.com/job_aec91123-f68c-44df-910e-d0f391e2836a/artifacts/5xtfvgc8_image.png';
const CANADA_IMG = 'https://images.unsplash.com/photo-1632857997897-9418428d7368?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA2MjJ8MHwxfHNlYXJjaHwyfHxDYW5hZGElMjBtb2Rlcm4lMjBza3lsaW5lJTIwYXJjaGl0ZWN0dXJlfGVufDB8fHx8MTc3NjQzNzQzOXww&ixlib=rb-4.1.0&q=85';

const content = {
  en: {
    overline: 'ABOUT BIDVEX INC.',
    heroTitle: 'Your World,\nUnder the Gavel',
    heroSub: 'Bringing the Thrill of the Auction to Everyone',
    ctaStart: 'Start Selling',
    ctaLearn: 'How It Works',
    visionTitle: 'A Vision Born from Ambition',
    visionText: 'The story of Bidvex began three years ago when our founder, Charbel Lichaa, arrived in Canada with a bold observation: the power of the auction was reserved for the few, but the need to sell fast was shared by many. He saw incredible Canadian assets\u2014from a family\u2019s garage sale and individual vehicles to heavy-duty farm equipment\u2014and realized that everyone deserves a global stage to sell their items in record time.',
    engTitle: 'Two Years of Precision Engineering',
    engText: 'Trust and speed don\u2019t happen by accident. We spent two years meticulously designing the Bidvex engine to make the \u201cAuctioneer Feeling\u201d accessible to everyone. We didn\u2019t just build a website; we built a high-speed marketplace where you can list today and be sold tomorrow.',
    engBadge: '2 Years Building',
    missionTitle: 'Our Mission: Sold in a Day',
    missionText: 'At Bidvex, we believe that selling should be an adrenaline rush, not a waiting game. Our mission is to democratize the auction. By removing traditional barriers, we\u2019ve created a \u201cWorldwide Marketplace\u201d where a garage sale in Sherbrooke or a dealership in Montreal can conclude a successful sale in just 24 hours. We give you the tools to be your own auctioneer, reaching the world with just a few clicks.',
    persona1Title: 'The Individual Seller',
    persona1Text: 'Feel the excitement of a live auction. Whether it\u2019s a car, a vintage collection, or a one-day garage sale, we make it safe and simple to turn your items into cash.',
    persona2Title: 'The Local Hero',
    persona2Text: 'Reach your neighbors in Quebec or buyers across Canada instantly.',
    persona3Title: 'The Global Player',
    persona3Text: 'Seamlessly connect with markets in Europe, Asia, Africa, and the Middle East when you\u2019re ready to go big.',
    empowerLabel: 'Every feature was developed to empower:',
    canadaTitle: 'Why Canada? The Gold Standard of Trust',
    canadaText: 'Canada is known for integrity and world-class standards. As a Canadian-born company, Bidvex takes that local reliability and applies it to the global stage. When you host an auction on Bidvex, you are trading with the confidence of Canadian excellence and the security of a platform built on local trust.',
    futureTitle: 'The Future is Instant',
    futureText: 'We are just getting started. Our vision includes AI-driven tools and lightning-fast logistics to make \u201cSold on Bidvex\u201d the fastest way to trade on earth. Whether it\u2019s a single item or a massive liquidation, Bidvex is your commitment to speed, ease, and global connectivity.',
    founderTitle: 'Meet Our Founder',
    founderName: 'Charbel Lichaa',
    founderRole: 'CEO & Founder, Bidvex Inc.',
    founderBio: 'Charbel moved to Canada with a passion for innovation and a simple goal: to make the power of the auction available to every individual. After two years of building the Bidvex infrastructure, he ensures the platform remains the fastest, most secure way for you to sell anything, to anyone, anywhere.',
    founderQuote: '\u201cI built Bidvex because I believe everyone should have the power to be an auctioneer. Whether you are clearing out your garage or selling a fleet of vehicles, location and timing should never be a barrier to your success.\u201d',
    credTitle: 'Official Business Credentials',
    credCompany: 'Company Name',
    credFederal: 'Federal Registration Number',
    credNeq: 'NEQ (Quebec)',
    credPhone: 'Phone',
    credEmail: 'Email',
  },
  fr: {
    overline: '\u00c0 PROPOS DE BIDVEX INC.',
    heroTitle: 'Votre monde,\nsous le marteau',
    heroSub: 'L\u2019exc\u00e8s d\u2019ench\u00e8res accessible \u00e0 tous',
    ctaStart: 'Commencer \u00e0 vendre',
    ctaLearn: 'Comment \u00e7a marche',
    visionTitle: 'Une vision n\u00e9e de l\u2019ambition',
    visionText: 'L\u2019histoire de Bidvex a commenc\u00e9 il y a trois ans lorsque notre fondateur, Charbel Lichaa, est arriv\u00e9 au Canada avec un constat simple\u00a0: le pouvoir de l\u2019ench\u00e8re \u00e9tait r\u00e9serv\u00e9 \u00e0 une \u00e9lite, alors que le besoin de vendre rapidement \u00e9tait partag\u00e9 par tous. En voyant la qualit\u00e9 des biens canadiens \u2014 qu\u2019il s\u2019agisse d\u2019une vente de garage familiale, de v\u00e9hicules de particuliers ou d\u2019\u00e9quipement agricole lourd \u2014 il a compris que tout le monde m\u00e9rite une sc\u00e8ne mondiale pour vendre ses articles en un temps record.',
    engTitle: 'Deux ans d\u2019ing\u00e9nierie de pr\u00e9cision',
    engText: 'La confiance et la rapidit\u00e9 ne sont pas le fruit du hasard. Nous avons pass\u00e9 deux ans \u00e0 concevoir m\u00e9ticuleusement le moteur Bidvex pour rendre l\u2019exp\u00e9rience du \u00ab\u00a0commissaire-priseur\u00a0\u00bb accessible \u00e0 tous. Nous n\u2019avons pas seulement construit un site web\u00a0; nous avons cr\u00e9\u00e9 un march\u00e9 ultra-rapide o\u00f9 vous pouvez inscrire votre bien aujourd\u2019hui et le vendre d\u00e8s demain.',
    engBadge: '2 ans de construction',
    missionTitle: 'Notre mission\u00a0: Vendu en un jour',
    missionText: 'Chez Bidvex, nous croyons que la vente doit \u00eatre une source d\u2019adr\u00e9naline, pas une attente interminable. Notre mission est de d\u00e9mocratiser les ench\u00e8res. Nous avons cr\u00e9\u00e9 un \u00ab\u00a0March\u00e9 mondial\u00a0\u00bb o\u00f9 une vente de garage \u00e0 Sherbrooke ou un concessionnaire \u00e0 Montr\u00e9al peut conclure une vente r\u00e9ussie en seulement 24 heures.',
    persona1Title: 'Le vendeur particulier',
    persona1Text: 'Ressentez l\u2019excitation d\u2019une ench\u00e8re en direct. Qu\u2019il s\u2019agisse d\u2019une voiture, d\u2019une collection vintage ou d\u2019une vente de garage d\u2019une journ\u00e9e, nous rendons la conversion de vos objets en argent simple et s\u00e9curis\u00e9e.',
    persona2Title: 'Le h\u00e9ros local',
    persona2Text: 'Rejoignez vos voisins au Qu\u00e9bec ou des acheteurs partout au Canada instantan\u00e9ment.',
    persona3Title: 'L\u2019acteur mondial',
    persona3Text: 'Connectez-vous en toute fluidit\u00e9 avec les march\u00e9s d\u2019Europe, d\u2019Asie, d\u2019Afrique et du Moyen-Orient.',
    empowerLabel: 'Chaque fonctionnalit\u00e9 a \u00e9t\u00e9 d\u00e9velopp\u00e9e pour donner du pouvoir \u00e0\u00a0:',
    canadaTitle: 'Pourquoi le Canada\u00a0? La r\u00e9f\u00e9rence en mati\u00e8re de confiance',
    canadaText: 'Le Canada est reconnu pour son int\u00e9grit\u00e9 et ses normes de classe mondiale. En tant qu\u2019entreprise canadienne, Bidvex applique cette fiabilit\u00e9 locale \u00e0 l\u2019\u00e9chelle mondiale. Lorsque vous organisez une ench\u00e8re sur Bidvex, vous commercez avec la confiance de l\u2019excellence canadienne et la s\u00e9curit\u00e9 d\u2019une plateforme b\u00e2tie sur la confiance locale.',
    futureTitle: 'Le futur est instantan\u00e9',
    futureText: 'Nous ne faisons que commencer. Notre vision inclut des outils pilot\u00e9s par l\u2019IA et une logistique ultra-rapide pour faire de \u00ab\u00a0Vendu sur Bidvex\u00a0\u00bb le moyen le plus rapide de commercer sur terre.',
    founderTitle: 'Rencontrez notre fondateur',
    founderName: 'Charbel Lichaa',
    founderRole: 'PDG et fondateur, Bidvex Inc.',
    founderBio: 'Charbel s\u2019est install\u00e9 au Canada avec une passion pour l\u2019innovation et un objectif simple\u00a0: mettre la puissance des ench\u00e8res \u00e0 la port\u00e9e de chaque individu.',
    founderQuote: '\u00ab\u00a0J\u2019ai cr\u00e9\u00e9 Bidvex parce que je crois que tout le monde devrait avoir le pouvoir d\u2019\u00eatre son propre commissaire-priseur. Que vous vidiez votre garage ou vendiez une flotte de v\u00e9hicules, l\u2019emplacement et le temps ne devraient jamais \u00eatre des obstacles \u00e0 votre succ\u00e8s.\u00a0\u00bb',
    credTitle: 'Informations officielles',
    credCompany: 'Nom de l\u2019entreprise',
    credFederal: 'Enregistrement f\u00e9d\u00e9ral',
    credNeq: 'NEQ (Qu\u00e9bec)',
    credPhone: 'T\u00e9l\u00e9phone',
    credEmail: 'Courriel',
  },
};

const personas = [
  { icon: User, color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-950/40', ring: 'ring-blue-200' },
  { icon: MapPin, color: 'text-emerald-600', bg: 'bg-emerald-50 dark:bg-emerald-950/40', ring: 'ring-emerald-200' },
  { icon: Globe, color: 'text-cyan-600', bg: 'bg-cyan-50 dark:bg-cyan-950/40', ring: 'ring-cyan-200' },
];

const AboutUsPage = () => {
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const [lang, setLang] = useState(i18n.language?.startsWith('fr') ? 'fr' : 'en');
  const t = content[lang];

  const toggleLang = () => {
    const next = lang === 'en' ? 'fr' : 'en';
    setLang(next);
    i18n.changeLanguage(next);
  };

  return (
    <div className="min-h-screen bg-white dark:bg-slate-950" style={{ fontFamily: "'DM Sans', sans-serif" }} data-testid="about-us-page">

      {/* Language Toggle Floating */}
      <div className="sticky top-20 z-30 flex justify-end max-w-7xl mx-auto px-6 md:px-12">
        <Button
          variant="outline"
          size="sm"
          onClick={toggleLang}
          className="rounded-full border-[#1E3A8A] text-[#1E3A8A] hover:bg-[#1E3A8A] hover:text-white transition-all shadow-sm"
          data-testid="about-lang-toggle"
        >
          {lang === 'en' ? 'FR' : 'EN'}
        </Button>
      </div>

      {/* ========== HERO ========== */}
      <section className="relative overflow-hidden" data-testid="about-hero">
        <div className="absolute inset-0 bg-gradient-to-br from-[#1E3A8A]/5 via-transparent to-[#06B6D4]/5" />
        <div className="max-w-7xl mx-auto px-6 md:px-12 pt-16 pb-20 md:pt-24 md:pb-28">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            <div className="space-y-6">
              <p className="uppercase text-xs tracking-[0.2em] font-bold text-[#06B6D4]">{t.overline}</p>
              <h1 className="text-4xl sm:text-5xl lg:text-6xl tracking-tight font-medium text-[#1E3A8A] dark:text-blue-300 whitespace-pre-line leading-[1.1]" style={{ fontFamily: "'Outfit', sans-serif" }}>
                {t.heroTitle}
              </h1>
              <p className="text-lg text-[#64748B] dark:text-slate-400 max-w-lg leading-relaxed">{t.heroSub}</p>
              <div className="flex flex-wrap gap-3 pt-2">
                <Button
                  className="bg-[#1E3A8A] hover:bg-[#1E3A8A]/90 text-white rounded-full px-6"
                  onClick={() => navigate('/create-listing')}
                  data-testid="hero-cta-sell"
                >
                  {t.ctaStart} <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
                <Button
                  variant="outline"
                  className="rounded-full border-[#1E3A8A]/30 text-[#1E3A8A] hover:bg-[#1E3A8A]/5"
                  onClick={() => navigate('/how-it-works')}
                  data-testid="hero-cta-learn"
                >
                  {t.ctaLearn}
                </Button>
              </div>
            </div>
            <div className="relative hidden md:block">
              <div className="absolute -top-8 -right-8 w-64 h-64 bg-[#06B6D4]/10 rounded-full blur-3xl" />
              <div className="absolute bottom-0 left-0 w-48 h-48 bg-[#1E3A8A]/10 rounded-full blur-3xl" />
              <div className="relative z-10 rounded-2xl overflow-hidden shadow-2xl border border-slate-200/50 dark:border-slate-700">
                <img src={CANADA_IMG} alt="Bidvex Global" className="w-full h-80 object-cover" loading="lazy" />
                <div className="absolute inset-0 bg-gradient-to-t from-[#1E3A8A]/40 to-transparent" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========== COMPANY STORY - BENTO GRID ========== */}
      <section className="max-w-7xl mx-auto px-6 md:px-12 py-20 md:py-28" data-testid="about-story">
        <div className="grid md:grid-cols-3 gap-6 md:gap-8">
          {/* Vision Card - spans 2 cols */}
          <div className="md:col-span-2 bg-[#F8FAFC] dark:bg-slate-900 border border-[#E2E8F0] dark:border-slate-800 rounded-2xl p-8 md:p-10">
            <Badge variant="outline" className="text-[#06B6D4] border-[#06B6D4]/30 mb-4">{lang === 'en' ? 'Our Story' : 'Notre histoire'}</Badge>
            <h2 className="text-2xl sm:text-3xl font-semibold text-[#0F172A] dark:text-slate-100 mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.visionTitle}</h2>
            <p className="text-base leading-relaxed text-[#64748B] dark:text-slate-400">{t.visionText}</p>
          </div>

          {/* Engineering Card - dark */}
          <div className="bg-[#1E3A8A] rounded-2xl p-8 md:p-10 flex flex-col justify-between">
            <div>
              <Badge className="bg-[#06B6D4] text-white border-0 mb-4">{t.engBadge}</Badge>
              <h2 className="text-xl sm:text-2xl font-semibold text-white mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.engTitle}</h2>
              <p className="text-sm leading-relaxed text-blue-100/80">{t.engText}</p>
            </div>
            <div className="mt-6 flex items-center gap-2 text-[#06B6D4]">
              <Zap className="h-5 w-5" />
              <span className="text-sm font-medium">{lang === 'en' ? 'High-Speed Engine' : 'Moteur ultra-rapide'}</span>
            </div>
          </div>

          {/* Mission Card - full width */}
          <div className="md:col-span-3 bg-white dark:bg-slate-900 border border-[#E2E8F0] dark:border-slate-800 rounded-2xl p-8 md:p-10">
            <div className="max-w-3xl">
              <h2 className="text-2xl sm:text-3xl font-semibold text-[#0F172A] dark:text-slate-100 mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.missionTitle}</h2>
              <p className="text-base leading-relaxed text-[#64748B] dark:text-slate-400">{t.missionText}</p>
            </div>
          </div>
        </div>
      </section>

      {/* ========== SELLER PERSONAS ========== */}
      <section className="bg-[#F8FAFC] dark:bg-slate-900/50 py-20 md:py-28" data-testid="about-personas">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <p className="uppercase text-xs tracking-[0.2em] font-bold text-[#06B6D4] mb-3">{lang === 'en' ? 'WHO WE SERVE' : 'QUI NOUS SERVONS'}</p>
          <h2 className="text-2xl sm:text-3xl font-semibold text-[#0F172A] dark:text-slate-100 mb-3" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.empowerLabel}</h2>
          <div className="grid md:grid-cols-3 gap-6 mt-10">
            {[
              { titleKey: 'persona1Title', textKey: 'persona1Text' },
              { titleKey: 'persona2Title', textKey: 'persona2Text' },
              { titleKey: 'persona3Title', textKey: 'persona3Text' },
            ].map((p, i) => {
              const Icon = personas[i].icon;
              return (
                <div
                  key={i}
                  className="group bg-white dark:bg-slate-800 border border-[#E2E8F0] dark:border-slate-700 rounded-2xl p-8 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg"
                  data-testid={`persona-card-${i}`}
                >
                  <div className={`w-12 h-12 ${personas[i].bg} rounded-xl flex items-center justify-center mb-5 ring-1 ${personas[i].ring}`}>
                    <Icon className={`h-6 w-6 ${personas[i].color}`} />
                  </div>
                  <h3 className="text-lg font-semibold text-[#0F172A] dark:text-slate-100 mb-3" style={{ fontFamily: "'Outfit', sans-serif" }}>{t[p.titleKey]}</h3>
                  <p className="text-sm leading-relaxed text-[#64748B] dark:text-slate-400">{t[p.textKey]}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ========== WHY CANADA ========== */}
      <section className="max-w-7xl mx-auto px-6 md:px-12 py-20 md:py-28" data-testid="about-canada">
        <div className="grid md:grid-cols-2 gap-12 items-center">
          <div className="relative rounded-2xl overflow-hidden shadow-xl">
            <img src={CANADA_IMG} alt="Canada" className="w-full h-72 md:h-96 object-cover" loading="lazy" />
            <div className="absolute inset-0 bg-gradient-to-t from-[#1E3A8A]/30 to-transparent" />
            <div className="absolute bottom-4 left-4">
              <Badge className="bg-white/90 text-[#1E3A8A] border-0 shadow-sm backdrop-blur-sm">
                <ShieldCheck className="h-3.5 w-3.5 mr-1" /> {lang === 'en' ? 'Canadian Trust' : 'Confiance canadienne'}
              </Badge>
            </div>
          </div>
          <div className="space-y-5">
            <p className="uppercase text-xs tracking-[0.2em] font-bold text-[#06B6D4]">{lang === 'en' ? 'TRUST & INTEGRITY' : 'CONFIANCE ET INT\u00c9GRIT\u00c9'}</p>
            <h2 className="text-2xl sm:text-3xl font-semibold text-[#0F172A] dark:text-slate-100" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.canadaTitle}</h2>
            <p className="text-base leading-relaxed text-[#64748B] dark:text-slate-400">{t.canadaText}</p>
          </div>
        </div>
      </section>

      {/* ========== FUTURE IS INSTANT (Dark Block) ========== */}
      <section className="bg-[#0B1120] py-20 md:py-28 relative overflow-hidden" data-testid="about-future">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-[#06B6D4]/10 rounded-full blur-[120px]" />
        <div className="max-w-3xl mx-auto px-6 md:px-12 text-center relative z-10">
          <Rocket className="h-10 w-10 text-[#06B6D4] mx-auto mb-6" />
          <h2 className="text-3xl sm:text-4xl font-semibold text-white mb-5" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.futureTitle}</h2>
          <p className="text-base leading-relaxed text-slate-300">{t.futureText}</p>
          <Button
            className="mt-8 bg-[#06B6D4] hover:bg-[#06B6D4]/90 text-white rounded-full px-8"
            onClick={() => navigate('/marketplace')}
            data-testid="future-cta"
          >
            {lang === 'en' ? 'Explore the Marketplace' : 'Explorer le march\u00e9'}
          </Button>
        </div>
      </section>

      {/* ========== FOUNDER ========== */}
      <section className="max-w-7xl mx-auto px-6 md:px-12 py-20 md:py-28" data-testid="about-founder">
        <div className="max-w-3xl mx-auto text-center">
          <p className="uppercase text-xs tracking-[0.2em] font-bold text-[#06B6D4] mb-6">{lang === 'en' ? 'LEADERSHIP' : 'DIRECTION'}</p>
          <h2 className="text-2xl sm:text-3xl font-semibold text-[#0F172A] dark:text-slate-100 mb-10" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.founderTitle}</h2>

          {/* Avatar */}
          <div className="mx-auto w-32 h-32 rounded-full overflow-hidden ring-2 ring-[#1E3A8A] ring-offset-4 ring-offset-white dark:ring-offset-slate-950 mb-6 shadow-lg">
            <img src={FOUNDER_PHOTO} alt={t.founderName} className="w-full h-full object-cover" />
          </div>

          <h3 className="text-xl font-semibold text-[#0F172A] dark:text-slate-100" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.founderName}</h3>
          <p className="text-sm text-[#06B6D4] font-medium mt-1">{t.founderRole}</p>
          <p className="text-base leading-relaxed text-[#64748B] dark:text-slate-400 mt-5 max-w-xl mx-auto">{t.founderBio}</p>

          {/* Quote */}
          <div className="mt-10 relative bg-[#F8FAFC] dark:bg-slate-900 border border-[#E2E8F0] dark:border-slate-800 rounded-2xl p-8 max-w-2xl mx-auto">
            <Quote className="h-8 w-8 text-[#1E3A8A]/20 dark:text-blue-400/20 absolute top-4 left-4" />
            <p className="text-base sm:text-lg leading-relaxed text-[#0F172A] dark:text-slate-200 italic pl-6" style={{ fontFamily: "'DM Sans', serif" }}>
              {t.founderQuote}
            </p>
          </div>
        </div>
      </section>

      {/* ========== BUSINESS CREDENTIALS ========== */}
      <section className="bg-[#F8FAFC] dark:bg-slate-900/50 py-16 md:py-20" data-testid="about-credentials">
        <div className="max-w-3xl mx-auto px-6 md:px-12">
          <h2 className="text-xl sm:text-2xl font-semibold text-[#0F172A] dark:text-slate-100 mb-8 text-center" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.credTitle}</h2>
          <div className="bg-white dark:bg-slate-800 border border-[#E2E8F0] dark:border-slate-700 rounded-2xl divide-y divide-[#E2E8F0] dark:divide-slate-700 overflow-hidden">
            {[
              { label: t.credCompany, value: 'Bidvex Inc.', icon: Building2 },
              { label: t.credFederal, value: '706766367', icon: Hash },
              { label: t.credNeq, value: '1181780744', icon: ShieldCheck },
              { label: t.credPhone, value: '+1 514 949 0038', icon: Phone },
              { label: t.credEmail, value: 'info@bidvex.com', icon: Mail },
            ].map((item, idx) => {
              const Icon = item.icon;
              return (
                <div key={idx} className="flex items-center gap-4 px-6 py-4" data-testid={`cred-row-${idx}`}>
                  <div className="w-9 h-9 bg-[#1E3A8A]/5 dark:bg-blue-900/30 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Icon className="h-4 w-4 text-[#1E3A8A] dark:text-blue-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-[#64748B] dark:text-slate-400">{item.label}</p>
                    <p className="text-sm font-medium text-[#0F172A] dark:text-slate-100 truncate">{item.value}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>
    </div>
  );
};

export default AboutUsPage;
