import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Skeleton } from './ui/skeleton';
import { Button } from './ui/button';
import { RefreshCw, WifiOff } from 'lucide-react';

/**
 * LoadingTimeout – Progressive loading state with timeout messages.
 *
 * Phase 1 (0–8s):  Skeleton placeholders
 * Phase 2 (8–15s): "Taking longer than usual…"
 * Phase 3 (15s+):  "Having trouble connecting" + Refresh button
 *
 * @param {number} rows - Number of skeleton card rows (default 4)
 * @param {string} variant - "cards" | "table" | "list"
 */
export const LoadingTimeout = ({ rows = 4, variant = 'cards' }) => {
  const { t } = useTranslation();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setElapsed(e => e + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  if (elapsed >= 15) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center px-4" data-testid="loading-timeout-error">
        <div className="text-center space-y-4 max-w-sm">
          <WifiOff className="h-12 w-12 mx-auto text-slate-400" />
          <h3 className="text-lg font-semibold text-slate-900">
            {t('loading.troubleConnecting', 'Having trouble connecting.')}
          </h3>
          <p className="text-sm text-slate-500">
            {t('loading.pleaseRefresh', 'Please refresh the page.')}
          </p>
          <Button
            onClick={() => window.location.reload()}
            className="gap-2"
            data-testid="loading-timeout-refresh-btn"
          >
            <RefreshCw className="h-4 w-4" />
            {t('loading.refresh', 'Refresh')}
          </Button>
        </div>
      </div>
    );
  }

  if (elapsed >= 8) {
    return (
      <div className="space-y-6 px-4" data-testid="loading-timeout-slow">
        <div className="text-center py-4">
          <div className="relative mx-auto w-10 h-10 mb-3">
            <div className="absolute inset-0 rounded-full border-4 border-slate-200" />
            <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-primary animate-spin" />
          </div>
          <p className="text-sm text-amber-600 font-medium">
            {t('loading.takingLonger', 'Taking longer than usual... still loading')}
          </p>
        </div>
        <SkeletonGrid rows={rows} variant={variant} />
      </div>
    );
  }

  return (
    <div className="space-y-4 px-4" data-testid="loading-timeout-skeleton">
      <SkeletonGrid rows={rows} variant={variant} />
    </div>
  );
};

const SkeletonGrid = ({ rows, variant }) => {
  if (variant === 'table') {
    return (
      <div className="space-y-3">
        <Skeleton className="h-10 w-full rounded-lg" />
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full rounded-lg" />
        ))}
      </div>
    );
  }
  if (variant === 'list') {
    return (
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex gap-4 items-center">
            <Skeleton className="h-12 w-12 rounded-xl" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-3/4 rounded" />
              <Skeleton className="h-3 w-1/2 rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }
  // cards (default)
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="bg-white rounded-xl p-3 shadow-sm ring-1 ring-slate-100 space-y-3">
          <Skeleton className="h-40 w-full rounded-lg" />
          <Skeleton className="h-4 w-3/4 rounded" />
          <Skeleton className="h-4 w-1/2 rounded" />
          <div className="flex justify-between items-center pt-2">
            <Skeleton className="h-6 w-20 rounded" />
            <Skeleton className="h-8 w-24 rounded-lg" />
          </div>
        </div>
      ))}
    </div>
  );
};

export default LoadingTimeout;
