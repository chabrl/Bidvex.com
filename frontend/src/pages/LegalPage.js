import React from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent } from '../components/ui/card';
import { ScrollText, Shield, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

const LegalPage = () => {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-background py-12 px-4">
      <div className="max-w-4xl mx-auto space-y-10">
        {/* Header */}
        <div className="text-center space-y-3">
          <Link to="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-primary mb-4">
            <ArrowLeft className="h-4 w-4" /> Back to Home
          </Link>
          <h1 className="text-4xl font-bold tracking-tight" data-testid="legal-page-title">Legal</h1>
          <p className="text-muted-foreground">Terms of Service and Privacy Policy for BidVex</p>
        </div>

        {/* Terms of Service */}
        <Card id="terms" data-testid="terms-section">
          <CardContent className="pt-6 space-y-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <ScrollText className="h-6 w-6 text-blue-600" />
              </div>
              <h2 className="text-2xl font-bold">Terms of Service</h2>
            </div>
            <p className="text-sm text-muted-foreground">Last updated: March 14, 2026</p>

            <div className="prose prose-sm dark:prose-invert max-w-none space-y-4">
              <h3 className="text-lg font-semibold">1. Acceptance of Terms</h3>
              <p>By creating an account on BidVex, you agree to be bound by these Terms of Service. If you do not agree, you may not use the platform.</p>

              <h3 className="text-lg font-semibold">2. Eligibility</h3>
              <p>You must be at least 18 years old and legally capable of entering binding contracts. By using BidVex, you represent and warrant that you meet these requirements.</p>

              <h3 className="text-lg font-semibold">3. Account Responsibilities</h3>
              <p>You are responsible for maintaining the confidentiality of your account credentials. All activities under your account are your responsibility. You agree to immediately notify BidVex of any unauthorized use.</p>

              <h3 className="text-lg font-semibold">4. Bidding & Transactions</h3>
              <p>All bids placed on BidVex are legally binding commitments to purchase. Once a bid is placed, it cannot be retracted. Winning bidders are obligated to complete the transaction within 14 days. A 2% monthly late penalty applies to overdue payments.</p>

              <h3 className="text-lg font-semibold">5. Fees & Pricing</h3>
              <p>BidVex charges the following fees:</p>
              <ul className="list-disc pl-6 space-y-1">
                <li><strong>Buyer Premium:</strong> 5% (Standard), 3.5% (Premium), 3% (VIP Elite)</li>
                <li><strong>Seller Commission:</strong> 4% (Standard), 2.5% (Premium), 2% (VIP Elite)</li>
                <li><strong>Platform Fee:</strong> 2.5% on partner listings, 3% on partner transactions</li>
              </ul>
              <p>Subscription tiers: Free ($0/mo), Premium ($213.45/mo), VIP Elite ($355.54/mo).</p>

              <h3 className="text-lg font-semibold">6. No Refund Policy</h3>
              <p><strong>All payments, including subscription fees and auction transaction fees, are final and non-refundable.</strong> No partial refunds, pro-rated refunds, or credits will be issued. You may cancel your subscription at any time to prevent future billing, but the current billing period will not be refunded.</p>

              <h3 className="text-lg font-semibold">7. Anti-Sniping</h3>
              <p>BidVex uses an anti-sniping system. If a bid is placed in the final 2 minutes of an auction, the timer extends by 2 minutes from the time of the bid. This ensures fairness for all participants.</p>

              <h3 className="text-lg font-semibold">8. Prohibited Conduct</h3>
              <p>You may not use BidVex for any illegal purposes, engage in shill bidding, create multiple accounts, or manipulate auction outcomes. Violations may result in immediate account termination.</p>

              <h3 className="text-lg font-semibold">9. Limitation of Liability</h3>
              <p>BidVex acts as a marketplace platform and is not a party to transactions between buyers and sellers. Items are sold "as is, where is." BidVex is not responsible for the condition, legality, or quality of listed items.</p>

              <h3 className="text-lg font-semibold">10. Governing Law</h3>
              <p>These Terms are governed by the laws of the Province of Quebec and the federal laws of Canada applicable therein.</p>

              <h3 className="text-lg font-semibold">11. Contact</h3>
              <p>For questions about these Terms, contact us at <a href="mailto:support@bidvex.com" className="text-primary hover:underline">support@bidvex.com</a>.</p>
            </div>
          </CardContent>
        </Card>

        {/* Privacy Policy */}
        <Card id="privacy" data-testid="privacy-section">
          <CardContent className="pt-6 space-y-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                <Shield className="h-6 w-6 text-green-600" />
              </div>
              <h2 className="text-2xl font-bold">Privacy Policy</h2>
            </div>
            <p className="text-sm text-muted-foreground">Last updated: March 14, 2026</p>

            <div className="prose prose-sm dark:prose-invert max-w-none space-y-4">
              <h3 className="text-lg font-semibold">1. Information We Collect</h3>
              <p>We collect information you provide when registering (name, email, phone, address, business details), transaction data (bids, purchases, payments), and usage data (IP address, device information, browsing activity).</p>

              <h3 className="text-lg font-semibold">2. How We Use Your Information</h3>
              <p>We use your information to operate the platform, process transactions, verify identity, prevent fraud, comply with tax regulations, send transactional emails, and improve our services.</p>

              <h3 className="text-lg font-semibold">3. Data Sharing</h3>
              <p>We may share your information with payment processors (Stripe), email service providers (SendGrid), law enforcement when required by law, and other users as necessary to complete transactions (e.g., seller sees buyer name after winning).</p>

              <h3 className="text-lg font-semibold">4. Canadian Tax Compliance</h3>
              <p>BidVex collects tax registration numbers (GST/HST, QST) from sellers as required by Canadian Revenue Agency regulations. This information is stored securely and used solely for tax reporting purposes.</p>

              <h3 className="text-lg font-semibold">5. Data Security</h3>
              <p>We implement industry-standard security measures including encrypted data transmission (TLS/SSL), secure password hashing (bcrypt), and regular security audits. However, no system is 100% secure.</p>

              <h3 className="text-lg font-semibold">6. Data Retention</h3>
              <p>We retain your data for as long as your account is active, plus 7 years for tax and legal compliance. You may request account deletion, subject to legal retention requirements.</p>

              <h3 className="text-lg font-semibold">7. Your Rights</h3>
              <p>Under applicable Canadian privacy laws, you have the right to access your personal data, request corrections, request deletion (subject to legal requirements), and withdraw consent for marketing communications.</p>

              <h3 className="text-lg font-semibold">8. Cookies</h3>
              <p>BidVex uses essential cookies for authentication and session management, and optional analytics cookies to improve the user experience. You can manage cookie preferences through our cookie consent banner.</p>

              <h3 className="text-lg font-semibold">9. Contact</h3>
              <p>For privacy inquiries, contact our Data Protection Officer at <a href="mailto:privacy@bidvex.com" className="text-primary hover:underline">privacy@bidvex.com</a>.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default LegalPage;
