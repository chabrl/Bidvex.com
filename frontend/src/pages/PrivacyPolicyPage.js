import React from 'react';
import DynamicLegalPage from '../components/DynamicLegalPage';

const PrivacyPolicyPage = () => {
  return (
    <DynamicLegalPage
      pageKey="privacy_policy"
      fallbackTitle="Privacy Policy"
      fallbackContent="<h1>Privacy Policy</h1><p>Loading content...</p>"
    />
  );
};

export default PrivacyPolicyPage;