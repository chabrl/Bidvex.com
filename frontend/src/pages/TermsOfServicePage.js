import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ScrollText, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

const tocEN = [
  { id: 'intro', label: '1. Introduction & Acceptance' },
  { id: 'platform', label: '2. Platform Role & Disclaimers' },
  { id: 'accounts', label: '3. User Accounts' },
  { id: 'seller', label: '4. Seller Responsibilities' },
  { id: 'fees', label: '5. Fees & Payment Structure' },
  { id: 'sticky-card', label: '5A. Mandatory Payment Method' },
  { id: 'escrow', label: '5B. Escrow & Pickup Code' },
  { id: 'penalty', label: '6A. Cancellation Penalty' },
  { id: 'bidding', label: '6. Bidding Rules' },
  { id: 'payment', label: '7. Payment Processing' },
  { id: 'dispute', label: '8. Dispute Resolution' },
  { id: 'prohibited', label: '9. Prohibited Conduct' },
  { id: 'liability', label: '10. Limitation of Liability' },
  { id: 'modifications', label: '11. Modifications' },
  { id: 'governing', label: '12. Governing Law & Dispute Resolution' },
  { id: 'contact', label: '13. Contact Information' },
  { id: 'vehicle-opc', label: '14. Vehicle Auctions & Provincial Dealer Compliance' },
  { id: 'broker-accounts', label: '15. Broker & Dealer Accounts' },
  { id: 'individual-accounts', label: '16. Individual User Accounts' },
  { id: 'pricing-modify', label: '17. Right to Modify Fees & Pricing' },
  { id: 'no-refund', label: '18. No-Refund Policy' },
];

