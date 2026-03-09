import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { 
  Shield, Mail, MapPin, Lock, Eye, Users, Building2,
  CreditCard, Database, Cookie, Cpu, Clock, CheckCircle,
  FileText, Globe, UserCheck, Server, AlertTriangle
} from 'lucide-react';

const PrivacyPolicyPage = () => {
  return (
    <div className="min-h-screen py-12 px-4 max-w-4xl mx-auto">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3 mb-4">
            <Shield className="h-8 w-8 text-primary" />
            <CardTitle className="text-3xl">BidVex Privacy Policy</CardTitle>
          </div>
          <p className="text-muted-foreground">Last Updated: March 2026</p>
        </CardHeader>
        <CardContent className="prose prose-sm max-w-none space-y-8">
          
          {/* Table of Contents */}
          <section className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Table of Contents</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <ol className="list-decimal pl-6 space-y-1 text-blue-600 dark:text-blue-400">
                <li><a href="#introduction" className="hover:underline">Introduction</a></li>
                <li><a href="#information-collect" className="hover:underline">Information We Collect</a></li>
                <li><a href="#purpose" className="hover:underline">Purpose of Processing</a></li>
                <li><a href="#sharing" className="hover:underline">Information Sharing & Disclosure</a></li>
                <li><a href="#cookies" className="hover:underline">Cookies & Tracking</a></li>
              </ol>
              <ol className="list-decimal pl-6 space-y-1 text-blue-600 dark:text-blue-400" start={6}>
                <li><a href="#ai" className="hover:underline">AI-Powered Recommendation Engine</a></li>
                <li><a href="#security" className="hover:underline">Data Security</a></li>
                <li><a href="#rights" className="hover:underline">Your Privacy Rights</a></li>
                <li><a href="#retention" className="hover:underline">Data Retention</a></li>
                <li><a href="#contact" className="hover:underline">Contact Us</a></li>
              </ol>
            </div>
          </section>

          {/* 1. Introduction */}
          <section id="introduction">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">1</span>
              Introduction
            </h2>
            <p className="mb-4">
              At BidVex Inc. ("BidVex," "we," "us," or "our"), we are committed to protecting the privacy and security of your personal information. This Privacy Policy explains how we collect, use, disclose, and safeguard your data when you use our online auction platform ("the Platform").
            </p>
            <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
              <p className="text-blue-800 dark:text-blue-200 text-sm">
                <strong>Compliance:</strong> This policy is designed to comply with the <strong>Act respecting the protection of personal information in the private sector (Quebec Law 25)</strong>, the <strong>Personal Information Protection and Electronic Documents Act (PIPEDA)</strong>, and the <strong>General Data Protection Regulation (GDPR)</strong>.
              </p>
            </div>
          </section>

          {/* 2. Information We Collect */}
          <section id="information-collect">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">2</span>
              <Database className="h-5 w-5" /> Information We Collect
            </h2>
            <p className="mb-4">To provide a secure and efficient auction environment, we collect the following categories of data:</p>
            
            <div className="space-y-4">
              {/* Sellers */}
              <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-lg p-5">
                <h3 className="text-lg font-semibold text-emerald-800 dark:text-emerald-200 mb-3 flex items-center gap-2">
                  <Building2 className="h-5 w-5" /> 2.1 Sellers (including Vehicle & Equipment sections)
                </h3>
                <div className="space-y-3 text-emerald-700 dark:text-emerald-300">
                  <div className="flex items-start gap-2">
                    <UserCheck className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Identity & Verification Data:</strong> Full name, date of birth, and government-issued ID (for identity verification and fraud prevention).</p>
                  </div>
                  <div className="flex items-start gap-2">
                    <Mail className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Contact Data:</strong> Email address, telephone number, and physical business/residential address.</p>
                  </div>
                  <div className="flex items-start gap-2">
                    <Building2 className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Business Data:</strong> Business name, tax ID numbers, and dealer licenses (where applicable).</p>
                  </div>
                  <div className="flex items-start gap-2">
                    <FileText className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Asset Data:</strong> VINs, vehicle/equipment history reports, make, model, year, photos, and related ownership documentation.</p>
                  </div>
                  <div className="flex items-start gap-2">
                    <CreditCard className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Financial Data:</strong> Banking details and settlement information for payouts.</p>
                  </div>
                </div>
              </div>

              {/* Buyers */}
              <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-5">
                <h3 className="text-lg font-semibold text-blue-800 dark:text-blue-200 mb-3 flex items-center gap-2">
                  <Users className="h-5 w-5" /> 2.2 Buyers
                </h3>
                <div className="space-y-3 text-blue-700 dark:text-blue-300">
                  <div className="flex items-start gap-2">
                    <UserCheck className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Identity Data:</strong> Full name and username.</p>
                  </div>
                  <div className="flex items-start gap-2">
                    <Mail className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Contact Data:</strong> Email address, telephone number, and billing/shipping address.</p>
                  </div>
                  <div className="flex items-start gap-2">
                    <CreditCard className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Payment Data:</strong> Credit card and payment method details. <em>Note: All payment data is processed securely via Stripe; BidVex does not store full credit card numbers.</em></p>
                  </div>
                  <div className="flex items-start gap-2">
                    <FileText className="h-4 w-4 mt-1 flex-shrink-0" />
                    <p><strong>Transaction Data:</strong> Bidding history, watchlist items, and records of won auctions.</p>
                  </div>
                </div>
              </div>

              {/* Technical Data */}
              <div className="bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-5">
                <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-200 mb-3 flex items-center gap-2">
                  <Server className="h-5 w-5" /> 2.3 Technical Data (All Users)
                </h3>
                <p className="text-slate-600 dark:text-slate-400">
                  IP address, browser type and version, time zone setting, device identifiers, and operating system information for security monitoring and platform optimization.
                </p>
              </div>
            </div>
          </section>

          {/* 3. Purpose of Processing */}
          <section id="purpose">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">3</span>
              Purpose of Processing
            </h2>
            <p className="mb-4">We process your personal data based on the following legal grounds:</p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <CheckCircle className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold">Contractual Necessity</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">To facilitate bidding, buying, and selling transactions.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <Shield className="h-5 w-5 text-blue-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold">Identity Verification</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">To maintain a high-trust marketplace and prevent fraud.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <Mail className="h-5 w-5 text-purple-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold">Communication</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">To enable secure messaging between buyers and sellers.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <CreditCard className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold">Payment Processing</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">To securely handle transaction fees via Stripe.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <Cpu className="h-5 w-5 text-amber-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold">Improvement</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">To analyze usage patterns and optimize recommendations.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <FileText className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
                <div>
                  <h4 className="font-semibold">Legal Compliance</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">To satisfy tax, accounting, and AML obligations.</p>
                </div>
              </div>
            </div>
          </section>

          {/* 4. Information Sharing */}
          <section id="sharing">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">4</span>
              Information Sharing & Disclosure
            </h2>
            
            <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-4">
              <p className="text-red-800 dark:text-red-200 font-semibold flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                We do not sell your personal data to third parties.
              </p>
            </div>
            
            <p className="mb-3">Disclosure occurs only in the following contexts:</p>
            
            <div className="space-y-3">
              <div className="border-l-4 border-blue-500 pl-4 py-2">
                <h4 className="font-semibold">Transaction Completion</h4>
                <p className="text-sm text-slate-600 dark:text-slate-400">Upon the conclusion of a successful auction, the winning buyer and the seller receive each other's contact information to finalize logistics.</p>
              </div>
              <div className="border-l-4 border-blue-500 pl-4 py-2">
                <h4 className="font-semibold">Public Profile</h4>
                <p className="text-sm text-slate-600 dark:text-slate-400">Trust indicators, verified badges, and user ratings are displayed publicly to maintain community transparency.</p>
              </div>
              <div className="border-l-4 border-blue-500 pl-4 py-2">
                <h4 className="font-semibold">Service Providers</h4>
                <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">We share data with trusted partners strictly for operational purposes:</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <div className="bg-white dark:bg-slate-800 rounded px-3 py-2 text-center text-xs">
                    <p className="font-semibold">Stripe</p>
                    <p className="text-slate-500">Payments</p>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded px-3 py-2 text-center text-xs">
                    <p className="font-semibold">SendGrid</p>
                    <p className="text-slate-500">Email</p>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded px-3 py-2 text-center text-xs">
                    <p className="font-semibold">Twilio</p>
                    <p className="text-slate-500">SMS</p>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded px-3 py-2 text-center text-xs">
                    <p className="font-semibold">AWS/GCP</p>
                    <p className="text-slate-500">Hosting</p>
                  </div>
                </div>
              </div>
              <div className="border-l-4 border-blue-500 pl-4 py-2">
                <h4 className="font-semibold">Legal Authorities</h4>
                <p className="text-sm text-slate-600 dark:text-slate-400">We may disclose data if required by law, court order, or to protect the rights and safety of our users.</p>
              </div>
            </div>
          </section>

          {/* 5. Cookies */}
          <section id="cookies">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">5</span>
              <Cookie className="h-5 w-5" /> Cookies & Tracking
            </h2>
            <p className="mb-4">We use cookies to enhance your experience and analyze traffic.</p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4">
                <h4 className="font-semibold text-green-800 dark:text-green-200 mb-1">Essential Cookies</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Required for core platform functionality (e.g., staying logged in).</p>
              </div>
              <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <h4 className="font-semibold text-blue-800 dark:text-blue-200 mb-1">Analytics Cookies</h4>
                <p className="text-sm text-blue-700 dark:text-blue-300">Help us understand how users interact with the site.</p>
              </div>
              <div className="bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800 rounded-lg p-4">
                <h4 className="font-semibold text-purple-800 dark:text-purple-200 mb-1">Personalization Cookies</h4>
                <p className="text-sm text-purple-700 dark:text-purple-300">Remember your preferences, such as language (English/French).</p>
              </div>
              <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                <h4 className="font-semibold text-amber-800 dark:text-amber-200 mb-1">Marketing Cookies</h4>
                <p className="text-sm text-amber-700 dark:text-amber-300">Used to deliver relevant advertisements. Opt-out available via Google Ads Settings.</p>
              </div>
            </div>
          </section>

          {/* 6. AI */}
          <section id="ai">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-purple-100 dark:bg-purple-900 rounded-full flex items-center justify-center text-purple-600 text-sm font-bold">6</span>
              <Cpu className="h-5 w-5 text-purple-600" /> AI-Powered Recommendation Engine
            </h2>
            
            <div className="bg-purple-50 dark:bg-purple-950/30 border border-purple-200 dark:border-purple-800 rounded-lg p-5">
              <p className="text-purple-800 dark:text-purple-200 mb-3">
                BidVex utilizes a proprietary recommendation engine to suggest items based on:
              </p>
              <ul className="list-disc pl-6 space-y-1 text-purple-700 dark:text-purple-300 mb-4">
                <li>Your browsing and search history</li>
                <li>Past bidding and purchase patterns</li>
                <li>Items added to your "Watchlist"</li>
              </ul>
              <div className="bg-white dark:bg-slate-800 rounded-lg p-3 border border-purple-200 dark:border-purple-700">
                <p className="text-sm flex items-center gap-2">
                  <Eye className="h-4 w-4 text-purple-600" />
                  <span><strong>Opt-Out:</strong> Users may disable personalized recommendations in their Account Settings. This will not affect core bidding or platform functionality.</span>
                </p>
              </div>
            </div>
          </section>

          {/* 7. Security */}
          <section id="security">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center text-green-600 text-sm font-bold">7</span>
              <Lock className="h-5 w-5 text-green-600" /> Data Security
            </h2>
            <p className="mb-4">We implement industry-leading security measures to protect your data:</p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-center">
                <Lock className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <h4 className="font-semibold text-green-800 dark:text-green-200">TLS/SSL</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Encryption in Transit</p>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-center">
                <Shield className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <h4 className="font-semibold text-green-800 dark:text-green-200">AES-256</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Encryption at Rest</p>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-center">
                <CreditCard className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <h4 className="font-semibold text-green-800 dark:text-green-200">PCI-DSS</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Payment Compliance</p>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-center">
                <UserCheck className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <h4 className="font-semibold text-green-800 dark:text-green-200">MFA</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Multi-Factor Auth</p>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-center">
                <Users className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <h4 className="font-semibold text-green-800 dark:text-green-200">Role-Based</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Access Control</p>
              </div>
              <div className="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg p-4 text-center">
                <Eye className="h-8 w-8 text-green-600 mx-auto mb-2" />
                <h4 className="font-semibold text-green-800 dark:text-green-200">24/7</h4>
                <p className="text-sm text-green-700 dark:text-green-300">Security Monitoring</p>
              </div>
            </div>
          </section>

          {/* 8. Rights */}
          <section id="rights">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">8</span>
              <Globe className="h-5 w-5" /> Your Privacy Rights
            </h2>
            <p className="mb-4">Depending on your jurisdiction (Quebec, Canada, or EU), you have the following rights:</p>
            
            <div className="space-y-3">
              <div className="flex items-start gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <Eye className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Access</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">The right to request a copy of the personal data we hold about you.</p>
                </div>
              </div>
              <div className="flex items-start gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-10 h-10 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <FileText className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Correction</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">The right to fix inaccurate or incomplete information.</p>
                </div>
              </div>
              <div className="flex items-start gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-10 h-10 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <AlertTriangle className="h-5 w-5 text-red-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Deletion (Right to be Forgotten)</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">The right to request the removal of your data, subject to legal retention requirements.</p>
                </div>
              </div>
              <div className="flex items-start gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <Database className="h-5 w-5 text-purple-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Portability</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">The right to receive your data in a structured, machine-readable format.</p>
                </div>
              </div>
              <div className="flex items-start gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-10 h-10 bg-amber-100 dark:bg-amber-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <Lock className="h-5 w-5 text-amber-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Withdrawal of Consent</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">The right to stop processing for specific purposes (e.g., marketing).</p>
                </div>
              </div>
            </div>
            
            <div className="mt-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
              <p className="text-blue-800 dark:text-blue-200 text-sm">
                <strong>To exercise these rights,</strong> please contact our Data Protection Officer at <a href="mailto:support@bidvex.com" className="underline">support@bidvex.com</a>.
              </p>
            </div>
          </section>

          {/* 9. Retention */}
          <section id="retention">
            <h2 className="text-2xl font-semibold mb-3 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">9</span>
              <Clock className="h-5 w-5" /> Data Retention
            </h2>
            
            <div className="space-y-3">
              <div className="flex items-center gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-2xl font-bold text-blue-600">7</span>
                </div>
                <div>
                  <h4 className="font-semibold">Account Data</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Retained for the duration of your active account and up to 7 years after closure.</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-2xl font-bold text-green-600">7</span>
                </div>
                <div>
                  <h4 className="font-semibold">Transaction Records</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Retained for 7 years to comply with Canadian and Quebec tax and legal obligations.</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 bg-slate-50 dark:bg-slate-800/50 rounded-lg">
                <div className="w-16 h-16 bg-amber-100 dark:bg-amber-900 rounded-lg flex items-center justify-center flex-shrink-0">
                  <CheckCircle className="h-8 w-8 text-amber-600" />
                </div>
                <div>
                  <h4 className="font-semibold">Identification Documents</h4>
                  <p className="text-sm text-slate-600 dark:text-slate-400">Deleted once verification is successfully completed, unless otherwise required for ongoing fraud prevention.</p>
                </div>
              </div>
            </div>
          </section>

          {/* 10. Contact */}
          <section id="contact" className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-6">
            <h2 className="text-2xl font-semibold mb-4 flex items-center gap-2">
              <span className="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center text-blue-600 text-sm font-bold">10</span>
              Contact Us
            </h2>
            <p className="mb-4">For questions regarding this policy or our data practices, please contact:</p>
            
            <div className="bg-white dark:bg-slate-900 rounded-lg p-5 border border-slate-200 dark:border-slate-700">
              <p className="font-semibold text-lg mb-4">BidVex Data Protection Officer</p>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                    <Mail className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Email</p>
                    <a href="mailto:support@bidvex.com" className="font-medium text-blue-600 hover:underline">support@bidvex.com</a>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center flex-shrink-0">
                    <MapPin className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Mailing Address</p>
                    <p className="font-medium">
                      761 Chalifoux Street<br />
                      Sherbrooke, Quebec, Canada<br />
                      J1G 0A8
                    </p>
                  </div>
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

export default PrivacyPolicyPage;
