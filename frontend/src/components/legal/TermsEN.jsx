import React from 'react';

export const TermsEN = () => (
  <div className="min-h-screen bg-background py-12 px-4">
    <div className="max-w-4xl mx-auto prose prose-sm dark:prose-invert">
      <h1>BidVex Inc. — Terms of Service</h1>
      <p className="text-muted-foreground">Last Updated: April 15, 2026 | Effective Date: April 15, 2026</p>

      <h2>1. Introduction &amp; Acceptance</h2>
      <p>Welcome to BidVex. These Terms of Service ("Terms") form a legally binding agreement between you ("User") and BidVex Inc. ("BidVex," "we," "us"). By registering, browsing, or participating in any auction, you agree to these Terms and our Privacy Policy. If you do not agree, do not use the Platform.</p>

      <h2>2. Definitions</h2>
      <ul>
        <li><strong>Platform</strong>: The BidVex website, mobile site, and all associated services.</li>
        <li><strong>Seller</strong>: A User who lists items for auction.</li>
        <li><strong>Buyer</strong>: A User who places bids or purchases items.</li>
        <li><strong>Partner</strong>: A verified business account with enhanced listing privileges.</li>
        <li><strong>Hammer Price</strong>: The winning bid amount at auction close.</li>
        <li><strong>Buyer's Premium</strong>: An additional fee charged to the Buyer on top of the Hammer Price.</li>
        <li><strong>Escrow</strong>: The holding of Buyer funds by BidVex until pickup/delivery is confirmed.</li>
        <li><strong>Pickup Code</strong>: A 6-character alphanumeric code sent to the Buyer to confirm item handoff.</li>
        <li><strong>Sticky Card</strong>: The requirement that Sellers maintain a valid payment method on file while listings are active.</li>
      </ul>

      <h2>3. Account Registration</h2>
      <p>You must be at least 18 years old and a resident of Canada to create an account. You agree to provide accurate, current, and complete information. You are responsible for all activity under your account. BidVex reserves the right to suspend or terminate accounts that violate these Terms.</p>

      <h2>4. Mandatory Payment Method (Sticky Card Policy)</h2>
      <h3>4.1 Requirement</h3>
      <p>To create a listing, every Seller must have a valid payment method (credit or debit card) on file, attached to their Stripe Customer profile. This requirement ensures accountability and protects Buyers.</p>
      <h3>4.2 Card Retention During Active Listings</h3>
      <p>Sellers <strong>cannot remove</strong> their payment method while any of their listings are in an active, live, or ending-soon status. Attempting to remove a payment method during this period will be blocked by the system.</p>
      <h3>4.3 Card Verification</h3>
      <p>BidVex verifies that the payment method on file is valid and not expired before allowing listing creation. If your card expires, you must update it before creating new listings.</p>
      <h3>4.4 Stripe Token Retention</h3>
      <p>BidVex stores a Stripe payment method token (not raw card data) on your account. This token may be used to process authorized charges, including cancellation penalties under Section 5.</p>

      <h2>5. Cancellation Penalty</h2>
      <h3>5.1 Trigger</h3>
      <p>A cancellation penalty is triggered when a Seller marks an item as "unable to deliver" after an auction has closed with a winning bid, or when an administrator flags a Seller for non-delivery.</p>
      <h3>5.2 Amount</h3>
      <p>The penalty is a flat fee of <strong>$50.00 CAD</strong>. This amount is automatically charged to the Seller's payment method on file.</p>
      <h3>5.3 Card Failure</h3>
      <p>If the penalty charge fails (e.g., card declined), the Seller's account will be flagged for administrative review and may be suspended until the penalty is resolved.</p>
      <h3>5.4 Authorization</h3>
      <p>By creating a listing on BidVex, you authorize BidVex to charge your payment method on file for any applicable cancellation penalties without further notice.</p>

      <h2>6. Escrow &amp; Pickup Code System (Non-Vehicle Items)</h2>
      <h3>6.1 How It Works</h3>
      <p>For non-vehicle items, when a Buyer wins an auction and payment is captured, the funds are held in escrow by BidVex. A unique 6-character Pickup Code is generated and emailed to the Buyer. The Seller must enter this code on their dashboard to confirm the item handoff and release the funds.</p>
      <h3>6.2 Pickup Code Delivery</h3>
      <p>The Pickup Code is sent to the Buyer's registered email address. Buyers are responsible for presenting this code to the Seller at the time of pickup or delivery.</p>
      <h3>6.3 Funds Release</h3>
      <p>Funds are released to the Seller's Stripe Connect account only after the correct Pickup Code is entered by the Seller.</p>
      <h3>6.4 48-Hour Auto-Release</h3>
      <p>If the Buyer does not present the Pickup Code within 48 hours of the escrow creation, funds are <strong>automatically released</strong> to the Seller. Both parties are notified by email when an auto-release occurs.</p>
      <h3>6.5 Dispute</h3>
      <p>Either party may open a dispute on an active escrow. Disputed escrows are reviewed by the BidVex team. During a dispute, funds remain held until resolution.</p>
      <h3>6.6 Vehicle Exclusion</h3>
      <p>Vehicle transactions are excluded from the escrow/pickup code system. Vehicles use a separate payment and settlement flow governed by the Vehicle Seller Licensing requirements.</p>

      <h2>7. Vehicle Seller Licensing</h2>
      <p>Only licensed vehicle sellers with a verified OPC (Office de la protection du consommateur) permit may list road vehicles on BidVex. Individual (unlicensed) sellers are prohibited from listing vehicles. Fraudulent attempts to list vehicles without proper licensing will result in immediate account suspension.</p>

      <h2>8. Fees &amp; Pricing</h2>
      <p>BidVex charges Buyer's Premiums, Seller Commissions, and platform fees as calculated by our PricingManager. Fee schedules vary by subscription tier (Free, Premium, VIP, Partner). All fees are transparently displayed before bid confirmation and at checkout. Stripe processing fees are recovered dynamically.</p>

      <h2>9. Marketplace Conduct</h2>
      <h3>9.1 Prohibited Behavior</h3>
      <ul>
        <li>Shill bidding (bidding on your own items to inflate prices)</li>
        <li>Listing counterfeit, stolen, or illegal items</li>
        <li>Providing false or misleading item descriptions</li>
        <li>Harassment of other users via messages or the Community Q&amp;A</li>
        <li>Manipulating auction outcomes through multiple accounts</li>
        <li>Attempting to circumvent the escrow or payment systems</li>
      </ul>
      <h3>9.2 Seller Obligations</h3>
      <p>Sellers must deliver items as described. Non-delivery after auction close triggers the cancellation penalty. Sellers must respond to Buyer inquiries within a reasonable timeframe.</p>
      <h3>9.3 Buyer Obligations</h3>
      <p>Buyers must complete payment promptly upon winning an auction. Buyers must present their Pickup Code at the time of item collection. Failure to collect within the escrow window does not entitle the Buyer to a refund (funds auto-release to the Seller).</p>

      <h2>10. Community Q&amp;A</h2>
      <p>The Community Q&amp;A is provided for informational purposes. Users must not post spam, offensive content, personal information of others, or commercial solicitations. BidVex reserves the right to moderate, edit, or remove content. Repeated violations may result in account restrictions.</p>

      <h2>11. Stripe Connect &amp; Payment Processing</h2>
      <p>BidVex uses Stripe as its payment processor. By using the Platform, you agree to Stripe's Connected Account Agreement and Stripe's Terms of Service. You authorize BidVex to create charges, holds, transfers, and penalties on your behalf through Stripe.</p>

      <h2>12. Limitation of Liability</h2>
      <p>BidVex acts as a marketplace facilitator and is not a party to the sale between Buyer and Seller. BidVex is not responsible for the quality, safety, legality, or accuracy of items listed. Our liability is limited to the fees collected by BidVex on any given transaction.</p>

      <h2>13. Governing Law</h2>
      <p>These Terms are governed by the laws of the Province of Quebec and the federal laws of Canada applicable therein. Any disputes shall be resolved in the courts of Quebec.</p>

      <h2>14. Changes to Terms</h2>
      <p>BidVex reserves the right to modify these Terms at any time. Material changes will be communicated via email or platform notification. Continued use after changes constitutes acceptance.</p>

      <h2>15. Contact</h2>
      <p>For questions about these Terms, contact us at <strong>legal@bidvex.com</strong>.</p>
    </div>
  </div>
);
