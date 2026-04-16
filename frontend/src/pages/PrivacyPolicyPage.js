import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Shield, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

const tocEN = [
  { id: 'intro', label: '1. Introduction' },
  { id: 'info-collect', label: '2. Information We Collect' },
  { id: 'purpose', label: '3. Purpose of Processing' },
  { id: 'sharing', label: '4. Information Sharing' },
  { id: 'cookies', label: '5. Cookies & Tracking' },
  { id: 'ai-engine', label: '6. AI Recommendation Engine' },
  { id: 'security', label: '7. Data Security' },
  { id: 'rights', label: '8. Your Privacy Rights' },
  { id: 'retention', label: '9. Data Retention' },
  { id: 'contact', label: '10. Contact Us' },
  { id: 'stripe-data', label: '11. Stripe Payment Data' },
  { id: 'ai-disclosure', label: '12. AI Disclosure' },
  { id: 'vehicle-opc', label: '13. Vehicle Auctions & OPC' },
];

const tocFR = [
  { id: 'intro', label: '1. Introduction' },
  { id: 'info-collect', label: '2. Renseignements collectés' },
  { id: 'purpose', label: '3. Finalités du traitement' },
  { id: 'sharing', label: '4. Partage des informations' },
  { id: 'cookies', label: '5. Cookies et suivi' },
  { id: 'ai-engine', label: '6. Moteur de recommandation IA' },
  { id: 'security', label: '7. Sécurité des données' },
  { id: 'rights', label: '8. Vos droits' },
  { id: 'retention', label: '9. Conservation des données' },
  { id: 'contact', label: '10. Nous contacter' },
  { id: 'stripe-data', label: '11. Données Stripe' },
  { id: 'ai-disclosure', label: '12. Divulgation IA' },
  { id: 'vehicle-opc', label: '13. Véhicules et OPC' },
];

const Badge = ({ n }) => (
  <span className="inline-flex items-center justify-center w-7 h-7 rounded-full text-white text-xs font-bold flex-shrink-0" style={{ background: '#2186C6' }}>{n}</span>
);

const BlueBox = ({ children }) => (
  <div className="rounded-r-lg my-4 py-4 px-5" style={{ borderLeft: '4px solid #3FB4CB', background: '#F0F8FF' }}>
    <div className="text-slate-800 text-sm leading-relaxed space-y-2">{children}</div>
  </div>
);

const RedBox = ({ children }) => (
  <div className="rounded-r-lg my-4 py-4 px-5" style={{ borderLeft: '4px solid #DC2626', background: '#FFF5F5' }}>
    <div className="text-red-900 text-sm leading-relaxed space-y-2">{children}</div>
  </div>
);

const GreenBox = ({ children }) => (
  <div className="rounded-r-lg my-4 py-4 px-5" style={{ borderLeft: '4px solid #059669', background: '#F0FDF4' }}>
    <div className="text-emerald-900 text-sm leading-relaxed space-y-2">{children}</div>
  </div>
);

const SH = ({ children, id, n }) => (
  <h2 id={id} className="flex items-center gap-3 text-xl font-bold mt-10 mb-4 scroll-mt-24" style={{ color: '#0B2545' }}>
    <Badge n={n} />{children}
  </h2>
);

const DataCard = ({ color, title, desc }) => (
  <div className={`bg-${color}-50 dark:bg-${color}-950/30 border border-${color}-200 dark:border-${color}-800 rounded-lg p-5`}>
    <h3 className={`text-base font-semibold text-${color}-800 dark:text-${color}-200 mb-2`}>{title}</h3>
    <p className={`text-${color}-700 dark:text-${color}-300 text-sm`}>{desc}</p>
  </div>
);

const CookieCard = ({ color, title, desc }) => (
  <div className={`bg-${color}-50 dark:bg-${color}-950/30 border border-${color}-200 dark:border-${color}-800 rounded-lg p-4`}>
    <h4 className={`font-semibold text-${color}-800 dark:text-${color}-200`}>{title}</h4>
    <p className={`text-sm text-${color}-700 dark:text-${color}-300`}>{desc}</p>
  </div>
);

