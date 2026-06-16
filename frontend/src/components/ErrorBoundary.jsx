import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { withTranslation } from 'react-i18next';

/**
 * iter211 — Reusable React Error Boundary
 *
 * Catches render-time exceptions in subtree and renders a calm bilingual
 * fallback UI instead of a blank page. Auto-detects EN/FR via i18next.
 *
 * Usage:
 *   <ErrorBoundary scope="listing-detail">
 *     <ListingDetailPage />
 *   </ErrorBoundary>
 *
 * The `scope` prop is logged with the error and used in `data-testid` so QA
 * can detect crashes per page.
 */
class ErrorBoundaryBase extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // eslint-disable-next-line no-console
    console.error(`[ErrorBoundary:${this.props.scope || 'unknown'}]`, error, errorInfo);
    // iter306 — Best-effort log to backend so production crashes surface in
    // the Admin Error Logs tab. Never throw from within the catch.
    try {
      const token = typeof localStorage !== 'undefined' ? localStorage.getItem('token') : null;
      const url = typeof window !== 'undefined' ? window.location.href : '';
      const ua = typeof navigator !== 'undefined' ? navigator.userAgent : '';
      const apiBase = (typeof process !== 'undefined' && process.env && process.env.REACT_APP_BACKEND_URL) || '';
      if (apiBase && typeof fetch !== 'undefined') {
        fetch(`${apiBase}/api/errors/frontend`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            error_message: String(error?.message || error || 'unknown').slice(0, 2000),
            component_stack: String(errorInfo?.componentStack || '').slice(0, 10000),
            url,
            user_agent: ua.slice(0, 500),
            scope: String(this.props.scope || '').slice(0, 100),
          }),
          // Keep silent — we don't want to await this in render
        }).catch(() => {});
      }
    } catch (_e) { /* silent */ }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  handleHome = () => {
    window.location.href = '/';
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    const { t, scope = 'page' } = this.props;
    const isFR = (this.props.i18n?.language || 'en').startsWith('fr');

    const title = isFR
      ? 'Une erreur inattendue est survenue'
      : 'Something went wrong';
    const subtitle = isFR
      ? "Cette section a rencontré un problème. Vous pouvez réessayer ou revenir à l'accueil."
      : 'This section hit a snag. You can retry or return home.';
    const retryLabel = isFR ? 'Réessayer' : 'Try again';
    const homeLabel = isFR ? "Retour à l'accueil" : 'Back to home';
    const supportLine = isFR
      ? "Si l'erreur persiste, contactez le support : support@bidvex.ca"
      : 'If the error persists, contact support: support@bidvex.ca';

    return (
      <div
        data-testid={`error-boundary-${scope}`}
        className="min-h-[400px] flex items-center justify-center px-4 py-12"
      >
        <div className="max-w-md w-full bg-white border border-rose-200 rounded-2xl shadow-sm p-8 text-center">
          <div className="flex justify-center mb-4">
            <div className="w-14 h-14 rounded-full bg-rose-50 flex items-center justify-center">
              <AlertTriangle className="w-7 h-7 text-rose-600" />
            </div>
          </div>
          <h2
            data-testid={`error-boundary-${scope}-title`}
            className="text-xl font-semibold text-slate-900 mb-2"
          >
            {title}
          </h2>
          <p
            data-testid={`error-boundary-${scope}-subtitle`}
            className="text-sm text-slate-600 mb-6 leading-relaxed"
          >
            {subtitle}
          </p>
          <div className="flex flex-col sm:flex-row gap-2 justify-center">
            <button
              data-testid={`error-boundary-${scope}-retry-btn`}
              onClick={this.handleRetry}
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              {retryLabel}
            </button>
            <button
              data-testid={`error-boundary-${scope}-home-btn`}
              onClick={this.handleHome}
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50 transition-colors"
            >
              <Home className="w-4 h-4" />
              {homeLabel}
            </button>
          </div>
          <p className="mt-6 text-xs text-slate-400">{supportLine}</p>
          {this.state.error && process.env.NODE_ENV !== 'production' && (
            <details className="mt-4 text-left text-xs text-slate-500 bg-slate-50 rounded p-3">
              <summary className="cursor-pointer">Dev details</summary>
              <pre className="mt-2 whitespace-pre-wrap break-words">
                {this.state.error?.message || String(this.state.error)}
              </pre>
            </details>
          )}
        </div>
      </div>
    );
  }
}

const ErrorBoundary = withTranslation()(ErrorBoundaryBase);
export default ErrorBoundary;
export { ErrorBoundary };
