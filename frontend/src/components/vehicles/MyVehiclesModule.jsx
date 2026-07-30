/**
 * iter428 — My Vehicles Module
 *
 * Reusable module extracted from `pages/vehicles/MyVehicleListingsPage.js`
 * so it can be mounted inside `/vehicle-dashboard`. Renders the dealer's
 * own vehicle listings as a card grid with filter tabs, action buttons
 * (Edit / Duplicate / Retire) and an empty-state CTA.
 *
 * Backing endpoints:
 *   GET   /api/vehicles/my/listings
 *   POST  /api/vehicles/{id}/duplicate    (iter428)
 *   POST  /api/vehicles/{id}/retire       (iter428)
 *   GET   /api/vehicle-sellers/me
 *
 * All copy comes from `locales/{en,fr}.json` under `vehicleListings.*`.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Car, Plus, Clock, CheckCircle, XCircle, Eye,
  DollarSign, TrendingUp, Edit, Copy, Archive,
} from 'lucide-react';

import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { extractErrorMessage } from '../../utils/errorHandler';

import SafeImage from '../SafeImage';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';

const API = API_BASE;

const formatPrice = (price) => {
  const n = Number.isFinite(Number(price)) ? Number(price) : 0;
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 0,
  }).format(n);
};

/* ---------------------------- status pill ------------------------------- */

const STATUS_STYLE = {
  draft:            { color: 'bg-slate-500',  Icon: Edit },
  pending_approval: { color: 'bg-yellow-500', Icon: Clock },
  approved:         { color: 'bg-blue-500',   Icon: CheckCircle },
  active:           { color: 'bg-green-500',  Icon: TrendingUp },
  ended:            { color: 'bg-slate-500',  Icon: Clock },
  sold:             { color: 'bg-purple-500', Icon: DollarSign },
  retired:          { color: 'bg-slate-600',  Icon: Archive },
  rejected:         { color: 'bg-red-500',    Icon: XCircle },
  cancelled:        { color: 'bg-red-500',    Icon: XCircle },
  expired:          { color: 'bg-slate-500',  Icon: Clock },
};

const StatusPill = ({ status, t }) => {
  const meta = STATUS_STYLE[status] || STATUS_STYLE.draft;
  const Icon = meta.Icon;
  return (
    <Badge
      className={`${meta.color} gap-1 text-white whitespace-nowrap`}
      data-testid={`my-vehicle-status-pill-${status}`}
    >
      <Icon className="h-3 w-3" />
      {t(`vehicleListings.status.${status}`, { defaultValue: status })}
    </Badge>
  );
};

/* ---------------------------- card ------------------------------------- */

