import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { 
  Mail, Users, Send, Upload, Eye, CreditCard, BarChart3, 
  FileText, Crown, Zap, Check, ArrowRight, Sparkles, 
  TrendingUp, MousePointer, AlertCircle, Copy, Calculator,
  Gift, Percent, Star, ChevronRight, Shield
} from 'lucide-react';

const EmailMarketingPricing = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [selectedTier, setSelectedTier] = useState('premium');

  // Pricing data
  const pricingTiers = {
    free: {
      name: 'Free',
      color: 'slate',
      gradient: 'from-slate-500 to-slate-600',
      pricePerEmail: 0.015,
      monthlyEmails: 0,
      dailyLimit: 0,
      contacts: 50,
      freeCampaigns: 0,
      features: [
        'Store up to 50 contacts',
        'Preview campaign builder',
        'Basic templates access'
      ],
      limitations: [
        'Cannot send emails',
        'No analytics access'
      ]
    },
    premium: {
      name: 'Premium',
      color: 'blue',
      gradient: 'from-blue-500 to-cyan-500',
      pricePerEmail: 0.008,
      monthlyEmails: 5000,
      dailyLimit: 500,
      contacts: 5000,
      freeCampaigns: 3,
      features: [
        '5,000 emails/month included',
        '500 emails/day limit',
        '5,000 contacts storage',
        '3 free campaigns/month',
        'All 5 premium templates',
        'Open & click analytics',
        '47% savings vs pay-as-you-go'
      ],
      limitations: []
    },
    vip: {
      name: 'VIP',
      color: 'purple',
      gradient: 'from-purple-500 to-pink-500',
      pricePerEmail: 0.005,
      monthlyEmails: 50000,
      dailyLimit: 2000,
      contacts: 25000,
      freeCampaigns: 10,
      features: [
        '50,000 emails/month included',
        '2,000 emails/day limit',
        '25,000 contacts storage',
        '10 free campaigns/month',
        'All templates + custom branding',
        'Advanced analytics dashboard',
        'Priority sending queue',
        '67% savings vs pay-as-you-go'
      ],
      limitations: []
    }
  };

  // Flow steps
  const flowSteps = [
    {
      step: 1,
      title: 'Dashboard',
      subtitle: 'Your Marketing Hub',
      icon: BarChart3,
      color: 'blue',
      description: 'View your credits, free campaigns remaining, and past campaign performance at a glance.',
      details: ['Available credits', 'Free campaigns left', 'Recent campaigns']
    },
    {
      step: 2,
      title: 'Create Campaign',
      subtitle: 'Build Your Message',
      icon: Upload,
      color: 'green',
      description: 'Upload your contact list or select from existing contacts. Choose from 5 professional templates.',
      details: ['Upload CSV or add manually', 'Select template', 'Customize content']
    },
    {
      step: 3,
      title: 'Cost Calculation',
      subtitle: 'Transparent Pricing',
      icon: Calculator,
      color: 'amber',
      description: 'See exactly what you\'ll pay. Your tier discounts and free campaigns are automatically applied.',
      details: ['Email count × price', 'Tier discount applied', 'Free campaign check']
    },
    {
      step: 4,
      title: 'Preview & Confirm',
      subtitle: 'Review Everything',
      icon: Eye,
      color: 'cyan',
      description: 'Preview your email, verify recipient count, and confirm the final cost before sending.',
      details: ['Email preview', 'Total recipients', 'Final cost summary']
    },
    {
      step: 5,
      title: 'Payment',
      subtitle: 'Secure Checkout',
      icon: CreditCard,
      color: 'indigo',
      description: 'Pay securely via Stripe or use stored payment method. Free campaigns skip this step!',
      details: ['Stripe checkout', 'Saved cards', 'Free campaign bypass']
    },
    {
      step: 6,
      title: 'Campaign Sent',
      subtitle: 'Watch It Fly',
      icon: Send,
      color: 'emerald',
      description: 'Track your campaign in real-time. See opens, clicks, and bounces as they happen.',
      details: ['Live delivery status', 'Open tracking', 'Click analytics']
    },
    {
      step: 7,
      title: 'Summary',
      subtitle: 'Campaign Complete',
      icon: FileText,
      color: 'purple',
      description: 'Review full analytics, check remaining credits, and duplicate successful campaigns.',
      details: ['Performance report', 'Credits remaining', 'Duplicate option']
    }
  ];

  // Cost calculator example
  const calculateCost = (emails, tier) => {
    const tierData = pricingTiers[tier];
    if (emails <= tierData.monthlyEmails) {
      return { cost: 0, savings: emails * pricingTiers.free.pricePerEmail, isFree: true };
    }
    const extraEmails = emails - tierData.monthlyEmails;
    const cost = extraEmails * tierData.pricePerEmail;
    const baseCost = emails * pricingTiers.free.pricePerEmail;
    return { cost, savings: baseCost - cost, isFree: false };
  };

  const exampleCampaign = calculateCost(2500, selectedTier);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-purple-50/30 dark:from-slate-950 dark:via-blue-950/20 dark:to-purple-950/20">
      {/* Hero Section */}
      <section className="relative overflow-hidden py-16 md:py-24">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-600/10 to-purple-600/10 dark:from-blue-600/5 dark:to-purple-600/5" />
        <div className="absolute top-20 left-10 w-72 h-72 bg-blue-400/20 rounded-full blur-3xl" />
        <div className="absolute bottom-10 right-10 w-96 h-96 bg-purple-400/20 rounded-full blur-3xl" />
        
        <div className="container mx-auto px-4 relative z-10">
          <div className="text-center max-w-4xl mx-auto">
            <Badge className="mb-4 bg-gradient-to-r from-blue-500 to-purple-500 text-white border-0">
              <Sparkles className="h-3 w-3 mr-1" />
              Client Email Marketing
            </Badge>
            
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 bg-gradient-to-r from-slate-900 via-blue-800 to-purple-800 dark:from-white dark:via-blue-200 dark:to-purple-200 bg-clip-text text-transparent">
              Turn Your Buyer List Into Revenue
            </h1>
            
            <p className="text-lg md:text-xl text-slate-600 dark:text-slate-300 mb-8 max-w-2xl mx-auto">
              Simple, transparent pricing. Send auction announcements, ending soon reminders, 
              and exclusive previews to your clients. Pay only for what you use.
            </p>
            
            <div className="flex flex-wrap justify-center gap-4">
              <Button 
                size="lg" 
                className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white gap-2"
                onClick={() => navigate('/client-marketing')}
              >
                <Mail className="h-5 w-5" />
                Start Sending
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button size="lg" variant="outline" className="gap-2" onClick={() => navigate('/pricing')}>
                <Crown className="h-5 w-5" />
                View Plans
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Tiers */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Simple, Transparent Pricing</h2>
            <p className="text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
              Choose your plan. Premium and VIP users get included emails, free campaigns, and lower rates.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 lg:gap-8">
            {Object.entries(pricingTiers).map(([key, tier]) => (
              <Card 
                key={key}
                className={`relative overflow-hidden transition-all duration-300 cursor-pointer
                  ${selectedTier === key ? 'ring-2 ring-offset-2 scale-105' : 'hover:scale-102'}
                  ${key === 'premium' ? 'ring-blue-500' : key === 'vip' ? 'ring-purple-500' : 'ring-slate-300'}
                `}
                onClick={() => setSelectedTier(key)}
              >
                {key === 'premium' && (
                  <div className="absolute top-0 right-0 bg-gradient-to-r from-blue-500 to-cyan-500 text-white text-xs font-bold px-3 py-1 rounded-bl-lg">
                    POPULAR
                  </div>
                )}
                {key === 'vip' && (
                  <div className="absolute top-0 right-0 bg-gradient-to-r from-purple-500 to-pink-500 text-white text-xs font-bold px-3 py-1 rounded-bl-lg">
                    BEST VALUE
                  </div>
                )}
                
                <CardHeader className="pb-4">
                  <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium mb-3 w-fit
                    ${key === 'free' ? 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300' : ''}
                    ${key === 'premium' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300' : ''}
                    ${key === 'vip' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300' : ''}
                  `}>
                    {key === 'vip' && <Crown className="h-4 w-4" />}
                    {key === 'premium' && <Zap className="h-4 w-4" />}
                    {tier.name}
                  </div>
                  
                  <div className="space-y-1">
                    <div className="flex items-baseline gap-1">
                      <span className="text-4xl font-bold">${tier.pricePerEmail.toFixed(3)}</span>
                      <span className="text-slate-500">/email</span>
                    </div>
                    {tier.monthlyEmails > 0 && (
                      <p className="text-sm text-emerald-600 dark:text-emerald-400 font-medium">
                        + {tier.monthlyEmails.toLocaleString()} emails included
                      </p>
                    )}
                  </div>
                </CardHeader>
                
                <CardContent className="space-y-4">
                  {/* Key Stats */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold">{tier.dailyLimit || '—'}</p>
                      <p className="text-xs text-slate-500">Daily Limit</p>
                    </div>
                    <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold">{tier.freeCampaigns || '—'}</p>
                      <p className="text-xs text-slate-500">Free/Month</p>
                    </div>
                  </div>
                  
                  {/* Features */}
                  <ul className="space-y-2">
                    {tier.features.map((feature, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <Check className={`h-4 w-4 mt-0.5 flex-shrink-0
                          ${key === 'premium' ? 'text-blue-500' : key === 'vip' ? 'text-purple-500' : 'text-slate-400'}
                        `} />
                        <span>{feature}</span>
                      </li>
                    ))}
                    {tier.limitations.map((limit, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-slate-400">
                        <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                        <span>{limit}</span>
                      </li>
                    ))}
                  </ul>
                  
                  {key !== 'free' && (
                    <Button 
                      className={`w-full ${key === 'premium' ? 'bg-blue-600 hover:bg-blue-700' : 'bg-purple-600 hover:bg-purple-700'} text-white`}
                      onClick={(e) => { e.stopPropagation(); navigate('/pricing'); }}
                    >
                      Upgrade to {tier.name}
                    </Button>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Cost Calculator */}
      <section className="py-16 px-4 bg-white/50 dark:bg-slate-900/50">
        <div className="container mx-auto max-w-4xl">
          <div className="text-center mb-10">
            <h2 className="text-3xl font-bold mb-3">See Your Savings</h2>
            <p className="text-slate-600 dark:text-slate-400">
              Example: Sending 2,500 emails to your client list
            </p>
          </div>
          
          <div className="grid md:grid-cols-3 gap-6">
            {Object.entries(pricingTiers).map(([key, tier]) => {
              const calc = calculateCost(2500, key);
              return (
                <Card key={key} className={`text-center ${selectedTier === key ? 'ring-2 ring-blue-500' : ''}`}>
                  <CardContent className="pt-6">
                    <Badge className={`mb-4 ${key === 'vip' ? 'bg-purple-500' : key === 'premium' ? 'bg-blue-500' : 'bg-slate-500'}`}>
                      {tier.name}
                    </Badge>
                    
                    <div className="space-y-3">
                      <div>
                        <p className="text-4xl font-bold">
                          {calc.isFree ? (
                            <span className="text-emerald-500">FREE</span>
                          ) : (
                            <span>${calc.cost.toFixed(2)}</span>
                          )}
                        </p>
                        <p className="text-sm text-slate-500">for 2,500 emails</p>
                      </div>
                      
                      {calc.savings > 0 && !calc.isFree && (
                        <div className="flex items-center justify-center gap-1 text-emerald-600 dark:text-emerald-400">
                          <TrendingUp className="h-4 w-4" />
                          <span className="text-sm font-medium">Save ${calc.savings.toFixed(2)}</span>
                        </div>
                      )}
                      
                      {calc.isFree && (
                        <div className="flex items-center justify-center gap-1 text-emerald-600">
                          <Gift className="h-4 w-4" />
                          <span className="text-sm font-medium">Included in plan!</span>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* User Flow */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">How It Works</h2>
            <p className="text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
              From dashboard to delivery — a seamless experience in 7 simple steps
            </p>
          </div>

          {/* Desktop Flow - Horizontal with Connections */}
          <div className="hidden lg:block">
            <div className="relative">
              {/* Connection Line */}
              <div className="absolute top-12 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-200 via-purple-200 to-emerald-200 dark:from-blue-800 dark:via-purple-800 dark:to-emerald-800" />
              
              <div className="grid grid-cols-7 gap-4 relative">
                {flowSteps.map((step, index) => {
                  const IconComponent = step.icon;
                  const colorClasses = {
                    blue: 'bg-blue-500 text-white',
                    green: 'bg-emerald-500 text-white',
                    amber: 'bg-amber-500 text-white',
                    cyan: 'bg-cyan-500 text-white',
                    indigo: 'bg-indigo-500 text-white',
                    emerald: 'bg-emerald-500 text-white',
                    purple: 'bg-purple-500 text-white'
                  };
                  
                  return (
                    <div key={step.step} className="flex flex-col items-center text-center group">
                      {/* Step Number & Icon */}
                      <div className={`relative z-10 w-24 h-24 rounded-2xl ${colorClasses[step.color]} 
                        flex flex-col items-center justify-center shadow-lg transition-transform group-hover:scale-110 group-hover:shadow-xl`}
                      >
                        <IconComponent className="h-8 w-8 mb-1" />
                        <span className="text-xs font-bold opacity-80">Step {step.step}</span>
                      </div>
                      
                      {/* Arrow (except last) */}
                      {index < flowSteps.length - 1 && (
                        <div className="absolute top-12 -right-2 z-20">
                          <ChevronRight className="h-5 w-5 text-slate-300 dark:text-slate-600" />
                        </div>
                      )}
                      
                      {/* Content */}
                      <div className="mt-4">
                        <h3 className="font-bold text-sm">{step.title}</h3>
                        <p className="text-xs text-slate-500 mt-1">{step.subtitle}</p>
                      </div>
                      
                      {/* Hover Details */}
                      <div className="mt-3 space-y-1 opacity-60 group-hover:opacity-100 transition-opacity">
                        {step.details.map((detail, i) => (
                          <p key={i} className="text-xs text-slate-500 flex items-center gap-1">
                            <span className="w-1 h-1 rounded-full bg-slate-400" />
                            {detail}
                          </p>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Mobile Flow - Vertical Cards */}
          <div className="lg:hidden space-y-4">
            {flowSteps.map((step, index) => {
              const IconComponent = step.icon;
              const colorClasses = {
                blue: 'from-blue-500 to-blue-600',
                green: 'from-emerald-500 to-emerald-600',
                amber: 'from-amber-500 to-amber-600',
                cyan: 'from-cyan-500 to-cyan-600',
                indigo: 'from-indigo-500 to-indigo-600',
                emerald: 'from-emerald-500 to-emerald-600',
                purple: 'from-purple-500 to-purple-600'
              };
              
              return (
                <Card key={step.step} className="overflow-hidden">
                  <CardContent className="p-0">
                    <div className="flex gap-4">
                      {/* Icon Side */}
                      <div className={`w-20 bg-gradient-to-br ${colorClasses[step.color]} flex flex-col items-center justify-center p-4 text-white`}>
                        <IconComponent className="h-8 w-8 mb-1" />
                        <span className="text-xs font-bold opacity-80">Step {step.step}</span>
                      </div>
                      
                      {/* Content Side */}
                      <div className="flex-1 py-4 pr-4">
                        <h3 className="font-bold">{step.title}</h3>
                        <p className="text-sm text-slate-500 mb-2">{step.subtitle}</p>
                        <p className="text-sm text-slate-600 dark:text-slate-400">{step.description}</p>
                        
                        <div className="flex flex-wrap gap-2 mt-3">
                          {step.details.map((detail, i) => (
                            <Badge key={i} variant="secondary" className="text-xs">
                              {detail}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                    
                    {/* Arrow to next step */}
                    {index < flowSteps.length - 1 && (
                      <div className="flex justify-center py-2 bg-slate-50 dark:bg-slate-800/50">
                        <ArrowRight className="h-4 w-4 text-slate-400 rotate-90" />
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* Analytics Preview */}
      <section className="py-16 px-4 bg-gradient-to-br from-slate-900 to-slate-800 text-white">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-12">
            <Badge className="mb-4 bg-emerald-500">Real-Time Analytics</Badge>
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Track Every Click, Every Open</h2>
            <p className="text-slate-300 max-w-2xl mx-auto">
              Know exactly how your campaigns perform with detailed analytics
            </p>
          </div>
          
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {[
              { icon: Send, label: 'Delivered', value: '2,487', subtext: '99.5% rate', color: 'emerald' },
              { icon: Eye, label: 'Opened', value: '1,245', subtext: '50.1% rate', color: 'blue' },
              { icon: MousePointer, label: 'Clicked', value: '312', subtext: '12.5% rate', color: 'purple' },
              { icon: AlertCircle, label: 'Bounced', value: '13', subtext: '0.5% rate', color: 'amber' }
            ].map((stat, i) => (
              <div key={i} className="bg-white/10 backdrop-blur rounded-xl p-6 text-center">
                <stat.icon className={`h-8 w-8 mx-auto mb-3 text-${stat.color}-400`} />
                <p className="text-3xl font-bold">{stat.value}</p>
                <p className="text-sm text-slate-400">{stat.label}</p>
                <Badge variant="secondary" className="mt-2 bg-white/10 text-white">
                  {stat.subtext}
                </Badge>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Templates Preview */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">5 Professional Templates</h2>
            <p className="text-slate-600 dark:text-slate-400">
              Ready-to-use templates designed for auction announcements
            </p>
          </div>
          
          <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {[
              { name: 'New Auction', color: 'from-blue-500 to-cyan-500', icon: '🔔' },
              { name: 'Ending Soon', color: 'from-red-500 to-orange-500', icon: '⏰' },
              { name: 'New Inventory', color: 'from-emerald-500 to-teal-500', icon: '📦' },
              { name: 'VIP Preview', color: 'from-purple-500 to-pink-500', icon: '👑' },
              { name: 'Price Drop', color: 'from-amber-500 to-yellow-500', icon: '💰' }
            ].map((template, i) => (
              <Card key={i} className="overflow-hidden group cursor-pointer hover:shadow-lg transition-all">
                <div className={`h-24 bg-gradient-to-br ${template.color} flex items-center justify-center text-4xl`}>
                  {template.icon}
                </div>
                <CardContent className="p-3 text-center">
                  <p className="font-medium text-sm">{template.name}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-3xl">
          <Card className="overflow-hidden bg-gradient-to-br from-blue-600 to-purple-600 text-white border-0">
            <CardContent className="p-8 md:p-12 text-center">
              <Shield className="h-12 w-12 mx-auto mb-4 opacity-80" />
              <h2 className="text-2xl md:text-3xl font-bold mb-4">
                Ready to Reach Your Clients?
              </h2>
              <p className="text-blue-100 mb-8 max-w-xl mx-auto">
                Start with our free tier to build your contact list, or upgrade to Premium/VIP 
                for included emails and lower rates.
              </p>
              
              <div className="flex flex-wrap justify-center gap-4">
                <Button 
                  size="lg" 
                  className="bg-white text-blue-600 hover:bg-blue-50 gap-2"
                  onClick={() => navigate('/client-marketing')}
                >
                  <Mail className="h-5 w-5" />
                  Go to Marketing Dashboard
                </Button>
                <Button 
                  size="lg" 
                  variant="outline" 
                  className="border-white/30 text-white hover:bg-white/10 gap-2"
                  onClick={() => navigate('/pricing')}
                >
                  <Crown className="h-5 w-5" />
                  Compare Plans
                </Button>
              </div>
              
              <div className="flex justify-center gap-6 mt-8 text-sm text-blue-100">
                <span className="flex items-center gap-1">
                  <Check className="h-4 w-4" /> No setup fees
                </span>
                <span className="flex items-center gap-1">
                  <Check className="h-4 w-4" /> Cancel anytime
                </span>
                <span className="flex items-center gap-1">
                  <Check className="h-4 w-4" /> GDPR compliant
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* FAQ Quick */}
      <section className="py-16 px-4 bg-slate-50 dark:bg-slate-900/50">
        <div className="container mx-auto max-w-3xl">
          <h2 className="text-2xl font-bold text-center mb-8">Quick Answers</h2>
          
          <div className="space-y-4">
            {[
              { q: 'What happens if I exceed my monthly limit?', a: 'You\'ll be charged the per-email rate for your tier. Premium users pay $0.008/email, VIP users pay $0.005/email for extra emails.' },
              { q: 'Can I upgrade mid-month?', a: 'Yes! Your new tier benefits apply immediately, and you\'ll get the prorated included emails for the remainder of the month.' },
              { q: 'What counts as a "free campaign"?', a: 'Free campaigns are full campaigns sent within your included email limit. Premium gets 3/month, VIP gets 10/month.' },
              { q: 'Are contacts shared with BidVex?', a: 'No. Your contacts are private to your account. We never share, sell, or use your contact lists.' }
            ].map((faq, i) => (
              <Card key={i}>
                <CardContent className="p-4">
                  <p className="font-medium mb-2">{faq.q}</p>
                  <p className="text-sm text-slate-600 dark:text-slate-400">{faq.a}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};

export default EmailMarketingPricing;