const tocFR = [
  { id: 'intro', label: '1. Introduction et acceptation' },
  { id: 'platform', label: '2. Rôle de la plateforme' },
  { id: 'accounts', label: '3. Comptes utilisateur' },
  { id: 'seller', label: '4. Responsabilités du vendeur' },
  { id: 'fees', label: '5. Frais et paiement' },
  { id: 'sticky-card', label: '5A. Moyen de paiement obligatoire' },
  { id: 'escrow', label: '5B. Séquestre et code de retrait' },
  { id: 'penalty', label: '6A. Pénalité d\'annulation' },
  { id: 'bidding', label: '6. Règles d\'enchères' },
  { id: 'payment', label: '7. Traitement des paiements' },
  { id: 'dispute', label: '8. Résolution de litiges' },
  { id: 'prohibited', label: '9. Conduite interdite' },
  { id: 'liability', label: '10. Limitation de responsabilité' },
  { id: 'modifications', label: '11. Modifications' },
  { id: 'governing', label: '12. Loi applicable et résolution des litiges' },
  { id: 'contact', label: '13. Contact' },
  { id: 'vehicle-opc', label: '14. Véhicules et conformité concessionnaires provinciaux' },
  { id: 'broker-accounts', label: '15. Comptes courtiers et concessionnaires' },
  { id: 'individual-accounts', label: '16. Comptes utilisateurs individuels' },
  { id: 'pricing-modify', label: '17. Droit de modifier les frais et la tarification' },
  { id: 'no-refund', label: '18. Politique de non-remboursement' },
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

const TermsOfServicePage = () => {
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
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg"><ScrollText className="h-6 w-6 text-blue-600" /></div>
            <h1 className="text-3xl font-bold" style={{ color: '#0B2545' }}>{fr ? 'Conditions d\'utilisation de BidVex' : 'BidVex Terms & Conditions'}</h1>
          </div>
          <p className="text-sm text-slate-500">{fr ? 'Dernière mise à jour : Février 2026' : 'Last Updated: February 2026'}</p>
        </div>
      </div>

      {/* Content with Sidebar */}
      <div className="max-w-5xl mx-auto px-4 py-10 flex gap-10">
        {/* Sidebar TOC */}
        <aside className="hidden lg:block w-64 flex-shrink-0">
          <nav className="sticky top-20 space-y-1" data-testid="terms-toc">
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
        <main className="flex-1 min-w-0 prose prose-sm dark:prose-invert max-w-none" data-testid="terms-content" style={{ scrollBehavior: 'smooth' }}>

          {/* ── EN CONTENT ── */}
          {!fr ? (<>
            <SH id="intro" n="1">Introduction &amp; Acceptance of Terms</SH>
            <p>Welcome to BidVex. These Terms &amp; Conditions ("Terms") form a legally binding agreement between you ("User," "you," or "your") and BidVex Inc. ("BidVex," "we," "us," or "our"). These Terms govern your access to and use of our online auction platform, website, and related services (collectively, "the Platform").</p>
            <p><strong>By registering for an account, browsing the Platform, or participating in an auction,</strong> you acknowledge that you have read, understood, and agree to be bound by these Terms, as well as our Privacy Policy. If you do not agree to these Terms, you must not access or use the Platform.</p>
            <p>BidVex facilitates online auctions for various items, including but not limited to vehicles, consumer goods, and commercial services.</p>

            <SH id="platform" n="2">Platform Role &amp; Disclaimers</SH>
            <h3 className="text-base font-semibold mt-4">2.1 Independent Marketplace</h3>
            <p>BidVex is a digital marketplace and is not a seller, dealer, broker, owner, consignee, or agent of any listed item. We provide the technology platform and administrative services for online auctions.</p>
            <h3 className="text-base font-semibold mt-4">2.2 Transaction Parties</h3>
            <p>All sales are concluded directly between the buyer and the seller. BidVex is not a party to the actual transaction between buyers and sellers. This means BidVex does not guarantee the accuracy of any listing, the condition of any item, or the performance of any party to a transaction.</p>
            <BlueBox>
              <p><strong>Disclaimer:</strong> BidVex provides tools for auctions but assumes no responsibility for the accuracy of item descriptions, the outcome of bidding, or post-auction delivery obligations. All transactions carry inherent risk, and users participate at their own discretion.</p>
            </BlueBox>

            <SH id="accounts" n="3">User Accounts</SH>
            <p>To participate in auctions, you are required to register and maintain a valid account.</p>
            <BlueBox>
              <p><strong>Account Requirements:</strong> You must be at least 18 years of age and a resident of Canada with a valid email address to create a BidVex account. You are responsible for maintaining the security and confidentiality of your account credentials.</p>
            </BlueBox>

            <SH id="seller" n="4">Seller Responsibilities</SH>
            <p>Sellers on BidVex bear full responsibility for their listings and the items they sell. By creating a listing, sellers represent and warrant that all information provided is accurate.</p>
            <h3 className="text-base font-semibold mt-4">4.1 Marketplace Platform Sellers</h3>
            <p>Platform Sellers must provide accurate descriptions, respond to buyer inquiries, and deliver items as described.</p>
            <h3 className="text-base font-semibold mt-4">4.2 Vehicle Auction Licensed Sellers</h3>
            <p>Vehicle listings are restricted to sellers holding a verified provincial dealer licence (e.g. OMVIC in Ontario, AMVIC in Alberta, VSA in British Columbia, SAAQ road-vehicle dealer licence in Quebec, and analogues in other provinces).</p>

            <SH id="fees" n="5">Fees, Terms and Payment Structure</SH>
            <p>Upon registration, users are assigned to a specific tier. This tier determines the buyer's premium and seller commission applicable to transactions.</p>
            <div className="overflow-x-auto my-4">
              <table className="w-full text-sm border-collapse">
                <thead><tr className="bg-slate-100 dark:bg-slate-800"><th className="border border-slate-200 dark:border-slate-700 p-2 text-left">Tier</th><th className="border border-slate-200 dark:border-slate-700 p-2 text-left">Buyer's Premium</th><th className="border border-slate-200 dark:border-slate-700 p-2 text-left">Seller Commission</th></tr></thead>
                <tbody>
                  <tr><td className="border border-slate-200 dark:border-slate-700 p-2">Standard</td><td className="border border-slate-200 dark:border-slate-700 p-2">5.0%</td><td className="border border-slate-200 dark:border-slate-700 p-2">4.0%</td></tr>
                  <tr><td className="border border-slate-200 dark:border-slate-700 p-2">Premium ($360 CAD/yr + taxes)</td><td className="border border-slate-200 dark:border-slate-700 p-2">3.5%</td><td className="border border-slate-200 dark:border-slate-700 p-2">2.5%</td></tr>
                  <tr><td className="border border-slate-200 dark:border-slate-700 p-2">VIP Elite ($600 CAD/yr + taxes)</td><td className="border border-slate-200 dark:border-slate-700 p-2">3.0%</td><td className="border border-slate-200 dark:border-slate-700 p-2">2.0%</td></tr>
                </tbody>
              </table>
            </div>

            {/* NEW: 5A Sticky Card */}
            <SH id="sticky-card" n="5A">Mandatory Payment Method (Sticky Card Policy)</SH>
            <BlueBox>
              <p>To create a listing on BidVex, every Seller must have a valid payment method registered and attached to their Stripe profile.</p>
              <ul className="list-disc pl-5 space-y-1 mt-2 text-sm">
                <li>Sellers may not remove their payment method while they have active listings. Attempting to do so will be blocked by the system with an error message.</li>
                <li>BidVex retains a Stripe token only — raw card data is never stored on BidVex servers.</li>
                <li>If a Seller's card on file becomes expired or invalid while a listing is active, the listing will be automatically paused until a valid payment method is added.</li>
                <li>This policy exists to ensure BidVex can collect applicable platform fees and cancellation penalties if required.</li>
              </ul>
            </BlueBox>

            {/* NEW: 5B Escrow */}
            <SH id="escrow" n="5B">Escrow &amp; Buyer Protection — Pickup Code System</SH>
            <BlueBox>
              <p>For all non-vehicle auction items, BidVex operates an escrow system to protect both buyers and sellers.</p>
              <p className="font-semibold mt-2">How it works:</p>
              <ol className="list-decimal pl-5 space-y-1 mt-1 text-sm">
                <li>When a buyer wins an auction, their payment is captured immediately by Stripe and held in escrow on the BidVex platform.</li>
                <li>Funds are NOT transferred to the seller at this stage.</li>
                <li>The buyer receives a unique 6-character alphanumeric pickup code by email.</li>
                <li>At the time of item pickup, the buyer presents this code to the seller.</li>
                <li>The seller enters the code in their BidVex seller dashboard to confirm the handoff.</li>
                <li>Upon successful code entry, funds are released from escrow and transferred to the seller.</li>
              </ol>
              <p className="mt-2"><strong>Auto-Release Rule:</strong> If the buyer fails to collect the item and the code is not entered within 48 hours of auction close, funds are automatically released to the seller. No refund is issued to the buyer after auto-release.</p>
              <p><strong>Security:</strong> The pickup code is cryptographically generated and single-use. Five failed entry attempts triggers an automatic admin review.</p>
              <p className="text-xs text-slate-500 mt-2"><strong>Note:</strong> Vehicle transactions are handled under a separate bilateral agreement between buyer and seller. BidVex does not hold or transfer vehicle purchase funds.</p>
            </BlueBox>

            {/* NEW: 6A Cancellation Penalty */}
            <SH id="penalty" n="6A">Cancellation Penalty</SH>
            <RedBox>
              <p>A cancellation penalty of <strong>$50.00 CAD</strong> is applied when a Seller reports inability to deliver an item after auction close.</p>
              <ul className="list-disc pl-5 space-y-1 mt-2 text-sm">
                <li>The penalty is charged automatically to the Seller's payment method on file via Stripe.</li>
                <li>If the charge fails, the Seller's account is flagged for suspension pending review.</li>
                <li>BidVex retains the Stripe payment method token even if the Seller removes the card from the UI, for the sole purpose of collecting outstanding penalties.</li>
                <li>This penalty exists to protect buyers and maintain platform integrity.</li>
              </ul>
            </RedBox>

            <SH id="bidding" n="6">Bidding Rules</SH>
            <p>By placing a bid, you enter into a binding agreement to purchase the item at the bid price if your bid is the winning bid at auction close.</p>
            <BlueBox><p><strong>All bids are final and binding.</strong> Retraction is not permitted except in limited circumstances (e.g., listing error confirmed by BidVex).</p></BlueBox>

            <SH id="payment" n="7">Payment Processing</SH>
            <p>BidVex uses Stripe as its exclusive payment processor. All payments are processed in Canadian Dollars (CAD). GST/HST and QST are applied per applicable law.</p>

            <SH id="dispute" n="8">Dispute Resolution</SH>
            <p>BidVex offers a dispute resolution mechanism. Either the buyer or seller may open a dispute within 48 hours of transaction completion. During a dispute, escrow funds remain held until resolution.</p>

            <SH id="prohibited" n="9">Prohibited Conduct</SH>
            <RedBox>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>Shill bidding (bidding on your own items)</li>
                <li>Listing counterfeit, stolen, or illegal items</li>
                <li>Providing false item descriptions</li>
                <li>Harassment of users via messages or Community Q&amp;A</li>
                <li>Circumventing escrow or payment systems</li>
                <li>Creating multiple accounts to manipulate auctions</li>
              </ul>
            </RedBox>

            <SH id="liability" n="10">Limitation of Liability</SH>
            <p>BidVex's total liability to any user shall not exceed the total fees paid by that user to BidVex in the twelve (12) months preceding the claim. BidVex is not liable for indirect, incidental, consequential, or punitive damages.</p>

            <SH id="modifications" n="11">Modifications to Terms</SH>
            <p>BidVex reserves the right to modify these Terms at any time. Material changes will be communicated by email or platform notification at least 30 days before taking effect.</p>

            <SH id="governing" n="12">Governing Law &amp; Dispute Resolution</SH>
            <p>These Terms &amp; Conditions are governed by the laws of the Province of Quebec and the federal laws of Canada applicable therein.</p>
            <p>Any dispute arising from the use of BidVex that cannot be resolved informally shall be submitted to the exclusive jurisdiction of the courts of the District of Saint-François (Sherbrooke), Quebec, Canada.</p>
            <BlueBox>
              <p>For users in other Canadian provinces, BidVex complies with applicable provincial consumer protection legislation. U.S.-based users acknowledge that BidVex is a Canadian platform subject to Canadian law.</p>
            </BlueBox>

            <SH id="contact" n="13">Contact Information</SH>
            <GreenBox><p><strong>BidVex Legal Department</strong><br />Email: <a href="mailto:support@bidvex.com" className="text-blue-600 underline">support@bidvex.com</a></p></GreenBox>

            <SH id="vehicle-opc" n="14">Vehicle Auctions — Platform Role &amp; Provincial Dealer Compliance</SH>
            <p>BidVex is a technology platform and auction facilitator only. BidVex is not a vendor, dealer, or party to vehicle sale contracts. Only sellers holding a verified provincial dealer licence (OMVIC, AMVIC, VSA, SAAQ, FCAA, MVSDA or the analogous regulator in their province) may list road vehicles.</p>
            <BlueBox><p>By listing vehicles on BidVex, dealers represent that they hold a valid provincial dealer licence and comply with all applicable federal and provincial consumer-protection and motor-vehicle-dealer laws.</p></BlueBox>

            <SH id="broker-accounts" n="15">Broker &amp; Dealer Accounts</SH>
            <h3 className="text-base font-semibold mt-4">15.1 Broker Registration and Eligibility</h3>
            <p>To register as a Broker or Dealer on BidVex, you must hold a valid and current broker or dealer license issued by the applicable provincial or federal authority in Canada or the United States. BidVex reserves the right to verify submitted credentials and to deny, suspend, or revoke broker status at any time if documents are found to be invalid, expired, or fraudulent.</p>

            <h3 className="text-base font-semibold mt-4">15.2 Broker Responsibilities</h3>
            <p>Brokers are responsible for the accuracy of all listings published through their account. Brokers must ensure all items listed comply with applicable Canadian and provincial law, including but not limited to the Competition Act (R.S.C., 1985, c. C-34) and the Consumer Protection Act (L.R.Q., c. P-40.1). BidVex is a marketplace platform and does not take title to any goods. Brokers bear full legal responsibility for the items they list and the transactions they facilitate.</p>

            <h3 className="text-base font-semibold mt-4">15.3 Broker Subscription Fees</h3>
            <BlueBox>
              <p>Brokers are subject to an annual platform subscription fee as published on the BidVex pricing page at the time of registration. BidVex may offer promotional pricing, launch discounts, or individualized pricing at its sole discretion. Subscription fees are non-refundable once the billing period has commenced. Access to broker features will remain active until the end of the current billing period following cancellation.</p>
            </BlueBox>

            <SH id="individual-accounts" n="16">Individual User Accounts (Buyers and Sellers)</SH>
            <h3 className="text-base font-semibold mt-4">16.1 Individual Registration</h3>
            <p>Individual users may register as buyers and/or sellers on BidVex by providing accurate personal information and agreeing to these Terms. Sellers must comply with all listing policies and applicable laws. Buyers acknowledge that all winning bids constitute a binding purchase commitment.</p>

            <h3 className="text-base font-semibold mt-4">16.2 Seller Commissions</h3>
            <p>Individual sellers may be subject to a commission on completed sales as published in the BidVex fee schedule. BidVex reserves the right to modify commission rates at any time with thirty (30) days written notice to active sellers.</p>

            <h3 className="text-base font-semibold mt-4">16.3 Buyer's Premium</h3>
            <p>Certain auctions on BidVex may include a buyer's premium, which is an additional percentage charged to the winning bidder on top of the hammer price. The applicable buyer's premium, if any, will be clearly disclosed on each auction listing prior to bidding. BidVex reserves the right to adjust buyer's premium rates at any time.</p>

            <SH id="pricing-modify" n="17">Fees, Pricing, and Right to Modify</SH>
            <RedBox>
              <p><strong>BidVex Inc. reserves the right to change, adjust, or discontinue any fee, subscription price, transaction commission, buyer's premium, platform charge, or promotional discount at any time without prior notice for new transactions or registrations.</strong></p>
              <p className="mt-2">For existing active subscriptions or ongoing agreements, BidVex will provide no less than thirty (30) days advance written notice of material price changes, delivered to the email address on file. If you do not accept the revised fees, you may cancel your subscription or account prior to the effective date. Continued use of BidVex after the effective date constitutes your acceptance of the new fee structure.</p>
              <p className="mt-2">This provision is made in accordance with the Quebec Consumer Protection Act (L.R.Q., c. P-40.1) and applicable Canadian contract law.</p>
            </RedBox>

            <SH id="no-refund" n="18">No-Refund Policy</SH>
            <BlueBox>
              <p>All subscription fees paid to BidVex are non-refundable. Upon cancellation, your subscription will remain active until the end of the current paid billing period. No partial refunds are issued for unused time. This policy applies to Broker Annual Plans and any other subscription products offered by BidVex Inc.</p>
              <p className="mt-2"><strong>Exception:</strong> BidVex may issue refunds at its sole discretion in cases of documented technical failure attributable to BidVex that prevents platform access for a continuous period exceeding seventy-two (72) hours.</p>
            </BlueBox>

            <p className="text-xs text-slate-400 mt-10">&copy; 2026 BidVex Inc. All rights reserved.</p>
          </>) : (<>

            {/* ── FR CONTENT ── */}
            <SH id="intro" n="1">Introduction et acceptation des conditions</SH>
            <p>Bienvenue sur BidVex. Les présentes conditions d'utilisation (« Conditions ») constituent un accord juridiquement contraignant entre vous (« Utilisateur ») et BidVex Inc. (« BidVex », « nous »). Ces Conditions régissent votre accès et votre utilisation de notre plateforme d'enchères en ligne.</p>
            <p><strong>En vous inscrivant, en naviguant sur la Plateforme ou en participant à une enchère,</strong> vous reconnaissez avoir lu, compris et accepté d'être lié par ces Conditions, ainsi que par notre Politique de confidentialité.</p>

            <SH id="platform" n="2">Rôle de la plateforme et avis de non-responsabilité</SH>
            <h3 className="text-base font-semibold mt-4">2.1 Marché indépendant</h3>
            <p>BidVex est un marché numérique et n'est pas un vendeur, concessionnaire, courtier, propriétaire ou agent de tout article listé.</p>
            <h3 className="text-base font-semibold mt-4">2.2 Parties à la transaction</h3>
            <p>Toutes les ventes sont conclues directement entre l'acheteur et le vendeur. BidVex n'est pas partie à la transaction.</p>

            <SH id="accounts" n="3">Comptes utilisateur</SH>
            <p>Pour participer aux enchères, vous devez créer et maintenir un compte valide. Vous devez avoir au moins 18 ans et résider au Canada.</p>

            <SH id="seller" n="4">Responsabilités du vendeur</SH>
            <p>Les vendeurs sont entièrement responsables de leurs annonces et des articles qu'ils vendent. En créant une annonce, les vendeurs déclarent que toutes les informations fournies sont exactes.</p>

            <SH id="fees" n="5">Frais, conditions et structure de paiement</SH>
            <p>Lors de l'inscription, les utilisateurs sont assignés à un niveau spécifique déterminant la prime acheteur et la commission vendeur.</p>
            <div className="overflow-x-auto my-4">
              <table className="w-full text-sm border-collapse">
                <thead><tr className="bg-slate-100 dark:bg-slate-800"><th className="border border-slate-200 dark:border-slate-700 p-2 text-left">Niveau</th><th className="border border-slate-200 dark:border-slate-700 p-2 text-left">Prime acheteur</th><th className="border border-slate-200 dark:border-slate-700 p-2 text-left">Commission vendeur</th></tr></thead>
                <tbody>
                  <tr><td className="border border-slate-200 dark:border-slate-700 p-2">Standard</td><td className="border border-slate-200 dark:border-slate-700 p-2">5,0 %</td><td className="border border-slate-200 dark:border-slate-700 p-2">4,0 %</td></tr>
                  <tr><td className="border border-slate-200 dark:border-slate-700 p-2">Premium (360 $ CAD/an + taxes)</td><td className="border border-slate-200 dark:border-slate-700 p-2">3,5 %</td><td className="border border-slate-200 dark:border-slate-700 p-2">2,5 %</td></tr>
                  <tr><td className="border border-slate-200 dark:border-slate-700 p-2">VIP Élite (600 $ CAD/an + taxes)</td><td className="border border-slate-200 dark:border-slate-700 p-2">3,0 %</td><td className="border border-slate-200 dark:border-slate-700 p-2">2,0 %</td></tr>
                </tbody>
              </table>
            </div>

            <SH id="sticky-card" n="5A">Moyen de paiement obligatoire (Politique Sticky Card)</SH>
            <BlueBox>
              <p>Pour créer une annonce sur BidVex, chaque Vendeur doit avoir un moyen de paiement valide enregistré, rattaché à son profil Stripe.</p>
              <ul className="list-disc pl-5 space-y-1 mt-2 text-sm">
                <li>Les Vendeurs ne peuvent pas supprimer leur moyen de paiement tant que leurs annonces sont actives. Toute tentative sera bloquée par le système avec un message d'erreur.</li>
                <li>BidVex conserve uniquement un jeton Stripe — les données brutes de carte ne sont jamais stockées sur les serveurs BidVex.</li>
                <li>Si la carte enregistrée d'un Vendeur expire ou devient invalide pendant qu'une annonce est active, l'annonce sera automatiquement mise en pause jusqu'à l'ajout d'un moyen de paiement valide.</li>
                <li>Cette politique permet à BidVex de percevoir les frais de plateforme applicables et les pénalités d'annulation si nécessaire.</li>
              </ul>
            </BlueBox>

            <SH id="escrow" n="5B">Séquestre et protection de l'acheteur — Système de code de retrait</SH>
            <BlueBox>
              <p>Pour tous les articles d'enchères non-véhicules, BidVex opère un système de séquestre pour protéger acheteurs et vendeurs.</p>
              <p className="font-semibold mt-2">Fonctionnement :</p>
              <ol className="list-decimal pl-5 space-y-1 mt-1 text-sm">
                <li>Lorsqu'un acheteur remporte une enchère, son paiement est capturé immédiatement par Stripe et conservé en séquestre sur la plateforme BidVex.</li>
                <li>Les fonds ne sont PAS transférés au Vendeur à ce stade.</li>
                <li>L'acheteur reçoit un code de retrait alphanumérique unique de 6 caractères par courriel.</li>
                <li>Au moment du retrait de l'article, l'acheteur présente ce code au Vendeur.</li>
                <li>Le Vendeur saisit le code dans son tableau de bord BidVex pour confirmer la remise.</li>
                <li>Après saisie correcte du code, les fonds sont libérés du séquestre et transférés au Vendeur.</li>
              </ol>
              <p className="mt-2"><strong>Règle de libération automatique :</strong> Si l'acheteur ne récupère pas l'article et que le code n'est pas saisi dans les 48 heures suivant la clôture de l'enchère, les fonds sont automatiquement libérés au Vendeur. Aucun remboursement n'est accordé après la libération automatique.</p>
              <p><strong>Sécurité :</strong> Le code de retrait est généré cryptographiquement et à usage unique. Cinq tentatives échouées déclenchent une révision administrative automatique.</p>
              <p className="text-xs text-slate-500 mt-2"><strong>Note :</strong> Les transactions de véhicules sont gérées par accord bilatéral entre acheteur et vendeur. BidVex ne détient ni ne transfère les fonds d'achat de véhicules.</p>
            </BlueBox>

            <SH id="penalty" n="6A">Pénalité d'annulation</SH>
            <RedBox>
              <p>Une pénalité d'annulation de <strong>50,00 $ CAD</strong> est appliquée lorsqu'un Vendeur signale l'impossibilité de livrer un article après la clôture d'une enchère.</p>
              <ul className="list-disc pl-5 space-y-1 mt-2 text-sm">
                <li>Le montant est prélevé automatiquement sur le moyen de paiement du Vendeur enregistré via Stripe.</li>
                <li>En cas d'échec du prélèvement, le compte du Vendeur est signalé pour suspension dans l'attente d'une révision.</li>
                <li>BidVex conserve le jeton Stripe même si le Vendeur supprime la carte de l'interface, dans le seul but de percevoir les pénalités impayées.</li>
                <li>Cette pénalité existe pour protéger les acheteurs et maintenir l'intégrité de la plateforme.</li>
              </ul>
            </RedBox>

            <SH id="bidding" n="6">Règles d'enchères</SH>
            <p>En plaçant une enchère, vous concluez un accord contraignant pour acheter l'article au prix de votre enchère si celle-ci est gagnante.</p>
            <BlueBox><p><strong>Toutes les enchères sont définitives et contraignantes.</strong></p></BlueBox>

            <SH id="payment" n="7">Traitement des paiements</SH>
            <p>BidVex utilise Stripe comme processeur de paiement exclusif. Tous les paiements sont en dollars canadiens (CAD). La TPS/TVH et la TVQ sont appliquées conformément à la loi.</p>

            <SH id="dispute" n="8">Résolution de litiges</SH>
            <p>BidVex offre un mécanisme de résolution de litiges. Chaque partie peut ouvrir un litige dans les 48 heures. Les fonds en séquestre restent détenus pendant la résolution.</p>

            <SH id="prohibited" n="9">Conduite interdite</SH>
            <RedBox>
              <ul className="list-disc pl-5 space-y-1 text-sm">
                <li>Enchères fictives sur vos propres articles</li>
                <li>Mise en vente d'articles contrefaits, volés ou illégaux</li>
                <li>Descriptions trompeuses d'articles</li>
                <li>Harcèlement via messages ou communauté Q&amp;R</li>
                <li>Contournement des systèmes de paiement ou séquestre</li>
                <li>Création de comptes multiples pour manipuler les enchères</li>
              </ul>
            </RedBox>

            <SH id="liability" n="10">Limitation de responsabilité</SH>
            <p>La responsabilité totale de BidVex est limitée aux frais payés par l'utilisateur dans les douze (12) mois précédant la réclamation.</p>

            <SH id="modifications" n="11">Modifications</SH>
            <p>BidVex se réserve le droit de modifier ces Conditions. Les changements importants seront communiqués au moins 30 jours avant leur entrée en vigueur.</p>

            <SH id="governing" n="12">Loi applicable et résolution des litiges</SH>
            <p>Les présentes Conditions sont régies par les lois de la province de Québec et les lois fédérales du Canada qui y sont applicables.</p>
            <p>Tout litige découlant de l'utilisation de BidVex qui ne peut être résolu à l'amiable sera soumis à la compétence exclusive des tribunaux du district de Saint-François (Sherbrooke), Québec, Canada.</p>
            <BlueBox>
              <p>Pour les utilisateurs des autres provinces canadiennes, BidVex se conforme à la législation provinciale applicable en matière de protection du consommateur. Les utilisateurs basés aux États-Unis reconnaissent que BidVex est une plateforme canadienne soumise au droit canadien.</p>
            </BlueBox>

            <SH id="contact" n="13">Contact</SH>
            <GreenBox><p><strong>Département juridique BidVex</strong><br />Courriel : <a href="mailto:support@bidvex.com" className="text-blue-600 underline">support@bidvex.com</a></p></GreenBox>

            <SH id="vehicle-opc" n="14">Enchères de véhicules — Rôle de la plateforme et conformité concessionnaires provinciaux</SH>
            <p>BidVex est une plateforme technologique et un facilitateur d'enchères uniquement. Seuls les vendeurs détenant une licence de concessionnaire provinciale vérifiée (OMVIC, AMVIC, VSA, SAAQ, FCAA, MVSDA ou le régulateur analogue de leur province) peuvent lister des véhicules routiers.</p>
            <BlueBox><p>En listant des véhicules sur BidVex, les concessionnaires déclarent détenir une licence de concessionnaire provinciale valide et se conformer à toutes les lois fédérales et provinciales applicables en matière de protection du consommateur et de concessionnaires de véhicules.</p></BlueBox>

            <SH id="broker-accounts" n="15">Comptes courtiers et concessionnaires</SH>
            <h3 className="text-base font-semibold mt-4">15.1 Inscription et admissibilité du courtier</h3>
            <p>Pour vous inscrire en tant que courtier ou concessionnaire sur BidVex, vous devez détenir un permis de courtier ou de concessionnaire valide et en vigueur, délivré par l'autorité provinciale ou fédérale applicable au Canada ou aux États-Unis. BidVex se réserve le droit de vérifier les pièces justificatives soumises et de refuser, suspendre ou révoquer le statut de courtier à tout moment si les documents sont jugés invalides, expirés ou frauduleux.</p>

            <h3 className="text-base font-semibold mt-4">15.2 Responsabilités du courtier</h3>
            <p>Les courtiers sont responsables de l'exactitude de toutes les annonces publiées via leur compte. Les courtiers doivent s'assurer que tous les articles répertoriés respectent les lois canadiennes et provinciales applicables, y compris, sans s'y limiter, la Loi sur la concurrence (L.R.C., 1985, ch. C-34) et la Loi sur la protection du consommateur (L.R.Q., c. P-40.1). BidVex est une plateforme de marché et ne prend pas titre de propriété sur les biens. Les courtiers assument l'entière responsabilité légale des articles qu'ils listent et des transactions qu'ils facilitent.</p>

            <h3 className="text-base font-semibold mt-4">15.3 Frais d'abonnement de courtier</h3>
            <BlueBox>
              <p>Les courtiers sont assujettis à des frais annuels d'abonnement de plateforme tels que publiés sur la page de tarification BidVex au moment de l'inscription. BidVex peut offrir une tarification promotionnelle, des rabais de lancement ou une tarification individualisée à sa seule discrétion. Les frais d'abonnement ne sont pas remboursables une fois la période de facturation commencée. L'accès aux fonctionnalités de courtier restera actif jusqu'à la fin de la période de facturation en cours après annulation.</p>
            </BlueBox>

            <SH id="individual-accounts" n="16">Comptes utilisateurs individuels (acheteurs et vendeurs)</SH>
            <h3 className="text-base font-semibold mt-4">16.1 Inscription des particuliers</h3>
            <p>Les utilisateurs individuels peuvent s'inscrire en tant qu'acheteurs et/ou vendeurs sur BidVex en fournissant des informations personnelles exactes et en acceptant les présentes Conditions. Les vendeurs doivent respecter toutes les politiques d'annonces et les lois applicables. Les acheteurs reconnaissent que toute enchère gagnante constitue un engagement d'achat ferme.</p>

            <h3 className="text-base font-semibold mt-4">16.2 Commissions du vendeur</h3>
            <p>Les vendeurs individuels peuvent être soumis à une commission sur les ventes complétées, telle que publiée dans le barème de frais de BidVex. BidVex se réserve le droit de modifier les taux de commission à tout moment avec un préavis écrit de trente (30) jours aux vendeurs actifs.</p>

            <h3 className="text-base font-semibold mt-4">16.3 Prime de l'acheteur</h3>
            <p>Certaines enchères sur BidVex peuvent inclure une prime de l'acheteur, qui est un pourcentage additionnel facturé à l'enchérisseur gagnant en plus du prix marteau. La prime de l'acheteur applicable, le cas échéant, sera clairement divulguée sur chaque annonce d'enchère avant l'enchère. BidVex se réserve le droit d'ajuster les taux de prime de l'acheteur à tout moment.</p>

            <SH id="pricing-modify" n="17">Frais, tarification et droit de modifier</SH>
            <RedBox>
              <p><strong>BidVex Inc. se réserve le droit de modifier, ajuster ou interrompre tout frais, prix d'abonnement, commission de transaction, prime d'acheteur, frais de plateforme ou rabais promotionnel à tout moment sans préavis pour les nouvelles transactions ou inscriptions.</strong></p>
              <p className="mt-2">Pour les abonnements actifs ou les accords en cours, BidVex fournira un préavis écrit d'au moins trente (30) jours des modifications importantes de prix, envoyé à l'adresse courriel au dossier. Si vous n'acceptez pas les frais révisés, vous pouvez annuler votre abonnement ou compte avant la date d'entrée en vigueur. L'utilisation continue de BidVex après la date d'entrée en vigueur constitue votre acceptation de la nouvelle structure de frais.</p>
              <p className="mt-2">Cette disposition est prise conformément à la Loi sur la protection du consommateur du Québec (L.R.Q., c. P-40.1) et au droit canadien des contrats applicable.</p>
            </RedBox>

            <SH id="no-refund" n="18">Politique de non-remboursement</SH>
            <BlueBox>
              <p>Tous les frais d'abonnement payés à BidVex sont non remboursables. Après annulation, votre abonnement restera actif jusqu'à la fin de la période de facturation payée en cours. Aucun remboursement partiel n'est émis pour le temps non utilisé. Cette politique s'applique aux Forfaits annuels de courtier et à tout autre produit d'abonnement offert par BidVex Inc.</p>
              <p className="mt-2"><strong>Exception :</strong> BidVex peut émettre des remboursements à sa seule discrétion en cas de défaillance technique documentée attribuable à BidVex qui empêche l'accès à la plateforme pendant une période continue dépassant soixante-douze (72) heures.</p>
            </BlueBox>

            <p className="text-xs text-slate-400 mt-10">&copy; 2026 BidVex Inc. Tous droits réservés.</p>
          </>)}
        </main>
      </div>
    </div>
  );
};

export default TermsOfServicePage;
