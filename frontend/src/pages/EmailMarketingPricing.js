import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Slider } from '../components/ui/slider';
import { 
  Mail, Users, Send, Upload, Eye, CreditCard, BarChart3, 
  FileText, Crown, Zap, Check, ArrowRight, Sparkles, 
  TrendingUp, MousePointer, AlertCircle, Copy, Calculator,
  Gift, Percent, Star, ChevronRight, Shield, Rocket,
  Clock, Target, ArrowDown, Play, DollarSign, Layers
} from 'lucide-react';
import { formatCurrency } from '../utils/currencyFormatter';

const EmailMarketingPricing = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [emailCount, setEmailCount] = useState(2500);
  const [selectedPlan, setSelectedPlan] = useState('premium');

  // Volume-based pricing tiers
  const volumeTiers = [
    { min: 1, max: 1000, price: 0.018, label: '1 - 1,000' },
    { min: 1001, max: 5000, price: 0.015, label: '1,001 - 5,000' },
    { min: 5001, max: 10000, price: 0.012, label: '5,001 - 10,000' },
    { min: 10001, max: Infinity, price: 0.010, label: '10,001+' }
  ];

  // Plan perks
  const plans = {
    free: {
      name: 'Free',
      icon: Users,
      color: 'slate',
      gradient: 'from-slate-400 to-slate-500',
      bgGradient: 'from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800',
      freeCampaigns: 0,
      discount: 0,
      perks: ['Pay-as-you-go pricing', 'Basic templates', 'Standard delivery'],
      limitations: ['No free campaigns', 'No discounts']
    },
    premium: {
      name: 'Premium',
      icon: Zap,
      color: 'blue',
      gradient: 'from-blue-500 to-cyan-500',
      bgGradient: 'from-blue-50 to-cyan-50 dark:from-blue-950 dark:to-cyan-950',
      freeCampaigns: 1,
      discount: 10,
      perks: ['1 free campaign/month', '10% discount on all emails', 'All premium templates', 'Open & click analytics'],
      limitations: []
    },
    vip: {
      name: 'VIP',
      icon: Crown,
      color: 'purple',
      gradient: 'from-purple-500 to-pink-500',
      bgGradient: 'from-purple-50 to-pink-50 dark:from-purple-950 dark:to-pink-950',
      freeCampaigns: 2,
      discount: 20,
      perks: ['2 free campaigns/month', '20% discount on all emails', 'Priority delivery queue', 'Advanced analytics dashboard', 'Custom branding'],
      limitations: []
    }
  };

  // Calculate cost based on volume tiers
  const calculateCost = useMemo(() => {
    let remaining = emailCount;
    let totalCost = 0;
    let breakdown = [];

    for (const tier of volumeTiers) {
      if (remaining <= 0) break;
      
      const tierMax = tier.max === Infinity ? remaining : Math.min(tier.max - tier.min + 1, remaining);
      const emailsInTier = Math.min(remaining, tierMax);
      
      if (emailCount >= tier.min) {
        const cost = emailsInTier * tier.price;
        totalCost += cost;
        breakdown.push({
          ...tier,
          emails: emailsInTier,
          cost: cost
        });
        remaining -= emailsInTier;
      }
    }

    // Apply plan discount
    const plan = plans[selectedPlan];
    const discountAmount = totalCost * (plan.discount / 100);
    const finalCost = totalCost - discountAmount;

    // Effective rate
    const effectiveRate = emailCount > 0 ? finalCost / emailCount : 0;

    return {
      baseCost: totalCost,
      discount: discountAmount,
      discountPercent: plan.discount,
      finalCost,
      effectiveRate,
      breakdown,
      freeCampaigns: plan.freeCampaigns
    };
  }, [emailCount, selectedPlan]);

  // Flow steps with enhanced design
  const flowSteps = [
    {
      step: 1,
      title: 'Dashboard',
      subtitle: 'Your Marketing Hub',
      icon: BarChart3,
      gradient: 'from-blue-500 to-blue-600',
      shadowColor: 'shadow-blue-500/25',
      description: 'View credits, free campaigns, and past campaign performance',
      highlights: ['Available credits', 'Free campaigns left', 'Campaign history']
    },
    {
      step: 2,
      title: 'Create Campaign',
      subtitle: 'Build Your Message',
      icon: Upload,
      gradient: 'from-emerald-500 to-teal-500',
      shadowColor: 'shadow-emerald-500/25',
      description: 'Upload your contact list and choose from professional templates',
      highlights: ['CSV upload', '5 pro templates', 'Custom content']
    },
    {
      step: 3,
      title: 'Cost Calculation',
      subtitle: 'Transparent Pricing',
      icon: Calculator,
      gradient: 'from-amber-500 to-orange-500',
      shadowColor: 'shadow-amber-500/25',
      description: 'See your cost instantly with volume discounts applied',
      highlights: ['Volume tiers', 'Plan discounts', 'Free campaign check']
    },
    {
      step: 4,
      title: 'Preview & Confirm',
      subtitle: 'Final Review',
      icon: Eye,
      gradient: 'from-cyan-500 to-blue-500',
      shadowColor: 'shadow-cyan-500/25',
      description: 'Preview your email and confirm total cost',
      highlights: ['Email preview', 'Cost summary', 'Discount applied']
    },
    {
      step: 5,
      title: 'Payment',
      subtitle: 'Secure Checkout',
      icon: CreditCard,
      gradient: 'from-indigo-500 to-violet-500',
      shadowColor: 'shadow-indigo-500/25',
      description: 'Pay via Stripe or use saved payment method',
      highlights: ['Stripe secure', 'Saved cards', 'Free = skip!']
    },
    {
      step: 6,
      title: 'Campaign Sent',
      subtitle: 'Real-Time Tracking',
      icon: Send,
      gradient: 'from-green-500 to-emerald-500',
      shadowColor: 'shadow-green-500/25',
      description: 'Watch your campaign perform with live analytics',
      highlights: ['Delivery status', 'Open rates', 'Click tracking']
    },
    {
      step: 7,
      title: 'Summary',
      subtitle: 'Campaign Complete',
      icon: FileText,
      gradient: 'from-purple-500 to-pink-500',
      shadowColor: 'shadow-purple-500/25',
      description: 'Review results, check remaining perks, duplicate campaign',
      highlights: ['Full report', 'Credits left', 'Quick duplicate']
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/30 dark:from-slate-950 dark:via-slate-900 dark:to-blue-950/20">
      {/* Hero Section */}
      <section className="relative overflow-hidden py-16 md:py-20">
        {/* Animated Background Elements */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-blue-400/20 rounded-full blur-3xl animate-pulse" />
          <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-purple-400/20 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-r from-blue-200/20 to-purple-200/20 rounded-full blur-3xl" />
        </div>
        
        <div className="container mx-auto px-4 relative z-10">
          <div className="text-center max-w-4xl mx-auto">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-blue-100 to-purple-100 dark:from-blue-900/50 dark:to-purple-900/50 mb-6">
              <Sparkles className="h-4 w-4 text-blue-600 dark:text-blue-400" />
              <span className="text-sm font-medium text-blue-700 dark:text-blue-300">Pay-As-You-Go Email Marketing</span>
            </div>
            
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-6 leading-tight">
              <span className="bg-gradient-to-r from-slate-900 via-blue-800 to-purple-800 dark:from-white dark:via-blue-200 dark:to-purple-200 bg-clip-text text-transparent">
                Send Smarter,
              </span>
              <br />
              <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                Pay Only for What You Use
              </span>
            </h1>
            
            <p className="text-lg md:text-xl text-slate-600 dark:text-slate-300 mb-8 max-w-2xl mx-auto leading-relaxed">
              Volume-based pricing that rewards you for sending more. 
              Plus exclusive discounts and free campaigns for Premium & VIP members.
            </p>
            
            <div className="flex flex-wrap justify-center gap-4">
              <Button 
                size="lg" 
                className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white shadow-lg shadow-blue-500/25 gap-2 h-12 px-8"
                onClick={() => navigate('/client-marketing')}
              >
                <Mail className="h-5 w-5" />
                Start Your First Campaign
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button size="lg" variant="outline" className="gap-2 h-12 px-8 border-2" onClick={() => navigate('/pricing')}>
                <Crown className="h-5 w-5" />
                Unlock Premium Perks
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Volume Pricing Tiers */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-12">
            <Badge className="mb-4 bg-gradient-to-r from-amber-500 to-orange-500 text-white border-0">
              <Layers className="h-3 w-3 mr-1" />
              Volume Discounts
            </Badge>
            <h2 className="text-3xl md:text-4xl font-bold mb-4">The More You Send, The More You Save</h2>
            <p className="text-slate-600 dark:text-slate-400 max-w-xl mx-auto">
              Our tiered pricing automatically gives you better rates as your email volume increases
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {volumeTiers.map((tier, index) => (
              <Card 
                key={index} 
                className={`relative overflow-hidden transition-all duration-300 hover:scale-105 hover:shadow-xl
                  ${index === volumeTiers.length - 1 ? 'ring-2 ring-emerald-500 shadow-emerald-500/20' : ''}
                `}
              >
                {index === volumeTiers.length - 1 && (
                  <div className="absolute top-0 left-0 right-0 bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-xs font-bold py-1 text-center">
                    BEST RATE
                  </div>
                )}
                <CardContent className={`pt-${index === volumeTiers.length - 1 ? '8' : '6'} text-center`}>
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-800 dark:to-slate-700 mb-4">
                    <Mail className="h-6 w-6 text-slate-600 dark:text-slate-300" />
                  </div>
                  <p className="text-sm font-medium text-slate-500 mb-1">{tier.label} emails</p>
                  <p className="text-3xl font-bold text-slate-900 dark:text-white">
                    ${tier.price.toFixed(3)}
                  </p>
                  <p className="text-xs text-slate-400">per email</p>
                  {index > 0 && (
                    <Badge variant="secondary" className="mt-3 text-emerald-600 bg-emerald-50 dark:bg-emerald-950 dark:text-emerald-400">
                      Save {Math.round((1 - tier.price / volumeTiers[0].price) * 100)}%
                    </Badge>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Plan Perks Comparison */}
      <section className="py-16 px-4 bg-gradient-to-b from-white to-slate-50 dark:from-slate-900 dark:to-slate-950">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-12">
            <Badge className="mb-4 bg-gradient-to-r from-purple-500 to-pink-500 text-white border-0">
              <Gift className="h-3 w-3 mr-1" />
              Member Perks
            </Badge>
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Extra Savings for Premium & VIP</h2>
            <p className="text-slate-600 dark:text-slate-400 max-w-xl mx-auto">
              Get free campaigns every month plus additional discounts on all your emails
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {Object.entries(plans).map(([key, plan]) => {
              const IconComponent = plan.icon;
              return (
                <Card 
                  key={key}
                  className={`relative overflow-hidden cursor-pointer transition-all duration-300 
                    ${selectedPlan === key ? 'ring-2 scale-105 shadow-xl' : 'hover:shadow-lg hover:scale-102'}
                    ${key === 'premium' ? 'ring-blue-500' : key === 'vip' ? 'ring-purple-500' : 'ring-slate-300'}
                  `}
                  onClick={() => setSelectedPlan(key)}
                >
                  {/* Decorative top gradient */}
                  <div className={`h-2 bg-gradient-to-r ${plan.gradient}`} />
                  
                  <CardHeader className="pb-4">
                    <div className="flex items-center gap-3 mb-4">
                      <div className={`p-2.5 rounded-xl bg-gradient-to-br ${plan.gradient} text-white shadow-lg`}>
                        <IconComponent className="h-5 w-5" />
                      </div>
                      <div>
                        <CardTitle className="text-lg">{plan.name}</CardTitle>
                        {key !== 'free' && (
                          <p className="text-xs text-slate-500">Subscription required</p>
                        )}
                      </div>
                    </div>
                    
                    {/* Key Benefits */}
                    <div className="grid grid-cols-2 gap-3 mt-4">
                      <div className={`rounded-xl p-3 text-center bg-gradient-to-br ${plan.bgGradient}`}>
                        <p className="text-2xl font-bold">{plan.freeCampaigns}</p>
                        <p className="text-xs text-slate-500">Free/month</p>
                      </div>
                      <div className={`rounded-xl p-3 text-center bg-gradient-to-br ${plan.bgGradient}`}>
                        <p className="text-2xl font-bold">{plan.discount}%</p>
                        <p className="text-xs text-slate-500">Discount</p>
                      </div>
                    </div>
                  </CardHeader>
                  
                  <CardContent className="pt-0">
                    <ul className="space-y-2">
                      {plan.perks.map((perk, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <Check className={`h-4 w-4 mt-0.5 flex-shrink-0 ${
                            key === 'vip' ? 'text-purple-500' : key === 'premium' ? 'text-blue-500' : 'text-slate-400'
                          }`} />
                          <span>{perk}</span>
                        </li>
                      ))}
                      {plan.limitations.map((limit, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-slate-400">
                          <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                          <span>{limit}</span>
                        </li>
                      ))}
                    </ul>
                    
                    {key !== 'free' && (
                      <Button 
                        className={`w-full mt-4 bg-gradient-to-r ${plan.gradient} text-white border-0 hover:opacity-90`}
                        onClick={(e) => { e.stopPropagation(); navigate('/pricing'); }}
                      >
                        Upgrade to {plan.name}
                      </Button>
                    )}
                  </CardContent>
                  
                  {/* Selection indicator */}
                  {selectedPlan === key && (
                    <div className="absolute top-4 right-4">
                      <div className={`w-6 h-6 rounded-full bg-gradient-to-r ${plan.gradient} flex items-center justify-center`}>
                        <Check className="h-4 w-4 text-white" />
                      </div>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* Interactive Cost Calculator */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-4xl">
          <div className="text-center mb-10">
            <Badge className="mb-4 bg-gradient-to-r from-blue-500 to-cyan-500 text-white border-0">
              <Calculator className="h-3 w-3 mr-1" />
              Live Calculator
            </Badge>
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Calculate Your Campaign Cost</h2>
            <p className="text-slate-600 dark:text-slate-400">
              Slide to see how volume and plan discounts reduce your cost
            </p>
          </div>
          
          <Card className="overflow-hidden shadow-2xl">
            <div className="bg-gradient-to-r from-slate-900 to-slate-800 text-white p-6 md:p-8">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div className="flex-1">
                  <label className="text-sm text-slate-300 mb-2 block">Number of Emails</label>
                  <div className="flex items-center gap-4">
                    <Input
                      type="number"
                      value={emailCount}
                      onChange={(e) => setEmailCount(Math.max(1, parseInt(e.target.value) || 0))}
                      className="w-32 bg-white/10 border-white/20 text-white text-lg font-bold"
                    />
                    <div className="flex-1 hidden md:block">
                      <Slider
                        value={[emailCount]}
                        onValueChange={(val) => setEmailCount(val[0])}
                        max={25000}
                        min={100}
                        step={100}
                        className="w-full"
                      />
                    </div>
                  </div>
                </div>
                
                <div className="text-center md:text-right">
                  <p className="text-sm text-slate-400 mb-1">Selected Plan</p>
                  <Badge className={`bg-gradient-to-r ${plans[selectedPlan].gradient} text-white border-0 text-base px-4 py-1`}>
                    {plans[selectedPlan].name}
                  </Badge>
                </div>
              </div>
            </div>
            
            <CardContent className="p-6 md:p-8">
              <div className="grid md:grid-cols-2 gap-8">
                {/* Cost Breakdown */}
                <div className="space-y-4">
                  <h3 className="font-semibold text-lg flex items-center gap-2">
                    <Layers className="h-5 w-5 text-blue-500" />
                    Volume Breakdown
                  </h3>
                  
                  <div className="space-y-2">
                    {calculateCost.breakdown.map((tier, i) => (
                      <div key={i} className="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-800">
                        <div>
                          <p className="font-medium">{tier.emails.toLocaleString()} emails</p>
                          <p className="text-xs text-slate-500">@ ${tier.price.toFixed(3)}/email</p>
                        </div>
                        <p className="font-semibold">{formatCurrency(tier.cost)}</p>
                      </div>
                    ))}
                  </div>
                  
                  <div className="pt-2">
                    <div className="flex justify-between items-center">
                      <p className="text-slate-500">Subtotal</p>
                      <p className="font-semibold">{formatCurrency(calculateCost.baseCost)}</p>
                    </div>
                    
                    {calculateCost.discountPercent > 0 && (
                      <div className="flex justify-between items-center text-emerald-600 dark:text-emerald-400">
                        <p className="flex items-center gap-1">
                          <Percent className="h-4 w-4" />
                          {selectedPlan} discount ({calculateCost.discountPercent}%)
                        </p>
                        <p className="font-semibold">-{formatCurrency(calculateCost.discount)}</p>
                      </div>
                    )}
                  </div>
                </div>
                
                {/* Total & Perks */}
                <div>
                  <div className="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-800 dark:to-slate-900 rounded-2xl p-6 text-center">
                    <p className="text-sm text-slate-500 mb-2">Your Campaign Cost</p>
                    <p className="text-5xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                      {formatCurrency(calculateCost.finalCost)}
                    </p>
                    <p className="text-sm text-slate-500 mt-2">
                      Effective rate: ${calculateCost.effectiveRate.toFixed(4)}/email
                    </p>
                    
                    {calculateCost.freeCampaigns > 0 && (
                      <div className="mt-4 p-3 bg-emerald-50 dark:bg-emerald-950/50 rounded-xl border border-emerald-200 dark:border-emerald-800">
                        <p className="text-emerald-700 dark:text-emerald-400 font-medium flex items-center justify-center gap-2">
                          <Gift className="h-4 w-4" />
                          {calculateCost.freeCampaigns} free campaign{calculateCost.freeCampaigns > 1 ? 's' : ''}/month included!
                        </p>
                      </div>
                    )}
                    
                    <Button 
                      className="w-full mt-6 bg-gradient-to-r from-blue-600 to-purple-600 text-white h-12"
                      onClick={() => navigate('/client-marketing')}
                    >
                      Start This Campaign
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  </div>
                  
                  {/* Quick stats */}
                  <div className="grid grid-cols-2 gap-3 mt-4">
                    <div className="bg-blue-50 dark:bg-blue-950/30 rounded-xl p-3 text-center">
                      <p className="text-2xl font-bold text-blue-600">{emailCount.toLocaleString()}</p>
                      <p className="text-xs text-slate-500">Total Emails</p>
                    </div>
                    <div className="bg-emerald-50 dark:bg-emerald-950/30 rounded-xl p-3 text-center">
                      <p className="text-2xl font-bold text-emerald-600">
                        {calculateCost.discountPercent > 0 ? `${calculateCost.discountPercent}%` : '0%'}
                      </p>
                      <p className="text-xs text-slate-500">Saved</p>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Visual Flow Steps */}
      <section className="py-16 px-4 bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-950">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center mb-12">
            <Badge className="mb-4 bg-gradient-to-r from-emerald-500 to-teal-500 text-white border-0">
              <Play className="h-3 w-3 mr-1" />
              How It Works
            </Badge>
            <h2 className="text-3xl md:text-4xl font-bold mb-4">7 Simple Steps to Success</h2>
            <p className="text-slate-600 dark:text-slate-400 max-w-xl mx-auto">
              From dashboard to delivery — a seamless campaign experience
            </p>
          </div>

          {/* Desktop Flow */}
          <div className="hidden lg:block">
            <div className="relative">
              {/* Connecting line */}
              <div className="absolute top-16 left-0 right-0 h-1 bg-gradient-to-r from-blue-200 via-purple-200 to-emerald-200 dark:from-blue-800 dark:via-purple-800 dark:to-emerald-800 rounded-full" />
              
              <div className="grid grid-cols-7 gap-2">
                {flowSteps.map((step, index) => {
                  const IconComponent = step.icon;
                  return (
                    <div key={step.step} className="relative group">
                      {/* Step card */}
                      <div className="flex flex-col items-center">
                        {/* Icon circle */}
                        <div className={`relative z-10 w-32 h-32 rounded-2xl bg-gradient-to-br ${step.gradient} 
                          flex flex-col items-center justify-center text-white shadow-xl ${step.shadowColor}
                          transition-all duration-300 group-hover:scale-110 group-hover:shadow-2xl cursor-pointer`}
                        >
                          <IconComponent className="h-10 w-10 mb-2" />
                          <span className="text-xs font-bold opacity-80">Step {step.step}</span>
                        </div>
                        
                        {/* Arrow */}
                        {index < flowSteps.length - 1 && (
                          <div className="absolute top-14 -right-1 z-20">
                            <ChevronRight className="h-6 w-6 text-slate-300 dark:text-slate-600" />
                          </div>
                        )}
                        
                        {/* Labels */}
                        <div className="mt-4 text-center">
                          <h3 className="font-bold text-sm">{step.title}</h3>
                          <p className="text-xs text-slate-500">{step.subtitle}</p>
                        </div>
                        
                        {/* Hover popup */}
                        <div className="absolute top-full mt-6 left-1/2 -translate-x-1/2 w-48 opacity-0 group-hover:opacity-100 
                          transition-all duration-300 pointer-events-none z-30">
                          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-xl p-4 border">
                            <p className="text-sm text-slate-600 dark:text-slate-300 mb-3">{step.description}</p>
                            <div className="space-y-1">
                              {step.highlights.map((h, i) => (
                                <div key={i} className="flex items-center gap-2 text-xs text-slate-500">
                                  <div className={`w-1.5 h-1.5 rounded-full bg-gradient-to-r ${step.gradient}`} />
                                  {h}
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Mobile Flow */}
          <div className="lg:hidden space-y-4">
            {flowSteps.map((step, index) => {
              const IconComponent = step.icon;
              return (
                <div key={step.step}>
                  <Card className="overflow-hidden hover:shadow-lg transition-shadow">
                    <CardContent className="p-0">
                      <div className="flex">
                        {/* Icon side */}
                        <div className={`w-24 bg-gradient-to-br ${step.gradient} flex flex-col items-center justify-center p-4 text-white`}>
                          <IconComponent className="h-8 w-8 mb-1" />
                          <span className="text-xs font-bold opacity-80">Step {step.step}</span>
                        </div>
                        
                        {/* Content side */}
                        <div className="flex-1 p-4">
                          <h3 className="font-bold">{step.title}</h3>
                          <p className="text-sm text-slate-500 mb-2">{step.subtitle}</p>
                          <p className="text-sm text-slate-600 dark:text-slate-400">{step.description}</p>
                          
                          <div className="flex flex-wrap gap-1.5 mt-3">
                            {step.highlights.map((h, i) => (
                              <Badge key={i} variant="secondary" className="text-xs">
                                {h}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  {/* Arrow */}
                  {index < flowSteps.length - 1 && (
                    <div className="flex justify-center py-2">
                      <ArrowDown className="h-5 w-5 text-slate-300" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Analytics Preview */}
      <section className="py-16 px-4 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white relative overflow-hidden">
        {/* Background decoration */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
          <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />
        </div>
        
        <div className="container mx-auto max-w-5xl relative z-10">
          <div className="text-center mb-12">
            <Badge className="mb-4 bg-emerald-500 text-white border-0">
              <TrendingUp className="h-3 w-3 mr-1" />
              Real-Time Analytics
            </Badge>
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Track Every Email, Every Click</h2>
            <p className="text-slate-300 max-w-xl mx-auto">
              Watch your campaign perform live with comprehensive analytics
            </p>
          </div>
          
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { icon: Send, label: 'Delivered', value: '2,487', rate: '99.5%', color: 'emerald', desc: 'Successfully delivered' },
              { icon: Eye, label: 'Opened', value: '1,245', rate: '50.1%', color: 'blue', desc: 'Unique opens' },
              { icon: MousePointer, label: 'Clicked', value: '312', rate: '12.5%', color: 'purple', desc: 'Link clicks' },
              { icon: AlertCircle, label: 'Bounced', value: '13', rate: '0.5%', color: 'amber', desc: 'Failed delivery' }
            ].map((stat, i) => (
              <div key={i} className="bg-white/5 backdrop-blur-sm rounded-2xl p-6 text-center border border-white/10 hover:bg-white/10 transition-colors">
                <div className={`inline-flex items-center justify-center w-14 h-14 rounded-xl bg-${stat.color}-500/20 mb-4`}>
                  <stat.icon className={`h-7 w-7 text-${stat.color}-400`} />
                </div>
                <p className="text-4xl font-bold mb-1">{stat.value}</p>
                <p className="text-slate-400 text-sm mb-2">{stat.label}</p>
                <Badge className={`bg-${stat.color}-500/20 text-${stat.color}-300 border-0`}>
                  {stat.rate}
                </Badge>
              </div>
            ))}
          </div>
          
          {/* VIP Analytics callout */}
          <div className="mt-8 p-6 bg-gradient-to-r from-purple-500/20 to-pink-500/20 rounded-2xl border border-purple-500/30 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl bg-purple-500/20">
                <Crown className="h-8 w-8 text-purple-400" />
              </div>
              <div>
                <p className="font-semibold text-lg">VIP Analytics Dashboard</p>
                <p className="text-slate-400 text-sm">Advanced insights, heatmaps, and A/B testing results</p>
              </div>
            </div>
            <Button variant="outline" className="border-purple-500/50 text-purple-300 hover:bg-purple-500/20">
              Upgrade to VIP
            </Button>
          </div>
        </div>
      </section>

      {/* Templates */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold mb-4">5 Professional Templates</h2>
            <p className="text-slate-600 dark:text-slate-400">
              Ready-to-send designs optimized for auction announcements
            </p>
          </div>
          
          <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {[
              { name: 'New Auction', color: 'from-blue-500 to-cyan-500', icon: '🔔', shadow: 'shadow-blue-500/20' },
              { name: 'Ending Soon', color: 'from-red-500 to-orange-500', icon: '⏰', shadow: 'shadow-red-500/20' },
              { name: 'New Inventory', color: 'from-emerald-500 to-teal-500', icon: '📦', shadow: 'shadow-emerald-500/20' },
              { name: 'VIP Preview', color: 'from-purple-500 to-pink-500', icon: '👑', shadow: 'shadow-purple-500/20' },
              { name: 'Price Drop', color: 'from-amber-500 to-yellow-500', icon: '💰', shadow: 'shadow-amber-500/20' }
            ].map((template, i) => (
              <Card key={i} className={`overflow-hidden group cursor-pointer hover:shadow-xl ${template.shadow} transition-all hover:scale-105`}>
                <div className={`h-28 bg-gradient-to-br ${template.color} flex items-center justify-center`}>
                  <span className="text-5xl group-hover:scale-110 transition-transform">{template.icon}</span>
                </div>
                <CardContent className="p-4 text-center">
                  <p className="font-semibold">{template.name}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-16 px-4">
        <div className="container mx-auto max-w-3xl">
          <Card className="overflow-hidden bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600 text-white border-0 shadow-2xl">
            <CardContent className="p-8 md:p-12 text-center relative overflow-hidden">
              {/* Background elements */}
              <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl" />
              <div className="absolute bottom-0 left-0 w-64 h-64 bg-white/10 rounded-full blur-3xl" />
              
              <div className="relative z-10">
                <Rocket className="h-14 w-14 mx-auto mb-6 animate-bounce" />
                <h2 className="text-3xl md:text-4xl font-bold mb-4">
                  Ready to Launch Your Campaign?
                </h2>
                <p className="text-blue-100 mb-8 max-w-xl mx-auto text-lg">
                  Start free, pay as you go, or unlock premium perks. 
                  Your first campaign is just minutes away.
                </p>
                
                <div className="flex flex-wrap justify-center gap-4">
                  <Button 
                    size="lg" 
                    className="bg-white text-blue-600 hover:bg-blue-50 gap-2 h-14 px-8 text-lg font-semibold shadow-lg"
                    onClick={() => navigate('/client-marketing')}
                  >
                    <Mail className="h-5 w-5" />
                    Create Your First Campaign
                  </Button>
                </div>
                
                <div className="flex flex-wrap justify-center gap-6 mt-8 text-sm text-blue-100">
                  <span className="flex items-center gap-1.5">
                    <Check className="h-4 w-4" /> No setup fees
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Check className="h-4 w-4" /> Pay only for sends
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Check className="h-4 w-4" /> Cancel anytime
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Shield className="h-4 w-4" /> GDPR compliant
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-16 px-4 bg-slate-50 dark:bg-slate-900/50">
        <div className="container mx-auto max-w-3xl">
          <h2 className="text-2xl font-bold text-center mb-8">Frequently Asked Questions</h2>
          
          <div className="space-y-4">
            {[
              { 
                q: 'How does volume pricing work?', 
                a: 'As you send more emails in a single campaign, your per-email rate automatically decreases. Emails 1-1,000 are $0.018 each, 1,001-5,000 are $0.015, 5,001-10,000 are $0.012, and 10,001+ are just $0.010 each.' 
              },
              { 
                q: 'What are free campaigns?', 
                a: 'Premium members get 1 free campaign per month, VIP members get 2. A "free campaign" means the entire send is complimentary — you only pay if you exceed your free allocation.' 
              },
              { 
                q: 'Do discounts stack with volume pricing?', 
                a: 'Yes! Premium members get 10% off and VIP members get 20% off — applied after volume pricing. So a VIP sending 10,000 emails pays even less than the base volume rate.' 
              },
              { 
                q: 'Can I see results in real-time?', 
                a: 'Absolutely. Track delivered, opened, clicked, and bounced emails live. VIP members also get advanced analytics including click heatmaps and engagement scoring.' 
              }
            ].map((faq, i) => (
              <Card key={i} className="hover:shadow-md transition-shadow">
                <CardContent className="p-5">
                  <p className="font-semibold mb-2 flex items-start gap-2">
                    <span className="text-blue-500">Q:</span>
                    {faq.q}
                  </p>
                  <p className="text-sm text-slate-600 dark:text-slate-400 pl-6">{faq.a}</p>
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
