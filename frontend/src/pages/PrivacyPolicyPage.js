import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Shield, Mail, MapPin } from 'lucide-react';

const PrivacyPolicyPage = () => {
  return (
    <div className="min-h-screen py-12 px-4 max-w-4xl mx-auto">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3 mb-4">
            <Shield className="h-8 w-8 text-primary" />
            <CardTitle className="text-3xl">Privacy Policy</CardTitle>
          </div>
          <p className="text-muted-foreground">Last Updated: March 2026</p>
        </CardHeader>
        <CardContent className="prose prose-sm max-w-none space-y-8">
          
          {/* Table of Contents */}
          <section className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Table of Contents</h2>
            <ol className="list-decimal pl-6 space-y-1 text-blue-600 dark:text-blue-400">
              <li><a href="#introduction" className="hover:underline">Introduction</a></li>
              <li><a href="#information-collect" className="hover:underline">Information We Collect</a></li>
              <li><a href="#purpose" className="hover:underline">Purpose of Processing</a></li>
              <li><a href="#sharing" className="hover:underline">Information Sharing</a></li>
              <li><a href="#cookies" className="hover:underline">Cookies & Tracking</a></li>
              <li><a href="#recommendation" className="hover:underline">Recommendation Engine & Behavioral Tracking</a></li>
              <li><a href="#security" className="hover:underline">Data Security</a></li>
              <li><a href="#rights" className="hover:underline">Your Rights (GDPR/PIPEDA)</a></li>
              <li><a href="#retention" className="hover:underline">Data Retention</a></li>
              <li><a href="#contact" className="hover:underline">Contact Us</a></li>
            </ol>
          </section>

          {/* 1. Introduction */}
          <section id="introduction">
            <h2 className="text-2xl font-semibold mb-3">1. Introduction</h2>
            <p>BidVex is committed to protecting your privacy. This policy explains how we collect, use, and protect your personal data, including data specific to vehicle auctions.</p>
          </section>

          {/* 2. Information We Collect */}
          <section id="information-collect">
            <h2 className="text-2xl font-semibold mb-3">2. Information We Collect</h2>
            
            <div className="space-y-6">
              <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-emerald-800 dark:text-emerald-200 mb-3">Sellers (Vehicle Section)</h3>
                <ul className="list-disc pl-6 space-y-2 text-emerald-700 dark:text-emerald-300">
                  <li><strong>Identity Data:</strong> Name, date of birth, government-issued ID verification</li>
                  <li><strong>Contact Data:</strong> Email, phone, address</li>
                  <li><strong>Business Data:</strong> Business name, dealer license (if applicable)</li>
                  <li><strong>Vehicle Data:</strong> VIN, make, model, year, photos, documents</li>
                  <li><strong>Financial Data:</strong> Banking details for payouts</li>
                </ul>
              </div>

              <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-blue-800 dark:text-blue-200 mb-3">Buyers (Vehicle Section)</h3>
                <ul className="list-disc pl-6 space-y-2 text-blue-700 dark:text-blue-300">
                  <li><strong>Identity Data:</strong> Name, email</li>
                  <li><strong>Contact Data:</strong> Phone, address</li>
                  <li><strong>Payment Data:</strong> Credit card information (processed securely via Stripe)</li>
                  <li><strong>Transaction Data:</strong> Bidding history, won items</li>
                </ul>
              </div>

              <div className="bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-3">Technical Data (All Users)</h3>
                <p className="text-slate-600 dark:text-slate-400">IP address, browser type, device information for security and platform optimization</p>
              </div>
            </div>
          </section>

          {/* 3. Purpose of Processing */}
          <section id="purpose">
            <h2 className="text-2xl font-semibold mb-3">3. Purpose of Processing</h2>
            <p className="mb-3">We process your personal data to:</p>
            <ul className="list-disc pl-6 space-y-2">
              <li>Facilitate bidding, buying, and selling of vehicles</li>
              <li>Display trust indicators, verified badges, and user ratings</li>
              <li>Enable secure buyer/seller communication</li>
              <li>Verify identities to prevent fraud</li>
              <li>Process payments securely (via Stripe)</li>
              <li>Provide customer support</li>
              <li>Analyze usage patterns to improve platform functionality</li>
              <li>Comply with legal obligations (GDPR, PIPEDA, tax laws)</li>
            </ul>
          </section>

          {/* 4. Information Sharing */}
          <section id="sharing">
            <h2 className="text-2xl font-semibold mb-3">4. Information Sharing</h2>
            <ul className="list-disc pl-6 space-y-2 mb-4">
              <li>Winning buyers receive seller contact information to complete transactions</li>
              <li>Sellers receive buyer contact info for deliveries or pickups</li>
              <li>Ratings, trust badges, and verified status are public on the platform</li>
            </ul>
            
            <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4 my-4">
              <h4 className="font-semibold text-red-800 dark:text-red-200 mb-2">We do NOT:</h4>
              <ul className="list-disc pl-6 space-y-1 text-red-700 dark:text-red-300">
                <li>Sell your data to third parties</li>
                <li>Share data for marketing purposes without consent</li>
              </ul>
            </div>

            <p className="mt-4 mb-2"><strong>Third-party partners we may share data with for operations only:</strong></p>
            <ul className="list-disc pl-6 space-y-1">
              <li>Payment Processors (Stripe)</li>
              <li>Email Service Providers (SendGrid)</li>
              <li>SMS Services (Twilio)</li>
              <li>Shipping Providers (with consent)</li>
              <li>Legal Authorities (if required by law)</li>
            </ul>
          </section>

          {/* 5. Cookies & Tracking */}
          <section id="cookies">
            <h2 className="text-2xl font-semibold mb-3">5. Cookies & Tracking</h2>
            <p className="mb-3">Cookies enhance your experience and analyze platform usage</p>
            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
              <p className="mb-2"><strong>Types:</strong></p>
              <ul className="list-disc pl-6 space-y-1">
                <li><strong>Essential</strong> (required)</li>
                <li><strong>Analytics</strong> (optional)</li>
                <li><strong>Personalization</strong> (optional)</li>
                <li><strong>Marketing</strong> (optional)</li>
              </ul>
            </div>
            <p className="mt-3">Third-party advertising cookies (e.g., Google Ads) may be used; opt-out available via Google Ads Settings</p>
          </section>

          {/* 6. Recommendation Engine */}
          <section id="recommendation">
            <h2 className="text-2xl font-semibold mb-3">6. Recommendation Engine & Behavioral Tracking</h2>
            <p className="mb-3">AI-powered suggestions based on:</p>
            <ul className="list-disc pl-6 space-y-1 mb-3">
              <li>Browsing history</li>
              <li>Bidding patterns</li>
              <li>Purchase history</li>
              <li>Search queries</li>
              <li>Watchlist items</li>
            </ul>
            <p className="text-sm bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
              Users can opt out of personalized recommendations without affecting core platform functionality
            </p>
          </section>

          {/* 7. Data Security */}
          <section id="security">
            <h2 className="text-2xl font-semibold mb-3">7. Data Security</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-3">
                <p className="font-medium text-green-800 dark:text-green-200">TLS/SSL Encryption</p>
                <p className="text-sm text-green-600 dark:text-green-400">Data in transit</p>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-3">
                <p className="font-medium text-green-800 dark:text-green-200">AES-256 Encryption</p>
                <p className="text-sm text-green-600 dark:text-green-400">Data at rest</p>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-3">
                <p className="font-medium text-green-800 dark:text-green-200">PCI-DSS Compliant</p>
                <p className="text-sm text-green-600 dark:text-green-400">Payments via Stripe</p>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-3">
                <p className="font-medium text-green-800 dark:text-green-200">Multi-Factor Auth</p>
                <p className="text-sm text-green-600 dark:text-green-400">Role-based access</p>
              </div>
            </div>
            <p className="mt-3">24/7 security monitoring and regular vulnerability audits</p>
          </section>

          {/* 8. Your Rights */}
          <section id="rights">
            <h2 className="text-2xl font-semibold mb-3">8. Your Rights (GDPR/PIPEDA)</h2>
            <div className="space-y-3">
              <div className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="font-semibold text-blue-600 min-w-[120px]">Access:</span>
                <span>Request a copy of your data</span>
              </div>
              <div className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="font-semibold text-blue-600 min-w-[120px]">Correction:</span>
                <span>Fix inaccurate or incomplete information</span>
              </div>
              <div className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="font-semibold text-blue-600 min-w-[120px]">Deletion:</span>
                <span>Request removal of your personal data</span>
              </div>
              <div className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="font-semibold text-blue-600 min-w-[120px]">Withdrawal:</span>
                <span>Stop processing for specific purposes</span>
              </div>
              <div className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="font-semibold text-blue-600 min-w-[120px]">Objection:</span>
                <span>Object to certain data processing</span>
              </div>
              <div className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <span className="font-semibold text-blue-600 min-w-[120px]">Portability:</span>
                <span>Export your data in a machine-readable format</span>
              </div>
            </div>
          </section>

          {/* 9. Data Retention */}
          <section id="retention">
            <h2 className="text-2xl font-semibold mb-3">9. Data Retention</h2>
            <ul className="list-disc pl-6 space-y-2">
              <li><strong>Account data:</strong> Retained for 7 years after account closure</li>
              <li><strong>Transactions:</strong> Retained for 7 years for tax and legal compliance</li>
              <li><strong>Vehicle listings:</strong> Retained for disputes or verification purposes</li>
            </ul>
          </section>

          {/* 10. Contact Us */}
          <section id="contact" className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-4">10. Contact Us</h2>
            <p className="font-semibold text-lg mb-4">BidVex Data Protection Officer</p>
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Mail className="h-5 w-5 text-blue-600" />
                <span><strong>Email:</strong> support@bidvex.com</span>
              </div>
              <div className="flex items-start gap-3">
                <MapPin className="h-5 w-5 text-blue-600 mt-0.5" />
                <span><strong>Mailing Address:</strong> 761 Chalifoux Street, Sherbrooke, Quebec, Canada, J1G 0A8</span>
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

export default PrivacyPolicyPage;
