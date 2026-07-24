import React from 'react';

/**
 * iter387 — <SectionErrorBoundary>
 *
 * React Error Boundary designed to wrap the below-the-fold, lazy-mounted
 * homepage sections (Trending, Live Auctions, Hot Items, Featured, etc.).
 *
 * Why:
 *   After the iter386 production deploy, a runtime error inside one of
 *   the lazy sections caused the WHOLE middle of the homepage to unmount
 *   (blank white gap between hero and footer). Without an error boundary
 *   ANY throw from a lazy chunk propagates up and unmounts the closest
 *   ancestor Suspense/route — here that's the entire routed page.
 *
 * Behaviour:
 *   • On error: renders a compact fallback with the section name and a
 *     "reload page" button. Preserves the reserved `minHeight` so the
 *     CLS shape of the page is unchanged.
 *   • Logs the error + info to console (visible in DevTools + captured
 *     by any error tracker attached at window level).
 *   • Boundary is per-section so one crash never masks the entire page.
 *
 * Props:
 *   • sectionName  (string)  — displayed in the fallback for debug.
 *   • minHeight    (number)  — the same reservation used by LazyMount so
 *                              the fallback slot doesn't shift the page.
 *   • children     (node)    — the guarded subtree.
 */
export default class SectionErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // Log a compact, structured message. Rich enough for post-mortem
    // without leaking sensitive data. Downstream error trackers
    // (Sentry / GA) can hook into window.onerror or a custom listener.
    console.error(
      `[SectionErrorBoundary] "${this.props.sectionName || 'unknown'}" section crashed:`,
      error,
      '\nComponent stack:',
      info?.componentStack,
    );
    // Also emit a CustomEvent so an app-level listener (e.g. Sentry
    // adapter, or the admin analytics widget) can react. Non-fatal.
    try {
      window.dispatchEvent(
        new CustomEvent('bidvex:section-error', {
          detail: {
            section: this.props.sectionName || 'unknown',
            message: error?.message || String(error),
            stack: error?.stack,
          },
        }),
      );
    } catch (_) {
      /* dispatchEvent failures are non-critical */
    }
  }

  handleReload = () => {
    // Full reload is the safest recovery — clears any half-hydrated
    // state and re-runs the lazy import. `setState({hasError:false})`
    // alone would re-render the same broken tree.
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      const { minHeight = 320, sectionName = 'section' } = this.props;
      return (
        <div
          role="alert"
          data-testid={`section-error-${sectionName}`}
          className="w-full flex items-center justify-center py-8 px-4 bg-slate-50 dark:bg-slate-900/40 border-y border-slate-200 dark:border-slate-800"
          style={{ minHeight }}
        >
          <div className="max-w-md text-center">
            <div className="text-2xl mb-2" aria-hidden>
              <i className="fas fa-triangle-exclamation text-amber-500" />
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
              This section couldn&apos;t load right now. The rest of the page is still available.
            </p>
            <button
              type="button"
              onClick={this.handleReload}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors"
              data-testid={`section-error-reload-${sectionName}`}
            >
              <i className="fas fa-rotate-right" aria-hidden />
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
