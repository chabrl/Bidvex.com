/**
 * <MoneyLabel amount currency /> — single source of truth for price rendering.
 *
 * Spec rule: "Every price displayed to users must include the currency label —
 * never display a bare $ symbol."  e.g. $500.00 CAD or $500.00 USD.
 */
import React from 'react';

const formatNumber = (n) =>
  new Intl.NumberFormat('en-CA', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(n) || 0);

export const MoneyLabel = ({ amount = 0, currency = 'CAD', className = '', testId }) => {
  const cur = (currency || 'CAD').toUpperCase();
  return (
    <span className={className} data-testid={testId || 'money-label'}>
      ${formatNumber(amount)} {cur}
    </span>
  );
};

export const formatMoney = (amount = 0, currency = 'CAD') => {
  return `$${formatNumber(amount)} ${(currency || 'CAD').toUpperCase()}`;
};

export default MoneyLabel;
