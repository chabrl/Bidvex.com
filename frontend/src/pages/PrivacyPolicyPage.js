import React from 'react';
import { useTranslation } from 'react-i18next';
import { PrivacyEN, PrivacyFR } from '../components/legal';

const PrivacyPolicyPage = () => {
  const { i18n } = useTranslation();
  const currentLanguage = i18n.language || 'en';
  
  // Render the appropriate language component
  if (currentLanguage === 'fr' || currentLanguage.startsWith('fr')) {
    return <PrivacyFR />;
  }
  
  return <PrivacyEN />;
};

export default PrivacyPolicyPage;
