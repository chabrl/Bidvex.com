import React from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { ArrowRight, Gavel, TrendingUp, Shield, Users } from 'lucide-react';

const HomePage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen" data-testid="home-page">
      <section className="relative py-20 md:py-32 px-4 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/10 via-transparent to-accent/10 pointer-events-none"></div>
        
        <div className="max-w-7xl mx-auto relative">
          <div className="text-center space-y-8 max-w-4xl mx-auto">
            <h1 className="text-4xl sm:text-5xl lg:text-7xl font-bold leading-tight" data-testid="hero-title">
              {t('hero.title')}
            </h1>
            <p className="text-xl sm:text-2xl text-muted-foreground font-medium">
              {t('hero.subtitle')}
            </p>
            <p className="text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto">
              {t('hero.description')}
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center pt-4">
              <Button 
                className="gradient-button text-white border-0 text-lg px-8 py-6 rounded-full"
                onClick={() => navigate('/marketplace')}
                data-testid="explore-auctions-btn"
              >
                {t('hero.cta')} <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
              <Button 
                variant="outline" 
                className="text-lg px-8 py-6 rounded-full border-2"
                onClick={() => navigate('/create-listing')}
                data-testid="start-selling-btn"
              >
                {t('hero.sellNow')}
              </Button>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 px-4 bg-white/50 dark:bg-gray-800/50">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <FeatureCard 
              icon={<Gavel className="h-8 w-8" />}
              title="Live Auctions"
              description="Real-time bidding with instant updates"
            />
            <FeatureCard 
              icon={<TrendingUp className="h-8 w-8" />}
              title="Best Deals"
              description="Competitive pricing for buyers and sellers"
            />
            <FeatureCard 
              icon={<Shield className="h-8 w-8" />}
              title="Secure Payments"
              description="Protected transactions with Stripe"
            />
            <FeatureCard 
              icon={<Users className="h-8 w-8" />}
              title="Global Community"
              description="Connect with buyers worldwide"
            />
          </div>
        </div>
      </section>

      <section className="py-20 px-4">
        <div className="max-w-4xl mx-auto text-center space-y-6">
          <h2 className="text-3xl md:text-4xl font-bold">How It Works</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 pt-8">
            <Step number="1" title="Browse" description="Explore unique items from trusted sellers" />
            <Step number="2" title="Bid" description="Place competitive bids or buy instantly" />
            <Step number="3" title="Win" description="Secure your purchase with safe payments" />
          </div>
        </div>
      </section>
    </div>
  );
};

const FeatureCard = ({ icon, title, description }) => (
  <div className="p-6 rounded-2xl glassmorphism card-hover text-center space-y-3">
    <div className="gradient-bg w-16 h-16 rounded-xl flex items-center justify-center text-white mx-auto">
      {icon}
    </div>
    <h3 className="text-xl font-semibold">{title}</h3>
    <p className="text-muted-foreground text-sm">{description}</p>
  </div>
);

const Step = ({ number, title, description }) => (
  <div className="space-y-3">
    <div className="gradient-bg w-12 h-12 rounded-full flex items-center justify-center text-white text-xl font-bold mx-auto">
      {number}
    </div>
    <h3 className="text-lg font-semibold">{title}</h3>
    <p className="text-muted-foreground text-sm">{description}</p>
  </div>
);

export default HomePage;
