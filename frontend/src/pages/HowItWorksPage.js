import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Search, FileText, Gavel, CreditCard, Trophy, HelpCircle, ArrowRight } from 'lucide-react';

const HowItWorksPage = () => {
  const navigate = useNavigate();

  const steps = [
    {
      icon: <Search className="h-12 w-12" />,
      title: "1. Browse & Discover",
      description: "Explore our marketplace to find unique items. Use filters to narrow down by category, price, location, and more."
    },
    {
      icon: <FileText className="h-12 w-12" />,
      title: "2. Register & Verify",
      description: "Create your free account and verify your email. Complete your profile to build trust with the community."
    },
    {
      icon: <Gavel className="h-12 w-12" />,
      title: "3. Place Your Bid",
      description: "Found something you like? Place a bid and watch the auction in real-time. You'll get instant notifications if you're outbid."
    },
    {
      icon: <Trophy className="h-12 w-12" />,
      title: "4. Win & Celebrate",
      description: "If you win, you'll receive an email confirmation. Complete your secure payment through our Stripe integration."
    },
    {
      icon: <CreditCard className="h-12 w-12" />,
      title: "5. Secure Payment & Delivery",
      description: "Complete payment securely and coordinate delivery with the seller. All transactions are protected by our buyer guarantee."
    }
  ];

  const faqs = [
    {
      question: "How do I start bidding?",
      answer: "First, create a free account and verify your email. Then browse our marketplace, find an item you like, and click 'Place Bid' to enter your bid amount. You'll be notified if someone outbids you."
    },
    {
      question: "Is my payment information secure?",
      answer: "Absolutely! All payments are processed through Stripe, a leading payment processor trusted by millions. We never store your credit card information on our servers."
    },
    {
      question: "What happens if I win an auction?",
      answer: "Congratulations! You'll receive an email confirmation and be directed to complete your payment. Once payment is confirmed, you can coordinate delivery or pickup with the seller through our messaging system."
    },
    {
      question: "Can I cancel my bid?",
      answer: "Bids are binding commitments. Once placed, bids cannot be retracted. Please bid responsibly and make sure you're willing to complete the purchase if you win."
    },
    {
      question: "How do seller fees work?",
      answer: "Sellers pay a small commission on successful sales. Personal accounts pay 5%, while business accounts pay 4.5%. This helps us maintain a secure, feature-rich platform for everyone."
    }
  ];

  return (
    <div className="min-h-screen py-12 px-4">
      <div className="max-w-6xl mx-auto space-y-16">
        {/* Header */}
        <div className="text-center space-y-4">
          <Badge className="mb-4 gradient-bg text-white border-0 text-lg px-6 py-2">
            How It Works
          </Badge>
          <h1 className="text-4xl md:text-5xl font-bold">
            Start Bidding in <span className="gradient-text">5 Simple Steps</span>
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            Whether you're buying or selling, BidVex makes online auctions simple, secure, and exciting
          </p>
        </div>

        {/* Steps */}
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
          {steps.map((step, index) => (
            <Card key={index} className="relative overflow-hidden group hover:shadow-xl transition-shadow">
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-primary/10 to-accent/10 rounded-bl-full -mr-16 -mt-16 group-hover:scale-110 transition-transform"></div>
              <CardContent className="p-6 space-y-4 relative">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-white">
                  {step.icon}
                </div>
                <div>
                  <h3 className="text-xl font-bold mb-2">{step.title}</h3>
                  <p className="text-muted-foreground">{step.description}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* CTA Section */}
        <div className="bg-gradient-to-br from-primary/10 via-purple-500/10 to-accent/10 rounded-2xl p-8 md:p-12 text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Ready to Start Your Bidding Journey?
          </h2>
          <p className="text-lg text-muted-foreground mb-8 max-w-2xl mx-auto">
            Join thousands of buyers and sellers in the most trusted auction marketplace
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button 
              className="gradient-button text-white border-0 text-lg px-8 py-6 rounded-full group"
              onClick={() => navigate('/marketplace')}
            >
              Browse Auctions
              <ArrowRight className="ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
            </Button>
            <Button 
              variant="outline"
              className="text-lg px-8 py-6 rounded-full border-2"
              onClick={() => navigate('/create-listing')}
            >
              Start Selling
            </Button>
          </div>
        </div>

        {/* FAQ Section */}
        <div className="space-y-8">
          <div className="text-center space-y-4">
            <HelpCircle className="h-12 w-12 mx-auto text-primary" />
            <h2 className="text-3xl md:text-4xl font-bold">
              Frequently Asked Questions
            </h2>
            <p className="text-lg text-muted-foreground">
              Got questions? We've got answers
            </p>
          </div>

          <div className="space-y-4 max-w-4xl mx-auto">
            {faqs.map((faq, index) => (
              <Card key={index} className="overflow-hidden hover:shadow-lg transition-shadow">
                <CardContent className="p-6">
                  <h3 className="text-lg font-bold mb-3 flex items-start gap-3">
                    <span className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-primary to-accent text-white flex items-center justify-center text-sm font-bold">
                      {index + 1}
                    </span>
                    {faq.question}
                  </h3>
                  <p className="text-muted-foreground pl-11">{faq.answer}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Video Tutorial Placeholder */}
        <div className="bg-gradient-to-br from-gray-100 to-gray-50 dark:from-gray-900 dark:to-gray-800 rounded-2xl p-12 text-center">
          <div className="max-w-2xl mx-auto space-y-4">
            <div className="w-24 h-24 mx-auto rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-white text-4xl">
              📹
            </div>
            <h3 className="text-2xl font-bold">Video Tutorials Coming Soon</h3>
            <p className="text-muted-foreground">
              We're creating detailed video guides to help you get the most out of BidVex. 
              Check back soon for step-by-step tutorials!
            </p>
            <Button 
              variant="outline"
              onClick={() => navigate('/marketplace')}
            >
              Explore Marketplace Instead
            </Button>
          </div>
        </div>

        {/* Still Have Questions */}
        <div className="text-center space-y-4">
          <h3 className="text-2xl font-bold">Still Have Questions?</h3>
          <p className="text-muted-foreground mb-6">
            Our support team is here to help you succeed
          </p>
          <Button 
            variant="outline"
            className="rounded-full"
            onClick={() => navigate('/messages')}
          >
            Contact Support
          </Button>
        </div>
      </div>
    </div>
  );
};

export default HowItWorksPage;