const MyVehicleCard = ({ listing, t, onEdit, onDuplicate, onRetire }) => {
  const mainImage = listing.media?.find((m) => m.category === 'front')?.url
    || listing.media?.[0]?.url
    || listing.images?.[0]?.url
    || (Array.isArray(listing.images) ? listing.images[0] : null);

  const canEdit = ['draft', 'rejected'].includes(listing.status);
  const canRetire = listing.status !== 'sold' && listing.status !== 'retired';

  return (
    <Card
      className="overflow-hidden hover:shadow-lg transition-shadow flex flex-col"
      data-testid={`my-vehicle-card-${listing.id}`}
    >
      {/* Photo thumbnail */}
      <div className="w-full aspect-[16/10] bg-slate-100 flex-shrink-0">
        {mainImage ? (
          <SafeImage src={mainImage} alt="" className="w-full h-full object-cover" />
        ) : (
          <div
            className="w-full h-full flex items-center justify-center"
            data-testid={`my-vehicle-thumb-empty-${listing.id}`}
          >
            <Car className="h-10 w-10 text-slate-300" />
          </div>
        )}
      </div>

      <CardContent className="flex-1 p-4 flex flex-col">
        {/* Title + status pill */}
        <div className="flex items-start justify-between gap-2 min-w-0">
          <h3
            className="font-semibold text-base sm:text-lg leading-snug line-clamp-2 break-words"
            data-testid={`my-vehicle-title-${listing.id}`}
          >
            {listing.year} {listing.make} {listing.model}
          </h3>
          <StatusPill status={listing.status} t={t} />
        </div>

        {/* Stats row */}
        <div
          className="flex items-center flex-wrap gap-x-3 gap-y-1.5 mt-3 text-xs sm:text-sm text-slate-500"
          data-testid={`my-vehicle-stats-${listing.id}`}
        >
          <span className="flex items-center gap-1" data-testid={`my-vehicle-starting-bid-${listing.id}`}>
            <DollarSign className="h-3.5 w-3.5" />
            {t('vehicleListings.startingBid')}: {formatPrice(listing.starting_price)}
          </span>
          <span className="flex items-center gap-1" data-testid={`my-vehicle-bids-${listing.id}`}>
            <TrendingUp className="h-3.5 w-3.5" />
            {t('vehicleListings.bids', { count: listing.bid_count || 0 })}
          </span>
          <span className="flex items-center gap-1" data-testid={`my-vehicle-views-${listing.id}`}>
            <Eye className="h-3.5 w-3.5" />
            {t('vehicleListings.views', { count: listing.views_count || 0 })}
          </span>
        </div>

        {/* Action buttons */}
        <div className="mt-4 flex flex-wrap gap-2 pt-3 border-t border-slate-100">
          <Button
            size="sm"
            variant="outline"
            onClick={() => onEdit(listing)}
            disabled={!canEdit}
            className="flex-1 min-w-[90px]"
            data-testid={`my-vehicle-edit-${listing.id}`}
          >
            <Edit className="h-3.5 w-3.5 mr-1" />
            {t('vehicleListings.edit')}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onDuplicate(listing)}
            className="flex-1 min-w-[90px]"
            data-testid={`my-vehicle-duplicate-${listing.id}`}
          >
            <Copy className="h-3.5 w-3.5 mr-1" />
            {t('vehicleListings.duplicate')}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onRetire(listing)}
            disabled={!canRetire}
            className="flex-1 min-w-[90px] text-rose-600 border-rose-200 hover:bg-rose-50 hover:text-rose-700 disabled:text-slate-400 disabled:border-slate-200"
            data-testid={`my-vehicle-retire-${listing.id}`}
          >
            <Archive className="h-3.5 w-3.5 mr-1" />
            {t('vehicleListings.retire')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

/* ---------------------------- module ----------------------------------- */

const TABS = [
  { id: 'all',     labelKey: 'vehicleListings.allVehicles' },
  { id: 'active',  labelKey: 'vehicleListings.activeTab'   },
  { id: 'draft',   labelKey: 'vehicleListings.draftTab'    },
  { id: 'sold',    labelKey: 'vehicleListings.soldTab'     },
  { id: 'retired', labelKey: 'vehicleListings.retiredTab'  },
];

const matchTab = (tab, status) => {
  if (tab === 'all') return true;
  if (tab === 'active')  return ['active', 'approved', 'pending_approval'].includes(status);
  if (tab === 'draft')   return ['draft', 'rejected'].includes(status);
  if (tab === 'sold')    return status === 'sold';
  if (tab === 'retired') return ['retired', 'cancelled', 'expired', 'ended'].includes(status);
  return true;
};

const MyVehiclesModule = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token } = useAuth();

  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sellerProfile, setSellerProfile] = useState(null);
  const [activeTab, setActiveTab] = useState('all');
  const [retireTarget, setRetireTarget] = useState(null);
  const [busy, setBusy] = useState(false);

  const fetchData = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      const [sellerResp, listingsResp] = await Promise.all([
        axios
          .get(`${API}/vehicle-sellers/me`, { headers: { Authorization: `Bearer ${token}` } })
          .catch(() => null),
        axios.get(`${API}/vehicles/my/listings`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      setSellerProfile(sellerResp?.data || null);
      setListings(listingsResp.data.listings || []);
    } catch (err) {
      toast.error(extractErrorMessage(err) || t('vehicleListings.toastLoadFailed'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filtered = listings.filter((l) => matchTab(activeTab, l.status));

  const counts = TABS.reduce((acc, tab) => {
    acc[tab.id] = listings.filter((l) => matchTab(tab.id, l.status)).length;
    return acc;
  }, {});

  const handleEdit = (listing) => {
    navigate(`/vehicle-auctions/edit/${listing.id}`);
  };

  const handleDuplicate = async (listing) => {
    if (busy) return;
    setBusy(true);
    try {
      await axios.post(
        `${API}/vehicles/${listing.id}/duplicate`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(t('vehicleListings.toastDuplicated'));
      await fetchData();
      setActiveTab('draft');
    } catch (err) {
      toast.error(extractErrorMessage(err) || t('vehicleListings.toastDuplicateFailed'));
    } finally {
      setBusy(false);
    }
  };

  const handleRetireConfirm = async () => {
    if (!retireTarget || busy) return;
    setBusy(true);
    try {
      await axios.post(
        `${API}/vehicles/${retireTarget.id}/retire`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(t('vehicleListings.toastRetired'));
      setRetireTarget(null);
      await fetchData();
    } catch (err) {
      toast.error(extractErrorMessage(err) || t('vehicleListings.toastRetireFailed'));
    } finally {
      setBusy(false);
    }
  };

  /* ------------------------ render --------------------------------- */

  if (loading) {
    return (
      <div
        className="flex flex-col items-center justify-center py-12"
        data-testid="my-vehicles-loading"
      >
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mb-3" />
        <p className="text-sm text-slate-500">{t('vehicleListings.loading')}</p>
      </div>
    );
  }

  const canCreate = sellerProfile?.verification_status === 'approved';
  const isEmpty = listings.length === 0;

  return (
    <section data-testid="my-vehicles-module">
      {/* Filter tabs */}
      <div
        className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1 mb-5"
        style={{ WebkitOverflowScrolling: 'touch' }}
        data-testid="my-vehicles-tabs"
        role="tablist"
      >
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          const count = counts[tab.id] ?? 0;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-shrink-0 min-w-[90px] px-3 py-2 rounded-lg text-xs sm:text-sm font-semibold whitespace-nowrap transition-colors ${
                isActive
                  ? 'bg-[#0055FF] text-white shadow-sm'
                  : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 hover:bg-slate-50'
              }`}
              data-testid={`my-vehicles-tab-${tab.id}`}
            >
              {t(tab.labelKey)} ({count})
            </button>
          );
        })}
      </div>

      {/* Empty state / tab empty / grid */}
      {isEmpty ? (
        <Card className="p-10 text-center" data-testid="my-vehicles-empty">
          <Car className="h-14 w-14 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg sm:text-xl font-semibold mb-2">
            {t('vehicleListings.noVehicles')}
          </h3>
          <p className="text-sm text-slate-500 mb-6 max-w-md mx-auto">
            {t('vehicleListings.noVehiclesSubtitle')}
          </p>
          {canCreate ? (
            <Button
              onClick={() => navigate('/vehicle-auctions/create')}
              className="min-h-[44px]"
              data-testid="my-vehicles-create-first-cta"
            >
              <Plus className="h-4 w-4 mr-2" />
              {t('vehicleListings.createFirst')}
            </Button>
          ) : (
            <p
              className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 inline-block"
              data-testid="my-vehicles-verification-pending"
            >
              {t('vehicleListings.verificationPending')}
            </p>
          )}
        </Card>
      ) : filtered.length === 0 ? (
        <Card className="p-10 text-center" data-testid="my-vehicles-tab-empty">
          <Car className="h-14 w-14 text-slate-300 mx-auto mb-4" />
          <p className="text-sm text-slate-500">{t('vehicleListings.noVehiclesInTab')}</p>
        </Card>
      ) : (
        <div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
          data-testid="my-vehicles-grid"
        >
          {filtered.map((listing) => (
            <MyVehicleCard
              key={listing.id}
              listing={listing}
              t={t}
              onEdit={handleEdit}
              onDuplicate={handleDuplicate}
              onRetire={(l) => setRetireTarget(l)}
            />
          ))}
        </div>
      )}

      {/* Retire confirmation dialog */}
      <AlertDialog open={!!retireTarget} onOpenChange={(v) => { if (!v) setRetireTarget(null); }}>
        <AlertDialogContent data-testid="my-vehicles-retire-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>{t('vehicleListings.confirmRetireTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {retireTarget && (
                <span
                  className="block font-medium text-slate-900 dark:text-slate-100 mb-2"
                  data-testid="my-vehicles-retire-dialog-target"
                >
                  {retireTarget.year} {retireTarget.make} {retireTarget.model}
                </span>
              )}
              {t('vehicleListings.confirmRetireBody')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="my-vehicles-retire-cancel">
              {t('vehicleListings.confirmRetireCancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRetireConfirm}
              disabled={busy}
              className="bg-rose-600 hover:bg-rose-700 text-white"
              data-testid="my-vehicles-retire-confirm"
            >
              {t('vehicleListings.confirmRetireConfirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
};

export default MyVehiclesModule;
