import React from 'react';
import { Navigate } from 'react-router-dom';

/**
 * Redirect to the combined /legal page which contains the full Terms & Conditions.
 * The /legal page is the canonical, production-approved legal document.
 */
export const TermsEN = () => <Navigate to="/legal#terms" replace />;
export const TermsFR = () => <Navigate to="/legal#terms" replace />;
