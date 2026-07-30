/**
 * iter432 — /vehicle-auctions/my-listings redirect
 *
 * The dealer listing management surface has consolidated onto
 * `/vehicle-dashboard`. This file used to hold the full standalone
 * dealer listings page (kept intact under git history) and is now a
 * thin client-side redirect. The route is preserved so existing
 * bookmarks, marketing links, transactional emails, and any inbound
 * traffic land the user on the new hub instead of a 404.
 *
 * Per PRD (iter432): the component is NOT deleted — it simply
 * redirects. If we ever need to bring the old page back, restore from
 * git history.
 */

import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

const MyVehicleListingsPage = () => {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Preserve query string (e.g. ?tab=drafts) so downstream can honor
    // it if needed. The dashboard currently ignores it — safe no-op.
    navigate(`/vehicle-dashboard${location.search || ''}`, { replace: true });
  }, [navigate, location.search]);

  return (
    <div
      className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950"
      data-testid="my-vehicle-listings-redirect"
    >
      <div className="text-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-3" />
        <p className="text-sm text-slate-500">Redirecting to the Vehicle Dashboard…</p>
      </div>
    </div>
  );
};

export default MyVehicleListingsPage;
