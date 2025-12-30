import React from 'react';
import DynamicLegalPage from '../components/DynamicLegalPage';

const TermsOfServicePage = () => {
  return (
    <DynamicLegalPage
      pageKey="terms_of_service"
      fallbackTitle="Terms & Conditions"
      fallbackContent="<h1>Terms of Service</h1><p>Loading content...</p>"
    />
  );
};

export default TermsOfServicePage;
