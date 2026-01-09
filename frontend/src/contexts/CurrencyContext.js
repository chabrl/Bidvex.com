import React, { createContext, useContext, useState, useEffect } from 'react';

const CurrencyContext = createContext(null);

// Default exchange rate: 1 USD = 1.42 CAD
const DEFAULT_EXCHANGE_RATE = 1.42;

export const CurrencyProvider = ({ children }) => {
  const [currency, setCurrency] = useState(() => {
    return localStorage.getItem('preferred_currency') || 'USD';
  });
  
  const [exchangeRate, setExchangeRate] = useState(() => {
    const stored = localStorage.getItem('exchange_rate');
    return stored ? parseFloat(stored) : DEFAULT_EXCHANGE_RATE;
  });

  // Persist currency preference
  useEffect(() => {
    localStorage.setItem('preferred_currency', currency);
  }, [currency]);

  // Toggle between USD and CAD
  const toggleCurrency = () => {
    setCurrency(prev => prev === 'USD' ? 'CAD' : 'USD');
  };

  // Set specific currency
  const setPreferredCurrency = (newCurrency) => {
    if (['USD', 'CAD'].includes(newCurrency)) {
      setCurrency(newCurrency);
    }
  };

  // Update exchange rate (can be called from seller-defined rates)
  const updateExchangeRate = (rate) => {
    if (rate && rate > 0) {
      setExchangeRate(rate);
      localStorage.setItem('exchange_rate', rate.toString());
    }
  };

  // Convert amount based on current currency
  const convertPrice = (amountUSD, sellerRate = null) => {
    const rate = sellerRate || exchangeRate;
    if (currency === 'CAD') {
      return amountUSD * rate;
    }
    return amountUSD;
  };

  // Format price with currency symbol
  const formatPrice = (amountUSD, sellerRate = null, decimals = 2) => {
    const convertedAmount = convertPrice(amountUSD, sellerRate);
    const symbol = currency === 'CAD' ? 'CA$' : '$';
    return `${symbol}${convertedAmount.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    })}`;
  };

  // Get currency symbol
  const getCurrencySymbol = () => {
    return currency === 'CAD' ? 'CA$' : '$';
  };

  return (
    <CurrencyContext.Provider value={{
      currency,
      exchangeRate,
      toggleCurrency,
      setPreferredCurrency,
      updateExchangeRate,
      convertPrice,
      formatPrice,
      getCurrencySymbol,
      isCAD: currency === 'CAD',
      isUSD: currency === 'USD'
    }}>
      {children}
    </CurrencyContext.Provider>
  );
};

export const useCurrency = () => {
  const context = useContext(CurrencyContext);
  if (!context) {
    throw new Error('useCurrency must be used within a CurrencyProvider');
  }
  return context;
};

export default CurrencyContext;
