import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { FileText } from 'lucide-react';

const TermsOfServicePage = () => {
  return (
    <div className="min-h-screen py-12 px-4 max-w-4xl mx-auto">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3 mb-4">
            <FileText className="h-8 w-8 text-primary" />
            <CardTitle className="text-3xl">Terms of Service</CardTitle>
          </div>
          <p className="text-muted-foreground">Last updated: {new Date().toLocaleDateString()}</p>
        </CardHeader>
        <CardContent className="prose prose-sm max-w-none space-y-6">
          <section>
            <h2 className="text-2xl font-semibold mb-3">1. Acceptance of Terms</h2>
            <p>By accessing and using BidVex ("the Platform"), you agree to be bound by these Terms of Service. If you do not agree to these terms, please do not use the Platform.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">2. User Accounts</h2>
            <p><strong>Registration:</strong> You must create an account to participate in auctions. You are responsible for:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Providing accurate and complete information</li>
              <li>Maintaining the security of your account</li>
              <li>All activities under your account</li>
              <li>Notifying us of unauthorized access</li>
            </ul>
            <p className="mt-3"><strong>Eligibility:</strong> You must be at least 18 years old to use BidVex.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">3. Bidding Rules</h2>
            <p><strong>Binding Bids:</strong> All bids placed on BidVex are legally binding commitments to purchase. By placing a bid, you agree to:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Complete the purchase if you are the winning bidder</li>
              <li>Pay the final bid amount plus applicable fees and taxes</li>
              <li>Arrange payment and delivery within the specified timeframe</li>
            </ul>
            <p className="mt-3"><strong>Bid Retraction:</strong> Bids cannot be retracted except in rare circumstances (e.g., typographical error within 1 hour of bid). Contact support immediately if you need to retract a bid.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">4. Fees and Payments</h2>
            <p><strong>Buyer Fees:</strong> Buyers are responsible for the winning bid amount plus any applicable:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Shipping and handling fees</li>
              <li>Sales tax (GST/QST for Canadian buyers, as applicable)</li>
              <li>Currency conversion fees (if applicable)</li>
            </ul>
            <p className="mt-3"><strong>Seller Fees:</strong> Sellers pay a commission on successful sales:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Personal accounts: 5% commission</li>
              <li>Business accounts: 4.5% commission</li>
            </ul>
            <p className="mt-3"><strong>Payment Processing:</strong> All payments are processed through Stripe. Payment information is never stored on BidVex servers.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">5. Seller Responsibilities</h2>
            <p>Sellers must:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Provide accurate descriptions and photos of items</li>
              <li>Honor all winning bids</li>
              <li>Ship items promptly and securely</li>
              <li>Respond to buyer inquiries within 24 hours</li>
              <li>Comply with all applicable laws and regulations</li>
            </ul>
            <p className="mt-3"><strong>Prohibited Items:</strong> Sellers may not list illegal, counterfeit, stolen, or hazardous items. See our Prohibited Items Policy for details.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">6. Buyer Responsibilities</h2>
            <p>Buyers must:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Complete payment within 48 hours of auction end</li>
              <li>Arrange pickup or accept delivery as agreed</li>
              <li>Inspect items upon receipt and report issues within 48 hours</li>
              <li>Provide accurate shipping information</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">7. Dispute Resolution</h2>
            <p>In case of disputes between buyers and sellers:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Contact the other party first to resolve the issue</li>
              <li>If unresolved, contact BidVex support within 7 days</li>
              <li>BidVex will mediate but is not responsible for disputes</li>
              <li>Refunds are at the seller's discretion unless item is significantly not as described</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">8. Intellectual Property</h2>
            <p>All content on BidVex (logos, text, graphics, code) is owned by BidVex Inc. or its licensors. You may not:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Copy, modify, or distribute Platform content without permission</li>
              <li>Use BidVex branding without authorization</li>
              <li>Scrape or collect data from the Platform</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">9. Prohibited Conduct</h2>
            <p>Users may not:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Engage in fraud, shill bidding, or bid manipulation</li>
              <li>Harass or threaten other users</li>
              <li>Post spam, viruses, or malicious code</li>
              <li>Circumvent Platform fees</li>
              <li>Create multiple accounts to manipulate auctions</li>
            </ul>
            <p className="mt-3">Violation may result in account suspension or termination.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">10. Limitation of Liability</h2>
            <p>BidVex provides the Platform "as is" without warranties. We are not liable for:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Accuracy of item descriptions</li>
              <li>Actions of buyers or sellers</li>
              <li>Losses from Platform downtime or errors</li>
              <li>Disputes between users</li>
            </ul>
            <p className="mt-3">Maximum liability is limited to the fees paid by you in the 12 months prior to the claim.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">11. Termination</h2>
            <p>We reserve the right to suspend or terminate accounts that violate these Terms. You may close your account at any time, but remain liable for all outstanding obligations.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">12. Changes to Terms</h2>
            <p>We may update these Terms at any time. Significant changes will be communicated via email or Platform notification. Continued use after changes constitutes acceptance.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">13. Governing Law</h2>
            <p>These Terms are governed by the laws of the Province of Quebec and Canada. Disputes will be resolved in the courts of Montreal, Quebec.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">14. Contact</h2>
            <p>For questions about these Terms, contact us at:</p>
            <ul className="list-none pl-0 space-y-1 mt-3">
              <li><strong>Email:</strong> legal@bidvex.com</li>
              <li><strong>Address:</strong> BidVex Inc., Montreal, QC, Canada</li>
            </ul>
          </section>

          <div className="mt-8 p-4 bg-muted rounded-lg">
            <p className="text-sm text-muted-foreground">
              <strong>Legal Notice:</strong> This is a template Terms of Service. Please have legal counsel review and customize this document to ensure it meets the specific legal requirements for your jurisdiction and business model.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default TermsOfServicePage;