import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Shield, FileText, Cookie, Eye, Lock, Database, AlertCircle, Mail } from 'lucide-react';

const PrivacyPolicyPage = () => {
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
          <h1 className="text-4xl md:text-5xl font-bold text-slate-900 dark:text-white mb-4">
            Privacy Policy
          </h1>
          <p className="text-lg text-slate-600 dark:text-slate-400">
            📅 <strong>Last Updated:</strong> January 9, 2026
          </p>
        </div>

        {/* Table of Contents */}
        <div className="bg-blue-50 dark:bg-blue-900/20 border-2 border-blue-200 dark:border-blue-700 rounded-lg p-6 mb-8">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Table of Contents
          </h2>
          <div className="grid md:grid-cols-2 gap-2">
            <button onClick={() => scrollToSection('section-1')} className="text-left text-blue-600 dark:text-blue-400 hover:underline">
              1.0 Data Collection
            </button>
            <button onClick={() => scrollToSection('section-2')} className="text-left text-blue-600 dark:text-blue-400 hover:underline">
              2.0 Purpose of Processing
            </button>
            <button onClick={() => scrollToSection('section-3')} className="text-left text-blue-600 dark:text-blue-400 hover:underline">
              3.0 Data Sharing
            </button>
            <button onClick={() => scrollToSection('section-4')} className="text-left text-blue-600 dark:text-blue-400 hover:underline">
              4.0 Your Global Rights (GDPR/PIPEDA)
            </button>
            <button onClick={() => scrollToSection('section-5')} className="text-left text-blue-600 dark:text-blue-400 hover:underline">
              5.0 Cookies & Tracking
            </button>
            <button onClick={() => scrollToSection('section-6')} className="text-left text-blue-600 dark:text-blue-400 hover:underline">
              6.0 Recommendation Engine
            </button>
            <button onClick={() => scrollToSection('section-7')} className="text-left text-blue-600 dark:text-blue-400 hover:underline">
              7.0 Data Security
            </button>
            <button onClick={() => scrollToSection('section-8')} className="text-left text-blue-600 dark:text-blue-400 hover:underline">
              8.0 Contact Us
            </button>
          </div>
        </div>

        {/* Content Sections */}
        <div className="space-y-8">
          {/* Section 1.0 - Data Collection */}
          <section id="section-1" className="scroll-mt-20">
            <div className="bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500 p-6 rounded-r-lg">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                <Database className="h-6 w-6 text-blue-600" />
                1.0 Data Collection
              </h2>
              <p className="text-slate-700 dark:text-slate-300 mb-4">
                We collect the following types of personal data when you use BidVex:
              </p>
              
              <div className="space-y-4">
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-white mb-2">🆔 Identity Data</h3>
                  <ul className="list-disc list-inside text-slate-700 dark:text-slate-300 space-y-1 ml-4">
                    <li><strong>Name</strong> - For account registration and communication</li>
                    <li><strong>Email</strong> - Primary communication and login</li>
                    <li><strong>Phone Number</strong> - SMS notifications and verification</li>
                    <li><strong>Address</strong> - Shipping and billing purposes</li>
                  </ul>
                </div>

                <div>
                  <h3 className="font-bold text-slate-900 dark:text-white mb-2">🛡️ Verification Data (Sellers)</h3>
                  <ul className="list-disc list-inside text-slate-700 dark:text-slate-300 space-y-1 ml-4">
                    <li><strong>ID Verification</strong> - Government-issued ID for seller accounts</li>
                    <li><strong>Tax Numbers</strong> - GST/QST for business sellers</li>
                    <li><strong>Bank Details</strong> - For payment processing</li>
                  </ul>
                </div>

                <div>
                  <h3 className="font-bold text-slate-900 dark:text-white mb-2">💰 Transaction Data</h3>
                  <ul className="list-disc list-inside text-slate-700 dark:text-slate-300 space-y-1 ml-4">
                    <li><strong>Bidding History</strong> - All bids placed on auctions</li>
                    <li><strong>Purchase History</strong> - Items won and transactions</li>
                    <li><strong>Payment Information</strong> - Processed securely via Stripe</li>
                  </ul>
                </div>

                <div>
                  <h3 className="font-bold text-slate-900 dark:text-white mb-2">🔧 Technical Data</h3>
                  <ul className="list-disc list-inside text-slate-700 dark:text-slate-300 space-y-1 ml-4">
                    <li><strong>IP Address</strong> - For security and fraud prevention</li>
                    <li><strong>Browser Type</strong> - For compatibility and analytics</li>
                    <li><strong>Device Information</strong> - For responsive design optimization</li>
                  </ul>
                </div>
              </div>
            </div>
          </section>

          {/* Section 2.0 - Purpose of Processing */}
          <section id="section-2" className="scroll-mt-20">
            <div className="bg-slate-50 dark:bg-slate-800/50 border-l-4 border-slate-500 p-6 rounded-r-lg">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">2.0 Purpose of Processing</h2>
              <p className="text-slate-700 dark:text-slate-300 mb-4">
                We process your personal data for the following legitimate business purposes:
              </p>
              <ul className="list-disc list-inside text-slate-700 dark:text-slate-300 space-y-2 ml-4">
                <li><strong>Account Management</strong> - To create and maintain your BidVex account</li>
                <li><strong>Auction Operations</strong> - To facilitate bidding, buying, and selling on our platform</li>
                <li><strong>Payment Processing</strong> - To process transactions securely through our payment partners</li>
                <li><strong>Communication</strong> - To send auction updates, notifications, and customer support responses</li>
                <li><strong>Security & Fraud Prevention</strong> - To protect our platform and users from fraudulent activity</li>
                <li><strong>Legal Compliance</strong> - To comply with applicable laws and regulations (GDPR, PIPEDA, tax laws)</li>
                <li><strong>Platform Improvement</strong> - To analyze usage patterns and improve our services</li>
              </ul>
            </div>
          </section>

          {/* Section 3.0 - Data Sharing */}
          <section id="section-3" className="scroll-mt-20">
            <div className="bg-green-50 dark:bg-green-900/20 border-l-4 border-green-500 p-6 rounded-r-lg">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                <Shield className="h-6 w-6 text-green-600" />
                3.0 Data Sharing
              </h2>
              
              <div className="bg-green-100 dark:bg-green-900/40 border border-green-300 dark:border-green-700 rounded-lg p-4 mb-4">
                <p className="text-lg font-bold text-green-900 dark:text-green-100">
                  ✅ <span className="text-xl">BidVex NEVER sells your data</span>
                </p>
              </div>

              <p className="text-slate-700 dark:text-slate-300 mb-4">
                We only share your data with trusted partners who help us operate the platform:
              </p>
              <ul className="list-disc list-inside text-slate-700 dark:text-slate-300 space-y-2 ml-4">
                <li><strong>Payment Processor (Stripe)</strong> - For secure payment processing</li>
                <li><strong>Email Service (SendGrid)</strong> - For transactional emails and notifications</li>
                <li><strong>SMS Service (Twilio)</strong> - For SMS verification and notifications</li>
                <li><strong>Shipping Partners</strong> - To fulfill delivery of purchased items (only with your consent)</li>
                <li><strong>Legal Authorities</strong> - When required by law or court order</li>
              </ul>

              <p className="text-slate-700 dark:text-slate-300 mt-4">
                All third-party partners are contractually obligated to protect your data and use it only for the specified purposes.
              </p>
            </div>
          </section>

          {/* Section 4.0 - Your Global Rights */}
          <section id="section-4" className="scroll-mt-20">
            <div className="bg-purple-50 dark:bg-purple-900/20 border-l-4 border-purple-500 p-6 rounded-r-lg">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                <AlertCircle className="h-6 w-6 text-purple-600" />
                4.0 Your Global Rights (GDPR/PIPEDA)
              </h2>
              <p className="text-slate-700 dark:text-slate-300 mb-4">
                Under GDPR (European Union) and PIPEDA (Canada), you have the following rights:
              </p>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="bg-white dark:bg-slate-800 p-4 rounded-lg border border-purple-200 dark:border-purple-700">
                  <h3 className="font-bold text-purple-900 dark:text-purple-100 mb-2">🔍 Right to Access</h3>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    Request a copy of all personal data we hold about you
                  </p>
                </div>
                <div className="bg-white dark:bg-slate-800 p-4 rounded-lg border border-purple-200 dark:border-purple-700">
                  <h3 className="font-bold text-purple-900 dark:text-purple-100 mb-2">✏️ Right to Rectification</h3>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    Correct any inaccurate or incomplete data
                  </p>
                </div>
                <div className="bg-white dark:bg-slate-800 p-4 rounded-lg border border-purple-200 dark:border-purple-700">
                  <h3 className="font-bold text-purple-900 dark:text-purple-100 mb-2">🗑️ Right to be Forgotten</h3>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    Request deletion of your personal data (subject to legal retention requirements)
                  </p>
                </div>
                <div className="bg-white dark:bg-slate-800 p-4 rounded-lg border border-purple-200 dark:border-purple-700">
                  <h3 className="font-bold text-purple-900 dark:text-purple-100 mb-2">📦 Right to Data Portability</h3>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    Export your data in a machine-readable format
                  </p>
                </div>
                <div className="bg-white dark:bg-slate-800 p-4 rounded-lg border border-purple-200 dark:border-purple-700">
                  <h3 className="font-bold text-purple-900 dark:text-purple-100 mb-2">🚫 Right to Object</h3>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    Object to processing for marketing purposes
                  </p>
                </div>
                <div className="bg-white dark:bg-slate-800 p-4 rounded-lg border border-purple-200 dark:border-purple-700">
                  <h3 className="font-bold text-purple-900 dark:text-purple-100 mb-2">⏸️ Right to Restriction</h3>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    Restrict processing under certain circumstances
                  </p>
                </div>
              </div>

              {/* Request Account Deletion Button */}
              <div className="mt-6 bg-red-50 dark:bg-red-900/20 border-2 border-red-300 dark:border-red-700 rounded-lg p-6">
                <h3 className="text-lg font-bold text-red-900 dark:text-red-100 mb-3 flex items-center gap-2">
                  <AlertCircle className="h-5 w-5" />
                  Exercise Your Rights
                </h3>
                <p className="text-slate-700 dark:text-slate-300 mb-4">
                  To exercise any of these rights, including the Right to be Forgotten, please contact us or use the button below:
                </p>
                <Link 
                  to="/auth" 
                  className="inline-block bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-6 rounded-lg transition-colors"
                >
                  Request Account Deletion
                </Link>
              </div>
            </div>
          </section>

          {/* Section 5.0 - Cookies & Tracking */}
          <section id="section-5" className="scroll-mt-20">
            <div className="bg-amber-50 dark:bg-amber-900/20 border-l-4 border-amber-500 p-6 rounded-r-lg">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                <Cookie className="h-6 w-6 text-amber-600" />
                5.0 Cookies & Tracking
              </h2>
              <p className="text-slate-700 dark:text-slate-300 mb-4">
                BidVex uses cookies to enhance your experience and analyze platform usage. You can manage your cookie preferences at any time.
              </p>
              
              <div className="overflow-x-auto">
                <table className="w-full border-collapse bg-white dark:bg-slate-800 rounded-lg overflow-hidden">
                  <thead>
                    <tr className="bg-amber-100 dark:bg-amber-900/40">
                      <th className="text-left p-3 font-bold text-slate-900 dark:text-white border-b border-amber-200 dark:border-amber-700">Cookie Type</th>
                      <th className="text-left p-3 font-bold text-slate-900 dark:text-white border-b border-amber-200 dark:border-amber-700">Purpose</th>
                      <th className="text-left p-3 font-bold text-slate-900 dark:text-white border-b border-amber-200 dark:border-amber-700">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-slate-200 dark:border-slate-700">
                      <td className="p-3 font-semibold text-slate-900 dark:text-white">Essential</td>
                      <td className="p-3 text-slate-700 dark:text-slate-300">Required for login, authentication, and core platform functionality</td>
                      <td className="p-3">
                        <span className="inline-block bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200 px-3 py-1 rounded-full text-sm font-semibold">Required</span>
                      </td>
                    </tr>
                    <tr className="border-b border-slate-200 dark:border-slate-700">
                      <td className="p-3 font-semibold text-slate-900 dark:text-white">Analytics</td>
                      <td className="p-3 text-slate-700 dark:text-slate-300">Understand usage patterns and improve platform performance</td>
                      <td className="p-3">
                        <span className="inline-block bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200 px-3 py-1 rounded-full text-sm font-semibold">Optional</span>
                      </td>
                    </tr>
                    <tr className="border-b border-slate-200 dark:border-slate-700">
                      <td className="p-3 font-semibold text-slate-900 dark:text-white">Personalization</td>
                      <td className="p-3 text-slate-700 dark:text-slate-300">Remember your preferences (language, currency, theme)</td>
                      <td className="p-3">
                        <span className="inline-block bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200 px-3 py-1 rounded-full text-sm font-semibold">Optional</span>
                      </td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-slate-900 dark:text-white">Marketing</td>
                      <td className="p-3 text-slate-700 dark:text-slate-300">Targeted advertising and promotional content</td>
                      <td className="p-3">
                        <span className="inline-block bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200 px-3 py-1 rounded-full text-sm font-semibold">Optional</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          {/* Section 6.0 - Recommendation Engine */}
          <section id="section-6" className="scroll-mt-20">
            <div className="bg-cyan-50 dark:bg-cyan-900/20 border-l-4 border-cyan-500 p-6 rounded-r-lg">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                <Eye className="h-6 w-6 text-cyan-600" />
                6.0 Recommendation Engine & Behavioral Tracking
              </h2>
              <p className="text-slate-700 dark:text-slate-300 mb-4">
                <strong>BidVex uses an AI-powered recommendation engine</strong> to suggest auction lots that may interest you based on:
              </p>
              <ul className="list-disc list-inside text-slate-700 dark:text-slate-300 space-y-2 ml-4 mb-4">
                <li><strong>Browsing History</strong> - Pages you view and time spent on listings</li>
                <li><strong>Bidding Patterns</strong> - Categories and price ranges you bid on</li>
                <li><strong>Purchase History</strong> - Items you've won in the past</li>
                <li><strong>Search Queries</strong> - Keywords you search for on the platform</li>
                <li><strong>Watchlist Items</strong> - Auctions you've saved or favorited</li>
              </ul>
              <div className="bg-cyan-100 dark:bg-cyan-900/40 border border-cyan-300 dark:border-cyan-700 rounded-lg p-4">
                <p className="text-slate-900 dark:text-cyan-100 font-semibold">
                  💡 <strong>Transparency Note:</strong> You can opt out of personalized recommendations at any time in your account settings. This will not affect core platform functionality.
                </p>
              </div>
            </div>
          </section>

          {/* Section 7.0 - Data Security */}
          <section id="section-7" className="scroll-mt-20">
            <div className="bg-slate-50 dark:bg-slate-800/50 border-l-4 border-slate-500 p-6 rounded-r-lg">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                <Lock className="h-6 w-6 text-slate-600" />
                7.0 Data Security
              </h2>
              <p className="text-slate-700 dark:text-slate-300 mb-4">
                We implement industry-standard security measures to protect your personal data:
              </p>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="bg-white dark:bg-slate-800 p-4 rounded-lg border border-slate-200 dark:border-slate-700">
                  <h3 className="font-bold text-slate-900 dark:text-white mb-2">🔐 Encryption</h3>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    TLS/SSL encryption for all data in transit and AES-256 for data at rest
                  </p>
                </div>
                <div className="bg-white dark:bg-slate-800 p-4 rounded-lg border border-slate-200 dark:border-slate-700">
                  <h3 className="font-bold text-slate-900 dark:text-white mb-2">🔑 Access Control</h3>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    Role-based access with multi-factor authentication for sensitive operations
                  </p>
                </div>
                <div className="bg-white dark:bg-slate-800 p-4 rounded-lg border border-slate-200 dark:border-slate-700">
                  <h3 className="font-bold text-slate-900 dark:text-white mb-2">🛡️ Monitoring</h3>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    24/7 security monitoring and intrusion detection systems
                  </p>
                </div>
                <div className="bg-white dark:bg-slate-800 p-4 rounded-lg border border-slate-200 dark:border-slate-700">
                  <h3 className="font-bold text-slate-900 dark:text-white mb-2">📋 Audits</h3>
                  <p className="text-sm text-slate-700 dark:text-slate-300">
                    Regular security audits and vulnerability assessments
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Section 8.0 - Contact Us */}
          <section id="section-8" className="scroll-mt-20">
            <div className="bg-indigo-50 dark:bg-indigo-900/20 border-l-4 border-indigo-500 p-6 rounded-r-lg">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                <Mail className="h-6 w-6 text-indigo-600" />
                8.0 Contact Us
              </h2>
              <p className="text-slate-700 dark:text-slate-300 mb-4">
                If you have any questions about this Privacy Policy or wish to exercise your data protection rights, please contact us:
              </p>
              <div className="bg-white dark:bg-slate-800 rounded-lg p-6 border border-indigo-200 dark:border-indigo-700">
                <h3 className="font-bold text-slate-900 dark:text-white mb-3">BidVex Data Protection Officer</h3>
                <div className="space-y-2 text-slate-700 dark:text-slate-300">
                  <p><strong>Email:</strong> <a href="mailto:privacy@bidvex.com" className="text-blue-600 dark:text-blue-400 hover:underline">privacy@bidvex.com</a></p>
                  <p><strong>Mailing Address:</strong></p>
                  <p className="ml-4">
                    BidVex Legal Department<br />
                    123 Auction Street<br />
                    Montreal, Quebec, Canada<br />
                    H3B 2Y5
                  </p>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* Footer Note */}
        <div className="mt-12 pt-6 border-t-2 border-slate-200 dark:border-slate-700 text-center">
          <p className="text-sm text-slate-600 dark:text-slate-400">
            © 2026 BidVex. All rights reserved.
          </p>
        </div>
      </div>
    </div>
  );
};

export default PrivacyPolicyPage;