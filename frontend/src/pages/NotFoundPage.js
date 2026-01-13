import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Home, Search, ArrowLeft } from 'lucide-react';

const NotFoundPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 px-4">
      <Card className="max-w-2xl w-full">
        <CardContent className="p-12 text-center space-y-6">
          {/* 404 Animation */}
          <div className="text-9xl font-bold text-primary opacity-20">404</div>
          
          {/* Error Message */}
          <div className="space-y-3">
            <h1 className="text-4xl font-bold text-foreground">
              {t('errors.pageNotFound', 'Page Not Found')}
            </h1>
            <p className="text-lg text-muted-foreground">
              {t('errors.oops', 'Oops! The page you\'re looking for doesn\'t exist.')}
            </p>
            <p className="text-sm text-muted-foreground">
              {t('errors.auctionMissing', 'The auction you\'re searching for may have ended, been removed, or the link may be incorrect.')}
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-center pt-6">
            <Button 
              size="lg"
              onClick={() => navigate('/')}
              className="gradient-button text-white"
            >
              <Home className="mr-2 h-5 w-5" />
              {t('errors.goHome', 'Go to Homepage')}
            </Button>
            <Button 
              size="lg"
              variant="outline"
              onClick={() => navigate(-1)}
            >
              <ArrowLeft className="mr-2 h-5 w-5" />
              {t('common.back', 'Go Back')}
            </Button>
            <Button 
              size="lg"
              variant="outline"
              onClick={() => navigate('/marketplace')}
            >
              <Search className="mr-2 h-5 w-5" />
              {t('hero.browseAuctions', 'Browse Auctions')}
            </Button>
          </div>

          {/* Help Text */}
          <div className="pt-8 border-t">
            <p className="text-sm text-muted-foreground">
              {t('errors.needHelp', 'Need help?')} <a href="/contact" className="text-primary hover:underline">{t('paymentSuccess.contactSupport', 'Contact Support')}</a>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default NotFoundPage;
