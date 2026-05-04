/**
 * CurrencyBadge — iter179 FIX 5
 * =================================
 * Small bilingual currency chip to display next to prices on cards / detail pages.
 * Blue for CAD, green for USD.
 */
import React from 'react';

const CurrencyBadge = ({ currency = 'CAD', className = '', size = 'sm', testid = 'currency-badge' }) => {
  const code = (currency || 'CAD').toUpperCase();
  const isUsd = code === 'USD';
  const sizeClass = size === 'xs' ? 'text-[10px] px-1.5 py-0' : 'text-xs px-2 py-0.5';
  return (
    <span
      data-testid={testid}
      className={`inline-flex items-center font-bold rounded-full ${sizeClass} ${
        isUsd
          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
          : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
      } ${className}`}
    >
      {code}
    </span>
  );
};

export default CurrencyBadge;
