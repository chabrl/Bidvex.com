import React from 'react';
import { useTranslation } from 'react-i18next';
import { TermsEN, TermsFR } from '../components/legal';

const TermsOfServicePage = () => {
  const { i18n } = useTranslation();
  const currentLanguage = i18n.language || 'en';
  
  // Render the appropriate language component
  if (currentLanguage === 'fr' || currentLanguage.startsWith('fr')) {
    return <TermsFR />;
  }
  
  return <TermsEN />;
};

export default TermsOfServicePage;
