import React from 'react';

export const PrivacyEN = () => (
  <div className="min-h-screen bg-background py-12 px-4">
    <div className="max-w-4xl mx-auto prose prose-sm dark:prose-invert">
      <h1>BidVex Inc. — Privacy Policy</h1>
      <p className="text-muted-foreground">Last Updated: April 15, 2026 | Effective Date: April 15, 2026</p>

      <h2>1. Introduction</h2>
      <p>BidVex Inc. ("BidVex," "we," "us") is committed to protecting the privacy of our users. This Privacy Policy explains how we collect, use, store, and protect your personal information when you use our auction marketplace platform. This policy complies with the Personal Information Protection and Electronic Documents Act (PIPEDA) and Quebec's Law 25.</p>

      <h2>2. Information We Collect</h2>
      <h3>2.1 Account Information</h3>
      <p>Name, email address, phone number, province of residence, preferred language (EN/FR), account type (individual or business).</p>
      <h3>2.2 Payment Information</h3>
      <p>We use Stripe for payment processing. We store: Stripe Customer ID, Stripe payment method tokens (never raw card numbers), card brand, last four digits, and expiration date. We also store Stripe Connect account IDs for sellers.</p>
      <h3>2.3 Transaction Data</h3>
      <p>Bid amounts, auction outcomes, payment intents, escrow states, pickup codes, transfer records, penalty logs, and invoice details.</p>
      <h3>2.4 Escrow &amp; Pickup Code Data</h3>
      <p>When you participate in a non-vehicle auction, we generate and store: pickup codes, escrow status (held/released/auto-released/disputed), pickup code entry timestamps, failed pickup attempt logs, and auto-release schedules.</p>
      <h3>2.5 Usage Data</h3>
      <p>CTA click events, page views, session data, device information, IP addresses, and browser type. We use PostHog for analytics.</p>
      <h3>2.6 Communication Data</h3>
      <p>Messages between users, Community Q&amp;A posts and replies, email open/click events (via SendGrid).</p>

      <h2>3. How We Use Your Information</h2>
      <ul>
        <li>To facilitate auctions, payments, and escrow transactions</li>
        <li>To generate and deliver Pickup Codes to Buyers</li>
        <li>To verify payment methods for the Sticky Card system</li>
        <li>To process cancellation penalties when applicable</li>
        <li>To detect and prevent fraud (failed pickup attempt logging, brute force detection)</li>
        <li>To send transactional emails (bid confirmations, pickup codes, auto-release notices)</li>
        <li>To send marketing emails (with your consent)</li>
        <li>To comply with legal obligations</li>
        <li>To improve the Platform through analytics</li>
      </ul>

      <h2>4. Stripe &amp; Payment Data</h2>
      <p>We use Stripe as our payment processor. Stripe stores and processes your full card details in a PCI-DSS compliant environment. BidVex only stores tokenized references (pm_xxx, cus_xxx). We use Stripe Customer objects with metadata (user_id, platform identifier) for fraud prevention and payment routing.</p>

      <h2>5. Data Sharing</h2>
      <p>We share personal information only with:</p>
      <ul>
        <li><strong>Stripe</strong>: For payment processing, Connect transfers, and penalty charges</li>
        <li><strong>SendGrid</strong>: For transactional and marketing email delivery</li>
        <li><strong>Law enforcement</strong>: When required by law or to protect the safety of users</li>
        <li><strong>Other users</strong>: Your name/display name is visible to other users in auctions and Community Q&amp;A. Email addresses are never shared with other users.</li>
      </ul>

      <h2>6. Data Retention</h2>
      <ul>
        <li><strong>Account data</strong>: Retained for the lifetime of your account plus 3 years after deletion request</li>
        <li><strong>Transaction records</strong>: Retained for 7 years for tax and legal compliance</li>
        <li><strong>Escrow logs</strong>: Retained for 5 years</li>
        <li><strong>Penalty logs</strong>: Retained for 7 years</li>
        <li><strong>Pickup attempt logs</strong>: Retained for 2 years</li>
        <li><strong>Email event logs</strong>: Retained for 1 year</li>
        <li><strong>Admin flags</strong>: Retained for 3 years</li>
      </ul>

      <h2>7. Your Rights</h2>
      <p>Under PIPEDA and Quebec's Law 25, you have the right to:</p>
      <ul>
        <li><strong>Access</strong>: Request a copy of your personal information</li>
        <li><strong>Correction</strong>: Request correction of inaccurate data</li>
        <li><strong>Deletion</strong>: Request deletion of your data (subject to legal retention obligations)</li>
        <li><strong>Portability</strong>: Receive your data in a structured, machine-readable format</li>
        <li><strong>Withdrawal of consent</strong>: Withdraw consent for marketing communications at any time</li>
      </ul>
      <p><strong>Limitations</strong>: We cannot delete financial transaction records required for tax compliance, active escrow records, or penalty records during the retention period.</p>

      <h2>8. Security</h2>
      <ul>
        <li>All data transmitted via HTTPS/TLS encryption</li>
        <li>Payment data tokenized via Stripe (PCI-DSS Level 1)</li>
        <li>Pickup codes generated with cryptographic randomness (secrets module)</li>
        <li>Failed pickup attempt monitoring with automatic brute force detection (5-attempt escalation)</li>
        <li>Role-based access control for administrative functions</li>
        <li>MongoDB access restricted to internal network only</li>
      </ul>

      <h2>9. Cookies &amp; Tracking</h2>
      <p>We use essential cookies for authentication, language preferences, and cookie consent. We use PostHog for analytics (opt-out available). We use SendGrid for email open/click tracking.</p>

      <h2>10. Bilingual Services</h2>
      <p>BidVex is a bilingual platform (English and French). All communications, including pickup code emails, penalty notices, and marketing emails, are sent in your preferred language.</p>

      <h2>11. Children's Privacy</h2>
      <p>BidVex is not intended for users under 18 years of age. We do not knowingly collect data from minors.</p>

      <h2>12. Changes to This Policy</h2>
      <p>We may update this Privacy Policy from time to time. Material changes will be communicated via email or platform notification.</p>

      <h2>13. Contact &amp; Privacy Officer</h2>
      <p>For privacy inquiries or to exercise your rights, contact: <strong>privacy@bidvex.com</strong></p>
    </div>
  </div>
);
