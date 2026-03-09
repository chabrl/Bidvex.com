import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Shield } from 'lucide-react';

const PrivacyPolicyPage = () => {
  return (
    <div className="min-h-screen py-12 px-4 max-w-4xl mx-auto">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3 mb-4">
            <Shield className="h-8 w-8 text-primary" />
            <CardTitle className="text-3xl">Privacy Policy</CardTitle>
          </div>
          <p className="text-muted-foreground">Last updated: {new Date().toLocaleDateString()}</p>
        </CardHeader>
        <CardContent className="prose prose-sm max-w-none space-y-6">
          <section>
            <h2 className="text-2xl font-semibold mb-3">1. Information We Collect</h2>
            <p>BidVex collects information to provide better services to our users. We collect information in the following ways:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li><strong>Account Information:</strong> Name, email address, phone number, and payment details</li>
              <li><strong>Bidding Activity:</strong> Bid history, watchlist items, and auction participation</li>
              <li><strong>Transaction Data:</strong> Payment information, invoices, and purchase history</li>
              <li><strong>Usage Data:</strong> Pages visited, features used, and time spent on platform</li>
              <li><strong>Device Information:</strong> Browser type, IP address, and operating system</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">2. How We Use Your Information</h2>
            <p>We use the information we collect to:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Process bids and facilitate transactions</li>
              <li>Send auction notifications and updates</li>
              <li>Provide customer support</li>
              <li>Prevent fraud and ensure platform security</li>
              <li>Improve our services and user experience</li>
              <li>Comply with legal obligations</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">3. Information Sharing</h2>
            <p>We do not sell your personal information. We may share your information with:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li><strong>Sellers:</strong> Contact information when you win an auction</li>
              <li><strong>Payment Processors:</strong> Stripe for secure payment processing</li>
              <li><strong>Service Providers:</strong> Email and hosting services that help operate our platform</li>
              <li><strong>Legal Authorities:</strong> When required by law or to protect our rights</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">4. Data Security</h2>
            <p>We implement industry-standard security measures to protect your information:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>SSL encryption for all data transmission</li>
              <li>Secure password hashing (bcrypt)</li>
              <li>Regular security audits and updates</li>
              <li>Restricted access to personal data</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">5. Your Rights</h2>
            <p>You have the right to:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Access your personal data</li>
              <li>Correct inaccurate information</li>
              <li>Request deletion of your account</li>
              <li>Opt-out of marketing communications</li>
              <li>Export your data</li>
            </ul>
            <p className="mt-3">To exercise these rights, contact us at privacy@bidvex.com</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">6. Cookies and Tracking</h2>
            <p>We use cookies and similar technologies to:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Keep you logged in</li>
              <li>Remember your preferences</li>
              <li>Analyze platform usage</li>
              <li>Improve user experience</li>
            </ul>
            <p className="mt-3">You can control cookies through your browser settings.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">7. Children's Privacy</h2>
            <p>BidVex is not intended for users under 18 years old. We do not knowingly collect information from children. If you are a parent and believe your child has provided us with personal information, please contact us.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">8. International Users</h2>
            <p>BidVex operates globally. By using our platform, you consent to the transfer of your information to Canada and other countries where we operate.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">9. Changes to This Policy</h2>
            <p>We may update this Privacy Policy from time to time. We will notify you of significant changes via email or platform notification. Continued use of BidVex after changes constitutes acceptance of the updated policy.</p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold mb-3">10. Contact Us</h2>
            <p>For privacy-related questions or concerns, contact us at:</p>
            <ul className="list-none pl-0 space-y-1 mt-3">
              <li><strong>Email:</strong> privacy@bidvex.com</li>
              <li><strong>Address:</strong> BidVex Inc., Montreal, QC, Canada</li>
            </ul>
          </section>

          <div className="mt-8 p-4 bg-muted rounded-lg">
            <p className="text-sm text-muted-foreground">
              <strong>Note:</strong> This is a template privacy policy. Please have legal counsel review and customize this document to ensure compliance with applicable laws in your jurisdiction (GDPR, CCPA, PIPEDA, etc.).
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default PrivacyPolicyPage;