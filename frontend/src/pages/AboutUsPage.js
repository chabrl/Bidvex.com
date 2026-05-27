import React, { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../components/ui/button';
import { useNavigate } from 'react-router-dom';
import {
  Globe, Zap, ShieldCheck, MapPin, Rocket, User,
  Building2, Mail, Phone, Hash, ChevronRight, Quote, CheckCircle
} from 'lucide-react';

const FOUNDER_PHOTO = 'https://customer-assets.emergentagent.com/job_aec91123-f68c-44df-910e-d0f391e2836a/artifacts/5xtfvgc8_image.png';
const LOGO_ICON = 'https://customer-assets.emergentagent.com/job_aec91123-f68c-44df-910e-d0f391e2836a/artifacts/qw7mgoo3_logo%20icon.png';
const CANADA_FLAG_GIF = 'https://customer-assets.emergentagent.com/job_aec91123-f68c-44df-910e-d0f391e2836a/artifacts/qko352y2_Canada_240-animated-flag-gifs.gif';
const CITY_IMG = 'https://images.unsplash.com/photo-1663602003573-d2a029baa5fc?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzNzl8MHwxfHNlYXJjaHwxfHxUb3JvbnRvJTIwc2t5bGluZSUyMENOJTIwdG93ZXJ8ZW58MHx8fHwxNzc2NDM5ODY5fDA&ixlib=rb-4.1.0&q=85';
const CAR_IMG = 'https://images.unsplash.com/photo-1766524791677-6c6c495e0218?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMzl8MHwxfHNlYXJjaHwxfHxjYXIlMjBkZWFsZXJzaGlwJTIwcGFya2luZyUyMGxvdCUyMHZlaGljbGVzfGVufDB8fHx8MTc3NjQzOTk2NHww&ixlib=rb-4.1.0&q=85';

const content = {
  en: {
    overline: 'ABOUT BIDVEX',
    heroTitle: 'Your World,\nUnder the Gavel',
    heroSub: 'Bringing the Thrill of the Auction to Everyone',
    ctaSignup: 'Sign Up',
    ctaLearn: 'Learn More',
    heroImgLabel: "Canada's Premier Auction Platform",
    visionTitle: 'A Vision Born from Ambition',
    visionText: 'The story of Bidvex began three years ago when our founder, Charbel Lichaa, arrived in Canada with a bold observation: the power of the auction was reserved for the few, but the need to sell fast was shared by many. He saw incredible Canadian assets\u2014from a family\u2019s garage sale and individual vehicles to heavy-duty farm equipment\u2014and realized that everyone deserves a global stage to sell their items in record time.',
    engTitle: 'Two Years of Precision Engineering',
    engText: 'Trust and speed don\u2019t happen by accident. We spent two years meticulously designing the Bidvex engine to make the \u201cAuctioneer Feeling\u201d accessible to everyone. We didn\u2019t just build a website; we built a high-speed marketplace where you can list today and be sold tomorrow.',
    missionTitle: 'Our Mission: Sold in a Day',
    missionText: 'At Bidvex, we believe that selling should be an adrenaline rush, not a waiting game. Our mission is to democratize the auction. By removing traditional barriers, we\u2019ve created a \u201cWorldwide Marketplace\u201d where a garage sale in Sherbrooke or a dealership in Montreal can conclude a successful sale in just 24 hours. We give you the tools to be your own auctioneer, reaching the world with just a few clicks.',
    empowerLabel: 'Every Feature Was Developed to Empower',
    persona1Title: 'The Individual Seller',
    persona1Text: 'Feel the excitement of a live auction. Whether it\u2019s a car, a vintage collection, or a one-day garage sale, we make it safe and simple to turn your items into cash.',
    persona2Title: 'The Local Hero',
    persona2Text: 'Reach your neighbors in Quebec or buyers across Canada instantly.',
    persona3Title: 'The Global Player',
    persona3Text: 'Seamlessly connect with markets in Europe, Asia, Africa, and the Middle East when you\u2019re ready to go big.',
    canadaTitle: 'Why Canada? The Gold Standard of Trust',
    canadaText: 'Canada is known for integrity and world-class standards. As a Canadian-born company, Bidvex takes that local reliability and applies it to the global stage. When you host an auction on Bidvex, you are trading with the confidence of Canadian excellence and the security of a platform built on local trust.',
    futureTitle: 'The Future is Instant',
    futureText: 'We are just getting started. Our vision includes AI-driven tools and lightning-fast logistics to make \u201cSold on Bidvex\u201d the fastest way to trade on earth. Whether it\u2019s a single item or a massive liquidation, Bidvex is your commitment to speed, ease, and global connectivity.',
    futureCta: 'Explore the Marketplace',
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
    carImgLabel: 'Trusted by Canadian Auctioneers',
  },
  fr: {
    overline: '\u00c0 PROPOS DE BIDVEX',
    heroTitle: 'Votre monde,\nsous le marteau',
    heroSub: 'L\u2019exc\u00e8s d\u2019ench\u00e8res accessible \u00e0 tous',
    ctaSignup: 'S\u2019inscrire',
    ctaLearn: 'En savoir plus',
    heroImgLabel: 'La premi\u00e8re plateforme d\u2019ench\u00e8res du Canada',
    visionTitle: 'Une vision n\u00e9e de l\u2019ambition',
    visionText: 'L\u2019histoire de Bidvex a commenc\u00e9 il y a trois ans lorsque notre fondateur, Charbel Lichaa, est arriv\u00e9 au Canada avec un constat simple\u00a0: le pouvoir de l\u2019ench\u00e8re \u00e9tait r\u00e9serv\u00e9 \u00e0 une \u00e9lite, alors que le besoin de vendre rapidement \u00e9tait partag\u00e9 par tous. En voyant la qualit\u00e9 des biens canadiens \u2014 qu\u2019il s\u2019agisse d\u2019une vente de garage familiale, de v\u00e9hicules de particuliers ou d\u2019\u00e9quipement agricole lourd \u2014 il a compris que tout le monde m\u00e9rite une sc\u00e8ne mondiale pour vendre ses articles en un temps record.',
    engTitle: 'Deux ans d\u2019ing\u00e9nierie de pr\u00e9cision',
    engText: 'La confiance et la rapidit\u00e9 ne sont pas le fruit du hasard. Nous avons pass\u00e9 deux ans \u00e0 concevoir m\u00e9ticuleusement le moteur Bidvex pour rendre l\u2019exp\u00e9rience du \u00ab\u00a0commissaire-priseur\u00a0\u00bb accessible \u00e0 tous. Nous n\u2019avons pas seulement construit un site web\u00a0; nous avons cr\u00e9\u00e9 un march\u00e9 ultra-rapide o\u00f9 vous pouvez inscrire votre bien aujourd\u2019hui et le vendre d\u00e8s demain.',
    missionTitle: 'Notre mission\u00a0: Vendu en un jour',
    missionText: 'Chez Bidvex, nous croyons que la vente doit \u00eatre une source d\u2019adr\u00e9naline, pas une attente interminable. Notre mission est de d\u00e9mocratiser les ench\u00e8res. Nous avons cr\u00e9\u00e9 un \u00ab\u00a0March\u00e9 mondial\u00a0\u00bb o\u00f9 une vente de garage \u00e0 Sherbrooke ou un concessionnaire \u00e0 Montr\u00e9al peut conclure une vente r\u00e9ussie en seulement 24 heures.',
    empowerLabel: 'Chaque fonctionnalit\u00e9 a \u00e9t\u00e9 d\u00e9velopp\u00e9e pour donner du pouvoir',
    persona1Title: 'Le vendeur particulier',
    persona1Text: 'Ressentez l\u2019excitation d\u2019une ench\u00e8re en direct. Qu\u2019il s\u2019agisse d\u2019une voiture, d\u2019une collection vintage ou d\u2019une vente de garage d\u2019une journ\u00e9e, nous rendons la conversion de vos objets en argent simple et s\u00e9curis\u00e9e.',
    persona2Title: 'Le h\u00e9ros local',
    persona2Text: 'Rejoignez vos voisins au Qu\u00e9bec ou des acheteurs partout au Canada instantan\u00e9ment.',
    persona3Title: 'L\u2019acteur mondial',
    persona3Text: 'Connectez-vous en toute fluidit\u00e9 avec les march\u00e9s d\u2019Europe, d\u2019Asie, d\u2019Afrique et du Moyen-Orient.',
    canadaTitle: 'Pourquoi le Canada\u00a0? La r\u00e9f\u00e9rence en mati\u00e8re de confiance',
    canadaText: 'Le Canada est reconnu pour son int\u00e9grit\u00e9 et ses normes de classe mondiale. En tant qu\u2019entreprise canadienne, Bidvex applique cette fiabilit\u00e9 locale \u00e0 l\u2019\u00e9chelle mondiale. Lorsque vous organisez une ench\u00e8re sur Bidvex, vous commercez avec la confiance de l\u2019excellence canadienne et la s\u00e9curit\u00e9 d\u2019une plateforme b\u00e2tie sur la confiance locale.',
    futureTitle: 'Le futur est instantan\u00e9',
    futureText: 'Nous ne faisons que commencer. Notre vision inclut des outils pilot\u00e9s par l\u2019IA et une logistique ultra-rapide pour faire de \u00ab\u00a0Vendu sur Bidvex\u00a0\u00bb le moyen le plus rapide de commercer sur terre.',
    futureCta: 'Explorer le march\u00e9',
    founderTitle: 'Rencontrez notre fondateur',
    founderName: 'Charbel Lichaa',
    founderRole: 'PDG et fondateur, Bidvex Inc.',
    founderBio: 'Charbel s\u2019est install\u00e9 au Canada avec une passion pour l\u2019innovation et un objectif simple\u00a0: mettre la puissance des ench\u00e8res \u00e0 la port\u00e9e de chaque individu. Apr\u00e8s deux ans de construction de l\u2019infrastructure Bidvex, il veille \u00e0 ce que la plateforme reste le moyen le plus rapide et le plus s\u00e9curis\u00e9 pour vendre n\u2019importe quoi, \u00e0 n\u2019importe qui, n\u2019importe o\u00f9.',
    founderQuote: '\u00ab\u00a0J\u2019ai cr\u00e9\u00e9 Bidvex parce que je crois que tout le monde devrait avoir le pouvoir d\u2019\u00eatre son propre commissaire-priseur. Que vous vidiez votre garage ou vendiez une flotte de v\u00e9hicules, l\u2019emplacement et le temps ne devraient jamais \u00eatre des obstacles \u00e0 votre succ\u00e8s.\u00a0\u00bb',
    credTitle: 'Informations officielles',
    credCompany: 'Nom de l\u2019entreprise',
    credFederal: 'Enregistrement f\u00e9d\u00e9ral',
    credNeq: 'NEQ (Qu\u00e9bec)',
    credPhone: 'T\u00e9l\u00e9phone',
    credEmail: 'Courriel',
    carImgLabel: 'Approuv\u00e9 par les encanteurs canadiens',
  },
};

const personas = [
  { icon: User, color: '#1C6EC1' },
  { icon: MapPin, color: '#1C6EC1' },
  { icon: Globe, color: '#1C6EC1' },
];

/* ============ Interactive Hero Image ============ */
const HeroCityImage = ({ label }) => {
  const [hovered, setHovered] = React.useState(false);
  return (
    <div
      className="about-hero-img relative w-full h-full min-h-[320px] md:min-h-[480px] rounded-2xl overflow-hidden cursor-pointer select-none"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onTouchStart={() => setHovered(h => !h)}
      data-testid="hero-city-image"
    >
      <img src={CITY_IMG} alt="Canadian City" className="absolute inset-0 w-full h-full object-cover" loading="eager" fetchPriority="high" />
      {/* Overlay */}
      <div
        className="absolute inset-0 transition-all duration-[400ms]"
        style={{ backgroundColor: hovered ? 'rgba(33,134,198,0.3)' : 'rgba(255,0,0,0.15)' }}
      />
      {/* Logo */}
      <img
        src={LOGO_ICON}
        alt="BidVex"
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-20 h-20 drop-shadow-[0_4px_12px_rgba(255,255,255,0.5)] transition-all duration-[400ms]"
        style={{ opacity: hovered ? 0 : 1, transform: `translate(-50%,-50%) scale(${hovered ? 0.8 : 1})` }}
      />
      {/* Hover label */}
      <span
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-white font-bold text-base sm:text-lg md:text-xl text-center px-6 max-w-[90%] leading-snug transition-all duration-[400ms] pointer-events-none"
        style={{ opacity: hovered ? 1 : 0, transform: `translate(-50%,-50%) scale(${hovered ? 1 : 0.9})` }}
      >
        {label}
      </span>
    </div>
  );
};

/* ============ Car Lot Image ============ */
const CarLotImage = ({ label }) => {
  const [hovered, setHovered] = React.useState(false);
  return (
    <div
      className="about-car-img relative w-full h-full min-h-[300px] md:min-h-[400px] rounded-2xl overflow-hidden cursor-pointer select-none"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onTouchStart={() => setHovered(h => !h)}
      data-testid="hero-car-image"
    >
      <img src={CAR_IMG} alt="Vehicle Auction" className="absolute inset-0 w-full h-full object-cover" loading="lazy" />
      <div className="absolute inset-0" style={{ background: 'linear-gradient(135deg, rgba(11,37,69,0.7) 0%, rgba(33,134,198,0.5) 100%)' }} />
      {/* Branding */}
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
        <div className={`flex items-center gap-3 transition-transform duration-300 ${hovered ? 'about-pulse' : ''}`}>
          <img src={CANADA_FLAG_GIF} alt="Canada" className="h-12 w-auto drop-shadow-lg" style={{ mixBlendMode: 'multiply' }} />
          <img src={LOGO_ICON} alt="BidVex" className="h-14 w-14 drop-shadow-lg" />
        </div>
        <p className="text-white text-sm md:text-base font-semibold text-center px-4 drop-shadow">{label}</p>
      </div>
    </div>
  );
};

/* ============ Scroll Observer Hook ============ */
const useScrollReveal = () => {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { el.classList.add('about-visible'); observer.unobserve(el); } },
      { threshold: 0.15 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return ref;
};
const AnimSection = ({ children, className = '', delay = 0, ...props }) => {
  const ref = useScrollReveal();
  return (
    <div ref={ref} className={`about-animate ${className}`} style={{ transitionDelay: `${delay}ms` }} {...props}>
      {children}
    </div>
  );
};

/* ============ MAIN PAGE ============ */
const AboutUsPage = () => {
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const lang = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  const t = content[lang];

  return (
    <div className="about-page" style={{ fontFamily: "'DM Sans', sans-serif" }} data-testid="about-us-page">

      {/* ===== SECTION 1: HERO (dark navy) ===== */}
      <section className="bg-[#0B2545] relative overflow-hidden" data-testid="about-hero">
        <div className="max-w-7xl mx-auto px-6 md:px-12 py-16 md:py-24">
          <div className="grid md:grid-cols-2 gap-10 md:gap-16 items-center">
            {/* Left text — slides in */}
            <div className="about-hero-text space-y-6">
              <p className="uppercase text-xs tracking-[0.2em] font-bold text-[#3FB4CB]">{t.overline}</p>
              <h1
                className="text-4xl sm:text-5xl lg:text-6xl tracking-tight font-semibold text-white whitespace-pre-line leading-[1.1]"
                style={{ fontFamily: "'Outfit', sans-serif" }}
              >
                {t.heroTitle}
              </h1>
              <p className="text-base md:text-lg text-[#93C5FD] max-w-md leading-relaxed">{t.heroSub}</p>
              <div className="flex flex-wrap gap-3 pt-2">
                <Button
                  className="bg-[#1C6EC1] hover:bg-[#2186C6] text-white rounded-full px-6"
                  onClick={() => navigate('/auth')}
                  data-testid="hero-cta-signup"
                >
                  {t.ctaSignup} <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
                <button
                  className="rounded-full border border-white/40 text-white hover:bg-white/10 px-6 py-2 text-sm font-medium transition-all"
                  onClick={() => navigate('/how-it-works')}
                  data-testid="hero-cta-learn"
                >
                  {t.ctaLearn}
                </button>
              </div>
            </div>
            {/* Right image */}
            <HeroCityImage label={t.heroImgLabel} />
          </div>
        </div>
      </section>

      {/* ===== SECTION 2: VISION + MISSION (alternating rows) ===== */}
      <section className="max-w-7xl mx-auto px-6 md:px-12 py-20 md:py-28 space-y-16" data-testid="about-story">
        {/* Row 1: Vision text left, gradient card right */}
        <div className="grid md:grid-cols-2 gap-8 md:gap-12 items-center">
          <AnimSection>
            <h2 className="text-2xl sm:text-3xl font-semibold text-[#0F172A] dark:text-slate-100 mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.visionTitle}</h2>
            <p className="text-base leading-relaxed text-[#64748B] dark:text-slate-400">{t.visionText}</p>
          </AnimSection>
          <AnimSection delay={150}>
            <div className="rounded-[20px] p-8 md:p-10 text-white shadow-[0_20px_60px_rgba(0,0,0,0.3)]" style={{ background: 'linear-gradient(135deg, #0B2545 0%, #1C6EC1 100%)' }}>
              <Zap className="h-8 w-8 text-[#3FB4CB] mb-4" />
              <h3 className="text-xl font-semibold mb-3" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.engTitle}</h3>
              <p className="text-sm leading-relaxed text-blue-100/80">{t.engText}</p>
            </div>
          </AnimSection>
        </div>
        {/* Row 2: Car image left, Mission text right */}
        <div className="grid md:grid-cols-2 gap-8 md:gap-12 items-center">
          <AnimSection>
            <CarLotImage label={t.carImgLabel} />
          </AnimSection>
          <AnimSection delay={150}>
            <h2 className="text-2xl sm:text-3xl font-semibold text-[#0F172A] dark:text-slate-100 mb-4" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.missionTitle}</h2>
            <p className="text-base leading-relaxed text-[#64748B] dark:text-slate-400">{t.missionText}</p>
          </AnimSection>
        </div>
      </section>

      {/* ===== SECTION 3: FEATURE CARDS ===== */}
      <section className="bg-[#F8FAFC] dark:bg-slate-900/50 py-20 md:py-28" data-testid="about-personas">
        <div className="max-w-7xl mx-auto px-6 md:px-12">
          <AnimSection>
            <h2 className="text-2xl sm:text-3xl font-semibold text-[#0F172A] dark:text-slate-100 mb-10 text-center" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.empowerLabel}</h2>
          </AnimSection>
          <div className="grid md:grid-cols-3 gap-6">
            {[
              { titleKey: 'persona1Title', textKey: 'persona1Text', idx: 0 },
              { titleKey: 'persona2Title', textKey: 'persona2Text', idx: 1 },
              { titleKey: 'persona3Title', textKey: 'persona3Text', idx: 2 },
            ].map((p) => {
              const Icon = personas[p.idx].icon;
              return (
                <AnimSection key={p.idx} delay={p.idx * 100}>
                  <div
                    className="about-feature-card bg-white dark:bg-[#1E293B] border border-[#E2E8F0] dark:border-[#334155] rounded-2xl p-8 border-t-4 border-t-[#1C6EC1] transition-all duration-300 hover:-translate-y-2 hover:shadow-[0_20px_40px_rgba(33,134,198,0.2)] hover:border-t-[#3FB4CB]"
                    data-testid={`persona-card-${p.idx}`}
                  >
                    <Icon className="h-10 w-10 mb-5" style={{ color: '#1C6EC1' }} />
                    <h3 className="text-lg font-bold text-[#0F172A] dark:text-slate-100 mb-3" style={{ fontFamily: "'Outfit', sans-serif" }}>{t[p.titleKey]}</h3>
                    <p className="text-sm leading-relaxed text-[#64748B] dark:text-slate-400">{t[p.textKey]}</p>
                  </div>
                </AnimSection>
              );
            })}
          </div>
        </div>
      </section>

      {/* ===== SECTION 4: WHY CANADA (dark) ===== */}
      <section className="about-canada-bg bg-[#0B2545] py-20 md:py-28 relative overflow-hidden" data-testid="about-canada">
        <div className="about-canada-pattern absolute inset-0 opacity-[0.04]" />
        <div className="relative z-10 max-w-[700px] mx-auto px-6 md:px-12 text-center">
          <AnimSection>
            <div className="about-flag-float mx-auto mb-6 w-20 h-20 rounded-2xl bg-white flex items-center justify-center overflow-hidden shadow-lg">
              <img src={CANADA_FLAG_GIF} alt="Canada" className="h-14 w-auto" />
            </div>
            <h2 className="text-2xl sm:text-3xl font-semibold text-white mb-5" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.canadaTitle}</h2>
            <p className="text-base leading-relaxed text-[#93C5FD]">{t.canadaText}</p>
          </AnimSection>
        </div>
      </section>

      {/* ===== SECTION 5: FUTURE IS INSTANT (gradient CTA) ===== */}
      <section className="about-future-bg py-20 md:py-28" data-testid="about-future">
        <div className="max-w-3xl mx-auto px-6 md:px-12 text-center">
          <AnimSection>
            <Rocket className="h-10 w-10 text-white mx-auto mb-6 drop-shadow-lg" />
            <h2 className="text-3xl sm:text-4xl font-semibold text-white mb-5" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.futureTitle}</h2>
            <p className="text-base leading-relaxed text-white/80 mb-8">{t.futureText}</p>
            <Button
              className="bg-white text-[#0B2545] hover:bg-[#F0F8FF] hover:scale-[1.03] rounded-full px-8 font-semibold transition-all duration-300 shadow-lg"
              onClick={() => navigate('/marketplace')}
              data-testid="future-cta"
            >
              {t.futureCta}
            </Button>
          </AnimSection>
        </div>
      </section>

      {/* ===== SECTION 6: FOUNDER ===== */}
      <section className="bg-[#F1F5F9] dark:bg-slate-900 py-20 md:py-28" data-testid="about-founder">
        <AnimSection className="max-w-[600px] mx-auto px-6 md:px-12">
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-8 md:p-10 text-center">
            <p className="uppercase text-xs tracking-[0.2em] font-bold text-[#3FB4CB] mb-4">{lang === 'en' ? 'LEADERSHIP' : 'DIRECTION'}</p>
            <h2 className="text-2xl font-semibold text-[#0F172A] dark:text-slate-100 mb-8" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.founderTitle}</h2>
            <div className="mx-auto w-[120px] h-[120px] rounded-full overflow-hidden border-4 border-[#2186C6] shadow-lg mb-5">
              <img src={FOUNDER_PHOTO} alt={t.founderName} className="w-full h-full object-cover" />
            </div>
            <h3 className="text-xl font-semibold text-[#0F172A] dark:text-slate-100" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.founderName}</h3>
            <p className="text-sm text-[#1C6EC1] font-medium mt-1 mb-5">{t.founderRole}</p>
            <p className="text-sm leading-relaxed text-[#64748B] dark:text-slate-400 text-left">{t.founderBio}</p>
            <div className="mt-8 bg-[#F0F8FF] dark:bg-slate-700 rounded-xl p-6 border-l-4 border-[#3FB4CB] text-left relative">
              <Quote className="h-6 w-6 text-[#3FB4CB]/30 absolute top-3 left-3" />
              <p className="text-sm md:text-base leading-relaxed text-[#0F172A] dark:text-slate-200 italic pl-5">{t.founderQuote}</p>
            </div>
          </div>
        </AnimSection>
      </section>

      {/* ===== SECTION 7: CREDENTIALS ===== */}
      <section className="py-16 md:py-20" data-testid="about-credentials">
        <AnimSection className="max-w-[500px] mx-auto px-6 md:px-12">
          <h2 className="text-xl font-semibold text-[#0F172A] dark:text-slate-100 mb-6 text-center" style={{ fontFamily: "'Outfit', sans-serif" }}>{t.credTitle}</h2>
          <div className="bg-white dark:bg-slate-800 border border-[#E2E8F0] dark:border-slate-700 rounded-2xl shadow-md overflow-hidden divide-y divide-[#E2E8F0] dark:divide-slate-700">
            {[
              { label: t.credCompany, value: 'Bidvex Inc.', icon: Building2 },
              { label: t.credFederal, value: '706766367', icon: CheckCircle },
              { label: t.credNeq, value: '1181780744', icon: ShieldCheck },
              { label: t.credPhone, value: '+1 (450) 634-3099', icon: Phone },
              { label: t.credEmail, value: 'info@bidvex.com', icon: Mail },
            ].map((item, idx) => {
              const Icon = item.icon;
              return (
                <div key={idx} className="flex items-center gap-4 px-6 py-4" data-testid={`cred-row-${idx}`}>
                  <Icon className="h-5 w-5 flex-shrink-0" style={{ color: '#1C6EC1' }} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-[#64748B] dark:text-slate-400 font-bold">{item.label}</p>
                    <p className="text-sm text-[#0F172A] dark:text-slate-100">{item.value}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </AnimSection>
      </section>
    </div>
  );
};

export default AboutUsPage;
