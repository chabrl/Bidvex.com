import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronUp, AlertTriangle, Info, HelpCircle, CheckCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from './ui/accordion';

/**
 * BidErrorGuide Component
 * 
 * Displays a bilingual (EN/FR) guide for common bidding errors.
 * Helps users understand and resolve issues during the bidding process.
 * 
 * Props:
 * - compact (boolean): If true, shows as a small tooltip/popover. If false, shows full guide.
 * - className (string): Additional CSS classes
 */
const BidErrorGuide = ({ compact = false, className = '' }) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);

  const errorCategories = [
    {
      key: 'bidTooLow',
      icon: <AlertTriangle className="h-5 w-5 text-amber-500" />,
      severity: 'warning',
    },
    {
      key: 'minimumIncrement',
      icon: <Info className="h-5 w-5 text-blue-500" />,
      severity: 'info',
    },
    {
      key: 'networkError',
      icon: <AlertTriangle className="h-5 w-5 text-red-500" />,
      severity: 'error',
    },
    {
      key: 'invalidAmount',
      icon: <AlertTriangle className="h-5 w-5 text-orange-500" />,
      severity: 'warning',
    },
    {
      key: 'auctionEnded',
      icon: <Info className="h-5 w-5 text-gray-500" />,
      severity: 'info',
    },
    {
      key: 'insufficientFunds',
      icon: <AlertTriangle className="h-5 w-5 text-red-500" />,
      severity: 'error',
    },
    {
      key: 'unauthorized',
      icon: <Info className="h-5 w-5 text-blue-500" />,
      severity: 'info',
    },
  ];

  // Compact version (tooltip-like)
  if (compact) {
    return (
      <div className={`relative inline-block ${className}`}>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setIsOpen(!isOpen)}
          className="gap-2 text-muted-foreground hover:text-primary"
        >
          <HelpCircle className="h-4 w-4" />
          {t('bidErrorGuide.title')}
          {isOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </Button>

        {isOpen && (
          <Card className="absolute z-50 w-96 mt-2 right-0 shadow-lg border-2">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <HelpCircle className="h-4 w-4 text-primary" />
                {t('bidErrorGuide.title')}
              </CardTitle>
              <CardDescription className="text-xs">
                {t('bidErrorGuide.subtitle')}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 max-h-96 overflow-y-auto">
              {errorCategories.map((error) => (
                <div
                  key={error.key}
                  className="p-3 bg-muted/50 rounded-lg hover:bg-muted transition-colors"
                >
                  <div className="flex items-start gap-2 mb-1">
                    {error.icon}
                    <div className="flex-1">
                      <p className="text-sm font-semibold">
                        {t(`bidErrorGuide.errors.${error.key}.title`)}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {t(`bidErrorGuide.errors.${error.key}.solution`)}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
              
              <div className="pt-2 border-t">
                <p className="text-xs text-muted-foreground italic">
                  {t('bidErrorGuide.helpText')}
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    );
  }

  // Full version (accordion with detailed explanations)
  return (
    <Card className={`${className}`}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <HelpCircle className="h-5 w-5 text-primary" />
          {t('bidErrorGuide.title')}
        </CardTitle>
        <CardDescription>
          {t('bidErrorGuide.subtitle')}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Accordion type="single" collapsible className="w-full">
          {errorCategories.map((error, index) => (
            <AccordionItem key={error.key} value={`item-${index}`}>
              <AccordionTrigger className="hover:no-underline">
                <div className="flex items-center gap-3 text-left">
                  {error.icon}
                  <div className="flex-1">
                    <p className="font-semibold text-sm">
                      {t(`bidErrorGuide.errors.${error.key}.title`)}
                    </p>
                  </div>
                  <Badge 
                    variant={error.severity === 'error' ? 'destructive' : 'secondary'}
                    className="text-xs"
                  >
                    {error.severity}
                  </Badge>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-3 pt-2 pl-8">
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">
                      {t(`bidErrorGuide.errors.${error.key}.description`)}
                    </p>
                  </div>
                  
                  <div className="bg-green-50 dark:bg-green-900/20 p-3 rounded-lg border border-green-200 dark:border-green-800">
                    <div className="flex items-start gap-2">
                      <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="text-xs font-semibold text-green-800 dark:text-green-200 mb-1">
                          Solution:
                        </p>
                        <p className="text-xs text-green-700 dark:text-green-300">
                          {t(`bidErrorGuide.errors.${error.key}.solution`)}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>

        <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
          <p className="text-sm text-blue-800 dark:text-blue-200 flex items-start gap-2">
            <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <span>{t('bidErrorGuide.helpText')}</span>
          </p>
        </div>
      </CardContent>
    </Card>
  );
};

export default BidErrorGuide;
