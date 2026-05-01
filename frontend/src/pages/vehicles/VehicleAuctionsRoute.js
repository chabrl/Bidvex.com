/**
 * VehicleAuctionsRoute — iter176
 * ================================
 * Gate wrapper: checks `vehicle_auctions_enabled` feature flag.
 *   • enabled=true  → real VehicleAuctionsPage
 *   • enabled=false → VehicleComingSoonPage (Coming Soon + waitlist)
 *   • loading       → minimal centered spinner
 */
import React, { Suspense, lazy } from 'react';
import { Loader2 } from 'lucide-react';
import useFeatureFlag from '../../hooks/useFeatureFlag';

const VehicleAuctionsPage = lazy(() => import('./VehicleAuctionsPage'));
const VehicleComingSoonPage = lazy(() => import('./VehicleComingSoonPage'));

const VehicleAuctionsRoute = () => {
  const { enabled, loading } = useFeatureFlag('vehicle_auctions_enabled');

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center" data-testid="vehicle-gate-loading">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <Suspense fallback={
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    }>
      {enabled ? <VehicleAuctionsPage /> : <VehicleComingSoonPage />}
    </Suspense>
  );
};

export default VehicleAuctionsRoute;
