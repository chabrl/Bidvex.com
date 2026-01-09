import React from 'react';
import { useCurrency } from '../contexts/CurrencyContext';
import { Button } from './ui/button';
import { DollarSign } from 'lucide-react';

/**
 * CurrencyToggle - Global USD/CAD currency switcher for navbar
 * Features:
 * - Clean toggle design
 * - Persists preference across sessions
 * - Real-time price updates site-wide
 */
const CurrencyToggle = ({ className = '' }) => {
  const { currency, toggleCurrency, exchangeRate } = useCurrency();

  return (
    <div className={`flex items-center ${className}`}>
      <Button
        variant="ghost"
        size="sm"
        onClick={toggleCurrency}
        className="flex items-center gap-1.5 px-3 py-2 rounded-full border-2 border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all duration-200"
        data-testid="currency-toggle"
        title={`Switch to ${currency === 'USD' ? 'CAD' : 'USD'} (Rate: 1 USD = ${exchangeRate} CAD)`}
      >
        <DollarSign className="h-4 w-4 text-green-600" />
        <div className="flex items-center gap-0.5">
          <span 
            className={`text-sm font-bold transition-all duration-200 ${
              currency === 'USD' 
                ? 'text-blue-600 dark:text-blue-400' 
                : 'text-slate-400 dark:text-slate-500'
            }`}
          >
            USD
          </span>
          <span className="text-slate-300 dark:text-slate-600 mx-0.5">/</span>
          <span 
            className={`text-sm font-bold transition-all duration-200 ${
              currency === 'CAD' 
                ? 'text-red-600 dark:text-red-400' 
                : 'text-slate-400 dark:text-slate-500'
            }`}
          >
            CAD
          </span>
        </div>
      </Button>
    </div>
  );
};

export default CurrencyToggle;
