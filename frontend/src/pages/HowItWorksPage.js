import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { 
  Search, UserPlus, Gavel, Trophy, CreditCard, 
  ChevronDown, ChevronUp, Play, ArrowRight, 
  CheckCircle2, Sparkles, Shield, Clock
} from 'lucide-react';

const HowItWorksPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [openFaq, setOpenFaq] = useState(null);
  const [visibleSteps, setVisibleSteps] = useState([]);

  // Scroll animation effect
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const stepIndex = parseInt(entry.target.dataset.step);
            setVisibleSteps((prev) => [...new Set([...prev, stepIndex])]);
          }
        });
      },
      { threshold: 0.2 }
    );

    document.querySelectorAll('[data-step]').forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  const steps = [
    {
      icon: <Search className="h-8 w-8" />,
      title: "Browse & Discover",
      description: "Explore thousands of unique items from trusted sellers worldwide. Use filters to find exactly what you're looking for.",
      features: ["Smart search filters", "Category browsing", "Saved searches"]
    },
    {
      icon: <UserPlus className="h-8 w-8" />,
      title: "Register Free",
      description: "Create your free account in seconds. Verify your identity to unlock full bidding capabilities.",
      features: ["Quick signup", "Secure verification", "Profile customization"]
    },
    {
      icon: <Gavel className="h-8 w-8" />,
      title: "Place Your Bid",
      description: "Bid on items you love with confidence. Set maximum bids and let our system bid for you automatically.",
      features: ["Auto-bidding", "Bid alerts", "Real-time updates"]
    },
    {
      icon: <Trophy className="h-8 w-8" />,
      title: "Win the Auction",
      description: "When you're the highest bidder at auction end, you win! Receive instant notification of your victory.",
      features: ["Instant notifications", "Winner dashboard", "Purchase history"]
    },
    {
      icon: <CreditCard className="h-8 w-8" />,
      title: "Secure Payment",
      description: "Complete your purchase with our secure payment system. Multiple payment options available for your convenience.",
      features: ["Stripe security", "Multiple currencies", "Buyer protection"]
    }
  ];

  const faqs = [
    {
      question: "How do I start bidding on BidVex?",
      answer: "Simply create a free account, browse our listings, and click 'Place Bid' on any item you're interested in. You'll need to enter a bid amount equal to or higher than the current bid plus the minimum increment."
    },
    {
      question: "What happens if I win an auction?",
      answer: "Congratulations! You'll receive an email notification and can complete your purchase through our secure checkout. Payment is processed via Stripe for your security."
    },
    {
      question: "Is there a buyer protection policy?",
      answer: "Yes! BidVex offers comprehensive buyer protection. If an item doesn't match its description or doesn't arrive, our support team will help resolve the issue and process refunds when applicable."
    },
    {
      question: "Can I sell items on BidVex?",
      answer: "Absolutely! Click 'Start Selling' to create your seller profile. You can list single items or create multi-lot auctions for bulk sales."
    },
    {
      question: "What are the fees for sellers?",
      answer: "Sellers pay a small commission on successful sales only. There are no listing fees for basic accounts. Premium subscriptions offer reduced commission rates and additional features."
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Modern Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 text-white">
        {/* Animated background pattern */}
        <div className="absolute inset-0 opacity-20">
          <div className="absolute inset-0" style={{
            backgroundImage: `radial-gradient(circle at 2px 2px, rgba(255,255,255,0.15) 1px, transparent 0)`,
            backgroundSize: '40px 40px'
          }} />
        </div>
        
        {/* Gradient orbs */}
        <div className="absolute top-20 left-20 w-72 h-72 bg-blue-500/30 rounded-full blur-[100px]" />
        <div className="absolute bottom-20 right-20 w-96 h-96 bg-purple-500/20 rounded-full blur-[120px]" />
        
        <div className="relative max-w-6xl mx-auto px-4 py-24 md:py-32">
          <div className="text-center space-y-6">
            <Badge className="bg-white/10 backdrop-blur-sm text-white border-white/20 text-sm px-4 py-2">
              <Sparkles className="h-4 w-4 mr-2 inline" />
              Your Guide to Winning
            </Badge>
            
            <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold leading-tight">
              Master the Art of
              <span className="block bg-gradient-to-r from-blue-400 via-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Bidding on BidVex
              </span>
            </h1>
            
            <p className="text-lg md:text-xl text-blue-100/80 max-w-2xl mx-auto leading-relaxed">
              Join thousands of smart bidders who've discovered the thrill of winning. 
              Follow our simple 5-step process to start your journey.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
              <Button 
                onClick={() => navigate('/marketplace')}
                className="bg-white text-slate-900 hover:bg-blue-50 px-8 py-6 text-lg font-semibold shadow-xl hover:shadow-2xl transition-all"
              >
                Start Bidding Now
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
              <Button 
                onClick={() => navigate('/auth')}
                variant="outline"
                className="border-2 border-white/30 text-white hover:bg-white/10 px-8 py-6 text-lg"
              >
                Create Free Account
              </Button>
            </div>
          </div>
        </div>
        
        {/* Wave divider */}
        <div className="absolute bottom-0 left-0 right-0">
          <svg viewBox="0 0 1440 120" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M0 120L60 110C120 100 240 80 360 70C480 60 600 60 720 65C840 70 960 80 1080 85C1200 90 1320 90 1380 90L1440 90V120H1380C1320 120 1200 120 1080 120C960 120 840 120 720 120C600 120 480 120 360 120C240 120 120 120 60 120H0Z" fill="rgb(248 250 252)" />
          </svg>
        </div>
      </section>

      {/* 5 Steps Timeline Section */}
      <section className="py-20 md:py-32 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <Badge className="bg-blue-100 text-blue-700 mb-4">5 Simple Steps</Badge>
            <h2 className="text-3xl md:text-5xl font-bold text-slate-900 mb-4">
              Your Path to Winning
            </h2>
            <p className="text-lg text-slate-600 max-w-2xl mx-auto">
              From discovery to delivery, we've made every step seamless and secure
            </p>
          </div>

          {/* Zigzag Timeline */}
          <div className="relative">
            {/* Vertical line for desktop */}
            <div className="hidden md:block absolute left-1/2 transform -translate-x-1/2 w-1 h-full bg-gradient-to-b from-blue-200 via-blue-400 to-blue-600 rounded-full" />
            
            {steps.map((step, index) => (
              <div
                key={index}
                data-step={index}
                className={`relative flex flex-col md:flex-row items-center gap-8 mb-16 last:mb-0
                  ${index % 2 === 0 ? 'md:flex-row' : 'md:flex-row-reverse'}
                  transition-all duration-700 ${visibleSteps.includes(index) ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'}`}
              >
                {/* Step Number Circle */}
                <div className="hidden md:flex absolute left-1/2 transform -translate-x-1/2 z-10">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-600 to-blue-700 flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-blue-500/30 ring-4 ring-white">
                    {index + 1}
                  </div>
                </div>

                {/* Content Card */}
                <div className={`w-full md:w-5/12 ${index % 2 === 0 ? 'md:pr-16' : 'md:pl-16'}`}>
                  <Card className="group hover:shadow-2xl transition-all duration-300 border-0 shadow-lg overflow-hidden">
                    <CardContent className="p-0">
                      <div className="bg-gradient-to-br from-blue-600 to-blue-700 p-6 text-white">
                        <div className="flex items-center gap-4">
                          <div className="w-14 h-14 rounded-xl bg-white/20 backdrop-blur flex items-center justify-center">
                            {step.icon}
                          </div>
                          <div>
                            <Badge className="bg-white/20 text-white text-xs mb-1">Step {index + 1}</Badge>
                            <h3 className="text-xl font-bold">{step.title}</h3>
                          </div>
                        </div>
                      </div>
                      <div className="p-6 bg-white">
                        <p className="text-slate-600 mb-4 leading-relaxed">{step.description}</p>
                        <div className="flex flex-wrap gap-2">
                          {step.features.map((feature, i) => (
                            <span key={i} className="inline-flex items-center gap-1 text-sm text-blue-700 bg-blue-50 px-3 py-1 rounded-full">
                              <CheckCircle2 className="h-3 w-3" />
                              {feature}
                            </span>
                          ))}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* Spacer for zigzag */}
                <div className="hidden md:block w-5/12" />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-20 px-4 bg-slate-900 text-white">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold mb-4">Why Choose BidVex?</h2>
            <p className="text-slate-400">The trusted platform for buyers and sellers alike</p>
          </div>
          
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { icon: <Shield className="h-8 w-8" />, title: "Secure Transactions", desc: "Bank-level encryption protects every payment" },
              { icon: <Clock className="h-8 w-8" />, title: "Real-time Bidding", desc: "Instant updates with live auction countdown" },
              { icon: <Trophy className="h-8 w-8" />, title: "Buyer Protection", desc: "Full refund if items don't match description" }
            ].map((item, i) => (
              <div key={i} className="text-center p-8 rounded-2xl bg-white/5 backdrop-blur border border-white/10 hover:bg-white/10 transition-all">
                <div className="w-16 h-16 mx-auto mb-4 rounded-xl bg-blue-600/20 flex items-center justify-center text-blue-400">
                  {item.icon}
                </div>
                <h3 className="text-xl font-semibold mb-2">{item.title}</h3>
                <p className="text-slate-400">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Modern FAQ Accordion */}
      <section className="py-20 md:py-32 px-4">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-12">
            <Badge className="bg-slate-100 text-slate-700 mb-4">Got Questions?</Badge>
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
              Frequently Asked Questions
            </h2>
            <p className="text-slate-600">Everything you need to know to get started</p>
          </div>

          <div className="space-y-4">
            {faqs.map((faq, index) => (
              <div
                key={index}
                className={`rounded-xl border-2 transition-all duration-300 overflow-hidden
                  ${openFaq === index ? 'border-blue-500 shadow-lg shadow-blue-500/10' : 'border-slate-200 hover:border-slate-300'}`}
              >
                <button
                  onClick={() => setOpenFaq(openFaq === index ? null : index)}
                  className="w-full px-6 py-5 flex items-center justify-between text-left bg-white hover:bg-slate-50 transition-colors"
                >
                  <span className="font-semibold text-slate-900 pr-4">{faq.question}</span>
                  <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center transition-all
                    ${openFaq === index ? 'bg-blue-600 text-white rotate-180' : 'bg-slate-100 text-slate-600'}`}>
                    <ChevronDown className="h-5 w-5" />
                  </div>
                </button>
                <div className={`transition-all duration-300 ease-in-out ${openFaq === index ? 'max-h-96' : 'max-h-0'}`}>
                  <div className="px-6 pb-5 pt-0 bg-slate-50">
                    <p className="text-slate-600 leading-relaxed">{faq.answer}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Video Tutorials Teaser */}
      <section className="py-20 px-4 bg-gradient-to-br from-slate-100 to-blue-50">
        <div className="max-w-4xl mx-auto">
          <div className="relative rounded-3xl overflow-hidden shadow-2xl">
            {/* Blurred background image placeholder */}
            <div className="relative h-80 md:h-96 bg-gradient-to-br from-slate-800 to-slate-900">
              <div className="absolute inset-0" style={{
                backgroundImage: `url('https://images.unsplash.com/photo-1553028826-f4804a6dba3b?w=1200&q=80')`,
                backgroundSize: 'cover',
                backgroundPosition: 'center',
                filter: 'blur(8px) brightness(0.4)'
              }} />
              
              {/* Play button overlay */}
              <div className="absolute inset-0 flex flex-col items-center justify-center text-white">
                <div className="w-24 h-24 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center mb-6 cursor-pointer hover:bg-white/30 hover:scale-110 transition-all border-2 border-white/30">
                  <Play className="h-12 w-12 text-white ml-1" fill="white" />
                </div>
                <Badge className="bg-blue-600 text-white mb-3">Coming Soon</Badge>
                <h3 className="text-2xl md:text-3xl font-bold mb-2">Video Tutorials</h3>
                <p className="text-white/70 text-center max-w-md px-4">
                  Step-by-step video guides to help you master bidding on BidVex
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl md:text-5xl font-bold text-slate-900 mb-6">
            Ready to Start Winning?
          </h2>
          <p className="text-xl text-slate-600 mb-8 max-w-2xl mx-auto">
            Join thousands of savvy bidders. Create your free account and discover amazing deals today.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button 
              onClick={() => navigate('/auth')}
              className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white px-10 py-6 text-lg font-semibold shadow-lg shadow-blue-500/30 hover:shadow-xl hover:shadow-blue-500/40 transition-all"
            >
              Create Free Account
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            <Button 
              onClick={() => navigate('/marketplace')}
              variant="outline"
              className="border-2 border-slate-300 text-slate-700 hover:bg-slate-50 px-10 py-6 text-lg"
            >
              Browse Auctions
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
};

export default HowItWorksPage;
