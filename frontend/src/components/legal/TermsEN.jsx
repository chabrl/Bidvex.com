import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { 
  FileText, Mail, MapPin, Shield, AlertTriangle, Gavel, 
  Users, DollarSign, Scale, Lock, Ban, Clock, CheckCircle,
  XCircle, CreditCard, Building2
} from 'lucide-react';

export const TermsEN = () => {
  return (
    <div className="min-h-screen py-12 px-4 max-w-4xl mx-auto">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3 mb-4">
            <FileText className="h-8 w-8 text-primary" />
            <CardTitle className="text-3xl">BidVex Terms & Conditions</CardTitle>
          </div>
          <p className="text-muted-foreground">Last Updated: March 2026</p>
        </CardHeader>
        <CardContent className="prose prose-sm max-w-none space-y-8">
          
          {/* Table of Contents */}
          <section className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Table of Contents</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <ol className="list-decimal pl-6 space-y-1 text-blue-600 dark:text-blue-400">
                <li><a href="#introduction" className="hover:underline">Introduction & Acceptance</a></li>
                <li><a href="#platform-role" className="hover:underline">Platform Role & Disclaimers</a></li>
                <li><a href="#user-accounts" className="hover:underline">User Accounts</a></li>
                <li><a href="#seller" className="hover:underline">Seller Responsibilities</a></li>
                <li><a href="#buyer" className="hover:underline">Buyer Responsibilities</a></li>
                <li><a href="#bidding" className="hover:underline">Bidding & Auction Rules</a></li>
                <li><a href="#fees" className="hover:underline">Fees, Taxes & Payments</a></li>
                <li><a href="#as-is" className="hover:underline">AS-IS / WHERE-IS Clause</a></li>
              </ol>
              <ol className="list-decimal pl-6 space-y-1 text-blue-600 dark:text-blue-400" start={9}>
                <li><a href="#disputes" className="hover:underline">Dispute Resolution</a></li>
                <li><a href="#ip" className="hover:underline">Intellectual Property</a></li>
                <li><a href="#prohibited" className="hover:underline">Prohibited Conduct</a></li>
                <li><a href="#liability" className="hover:underline">Limitation of Liability</a></li>
                <li><a href="#termination" className="hover:underline">Suspension & Termination</a></li>
                <li><a href="#changes" className="hover:underline">Changes to Terms</a></li>
                <li><a href="#governing" className="hover:underline">Governing Law</a></li>
                <li><a href="#contact" className="hover:underline">Contact Information</a></li>
              </ol>
            </div>
          </section>

          {/* 1. Introduction */}
          <section id="introduction">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">1</span>
              Introduction & Acceptance of Terms
            </h2>
            <p className="mb-3">
              Welcome to BidVex. These Terms & Conditions ("Terms") form a legally binding agreement between you ("User," "you," or "your") and BidVex Inc. ("BidVex," "we," "us," or "our"). These Terms govern your access to and use of our online auction platform, website, and related services (collectively, "the Platform").
            </p>
            <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4 my-4">
              <p className="text-blue-800 dark:text-blue-200">
                <strong>By registering for an account, browsing the Platform, or participating in an auction,</strong> you acknowledge that you have read, understood, and agree to be bound by these Terms, as well as our Privacy Policy. If you do not agree to these Terms, you must not access or use the Platform.
              </p>
            </div>
            <p>BidVex facilitates online auctions for various items, including but not limited to vehicles, consumer goods, and commercial services.</p>
          </section>

          {/* 2. Platform Role */}
          <section id="platform-role">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">2</span>
              Platform Role & Disclaimers
            </h2>
            
            <div className="space-y-4">
              <div className="border-l-4 border-blue-500 pl-4">
                <h3 className="font-semibold text-lg">2.1 Independent Marketplace</h3>
                <p>BidVex is a digital marketplace and is not a seller, dealer, broker, owner, bailee, or agent of any listed items. BidVex does not have possession of, title to, or ownership rights in any item listed for sale.</p>
              </div>
              
              <div className="border-l-4 border-blue-500 pl-4">
                <h3 className="font-semibold text-lg">2.2 Transaction Parties</h3>
                <p>All sales are completed directly between the buyer and the seller. BidVex is not a party to the actual transaction between buyers and sellers. We do not transfer legal ownership of items from the seller to the buyer.</p>
              </div>
              
              <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                <h3 className="font-semibold text-lg text-amber-800 dark:text-amber-200 mb-2">2.3 BidVex Disclaimers</h3>
                <p className="text-amber-700 dark:text-amber-300 mb-2">BidVex does not and cannot:</p>
                <ul className="list-disc pl-6 space-y-1 text-amber-700 dark:text-amber-300">
                  <li>Inspect, certify, guarantee, or verify the condition, safety, legality, accuracy, or quality of listed items;</li>
                  <li>Handle or coordinate delivery, transport, storage, or logistics for any items;</li>
                  <li>Provide any warranties, express or implied, regarding the items; or</li>
                  <li>Accept responsibility for, or guarantee the resolution of, any disputes between buyers and sellers.</li>
                </ul>
              </div>
            </div>
          </section>

          {/* 3. User Accounts */}
          <section id="user-accounts">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">3</span>
              <Users className="h-5 w-5" /> User Accounts
            </h2>
            
            <div className="grid gap-4">
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">3.1 Registration</h3>
                <p>To participate in auctions, you are required to register and maintain a user account.</p>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">3.2 User Responsibilities</h3>
                <p className="mb-2">By creating an account, you agree to:</p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>Provide accurate, current, and complete information during the registration process;</li>
                  <li>Maintain the security of your account by protecting your password and restricting access;</li>
                  <li>Assume all responsibility for all activities that occur under your account; and</li>
                  <li>Immediately report any unauthorized access or use of your account to BidVex.</li>
                </ul>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">3.3 Eligibility</h3>
                <p>You must be at least <strong>eighteen (18) years of age</strong> and possess the legal capacity to enter into binding contracts to register for an account and use the Platform.</p>
              </div>
            </div>
          </section>

          {/* 4. Seller Responsibilities */}
          <section id="seller">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-emerald-100 dark:bg-emerald-900 rounded-full flex items-center justify-center text-emerald-600 text-sm font-bold">4</span>
              <Building2 className="h-5 w-5 text-emerald-600" /> Seller Responsibilities
            </h2>
            
            <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-lg p-4 mb-4">
              <h3 className="font-semibold text-lg text-emerald-800 dark:text-emerald-200 mb-2">4.1 Seller Covenants</h3>
              <p className="text-emerald-700 dark:text-emerald-300 mb-2">Sellers must adhere to the following obligations:</p>
              <ul className="list-disc pl-6 space-y-1 text-emerald-700 dark:text-emerald-300">
                <li>Provide accurate, complete, and detailed descriptions, specifications, and high-quality images of listed items;</li>
                <li>Confirm and guarantee legal ownership or the specific legal right to sell the listed items;</li>
                <li>Fully disclose any known defects, liens, encumbrances, or restrictions on the items;</li>
                <li>Comply with all applicable laws and regulations regarding the sale of the items;</li>
                <li>Complete the sale of an item with the winning bidder in a timely manner; and</li>
                <li>Respond promptly and professionally to buyer inquiries.</li>
              </ul>
            </div>
            
            <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <h3 className="font-semibold text-lg text-red-800 dark:text-red-200 mb-2 flex items-center gap-2">
                <Ban className="h-5 w-5" /> 4.2 Prohibited Listings
              </h3>
              <p className="text-red-700 dark:text-red-300">
                Sellers are strictly prohibited from listing items that are illegal, counterfeit, stolen, hazardous, recallable, or otherwise restricted by law or BidVex policy.
              </p>
            </div>
          </section>

          {/* 5. Buyer Responsibilities */}
          <section id="buyer">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">5</span>
              Buyer Responsibilities
            </h2>
            
            <div className="grid gap-4">
              <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <h3 className="font-semibold text-lg text-blue-800 dark:text-blue-200 mb-2">5.1 Due Diligence</h3>
                <p className="text-blue-700 dark:text-blue-300">
                  Buyers acknowledge that it is their sole responsibility to inspect items, ask questions of the seller, or arrange third-party inspections before placing a bid, as needed.
                </p>
              </div>
              
              <div className="bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800 rounded-lg p-4">
                <h3 className="font-semibold text-lg text-purple-800 dark:text-purple-200 mb-2 flex items-center gap-2">
                  <Gavel className="h-5 w-5" /> 5.2 Legally Binding Bids
                </h3>
                <p className="text-purple-700 dark:text-purple-300">
                  By placing a bid, you are making a <strong>legally binding offer</strong> to purchase the item if your bid is the highest at the close of the auction, subject to any reserve price.
                </p>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">5.3 Completion of Transaction</h3>
                <p>If you are the winning bidder, you agree to complete the payment within the specified deadlines and arrange for the delivery or pickup of the item directly with the seller.</p>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">5.4 Accurate Information</h3>
                <p>Buyers must provide accurate shipping and contact information to ensure successful communication and transaction completion.</p>
              </div>
            </div>
          </section>

          {/* 6. Bidding Rules */}
          <section id="bidding">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">6</span>
              <Gavel className="h-5 w-5" /> Bidding & Auction Rules
            </h2>
            
            <div className="grid gap-4">
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <CheckCircle className="h-6 w-6 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold">6.1 Binding Bids</h3>
                  <p>All bids placed on the Platform are legally binding contractual obligations.</p>
                </div>
              </div>
              
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <XCircle className="h-6 w-6 text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold">6.2 Bid Retraction</h3>
                  <p>Bid retractions are not permitted except in exceptional and limited circumstances, such as a material typographical error, and only if requested within <strong>one (1) hour</strong> of placing the bid.</p>
                </div>
              </div>
              
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <Shield className="h-6 w-6 text-blue-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold">6.3 Reserve Prices</h3>
                  <p>Sellers may set a "Reserve Price" (the confidential minimum price the seller is willing to accept). The item will not be sold unless the Reserve Price is met.</p>
                </div>
              </div>
              
              <div className="flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg">
                <Clock className="h-6 w-6 text-blue-600 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-blue-800 dark:text-blue-200">6.4 Anti-Sniping Policy</h3>
                  <p className="text-blue-700 dark:text-blue-300">If a bid is placed within the final <strong>two (2) minutes</strong> of an auction's scheduled end time, the auction duration will be extended by an additional two (2) minutes. This ensures a fair bidding process.</p>
                </div>
              </div>
            </div>
          </section>

          {/* 7. Fees */}
          <section id="fees">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center text-green-600 text-sm font-bold">7</span>
              <DollarSign className="h-5 w-5 text-green-600" /> Fees, Taxes, and Payment Structure
            </h2>
            
            <div className="space-y-4">
              <div>
                <h3 className="font-semibold text-lg mb-3">7.1 User Tiers</h3>
                <p className="mb-3">Upon registration, users are assigned to a specific tier. This tier dictates the applicable Buyer Premium and Seller Commission.</p>
                
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse">
                    <thead>
                      <tr className="bg-slate-100 dark:bg-slate-800">
                        <th className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-left font-semibold">Tier</th>
                        <th className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center font-semibold">Buyer Premium</th>
                        <th className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center font-semibold">Seller Commission</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="bg-slate-50 dark:bg-slate-800/50">
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 font-medium">Standard</td>
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center">5.0%</td>
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center">4.0%</td>
                      </tr>
                      <tr className="bg-blue-50 dark:bg-blue-950/30">
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 font-medium text-blue-700 dark:text-blue-300">Premium</td>
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center text-blue-700 dark:text-blue-300">3.5%</td>
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center text-blue-700 dark:text-blue-300">2.5%</td>
                      </tr>
                      <tr className="bg-amber-50 dark:bg-amber-950/30">
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 font-medium text-amber-700 dark:text-amber-300">VIP Elite</td>
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center text-amber-700 dark:text-amber-300">3.0%</td>
                        <td className="border border-slate-300 dark:border-slate-600 px-4 py-3 text-center text-amber-700 dark:text-amber-300">2.0%</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">7.2 Additional Fees</h3>
                <p>A mandatory <strong>Platform Fee of 2.5%</strong> is applied to all completed transactions for vehicles only.</p>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2">7.3 Taxes</h3>
                <p>Taxes (including GST, PST, HST, and QST, as applicable) are added to the final invoice. Tax calculations are based on the final sale price and the jurisdiction of the transaction.</p>
              </div>
              
              <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                <h3 className="font-semibold text-lg mb-2 text-amber-800 dark:text-amber-200">7.4 Payment Terms</h3>
                <p className="text-amber-700 dark:text-amber-300 mb-2">Full payment for all winning bids is due within <strong>fourteen (14) days</strong> of the auction close.</p>
                <p className="text-amber-700 dark:text-amber-300"><strong>Late Payments:</strong> Payments not received by the due date may incur a late payment penalty of <strong>2% per month</strong> (24% per annum) on the outstanding balance.</p>
              </div>
              
              <div className="flex items-start gap-3 p-4 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg">
                <CreditCard className="h-6 w-6 text-green-600 mt-0.5 flex-shrink-0" />
                <div>
                  <h3 className="font-semibold text-green-800 dark:text-green-200">7.5 Payment Processing</h3>
                  <p className="text-green-700 dark:text-green-300">All payments are handled via <strong>Stripe</strong>, a secure third-party payment processor. BidVex does not store, possess, or have access to any full credit card or bank account payment information.</p>
                </div>
              </div>
            </div>
          </section>

          {/* 8. AS-IS Clause */}
          <section id="as-is">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center text-red-600 text-sm font-bold">8</span>
              <AlertTriangle className="h-5 w-5 text-red-600" /> "AS-IS / WHERE-IS" Clause
            </h2>
            
            <div className="bg-red-50 dark:bg-red-950/30 border-2 border-red-300 dark:border-red-700 rounded-lg p-6">
              <p className="text-red-800 dark:text-red-200 font-medium uppercase text-sm leading-relaxed">
                YOU EXPRESSLY AGREE THAT ALL ITEMS LISTED ON THE PLATFORM ARE SOLD "AS-IS, WHERE-IS," WITH ALL FAULTS AND DEFECTS, AND WITHOUT ANY WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING ANY WARRANTY OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE. BIDVEX IS NOT RESPONSIBLE FOR THE CONDITION, SAFETY, LEGALITY, OR ACCURACY OF ANY ITEM OR FOR ANY DISPUTES BETWEEN USERS.
              </p>
            </div>
          </section>

          {/* 9. Disputes */}
          <section id="disputes">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">9</span>
              <Scale className="h-5 w-5" /> Dispute Resolution
            </h2>
            
            <div className="space-y-4">
              <div className="border-l-4 border-blue-500 pl-4">
                <h3 className="font-semibold">9.1 Direct Resolution</h3>
                <p>In the event of a dispute between a buyer and a seller, the parties agree to first attempt to resolve the issue directly and in good faith.</p>
              </div>
              
              <div className="border-l-4 border-blue-500 pl-4">
                <h3 className="font-semibold">9.2 Mediation by Support</h3>
                <p>If the parties are unable to resolve the dispute, they may contact BidVex Support within <strong>seven (7) days</strong> of the transaction close. BidVex may, at its sole discretion, attempt to mediate the dispute, but BidVex is not obligated to do so.</p>
              </div>
              
              <div className="border-l-4 border-blue-500 pl-4">
                <h3 className="font-semibold">9.3 Refunds</h3>
                <p>Refunds, returns, or adjustments are at the sole discretion of the seller unless BidVex determines that an item was significantly misrepresented in the listing.</p>
              </div>
            </div>
          </section>

          {/* 10. IP */}
          <section id="ip">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">10</span>
              Intellectual Property
            </h2>
            
            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 mb-4">
              <h3 className="font-semibold mb-2">10.1 Ownership</h3>
              <p>All content and materials on the Platform, including the BidVex logo, text, graphics, images, video, code, and software are the property of BidVex Inc. or its licensors and are protected by copyright, trademark, and other intellectual property laws.</p>
            </div>
            
            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
              <h3 className="font-semibold mb-2">10.2 Use Restrictions</h3>
              <ul className="list-disc pl-6 space-y-1">
                <li>Users are prohibited from copying, reproducing, modifying, distributing, or selling any Content without prior written permission.</li>
                <li>The use of our trademarks, logos, or branding without express authorization is prohibited.</li>
                <li>You are not permitted to use "scraping," "data mining," or automated agents to collect information from the Platform.</li>
              </ul>
            </div>
          </section>

          {/* 11. Prohibited */}
          <section id="prohibited">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center text-red-600 text-sm font-bold">11</span>
              <Ban className="h-5 w-5 text-red-600" /> Prohibited Conduct
            </h2>
            
            <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4">
              <p className="text-red-800 dark:text-red-200 mb-3">Users are strictly prohibited from engaging in the following conduct:</p>
              <ul className="list-disc pl-6 space-y-1 text-red-700 dark:text-red-300">
                <li>Engaging in fraud, shill bidding, or any form of bid manipulation or artificial inflation;</li>
                <li>Harassing, threatening, or defrauding other users or BidVex employees;</li>
                <li>Posting spam, viruses, or malicious code that may harm the Platform or users;</li>
                <li>Circumventing BidVex fees or manipulating the auction process;</li>
                <li>Creating multiple accounts to bypass restrictions or manipulate auctions; or</li>
                <li>Engaging in any conduct that violates applicable laws or regulations.</li>
              </ul>
              <p className="mt-3 text-red-800 dark:text-red-200 font-semibold">
                Violations of this section may result in immediate suspension or termination of your account, and may result in legal action.
              </p>
            </div>
          </section>

          {/* 12. Liability */}
          <section id="liability">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">12</span>
              Limitation of Liability
            </h2>
            
            <div className="bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded-lg p-4">
              <p className="text-sm uppercase leading-relaxed mb-3">
                TO THE FULLEST EXTENT PERMITTED BY LAW, BIDVEX PROVIDES THE PLATFORM "AS IS" AND "AS AVAILABLE." BIDVEX SHALL NOT BE LIABLE FOR:
              </p>
              <ul className="list-disc pl-6 space-y-1 text-sm">
                <li>THE ACCURACY, COMPLETENESS, OR RELIABILITY OF ITEM DESCRIPTIONS;</li>
                <li>THE ACTIONS, OMISSIONS, OR CONDUCT OF BUYERS OR SELLERS;</li>
                <li>ANY LOSSES, DAMAGES, OR HARM ARISING FROM DOWNTIME, ERRORS, OR TECHNICAL INTERRUPTIONS; OR</li>
                <li>ANY DIRECT, INDIRECT, INCIDENTAL, CONSEQUENTIAL, SPECIAL, OR PUNITIVE DAMAGES.</li>
              </ul>
              <p className="mt-3 text-sm font-semibold">
                OUR MAXIMUM AGGREGATE LIABILITY SHALL NOT EXCEED THE TOTAL FEES PAID BY YOU TO BIDVEX IN THE TWELVE (12) MONTHS PRIOR TO THE CLAIM.
              </p>
            </div>
          </section>

          {/* 13. Termination */}
          <section id="termination">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">13</span>
              Suspension & Termination
            </h2>
            
            <div className="grid gap-4">
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold mb-2">13.1 BidVex's Right</h3>
                <p>BidVex reserves the right, at its sole discretion, to suspend, terminate, or restrict your account and access to the Platform if you violate these Terms or engage in conduct harmful to BidVex or its users.</p>
              </div>
              
              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <h3 className="font-semibold mb-2">13.2 User Closing Account</h3>
                <p>You may close your BidVex account at any time. However, closing your account does not release you from any outstanding obligations, including legally binding bids and payment requirements.</p>
              </div>
            </div>
          </section>

          {/* 14. Changes */}
          <section id="changes">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">14</span>
              Changes to Terms & Conditions
            </h2>
            <p>BidVex reserves the right to update or modify these Terms at any time. Significant changes will be communicated to registered users via email and platform notifications. Your continued use of the Platform after the effective date of any changes constitutes your acceptance of the new Terms.</p>
          </section>

          {/* 15. Governing Law */}
          <section id="governing">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">15</span>
              <Scale className="h-5 w-5" /> Governing Law & Jurisdiction
            </h2>
            <p>These Terms and your use of the Platform are governed by and construed in accordance with the laws of the <strong>Province of Quebec</strong> and the federal laws of Canada applicable therein. Any disputes arising out of or related to these Terms shall be resolved exclusively in the courts of <strong>Montreal, Quebec</strong>.</p>
          </section>

          {/* 16. Contact */}
          <section id="contact" className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">16</span>
              Contact Information
            </h2>
            <p className="font-semibold text-lg mb-4">BidVex Legal & Data Protection Officer</p>
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Mail className="h-5 w-5 text-blue-600" />
                <span><strong>Email:</strong> support@bidvex.com</span>
              </div>
              <div className="flex items-start gap-3">
                <MapPin className="h-5 w-5 text-blue-600 mt-0.5" />
                <div>
                  <strong>Mailing Address:</strong><br />
                  761 Chalifoux Street<br />
                  Sherbrooke, Quebec, Canada<br />
                  J1G 0A8
                </div>
              </div>
            </div>
          </section>

          {/* Footer */}
          <div className="text-center text-sm text-muted-foreground pt-6 border-t">
            <p>© 2026 BidVex. All rights reserved.</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default TermsEN;
