import React from 'react';
import { Card, CardContent } from '../components/ui/card';
import { ScrollText, Shield, ArrowLeft, CreditCard, Lock, Key, Clock, AlertTriangle, Database } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { AIDisclosureLegalSection, VehicleAuctionLegalSection, CrossBorderLegalSection } from '../components/legal/LegalComplianceSections';

const LegalPage = () => {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen bg-background py-12 px-4">
      <div className="max-w-4xl mx-auto space-y-10">
        {/* Header */}
        <div className="text-center space-y-3">
          <Link to="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-primary mb-4" data-testid="legal-back-link">
            <ArrowLeft className="h-4 w-4" /> Back to Home
          </Link>
          <h1 className="text-4xl font-bold tracking-tight" data-testid="legal-page-title">Legal</h1>
          <p className="text-muted-foreground">Terms &amp; Conditions and Privacy Policy for BidVex Inc.</p>
        </div>

        {/* ──────────────────── TERMS & CONDITIONS ──────────────────── */}
        <Card id="terms" data-testid="terms-section">
          <CardContent className="pt-6 space-y-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <ScrollText className="h-6 w-6 text-blue-600" />
              </div>
              <h2 className="text-2xl font-bold">BidVex Terms &amp; Conditions</h2>
            </div>
            <p className="text-sm text-muted-foreground">Last Updated: March 2026</p>

            <div className="prose prose-sm dark:prose-invert max-w-none space-y-5">

              {/* 1 */}
              <h3 className="text-lg font-semibold">1. Introduction &amp; Acceptance of Terms</h3>
              <p>Welcome to BidVex. These Terms &amp; Conditions ("Terms") form a legally binding agreement between you ("User," "you," or "your") and BidVex Inc. ("BidVex," "we," "us," or "our"). These Terms govern your access to and use of our online auction platform, website, and related services (collectively, "the Platform").</p>
              <p><strong>By registering for an account, browsing the Platform, or participating in an auction,</strong> you acknowledge that you have read, understood, and agree to be bound by these Terms, as well as our Privacy Policy. If you do not agree to these Terms, you must not access or use the Platform.</p>
              <p>BidVex facilitates online auctions for various items, including but not limited to vehicles, consumer goods, and commercial services.</p>

              {/* 2 */}
              <h3 className="text-lg font-semibold">2. Platform Role &amp; Disclaimers</h3>
              <h4 className="font-semibold">2.1 Independent Marketplace</h4>
              <p>BidVex is a digital marketplace and is not a seller, dealer, broker, owner, bailee, or agent of any listed items. BidVex does not have possession of, title to, or ownership rights in any item listed for sale.</p>
              <h4 className="font-semibold">2.2 Transaction Parties</h4>
              <p>All sales are completed directly between the buyer and the seller. BidVex is not a party to the actual transaction between buyers and sellers. We do not transfer legal ownership of items from the seller to the buyer.</p>
              <h4 className="font-semibold">2.3 BidVex Disclaimers</h4>
              <p>BidVex does not and cannot:</p>
              <ul className="list-disc pl-6 space-y-1">
                <li>Inspect, certify, guarantee, or verify the condition, safety, legality, accuracy, or quality of listed items;</li>
                <li>Handle or coordinate delivery, transport, storage, or logistics for any items;</li>
                <li>Provide any warranties, express or implied, regarding the items; or</li>
                <li>Accept responsibility for, or guarantee the resolution of, any disputes between buyers and sellers.</li>
              </ul>

              {/* 3 */}
              <h3 className="text-lg font-semibold">3. User Accounts</h3>
              <h4 className="font-semibold">3.1 Registration</h4>
              <p>To participate in auctions, you are required to register and maintain a user account.</p>
              <h4 className="font-semibold">3.2 User Responsibilities</h4>
              <p>By creating an account, you agree to:</p>
              <ul className="list-disc pl-6 space-y-1">
                <li>Provide accurate, current, and complete information during the registration process;</li>
                <li>Maintain the security of your account by protecting your password and restricting access;</li>
                <li>Assume all responsibility for all activities that occur under your account; and</li>
                <li>Immediately report any unauthorized access or use of your account to BidVex.</li>
              </ul>
              <h4 className="font-semibold">3.3 Eligibility</h4>
              <p>{t("legal.mustBeAtLeast")} <strong>eighteen (18) years of age</strong> and possess the legal capacity to enter into binding contracts to register for an account and use the Platform.</p>

              {/* 4 */}
              <h3 className="text-lg font-semibold">4. Seller Responsibilities</h3>
              <h4 className="font-semibold">4.1 Seller Covenants</h4>
              <p>Sellers must adhere to the following obligations:</p>
              <ul className="list-disc pl-6 space-y-1">
                <li>Provide accurate, complete, and detailed descriptions, specifications, and high-quality images of listed items;</li>
                <li>Confirm and guarantee legal ownership or the specific legal right to sell the listed items;</li>
                <li>Fully disclose any known defects, liens, encumbrances, or restrictions on the items;</li>
                <li>Comply with all applicable laws and regulations regarding the sale of the items;</li>
                <li>Complete the sale of an item with the winning bidder in a timely manner; and</li>
                <li>Respond promptly and professionally to buyer inquiries.</li>
              </ul>
              <h4 className="font-semibold">4.2 Prohibited Listings</h4>
              <p>Sellers are strictly prohibited from listing items that are illegal, counterfeit, stolen, hazardous, recallable, or otherwise restricted by law or BidVex policy.</p>

              {/* 5 */}
              <h3 className="text-lg font-semibold">5. Buyer Responsibilities</h3>
              <h4 className="font-semibold">5.1 Due Diligence</h4>
              <p>Buyers acknowledge that it is their sole responsibility to inspect items, ask questions of the seller, or arrange third-party inspections before placing a bid, as needed.</p>
              <h4 className="font-semibold">5.2 Legally Binding Bids</h4>
              <p>By placing a bid, you are making a <strong>legally binding offer</strong> to purchase the item if your bid is the highest at the close of the auction, subject to any reserve price.</p>
              <h4 className="font-semibold">5.3 Completion of Transaction</h4>
              <p>If you are the winning bidder, you agree to complete the payment within the specified deadlines and arrange for the delivery or pickup of the item directly with the seller.</p>
              <h4 className="font-semibold">5.4 Accurate Information</h4>
              <p>Buyers must provide accurate shipping and contact information to ensure successful communication and transaction completion.</p>

              {/* 6 */}
              <h3 className="text-lg font-semibold">6. Bidding &amp; Auction Rules</h3>
              <h4 className="font-semibold">6.1 Binding Bids</h4>
              <p>All bids placed on the Platform are legally binding contractual obligations.</p>
              <h4 className="font-semibold">6.2 Bid Retraction</h4>
              <p>Bid retractions are not permitted except in exceptional and limited circumstances, such as a material typographical error, and only if requested within <strong>one (1) hour</strong> of placing the bid.</p>
              <h4 className="font-semibold">6.3 Reserve Prices</h4>
              <p>Sellers may set a "Reserve Price" (the confidential minimum price the seller is willing to accept). The item will not be sold unless the Reserve Price is met.</p>
              <h4 className="font-semibold">6.4 Anti-Sniping Policy</h4>
              <p>If a bid is placed within the final <strong>two (2) minutes</strong> of an auction's scheduled end time, the auction duration will be extended by an additional two (2) minutes. This ensures a fair bidding process.</p>

              {/* 7 */}
              <h3 className="text-lg font-semibold">7. Fees, Taxes, and Payment Structure</h3>
              <h4 className="font-semibold">7.1 User Tiers</h4>
              <p>Upon registration, users are assigned to a specific tier. This tier dictates the applicable Buyer Premium and Seller Commission. All amounts are in Canadian Dollars (CAD). Subscriptions are billed annually (yearly).</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse border border-border">
                  <thead><tr className="bg-muted"><th className="border border-border p-2 text-left">Tier</th><th className="border border-border p-2 text-left">Buyer Premium</th><th className="border border-border p-2 text-left">Seller Commission</th></tr></thead>
                  <tbody>
                    <tr><td className="border border-border p-2">Standard</td><td className="border border-border p-2">5.0%</td><td className="border border-border p-2">4.0%</td></tr>
                    <tr><td className="border border-border p-2">Premium ($180 CAD/yr + taxes)</td><td className="border border-border p-2">3.5%</td><td className="border border-border p-2">2.5%</td></tr>
                    <tr><td className="border border-border p-2">VIP Elite ($300 CAD/yr + taxes)</td><td className="border border-border p-2">3.0%</td><td className="border border-border p-2">2.0%</td></tr>
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-muted-foreground mt-2">GST/QST will be calculated and added at checkout based on the user's jurisdiction.</p>

              <h4 className="font-semibold">7.2 Partner Account Fees</h4>
              <p>Verified Partner accounts (licensed auctioneers, bankruptcy trustees, liquidators) are subject to the following fee structure. All amounts are in Canadian Dollars (CAD):</p>
              <ul className="list-disc pl-6 space-y-1">
                <li><strong>Annual Platform Access Fee:</strong> A flat fee of <strong>$100.00 CAD per year</strong> is charged for access to Partner-level platform features.</li>
                <li><strong>Hammer Price Commission:</strong> A <strong>3% platform fee</strong> is charged on the final "hammer price" (winning bid amount) of every item listed by a Partner.</li>
                <li><strong>Buyer's Premium Flexibility:</strong> Partners retain the full right to set their own Buyer's Premium (BP) independently of the platform fee. The BP is collected by the Partner and is not subject to the 3% commission.</li>
              </ul>
              <p>Partner accounts are subject to manual verification of business registration (NEQ) before they may list items on the Platform.</p>

              <h4 className="font-semibold">7.3 Additional Fees</h4>
              <p>A mandatory <strong>Platform Fee of 2.5%</strong> is applied to all completed transactions for vehicles only.</p>

              <h4 className="font-semibold">7.4 Taxes</h4>
              <p>All prices and fees quoted on this page are exclusive of taxes. <strong>GST (Goods and Services Tax) and QST (Quebec Sales Tax)</strong> are applied on top of all platform fees, commissions, and subscription charges in accordance with Canadian and Quebec tax law. Tax calculations are based on the final sale price and the jurisdiction of the transaction.</p>

              <h4 className="font-semibold">7.5 Payment Terms</h4>
              <p>{t("legal.fullPaymentDue")} <strong>fourteen (14) days</strong> of the auction close.</p>
              <p><strong>Late Payments:</strong> {t("legal.latePaymentPenalty")} <strong>2% per month</strong> (24% per annum) on the outstanding balance.</p>

              <h4 className="font-semibold">7.6 Payment Processing</h4>
              <p>{t("legal.paymentsHandledVia")} <strong>Stripe</strong>, a secure third-party payment processor. BidVex does not store, possess, or have access to any full credit card or bank account payment information.</p>

              {/* 8 */}
              <h3 className="text-lg font-semibold">8. "AS-IS / WHERE-IS" Clause</h3>
              <p className="uppercase text-xs leading-relaxed font-medium">
                YOU EXPRESSLY AGREE THAT ALL ITEMS LISTED ON THE PLATFORM ARE SOLD "AS-IS, WHERE-IS," WITH ALL FAULTS AND DEFECTS, AND WITHOUT ANY WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING ANY WARRANTY OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE. BIDVEX IS NOT RESPONSIBLE FOR THE CONDITION, SAFETY, LEGALITY, OR ACCURACY OF ANY ITEM OR FOR ANY DISPUTES BETWEEN USERS.
              </p>

              {/* 9 */}
              <h3 className="text-lg font-semibold">9. Listing Promotions &amp; Marketing</h3>
              <h4 className="font-semibold">9.1 Promotional Services</h4>
              <p>BidVex offers optional paid listing promotions (e.g., Featured Listing, Highlighted Listing, Homepage Spotlight) to increase visibility for sellers. Promotional fees are quoted in Canadian Dollars (CAD) and are subject to GST/QST.</p>
              <h4 className="font-semibold">9.2 Non-Refundable</h4>
              <p><strong>All listing promotions are non-refundable once activated.</strong> Once a promotion is applied to a listing, no refund, credit, or cancellation will be issued regardless of the auction outcome.</p>
              <h4 className="font-semibold">9.3 Pay-As-You-Go Marketing Emails</h4>
              <p><strong>Pay-as-you-go marketing email campaigns are billed immediately upon purchase and are final.</strong> No refunds or credits will be issued for unused email quota or campaign performance.</p>

              {/* 10 */}
              <h3 className="text-lg font-semibold">10. Dispute Resolution</h3>
              <h4 className="font-semibold">10.1 Direct Resolution</h4>
              <p>In the event of a dispute between a buyer and a seller, the parties agree to first attempt to resolve the issue directly and in good faith.</p>
              <h4 className="font-semibold">10.2 Mediation by Support</h4>
              <p>If the parties are unable to resolve the dispute, they may contact BidVex Support within <strong>seven (7) days</strong> of the transaction close. BidVex may, at its sole discretion, attempt to mediate the dispute, but BidVex is not obligated to do so.</p>
              <h4 className="font-semibold">10.3 Refunds</h4>
              <p>Refunds, returns, or adjustments are at the sole discretion of the seller unless BidVex determines that an item was significantly misrepresented in the listing. <strong>Subscription fees and platform service fees are non-refundable.</strong></p>

              {/* 11 */}
              <h3 className="text-lg font-semibold">11. Intellectual Property</h3>
              <h4 className="font-semibold">11.1 Ownership</h4>
              <p>All content and materials on the Platform, including the BidVex logo, text, graphics, images, video, code, and software are the property of BidVex Inc. or its licensors and are protected by copyright, trademark, and other intellectual property laws.</p>
              <h4 className="font-semibold">11.2 Use Restrictions</h4>
              <ul className="list-disc pl-6 space-y-1">
                <li>Users are prohibited from copying, reproducing, modifying, distributing, or selling any Content without prior written permission.</li>
                <li>The use of our trademarks, logos, or branding without express authorization is prohibited.</li>
                <li>You are not permitted to use "scraping," "data mining," or automated agents to collect information from the Platform.</li>
              </ul>

              {/* 12 */}
              <h3 className="text-lg font-semibold">12. Prohibited Conduct</h3>
              <p>Users are strictly prohibited from engaging in the following conduct:</p>
              <ul className="list-disc pl-6 space-y-1">
                <li>Engaging in fraud, shill bidding, or any form of bid manipulation or artificial inflation;</li>
                <li>Harassing, threatening, or defrauding other users or BidVex employees;</li>
                <li>Posting spam, viruses, or malicious code that may harm the Platform or users;</li>
                <li>Circumventing BidVex fees or manipulating the auction process;</li>
                <li>Creating multiple accounts to bypass restrictions or manipulate auctions; or</li>
                <li>Engaging in any conduct that violates applicable laws or regulations.</li>
              </ul>
              <p>Violations of this section may result in immediate suspension or termination of your account, and may result in legal action.</p>

              {/* 13 */}
              <h3 className="text-lg font-semibold">13. Limitation of Liability</h3>
              <p className="uppercase text-xs leading-relaxed font-medium">
                TO THE FULLEST EXTENT PERMITTED BY LAW, BIDVEX PROVIDES THE PLATFORM "AS IS" AND "AS AVAILABLE." BIDVEX SHALL NOT BE LIABLE FOR: THE ACCURACY, COMPLETENESS, OR RELIABILITY OF ITEM DESCRIPTIONS; THE ACTIONS, OMISSIONS, OR CONDUCT OF BUYERS OR SELLERS; ANY LOSSES, DAMAGES, OR HARM ARISING FROM DOWNTIME, ERRORS, OR TECHNICAL INTERRUPTIONS; OR ANY DIRECT, INDIRECT, INCIDENTAL, CONSEQUENTIAL, SPECIAL, OR PUNITIVE DAMAGES. OUR MAXIMUM AGGREGATE LIABILITY SHALL NOT EXCEED THE TOTAL FEES PAID BY YOU TO BIDVEX IN THE TWELVE (12) MONTHS PRIOR TO THE CLAIM.
              </p>

              {/* 14 */}
              <h3 className="text-lg font-semibold">14. Suspension &amp; Termination</h3>
              <h4 className="font-semibold">14.1 BidVex's Right</h4>
              <p>BidVex reserves the right, at its sole discretion, to suspend, terminate, or restrict your account and access to the Platform if you violate these Terms or engage in conduct harmful to BidVex or its users.</p>
              <h4 className="font-semibold">14.2 User Closing Account</h4>
              <p>You may close your BidVex account at any time. However, closing your account does not release you from any outstanding obligations, including legally binding bids and payment requirements.</p>

              {/* 15 */}
              <h3 className="text-lg font-semibold">15. Changes to Terms &amp; Conditions</h3>
              <p>BidVex reserves the right to update or modify these Terms at any time. Significant changes will be communicated to registered users via email and platform notifications. Your continued use of the Platform after the effective date of any changes constitutes your acceptance of the new Terms.</p>

              {/* 16 */}
              <h3 className="text-lg font-semibold">16. Governing Law &amp; Jurisdiction</h3>
              <p>{t("legal.governedByLaws")} <strong>{t("legal.provinceOfQuebec")}</strong> and the federal laws of Canada applicable therein. Any disputes arising out of or related to these Terms shall be resolved exclusively in the courts of <strong>Montreal, Quebec</strong>.</p>

              {/* 17 */}
              <h3 className="text-lg font-semibold">17. Contact Information</h3>
              <p>BidVex Legal &amp; Data Protection Officer</p>
              <p><strong>Email:</strong> <a href="mailto:support@bidvex.com" className="text-primary hover:underline">support@bidvex.com</a></p>

              {/* Cross-Border Compliance (Bilingual - Bill 96) */}
              <CrossBorderLegalSection />

              {/* Vehicle Auctions: OPC Compliance (Bilingual - Bill 96) */}
              <VehicleAuctionLegalSection />

              <p className="text-xs text-muted-foreground mt-4">&copy; 2026 BidVex Inc. All rights reserved.</p>
            </div>
          </CardContent>
        </Card>

        {/* ──────────────────── PRIVACY POLICY ──────────────────── */}
        <Card id="privacy" data-testid="privacy-section">
          <CardContent className="pt-6 space-y-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                <Shield className="h-6 w-6 text-green-600" />
              </div>
              <h2 className="text-2xl font-bold">BidVex Privacy Policy</h2>
            </div>
            <p className="text-sm text-muted-foreground">Last Updated: March 2026</p>

            <div className="prose prose-sm dark:prose-invert max-w-none space-y-5">

              {/* 1 */}
              <h3 className="text-lg font-semibold">1. Introduction</h3>
              <p>At BidVex Inc. ("BidVex," "we," "us," or "our"), we are committed to protecting the privacy and security of your personal information. This Privacy Policy explains how we collect, use, disclose, and safeguard your data when you use our online auction platform ("the Platform").</p>
              <p><strong>Compliance:</strong> {t("legal.compliancePolicy")} <strong>Act respecting the protection of personal information in the private sector (Quebec Law 25)</strong>, the <strong>Personal Information Protection and Electronic Documents Act (PIPEDA)</strong>, and the <strong>General Data Protection Regulation (GDPR)</strong>.</p>

              {/* 2 */}
              <h3 className="text-lg font-semibold">2. Information We Collect</h3>
              <p>To provide a secure and efficient auction environment, we collect the following categories of data:</p>
              <h4 className="font-semibold">2.1 Sellers (including Vehicle &amp; Equipment sections)</h4>
              <ul className="list-disc pl-6 space-y-1">
                <li><strong>Identity &amp; Verification Data:</strong> Full name, date of birth, and government-issued ID (for identity verification and fraud prevention).</li>
                <li><strong>Contact Data:</strong> Email address, telephone number, and physical business/residential address.</li>
                <li><strong>Business Data:</strong> Business name, tax ID numbers (including NEQ), and dealer licenses (where applicable).</li>
                <li><strong>Asset Data:</strong> VINs, vehicle/equipment history reports, make, model, year, photos, and related ownership documentation.</li>
                <li><strong>Financial Data:</strong> Banking details and settlement information for payouts.</li>
              </ul>
              <h4 className="font-semibold">2.2 Buyers</h4>
              <ul className="list-disc pl-6 space-y-1">
                <li><strong>Identity Data:</strong> Full name and username.</li>
                <li><strong>Contact Data:</strong> Email address, telephone number, and billing/shipping address.</li>
                <li><strong>Payment Data:</strong> Credit card and payment method details. <em>Note: All payment data is processed securely via Stripe; BidVex does not store full credit card numbers.</em></li>
                <li><strong>Transaction Data:</strong> Bidding history, watchlist items, and records of won auctions.</li>
              </ul>
              <h4 className="font-semibold">2.3 Technical Data (All Users)</h4>
              <p>IP address, browser type and version, time zone setting, device identifiers, and operating system information for security monitoring and platform optimization.</p>

              {/* 3 */}
              <h3 className="text-lg font-semibold">3. Purpose of Processing</h3>
              <p>We process your personal data based on the following legal grounds:</p>
              <ul className="list-disc pl-6 space-y-1">
                <li><strong>Contractual Necessity:</strong> To facilitate bidding, buying, and selling transactions.</li>
                <li><strong>Identity Verification:</strong> To maintain a high-trust marketplace and prevent fraud.</li>
                <li><strong>Communication:</strong> To enable secure messaging between buyers and sellers.</li>
                <li><strong>Payment Processing:</strong> To securely handle transaction fees via Stripe.</li>
                <li><strong>Improvement:</strong> To analyze usage patterns and optimize recommendations.</li>
                <li><strong>Legal Compliance:</strong> To satisfy tax, accounting, and AML obligations.</li>
              </ul>

              {/* 4 */}
              <h3 className="text-lg font-semibold">4. Information Sharing &amp; Disclosure</h3>
              <p>We do not sell your personal data to third parties. Disclosure occurs only in the following contexts:</p>
              <ul className="list-disc pl-6 space-y-1">
                <li><strong>Transaction Completion:</strong> Upon the conclusion of a successful auction, the winning buyer and the seller receive each other's contact information to finalize logistics.</li>
                <li><strong>Public Profile:</strong> Trust indicators, verified badges, and user ratings are displayed publicly to maintain community transparency.</li>
                <li><strong>Service Providers:</strong> We share data with trusted partners strictly for operational purposes: Stripe (payments), SendGrid (email), Twilio (SMS), AWS/GCP (hosting).</li>
                <li><strong>Legal Authorities:</strong> We may disclose data if required by law, court order, or to protect the rights and safety of our users.</li>
              </ul>

              {/* 5 */}
              <h3 className="text-lg font-semibold">5. Cookies &amp; Tracking</h3>
              <p>We use cookies to enhance your experience and analyze traffic:</p>
              <ul className="list-disc pl-6 space-y-1">
                <li><strong>Essential Cookies:</strong> Required for core platform functionality (e.g., staying logged in).</li>
                <li><strong>Analytics Cookies:</strong> Help us understand how users interact with the site.</li>
                <li><strong>Personalization Cookies:</strong> Remember your preferences, such as language (English/French).</li>
                <li><strong>Marketing Cookies:</strong> Used to deliver relevant advertisements. Opt-out available via Google Ads Settings.</li>
              </ul>

              {/* 6 */}
              <h3 className="text-lg font-semibold">6. AI-Powered Recommendation Engine</h3>
              <p>BidVex utilizes a proprietary recommendation engine to suggest items based on your browsing and search history, past bidding and purchase patterns, and items added to your "Watchlist."</p>
              <p><strong>Opt-Out:</strong> Users may disable personalized recommendations in their Account Settings. This will not affect core bidding or platform functionality.</p>

              {/* 7 */}
              <h3 className="text-lg font-semibold">7. Data Security</h3>
              <p>We implement industry-leading security measures to protect your data, including:</p>
              <ul className="list-disc pl-6 space-y-1">
                <li><strong>TLS/SSL:</strong> {t("legal.encryptionInTransit")}</li>
                <li><strong>AES-256:</strong> {t("legal.encryptionAtRest")}</li>
                <li><strong>PCI-DSS:</strong> {t("legal.paymentCompliance")}</li>
                <li><strong>MFA:</strong> Multi-factor authentication</li>
                <li><strong>Role-Based Access Control</strong></li>
                <li><strong>24/7 Security Monitoring</strong></li>
              </ul>

              {/* 8 */}
              <h3 className="text-lg font-semibold">8. Your Privacy Rights</h3>
              <p>Depending on your jurisdiction (Quebec, Canada, or EU), you have the following rights:</p>
              <ul className="list-disc pl-6 space-y-1">
                <li><strong>Access:</strong> The right to request a copy of the personal data we hold about you.</li>
                <li><strong>Correction:</strong> The right to fix inaccurate or incomplete information.</li>
                <li><strong>Deletion (Right to be Forgotten):</strong> The right to request the removal of your data, subject to legal retention requirements.</li>
                <li><strong>Portability:</strong> The right to receive your data in a structured, machine-readable format.</li>
                <li><strong>Withdrawal of Consent:</strong> The right to stop processing for specific purposes (e.g., marketing).</li>
              </ul>
              <p><strong>To exercise these rights,</strong> please contact our Data Protection Officer at <a href="mailto:support@bidvex.com" className="text-primary hover:underline">support@bidvex.com</a>.</p>

              {/* 9 */}
              <h3 className="text-lg font-semibold">9. Data Retention</h3>
              <ul className="list-disc pl-6 space-y-1">
                <li><strong>Account Data:</strong> Retained for the duration of your active account and up to 7 years after closure.</li>
                <li><strong>Transaction Records:</strong> Retained for 7 years to comply with Canadian and Quebec tax and legal obligations.</li>
                <li><strong>Identification Documents:</strong> Deleted once verification is successfully completed, unless otherwise required for ongoing fraud prevention.</li>
              </ul>

              {/* 10 */}
              <h3 className="text-lg font-semibold">10. Contact Us</h3>
              <p>For questions regarding this policy or our data practices, please contact:</p>
              <p>BidVex Data Protection Officer</p>
              <p><strong>Email:</strong> <a href="mailto:support@bidvex.com" className="text-primary hover:underline">support@bidvex.com</a></p>

              {/* Law 25: AI Disclosure (Bilingual - Bill 96) */}
              <AIDisclosureLegalSection />

              {/* Vehicle Auctions: OPC Compliance (Bilingual - Bill 96) */}
              <VehicleAuctionLegalSection />

              {/* ════════════════════════════════════════════════
                  ADDENDUM: Sticky Card + Escrow + Pickup Code
                  Added April 15, 2026 — DO NOT modify content above
                  ════════════════════════════════════════════════ */}

              <section id="sticky-card" className="space-y-4 border-l-4 border-cyan-400 pl-4">
                <h2 className="text-xl font-semibold flex items-center gap-2">
                  <CreditCard className="h-5 w-5 text-cyan-600" />
                  Payment Safety &amp; Escrow System — Addendum
                </h2>
                <p className="text-sm text-muted-foreground">Effective April 15, 2026 | Applicable to all users</p>

                <div className="space-y-4">
                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <span className="w-7 h-7 bg-cyan-100 dark:bg-cyan-900 rounded-full flex items-center justify-center text-cyan-600 text-xs font-bold">A1</span>
                    Mandatory Payment Method (Sticky Card Policy)
                  </h3>
                  <p>To create a listing on BidVex, every Seller must have a valid payment method (credit or debit card) on file, attached to their Stripe Customer profile. Sellers <strong>cannot remove</strong> their payment method while any of their listings are in an active, live, or ending-soon status. BidVex stores a Stripe payment method token (not raw card data). This token may be used to process authorized charges, including cancellation penalties.</p>

                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <span className="w-7 h-7 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center text-red-600 text-xs font-bold">A2</span>
                    Cancellation Penalty
                  </h3>
                  <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4">
                    <p className="text-red-800 dark:text-red-200">A penalty of <strong>$50.00 CAD</strong> is triggered when a Seller marks an item as "unable to deliver" after auction close, or when flagged by an administrator for non-delivery. This amount is automatically charged to the Seller's payment method on file. If the charge fails, the account is flagged for suspension.</p>
                  </div>

                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <span className="w-7 h-7 bg-emerald-100 dark:bg-emerald-900 rounded-full flex items-center justify-center text-emerald-600 text-xs font-bold">B1</span>
                    <Key className="h-4 w-4 text-emerald-600" />
                    Escrow &amp; Pickup Code System (Non-Vehicle Items)
                  </h3>
                  <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-lg p-5">
                    <p className="text-emerald-800 dark:text-emerald-200">For non-vehicle items, when a Buyer wins an auction and payment is captured, the funds are <strong>held in escrow</strong> by BidVex. A unique 6-character alphanumeric Pickup Code is generated and emailed to the Buyer. The Seller must enter this code on their dashboard to confirm item handoff and release the funds to their Stripe Connect account.</p>
                  </div>

                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <span className="w-7 h-7 bg-amber-100 dark:bg-amber-900 rounded-full flex items-center justify-center text-amber-600 text-xs font-bold">B2</span>
                    <Clock className="h-4 w-4 text-amber-600" />
                    48-Hour Auto-Release
                  </h3>
                  <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                    <p className="text-amber-800 dark:text-amber-200">If the Buyer does not present the Pickup Code within 48 hours, funds are <strong>automatically released</strong> to the Seller. Both parties receive email notification of auto-release. Vehicle transactions are excluded from this system.</p>
                  </div>

                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <span className="w-7 h-7 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-xs font-bold">B3</span>
                    <AlertTriangle className="h-4 w-4 text-blue-600" />
                    Disputes
                  </h3>
                  <p>Either party may open a dispute on an active escrow within the 48-hour window. Disputed escrows are reviewed by the BidVex team. Funds remain held until resolution.</p>

                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <span className="w-7 h-7 bg-slate-200 dark:bg-slate-700 rounded-full flex items-center justify-center text-slate-600 dark:text-slate-300 text-xs font-bold">B4</span>
                    <Database className="h-4 w-4 text-slate-600" />
                    Escrow Data &amp; Privacy
                  </h3>
                  <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg p-4">
                    <div className="space-y-2">
                      <div className="flex items-center gap-4 p-2">
                        <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center flex-shrink-0">
                          <span className="text-lg font-bold text-blue-600">5</span>
                        </div>
                        <div>
                          <h4 className="font-semibold text-sm">Escrow Logs</h4>
                          <p className="text-xs text-muted-foreground">Pickup codes, status, timestamps, failed attempt logs — retained for 5 years.</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4 p-2">
                        <div className="w-12 h-12 bg-red-100 dark:bg-red-900 rounded-lg flex items-center justify-center flex-shrink-0">
                          <span className="text-lg font-bold text-red-600">7</span>
                        </div>
                        <div>
                          <h4 className="font-semibold text-sm">Penalty Logs</h4>
                          <p className="text-xs text-muted-foreground">Cancellation penalty records — retained for 7 years.</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4 p-2">
                        <div className="w-12 h-12 bg-amber-100 dark:bg-amber-900 rounded-lg flex items-center justify-center flex-shrink-0">
                          <span className="text-lg font-bold text-amber-600">2</span>
                        </div>
                        <div>
                          <h4 className="font-semibold text-sm">Pickup Attempt Logs</h4>
                          <p className="text-xs text-muted-foreground">Failed code entry attempts — retained for 2 years.</p>
                        </div>
                      </div>
                    </div>
                    <p className="text-sm mt-3">This data is subject to our Privacy Policy and complies with PIPEDA and Quebec's Law 25.</p>
                  </div>
                </div>

                {/* French Translation */}
                <hr className="my-6 border-slate-200 dark:border-slate-700" />
                <h2 className="text-xl font-semibold flex items-center gap-2">
                  <CreditCard className="h-5 w-5 text-cyan-600" />
                  Sécurité des paiements et système de dépôt fiduciaire — Addendum
                </h2>
                <p className="text-sm text-muted-foreground">En vigueur le 15 avril 2026 | Applicable à tous les utilisateurs</p>

                <div className="space-y-4">
                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <span className="w-7 h-7 bg-cyan-100 dark:bg-cyan-900 rounded-full flex items-center justify-center text-cyan-600 text-xs font-bold">A1</span>
                    Moyen de paiement obligatoire (Politique Sticky Card)
                  </h3>
                  <p>Pour créer une annonce sur BidVex, chaque Vendeur doit avoir un moyen de paiement valide enregistré, rattaché à son profil Stripe. Les Vendeurs <strong>ne peuvent pas supprimer</strong> leur moyen de paiement tant que l'une de leurs annonces est active. BidVex conserve un jeton Stripe (jamais les données brutes de carte). Ce jeton peut être utilisé pour traiter les pénalités d'annulation.</p>

                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <span className="w-7 h-7 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center text-red-600 text-xs font-bold">A2</span>
                    Pénalité d'annulation
                  </h3>
                  <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4">
                    <p className="text-red-800 dark:text-red-200">Une pénalité de <strong>50,00 $ CAD</strong> est appliquée lorsqu'un Vendeur signale l'impossibilité de livrer après la clôture, ou lorsqu'un administrateur signale une non-livraison. Le montant est prélevé automatiquement. En cas d'échec, le compte est signalé pour suspension.</p>
                  </div>

                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <span className="w-7 h-7 bg-emerald-100 dark:bg-emerald-900 rounded-full flex items-center justify-center text-emerald-600 text-xs font-bold">B1</span>
                    Dépôt fiduciaire et code de retrait (articles non véhiculaires)
                  </h3>
                  <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-lg p-5">
                    <p className="text-emerald-800 dark:text-emerald-200">Pour les articles non véhiculaires, les fonds sont <strong>détenus en fiducie</strong> par BidVex après le paiement. Un code de retrait unique de 6 caractères est envoyé à l'Acheteur par courriel. Le Vendeur doit entrer ce code sur son tableau de bord pour confirmer la remise et libérer les fonds.</p>
                  </div>

                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <span className="w-7 h-7 bg-amber-100 dark:bg-amber-900 rounded-full flex items-center justify-center text-amber-600 text-xs font-bold">B2</span>
                    Libération automatique après 48 heures
                  </h3>
                  <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                    <p className="text-amber-800 dark:text-amber-200">Si l'Acheteur ne présente pas le code dans les 48 heures, les fonds sont <strong>automatiquement libérés</strong> au Vendeur. Les deux parties reçoivent une notification. Les véhicules sont exclus de ce système.</p>
                  </div>

                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <span className="w-7 h-7 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-xs font-bold">B3</span>
                    Litiges
                  </h3>
                  <p>Chaque partie peut ouvrir un litige sur un dépôt actif dans la fenêtre de 48 heures. Les fonds restent détenus pendant la résolution par l'équipe BidVex.</p>

                  <h3 className="text-lg font-semibold flex items-center gap-2">
                    <span className="w-7 h-7 bg-slate-200 dark:bg-slate-700 rounded-full flex items-center justify-center text-slate-600 dark:text-slate-300 text-xs font-bold">B4</span>
                    Données de dépôt et confidentialité
                  </h3>
                  <p>Les données de dépôt fiduciaire (codes, statuts, horodatages, journaux de tentatives) sont conservées 5 ans. Les journaux de pénalités sont conservés 7 ans. Ces données sont soumises à notre Politique de confidentialité et conformes à la LPRPDE et à la Loi 25.</p>
                </div>
              </section>

              <p className="text-xs text-muted-foreground mt-4">&copy; 2026 BidVex Inc. All rights reserved.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default LegalPage;
