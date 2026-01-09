import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FileText, DollarSign, Building2, Scale, AlertTriangle, Shield } from 'lucide-react';

const TermsOfServicePage = () => {
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const scrollToSection = (id) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="min-h-screen bg-white dark:bg-slate-900 py-8 md:py-12">
      <div className="container mx-auto px-4 max-w-5xl">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl md:text-5xl font-bold text-slate-900 dark:text-white mb-2">
            Terms & Conditions
          </h1>
          <h2 className="text-2xl md:text-3xl font-semibold text-slate-700 dark:text-slate-300 mb-4">
            BidVex Terms & Conditions
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-400">
            <strong>Effective Date:</strong> January 9, 2026
          </p>
        </div>

        {/* Content Sections */}
        <div className="space-y-8">
          {/* Section 1 - Acceptance of Terms */}
          <section id="section-1" className="scroll-mt-20">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">1. Acceptance of Terms</h2>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              By accessing and using the BidVex platform (<strong>"Service"</strong>), you agree to be bound by these Terms & Conditions. If you disagree with any part of the terms, you may not access the Service.
            </p>
          </section>

          {/* Section 2 - User Accounts */}
          <section id="section-2" className="scroll-mt-20">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">2. User Accounts</h2>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>2.1</strong> Users must provide accurate and complete information during registration.
            </p>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>2.2</strong> You are responsible for safeguarding your password and any activities or actions under your account.
            </p>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>2.3</strong> You may not use another user's account without permission, and you must notify BidVex immediately of any unauthorized account access.
            </p>
          </section>

          {/* Section 3 - Auction Participation */}
          <section id="section-3" className="scroll-mt-20">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">3. Auction Participation</h2>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>3.1</strong> All bids are legally binding contracts to purchase.
            </p>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>3.2</strong> Bid amounts, fees (including buyer's premium and applicable taxes), and bidder are permanently recorded.
            </p>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>3.3</strong> Anti-sniping protection: Bids placed in the final minutes may extend the auction close time.
            </p>
          </section>

          {/* Section 4 - Payment Terms */}
          <section id="section-4" className="scroll-mt-20">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">4. Payment Terms</h2>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>4.1</strong> All payments are processed through our payment processor without storing credit card numbers.
            </p>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>4.2</strong> Currency exchange rates specified by the seller are locked once the auction goes live and will not change.
            </p>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>4.3</strong> Applicable taxes are calculated based on seller's tax registration status and buyer's location.
            </p>
          </section>

          {/* Section 5 - Transaction Fees and Payments */}
          <section id="section-5" className="scroll-mt-20">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                <DollarSign className="h-7 w-7 text-blue-600" />
                5. Transaction Fees and Payments
              </h2>
              <p className="text-slate-700 dark:text-slate-300 mb-4">
                <strong>5.1 Fee Disclosure</strong><br />
                BidVex transparently discloses the following fee structure upon the successful completion of an auction:
              </p>
            </div>

            {/* Section 5.2 - Standard Fee Structure */}
            <div className="bg-blue-50 dark:bg-blue-900/20 border-2 border-blue-300 dark:border-blue-700 rounded-lg p-6 mb-6">
              <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-3">5.2 Standard Fee Structure</h3>
              <div className="space-y-2 text-slate-700 dark:text-slate-300">
                <p>
                  <strong>Seller Commission:</strong> A standard fee of <span className="text-2xl font-bold text-blue-700 dark:text-blue-400">4%</span> of the final hammer price.
                </p>
                <p>
                  <strong>Buyer's Premium:</strong> A standard fee of <span className="text-2xl font-bold text-blue-700 dark:text-blue-400">5%</span> added to the final hammer price.
                </p>
              </div>
            </div>

            {/* Section 5.3 - Premium Member Discount */}
            <div className="bg-green-50 dark:bg-green-900/20 border-2 border-green-300 dark:border-green-700 rounded-lg p-6 mb-6">
              <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-3">5.3 Premium Member Discount</h3>
              <p className="text-slate-700 dark:text-slate-300 mb-3">
                <strong>Subscription Discount:</strong> Active Premium Members receive a <span className="text-2xl font-bold text-green-700 dark:text-green-400">1.5%</span> reduction on their respective fees:
              </p>
              <ul className="list-disc list-inside text-slate-700 dark:text-slate-300 space-y-2 ml-4">
                <li>
                  <strong>Premium Sellers pay <span className="text-xl font-bold text-green-700 dark:text-green-400">2.5%</span></strong> commission (instead of 4%)
                </li>
                <li>
                  <strong>Premium Buyers pay <span className="text-xl font-bold text-green-700 dark:text-green-400">3.5%</span></strong> buyer's premium (instead of 5%)
                </li>
              </ul>
            </div>

            {/* Section 5.4 - Settlement Deadline */}
            <div className="bg-red-50 dark:bg-red-900/20 border-2 border-red-300 dark:border-red-700 rounded-lg p-6 mb-6">
              <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-3">5.4 Settlement Deadline</h3>
              <div className="space-y-3 text-slate-700 dark:text-slate-300">
                <p>
                  <strong className="text-red-700 dark:text-red-400 text-xl">⚠️ IMPORTANT:</strong> Seller fees must be settled in full within <span className="text-2xl font-bold text-red-700 dark:text-red-400">fourteen (14) days</span> of the auction close.
                </p>
                <p className="font-semibold">
                  <strong>Late Payment Penalties:</strong>
                </p>
                <p>
                  Late payments may result in an account suspension and are subject to a <span className="font-bold text-red-700 dark:text-red-400">2% monthly interest penalty</span> on outstanding balances.
                </p>
              </div>
            </div>
          </section>

          {/* Section 6 - Seller Obligations */}
          <section id="section-6" className="scroll-mt-20">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                <Building2 className="h-7 w-7 text-purple-600" />
                6. Seller Obligations
              </h2>
            </div>

            <div className="space-y-4">
              <div>
                <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-3">6.1 Listing Accuracy</h3>
                <p className="text-slate-700 dark:text-slate-300">
                  Sellers must provide accurate descriptions, images, and condition reports for all items.
                </p>
              </div>

              {/* Section 6.2 - Facility Details */}
              <div className="bg-purple-50 dark:bg-purple-900/20 border-2 border-purple-300 dark:border-purple-700 rounded-lg p-6">
                <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-3">6.2 Facility Details</h3>
                <div className="bg-purple-100 dark:bg-purple-900/40 border border-purple-300 dark:border-purple-700 rounded-lg p-4 mb-4">
                  <p className="text-purple-900 dark:text-purple-100 font-bold flex items-center gap-2">
                    <Shield className="h-5 w-5" />
                    BINDING AGREEMENT: By listing an item, the Seller agrees that facility details (including but not limited to dock availability, crane capacity, forklift access, site safety requirements, and removal deadlines) provided in the listing are legally binding.
                  </p>
                </div>
                <p className="text-slate-700 dark:text-slate-300 mb-3">
                  The Seller is contractually obligated to fulfill the information they submit in:
                </p>
                <ul className="list-disc list-inside text-slate-700 dark:text-slate-300 space-y-1 ml-4">
                  <li><strong>Pickup Location:</strong> Must be accurate and accessible</li>
                  <li><strong>Site Capabilities:</strong> Loading docks, cranes, forklifts, scales</li>
                  <li><strong>Removal Deadlines:</strong> Must honor stated timeframes</li>
                  <li><strong>Access Requirements:</strong> PPE, ID verification, authorized personnel</li>
                </ul>
              </div>

              <div>
                <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-3">6.3 Removal Deadlines</h3>
                <p className="text-slate-700 dark:text-slate-300">
                  Sellers must honor the removal deadline or auction start/end time limits if these details are specified in their listing. If a buyer fails to collect within the agreed timeframe, the seller may:
                </p>
                <ul className="list-disc list-inside text-slate-700 dark:text-slate-300 space-y-1 ml-4 mt-2">
                  <li>Charge reasonable storage fees (as disclosed in the listing)</li>
                  <li>Request BidVex mediation to enforce buyer obligations</li>
                </ul>
              </div>
            </div>
          </section>

          {/* Section 7 - Buyer Obligations */}
          <section id="section-7" className="scroll-mt-20">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">7. Buyer Obligations</h2>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>7.1</strong> Buyers must inspect all available auction listing details, including condition reports specified by the seller.
            </p>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>7.2</strong> All sales are final. Buyers are responsible for arranging and paying for item pickup/shipping by seller's deadlines unless seller offers alternative assistance.
            </p>
          </section>

          {/* Section 8 - Refund Policy */}
          <section id="section-8" className="scroll-mt-20">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">8. Refund Policy</h2>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>8.1</strong> Refund eligibility is determined by the seller's stated policy for each auction.
            </p>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>8.2</strong> If the item received "Materially Deviates" from the listed condition, the buyer may be eligible for a full or partial refund as determined by BidVex mediation.
            </p>
          </section>

          {/* Section 9 - Intellectual Property */}
          <section id="section-9" className="scroll-mt-20">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">9. Intellectual Property</h2>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              All content on BidVex, including but not limited to logos, trademarks, text, and design, is the intellectual property of BidVex and protected by international trademark laws.
            </p>
          </section>

          {/* Section 10 - Limitation of Liability */}
          <section id="section-10" className="scroll-mt-20">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
              <Scale className="h-6 w-6" />
              10. Limitation of Liability
            </h2>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>10.1</strong> BidVex acts as an intermediary facilitator and is not responsible for the quality, safety, or legality of goods listed.
            </p>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              <strong>10.2</strong> BidVex is not liable to buyers for BidVex against any claims arising from their use of the Platform.
            </p>
          </section>

          {/* Section 11 - Governing Law */}
          <section id="section-11" className="scroll-mt-20">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">11. Governing Law</h2>
            <p className="text-slate-700 dark:text-slate-300 mb-3">
              These Terms & Conditions shall be governed by and construed in accordance with the laws of the Province of Quebec and the federal laws of Canada applicable therein.
            </p>
          </section>

          {/* Section 12 - Contact Information */}
          <section id="section-12" className="scroll-mt-20">
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">12. Contact Information</h2>
            <div className="bg-slate-50 dark:bg-slate-800/50 border-2 border-slate-300 dark:border-slate-700 rounded-lg p-6">
              <p className="text-slate-700 dark:text-slate-300 mb-2">
                <strong>BidVex Legal Department</strong>
              </p>
              <p className="text-slate-700 dark:text-slate-300">
                Email: <a href="mailto:legal@bidvex.com" className="text-blue-600 dark:text-blue-400 hover:underline">legal@bidvex.com</a>
              </p>
              <p className="text-slate-700 dark:text-slate-300 mt-3">
                <strong>Address:</strong><br />
                123 Auction Street<br />
                Montreal, Quebec, Canada<br />
                H3B 2Y5
              </p>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="mt-12 pt-6 border-t-2 border-slate-200 dark:border-slate-700">
          <p className="text-sm text-slate-600 dark:text-slate-400 text-center">
            Last updated: 1/9/2026
          </p>
          <p className="text-sm text-slate-600 dark:text-slate-400 text-center mt-2">
            © 2026 BidVex. All rights reserved.
          </p>
        </div>
      </div>
    </div>
  );
};

export default TermsOfServicePage;