const SecurityCard = ({ title, desc }) => (
  <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-center">
    <h4 className="font-semibold text-green-800 dark:text-green-200">{title}</h4>
    <p className="text-sm text-green-700 dark:text-green-300">{desc}</p>
  </div>
);

const RightItem = ({ icon, title, desc }) => (
  <div className="flex items-start gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
    <span className="text-lg">{icon}</span>
    <div><h4 className="font-semibold">{title}</h4><p className="text-sm text-muted-foreground">{desc}</p></div>
  </div>
);

const RetentionItem = ({ years, color, title, desc }) => (
  <div className="flex items-center gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
    <div className={`w-14 h-14 bg-${color}-100 dark:bg-${color}-900 rounded-lg flex items-center justify-center flex-shrink-0`}>
      <span className={`text-2xl font-bold text-${color}-600`}>{years}</span>
    </div>
    <div><h4 className="font-semibold">{title}</h4><p className="text-sm text-muted-foreground">{desc}</p></div>
  </div>
);

const PrivacyPolicyPage = () => {
  const { i18n } = useTranslation();
  const fr = i18n.language?.startsWith('fr');
  const [activeSection, setActiveSection] = useState('intro');
  const toc = fr ? tocFR : tocEN;

  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) setActiveSection(e.target.id); });
    }, { rootMargin: '-80px 0px -70% 0px' });
    toc.forEach(item => {
      const el = document.getElementById(item.id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [fr]);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      {/* Hero */}
      <div className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 py-10 px-4">
        <div className="max-w-5xl mx-auto">
          <Link to="/" className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-blue-600 mb-4">
            <ArrowLeft className="h-4 w-4" /> {fr ? 'Retour à l\'accueil' : 'Back to Home'}
          </Link>
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg"><Shield className="h-6 w-6 text-green-600" /></div>
            <h1 className="text-3xl font-bold" style={{ color: '#0B2545' }}>{fr ? 'Politique de confidentialité de BidVex' : 'BidVex Privacy Policy'}</h1>
          </div>
          <p className="text-sm text-slate-500">{fr ? 'Dernière mise à jour : Mars 2026' : 'Last Updated: March 2026'}</p>
        </div>
      </div>

      {/* Content with Sidebar */}
      <div className="max-w-5xl mx-auto px-4 py-10 flex gap-10">
        {/* Sidebar TOC */}
        <aside className="hidden lg:block w-64 flex-shrink-0">
          <nav className="sticky top-20 space-y-1" data-testid="privacy-toc">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">{fr ? 'Table des matières' : 'Table of Contents'}</p>
            {toc.map(item => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className={`block text-[13px] py-1.5 px-3 rounded-md transition-all ${activeSection === item.id ? 'bg-blue-50 dark:bg-blue-950 text-blue-600 font-semibold' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
              >
                {item.label}
              </a>
            ))}
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 min-w-0 prose prose-sm dark:prose-invert max-w-none" data-testid="privacy-content" style={{ scrollBehavior: 'smooth' }}>

          {!fr ? (<>
            {/* ── EN CONTENT ── */}
            <SH id="intro" n="1">Introduction</SH>
            <p>At BidVex Inc. ("BidVex," "we," "us," or "our"), we are committed to protecting the privacy and security of your personal information. This Privacy Policy explains how we collect, use, disclose, and safeguard your data when you use our online auction platform ("the Platform").</p>
            <BlueBox><p><strong>Compliance:</strong> This policy is designed to comply with the <strong>Act respecting the protection of personal information in the private sector (Quebec Law 25)</strong>, the <strong>Personal Information Protection and Electronic Documents Act (PIPEDA)</strong>, and the <strong>General Data Protection Regulation (GDPR)</strong>.</p></BlueBox>

            <SH id="info-collect" n="2">Information We Collect</SH>
            <p>To provide a secure and efficient auction environment, we collect the following categories of data:</p>
            <div className="space-y-4 mt-4">
              <DataCard color="emerald" title="2.1 Sellers (Including Vehicle & Equipment sections)" desc="Identity & verification data, contact data, business information, asset data (VIN, history reports), financial data (banking details for payouts)." />
              <DataCard color="blue" title="2.2 Buyers" desc="Identity data, contact data, payment data (processed via Stripe — we never store full card numbers), transaction data (bidding history, watchlisted items, records of won auctions)." />
              <DataCard color="slate" title="2.3 Technical Data (All Users)" desc="IP address, browser type, time zone setting, device identifiers, and operating system information for security monitoring and platform optimization." />
            </div>

            <SH id="purpose" n="3">Purpose of Processing</SH>
            <p>We process your personal data on the following legal grounds:</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg"><div><h4 className="font-semibold">Contractual Necessity</h4><p className="text-sm text-muted-foreground">Facilitate auctions, purchases, and sales.</p></div></div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg"><div><h4 className="font-semibold">Identity Verification</h4><p className="text-sm text-muted-foreground">Maintain a trusted marketplace and prevent fraud.</p></div></div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg"><div><h4 className="font-semibold">Payment Processing</h4><p className="text-sm text-muted-foreground">Manage transaction fees securely via Stripe.</p></div></div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg"><div><h4 className="font-semibold">Legal Compliance</h4><p className="text-sm text-muted-foreground">Satisfy tax, accounting, and regulatory obligations.</p></div></div>
            </div>

            <SH id="sharing" n="4">Information Sharing &amp; Disclosure</SH>
            <RedBox><p><strong>We do not sell your personal data to third parties.</strong></p></RedBox>
            <p>Disclosure occurs only in the following contexts:</p>
            <ul className="list-disc pl-5 space-y-1 text-sm">
              <li><strong>Transaction Completion:</strong> Buyer/seller contact details shared for item collection only.</li>
              <li><strong>Public Profile:</strong> User names, verified badges, and ratings are displayed publicly.</li>
              <li><strong>Service Providers:</strong> Trusted partners (Stripe, SendGrid, Twilio) strictly for operations.</li>
              <li><strong>Legal Authorities:</strong> When required by law to protect rights and safety.</li>
            </ul>

            <SH id="cookies" n="5">Cookies &amp; Tracking</SH>
            <p>We use cookies to enhance your experience and analyze traffic.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
              <CookieCard color="green" title="Essential Cookies" desc="Required for core platform functionality (e.g., staying logged in)." />
              <CookieCard color="blue" title="Analytics Cookies" desc="Help us understand how users interact with the site." />
              <CookieCard color="purple" title="Personalization Cookies" desc="Remember your preferences, such as language." />
              <CookieCard color="amber" title="Marketing Cookies" desc="Relevant advertisements. Opt-out available." />
            </div>

            <SH id="ai-engine" n="6">AI-Powered Recommendation Engine</SH>
            <p>BidVex utilizes a proprietary recommendation engine to suggest items based on:</p>
            <ul className="list-disc pl-5 space-y-1 text-sm">
              <li>Past bidding and purchase patterns</li>
              <li>Items added to your Watchlist</li>
            </ul>
            <GreenBox><p><strong>Opt-Out:</strong> Users may disable personalized recommendations in their Account Settings. This will not affect core functionality.</p></GreenBox>

            <SH id="security" n="7">Data Security</SH>
            <p>We implement industry-leading security measures to protect your data:</p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
              <SecurityCard title="TLS/SSL" desc="Encryption in Transit" />
              <SecurityCard title="AES-256" desc="Encryption at Rest" />
              <SecurityCard title="PCI-DSS" desc="Payment Compliance" />
              <SecurityCard title="Multi-Guard" desc="Brute-force Detection" />
              <SecurityCard title="Role-Based" desc="Access Control" />
              <SecurityCard title="Security Monitoring" desc="24/7 Alerts" />
            </div>

            <SH id="rights" n="8">Your Privacy Rights</SH>
            <p>Depending on your jurisdiction (Quebec, Canada, or EU), you have the following rights:</p>
            <div className="space-y-3 mt-4">
              <RightItem icon="🔍" title="Access" desc="Request a copy of the personal data we hold about you." />
              <RightItem icon="✏️" title="Correction" desc="Fix inaccurate or incomplete information." />
              <RightItem icon="🗑️" title="Deletion (Right to be Forgotten)" desc="Request deletion of your data, subject to legal retention requirements." />
              <RightItem icon="📦" title="Portability" desc="Receive your data in a structured, machine-readable format." />
              <RightItem icon="🚫" title="Withdrawal of Consent" desc="Stop processing for specific purposes (e.g., marketing)." />
            </div>
            <BlueBox><p><strong>To exercise these rights,</strong> please contact our Data Protection Officer at <a href="mailto:support@bidvex.com" className="underline">support@bidvex.com</a>.</p></BlueBox>

            <SH id="retention" n="9">Data Retention</SH>
            <div className="space-y-3 mt-4">
              <RetentionItem years="7" color="blue" title="Account Data" desc="Duration of active account and up to 7 years after closure." />
              <RetentionItem years="7" color="green" title="Transaction Records" desc="Retained 7 years to comply with Canadian and Quebec tax and legal obligations." />
              <RetentionItem years="∞" color="red" title="Identification Documents" desc="Retained until permanently compliant, unless offline and unrelated to ongoing fraud investigation." />
            </div>

            <SH id="contact" n="10">Contact Us</SH>
            <GreenBox>
              <p className="font-semibold text-lg mb-2">BidVex Data Protection Officer</p>
              <p className="text-sm">Email: <a href="mailto:support@bidvex.com" className="text-blue-600 underline">support@bidvex.com</a></p>
            </GreenBox>

            {/* NEW: 11 Stripe Payment Data */}
            <SH id="stripe-data" n="11">Stripe Payment Data</SH>
            <BlueBox>
              <p>BidVex uses Stripe to process all payments. When you add a payment method, Stripe stores your card data on their PCI-DSS compliant servers. BidVex retains only a Stripe token (payment method ID) — never raw card numbers, CVV, or expiry dates. By using BidVex, you agree to Stripe's Privacy Policy available at <a href="https://stripe.com/privacy" target="_blank" rel="noopener noreferrer" className="underline">stripe.com/privacy</a>.</p>
              <p className="mt-2">BidVex may retain your Stripe payment method token after you request its removal from the platform interface, solely for the purpose of collecting outstanding platform fees or cancellation penalties as described in our Terms of Service.</p>
            </BlueBox>

            <SH id="ai-disclosure" n="12">Automated Decision-Making and AI Processing</SH>
            <p>BidVex uses AI to power: (1) customer support responses via AI Concierge; (2) listing categorization and fraud signal detection; (3) recommendation engine. No automated decision materially affects your legal rights without human review.</p>

            <SH id="vehicle-opc" n="13">Vehicle Auctions — Platform Role &amp; OPC Compliance</SH>
            <p>BidVex is a technology platform and auction facilitator only. BidVex is not a vendor, dealer, or party to vehicle sale contracts. Vehicle data (VIN, history reports) is processed for listing purposes only and subject to the same data protection standards.</p>

            <p className="text-xs text-slate-400 mt-10">&copy; 2026 BidVex Inc. All rights reserved.</p>
          </>) : (<>

            {/* ── FR CONTENT ── */}
            <SH id="intro" n="1">Introduction</SH>
            <p>Chez BidVex Inc. (« BidVex », « nous »), nous nous engageons à protéger la vie privée et la sécurité de vos renseignements personnels. La présente Politique de confidentialité explique comment nous collectons, utilisons, divulguons et protégeons vos données lorsque vous utilisez notre plateforme d'enchères en ligne (« la Plateforme »).</p>
            <BlueBox><p><strong>Conformité :</strong> Cette politique est conforme à la <strong>Loi sur la protection des renseignements personnels dans le secteur privé (Loi 25 du Québec)</strong>, à la <strong>LPRPDE</strong> et au <strong>RGPD</strong>.</p></BlueBox>

            <SH id="info-collect" n="2">Renseignements collectés</SH>
            <p>Pour assurer un environnement d'enchères sécurisé et efficace, nous collectons les catégories de données suivantes :</p>
            <div className="space-y-4 mt-4">
              <DataCard color="emerald" title="2.1 Vendeurs (y compris véhicules)" desc="Données d'identité et de vérification, coordonnées, informations commerciales, données d'actifs (NIV, rapports d'historique), données financières." />
              <DataCard color="blue" title="2.2 Acheteurs" desc="Données d'identité, coordonnées, données de paiement (traitées via Stripe — nous ne stockons jamais les numéros de carte complets), données de transaction." />
              <DataCard color="slate" title="2.3 Données techniques (tous les utilisateurs)" desc="Adresse IP, type de navigateur, fuseau horaire, identifiants d'appareil et système d'exploitation." />
            </div>

            <SH id="purpose" n="3">Finalités du traitement</SH>
            <p>Nous traitons vos données personnelles sur les bases juridiques suivantes :</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg"><div><h4 className="font-semibold">Nécessité contractuelle</h4><p className="text-sm text-muted-foreground">Faciliter les enchères et transactions.</p></div></div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg"><div><h4 className="font-semibold">Vérification d'identité</h4><p className="text-sm text-muted-foreground">Maintenir un marché de confiance.</p></div></div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg"><div><h4 className="font-semibold">Traitement des paiements</h4><p className="text-sm text-muted-foreground">Gérer les frais via Stripe.</p></div></div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg"><div><h4 className="font-semibold">Conformité légale</h4><p className="text-sm text-muted-foreground">Obligations fiscales et réglementaires.</p></div></div>
            </div>

            <SH id="sharing" n="4">Partage des informations</SH>
            <RedBox><p><strong>Nous ne vendons pas vos données personnelles à des tiers.</strong></p></RedBox>
            <p>La divulgation n'intervient que pour : complétion des transactions, profil public, fournisseurs de services (Stripe, SendGrid, Twilio) et autorités légales.</p>

            <SH id="cookies" n="5">Cookies et suivi</SH>
            <p>Nous utilisons des cookies pour améliorer votre expérience et analyser le trafic.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
              <CookieCard color="green" title="Cookies essentiels" desc="Requis pour les fonctionnalités de base." />
              <CookieCard color="blue" title="Cookies analytiques" desc="Comprendre l'interaction utilisateur." />
              <CookieCard color="purple" title="Cookies de personnalisation" desc="Mémoriser vos préférences (langue)." />
              <CookieCard color="amber" title="Cookies marketing" desc="Publicités pertinentes. Désactivation possible." />
            </div>

            <SH id="ai-engine" n="6">Moteur de recommandation IA</SH>
            <p>BidVex utilise un moteur de recommandation basé sur :</p>
            <ul className="list-disc pl-5 space-y-1 text-sm"><li>Historique d'enchères et d'achats</li><li>Articles dans votre liste de suivi</li></ul>
            <GreenBox><p><strong>Désactivation :</strong> Vous pouvez désactiver les recommandations personnalisées dans les Paramètres de votre compte.</p></GreenBox>

            <SH id="security" n="7">Sécurité des données</SH>
            <p>Nous appliquons des mesures de sécurité de pointe :</p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
              <SecurityCard title="TLS/SSL" desc="Chiffrement en transit" />
              <SecurityCard title="AES-256" desc="Chiffrement au repos" />
              <SecurityCard title="PCI-DSS" desc="Conformité paiements" />
              <SecurityCard title="Multi-Guard" desc="Détection force brute" />
              <SecurityCard title="Basé sur les rôles" desc="Contrôle d'accès" />
              <SecurityCard title="Surveillance" desc="Alertes 24/7" />
            </div>

            <SH id="rights" n="8">Vos droits de confidentialité</SH>
            <div className="space-y-3 mt-4">
              <RightItem icon="🔍" title="Accès" desc="Demander une copie de vos données personnelles." />
              <RightItem icon="✏️" title="Correction" desc="Corriger les informations inexactes." />
              <RightItem icon="🗑️" title="Suppression (droit à l'oubli)" desc="Demander la suppression, sous réserve des obligations légales." />
              <RightItem icon="📦" title="Portabilité" desc="Recevoir vos données dans un format structuré." />
              <RightItem icon="🚫" title="Retrait du consentement" desc="Cesser le traitement marketing." />
            </div>
            <BlueBox><p><strong>Pour exercer ces droits,</strong> contactez notre responsable de la protection des données à <a href="mailto:support@bidvex.com" className="underline">support@bidvex.com</a>.</p></BlueBox>

            <SH id="retention" n="9">Conservation des données</SH>
            <div className="space-y-3 mt-4">
              <RetentionItem years="7" color="blue" title="Données de compte" desc="Durée du compte actif et jusqu'à 7 ans après la fermeture." />
              <RetentionItem years="7" color="green" title="Dossiers de transactions" desc="Conservés 7 ans (conformité fiscale)." />
              <RetentionItem years="∞" color="red" title="Documents d'identification" desc="Conservés jusqu'à conformité permanente." />
            </div>

            <SH id="contact" n="10">Nous contacter</SH>
            <GreenBox>
              <p className="font-semibold text-lg mb-2">Responsable de la protection des données BidVex</p>
              <p className="text-sm">Courriel : <a href="mailto:support@bidvex.com" className="text-blue-600 underline">support@bidvex.com</a></p>
            </GreenBox>

            <SH id="stripe-data" n="11">Données de paiement Stripe</SH>
            <BlueBox>
              <p>BidVex utilise Stripe pour traiter tous les paiements. Lorsque vous ajoutez un moyen de paiement, Stripe stocke vos données de carte sur ses serveurs conformes PCI-DSS. BidVex conserve uniquement un jeton Stripe (identifiant du moyen de paiement) — jamais les numéros de carte bruts, le CVV, ni les dates d'expiration. En utilisant BidVex, vous acceptez la politique de confidentialité de Stripe disponible sur <a href="https://stripe.com/privacy" target="_blank" rel="noopener noreferrer" className="underline">stripe.com/privacy</a>.</p>
              <p className="mt-2">BidVex peut conserver votre jeton de moyen de paiement Stripe après que vous en ayez demandé la suppression de l'interface de la plateforme, uniquement dans le but de percevoir les frais de plateforme impayés ou les pénalités d'annulation telles que décrites dans nos Conditions d'utilisation.</p>
            </BlueBox>

            <SH id="ai-disclosure" n="12">Traitement automatisé et intelligence artificielle</SH>
            <p>BidVex utilise l'IA pour : (1) les réponses du support via le Concierge IA ; (2) la catégorisation des annonces et la détection de fraude ; (3) le moteur de recommandation. Aucune décision automatisée n'affecte matériellement vos droits sans révision humaine.</p>

            <SH id="vehicle-opc" n="13">Enchères de véhicules — Rôle de la plateforme et conformité OPC</SH>
            <p>BidVex est une plateforme technologique et un facilitateur d'enchères uniquement. Les données véhicules (NIV, rapports d'historique) sont traitées uniquement aux fins d'annonce et soumises aux mêmes normes de protection des données.</p>

            <p className="text-xs text-slate-400 mt-10">&copy; 2026 BidVex Inc. Tous droits réservés.</p>
          </>)}
        </main>
      </div>
    </div>
  );
};

export default PrivacyPolicyPage;
