import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import { AuthProvider } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';
import { QueryProvider } from './providers/QueryProvider';
import './i18n';

// ─── Sentry (optional) ───────────────────────────────────────────────
// Initialised only when REACT_APP_SENTRY_DSN env var is set.
import * as Sentry from '@sentry/react';

if (process.env.REACT_APP_SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.REACT_APP_SENTRY_DSN,
    tracesSampleRate: Number(process.env.REACT_APP_SENTRY_TRACES_SAMPLE_RATE || 0.1),
    environment: process.env.REACT_APP_ENVIRONMENT || 'production',
  });
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <QueryProvider>
      <ThemeProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ThemeProvider>
    </QueryProvider>
  </React.StrictMode>
);
