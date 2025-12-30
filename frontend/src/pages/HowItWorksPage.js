import React from 'react';
import DynamicLegalPage from '../components/DynamicLegalPage';

const HowItWorksPage = () => {
  return (
    <DynamicLegalPage
      pageKey="how_it_works"
      fallbackTitle="How It Works"
      fallbackContent="<h1>How BidVex Works</h1><p>Loading content...</p>"
    />
  );
};

export default HowItWorksPage;
