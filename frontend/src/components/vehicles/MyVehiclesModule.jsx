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
 * Bilingual via `useTranslation()` with keys under `vehicleListings.*`.
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

const STATUS_META = {
  draft:            { color: 'bg-slate-500',  Icon: Edit,       en: 'Draft',            fr: 'Brouillon' },
  pending_approval: { color: 'bg-yellow-500', Icon: Clock,      en: 'Pending',          fr: 'En attente' },
  approved:         { color: 'bg-blue-500',   Icon: CheckCircle,en: 'Approved',         fr: 'Approuvée' },
  active:           { color: 'bg-green-500',  Icon: TrendingUp, en: 'Active',           fr: 'Active' },
  ended:            { color: 'bg-slate-500',  Icon: Clock,      en: 'Ended',            fr: 'Terminée' },
  sold:             { color: 'bg-purple-500', Icon: DollarSign, en: 'Sold',             fr: 'Vendue' },
  retired:          { color: 'bg-slate-600',  Icon: Archive,    en: 'Retired',          fr: 'Retirée' },
  rejected:         { color: 'bg-red-500',    Icon: XCircle,    en: 'Rejected',         fr: 'Refusée' },
  cancelled:        { color: 'bg-red-500',    Icon: XCircle,    en: 'Cancelled',        fr: 'Annulée' },
  expired:          { color: 'bg-slate-500',  Icon: Clock,      en: 'Expired',          fr: 'Expirée' },
};

const StatusPill = ({ status, isFr }) => {
  const meta = STATUS_META[status] || STATUS_META.draft;
  const Icon = meta.Icon;
  return (
    <Badge className={`${meta.color} gap-1 text-white whitespace-nowrap`} data-testid={`my-vehicle-status-pill-${status}`}>
      <Icon className="h-3 w-3" />
      {isFr ? meta.fr : meta.en}
    </Badge>
  );
};

/* ---------------------------- card ------------------------------------- */

const MyVehicleCard = ({ listing, isFr, onEdit, onDuplicate, onRetire }) => {
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
          <div className="w-full h-full flex items-center justify-center" data-testid={`my-vehicle-thumb-empty-${listing.id}`}>
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
          <StatusPill status={listing.status} isFr={isFr} />
        </div>

        {/* Stats row */}
        <div
          className="flex items-center flex-wrap gap-x-3 gap-y-1.5 mt-3 text-xs sm:text-sm text-slate-500"
          data-testid={`my-vehicle-stats-${listing.id}`}
        >
          <span className="flex items-center gap-1" data-testid={`my-vehicle-starting-bid-${listing.id}`}>
            <DollarSign className="h-3.5 w-3.5" />
            {isFr ? 'Mise départ' : 'Start'}: {formatPrice(listing.starting_price)}
          </span>
          <span className="flex items-center gap-1" data-testid={`my-vehicle-bids-${listing.id}`}>
            <TrendingUp className="h-3.5 w-3.5" /> {listing.bid_count || 0} {isFr ? 'enchères' : 'bids'}
          </span>
          <span className="flex items-center gap-1" data-testid={`my-vehicle-views-${listing.id}`}>
            <Eye className="h-3.5 w-3.5" /> {listing.views_count || 0} {isFr ? 'vues' : 'views'}
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
            {isFr ? 'Modifier' : 'Edit'}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onDuplicate(listing)}
            className="flex-1 min-w-[90px]"
            data-testid={`my-vehicle-duplicate-${listing.id}`}
          >
            <Copy className="h-3.5 w-3.5 mr-1" />
            {isFr ? 'Dupliquer' : 'Duplicate'}
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
            {isFr ? 'Retirer' : 'Retire'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

/* ---------------------------- module ----------------------------------- */

const TABS = [
  { id: 'all',      en: 'All',      fr: 'Tous' },
  { id: 'active',   en: 'Active',   fr: 'Actifs' },
  { id: 'draft',    en: 'Draft',    fr: 'Brouillons' },
  { id: 'sold',     en: 'Sold',     fr: 'Vendus' },
  { id: 'retired',  en: 'Retired',  fr: 'Retirés' },
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
  const { i18n } = useTranslation();
  const isFr = (i18n.language || '').toLowerCase().startsWith('fr');
  const { token } = useAuth();

  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sellerProfile, setSellerProfile] = useState(null);
  const [activeTab, setActiveTab] = useState('all');
  const [retireTarget, setRetireTarget] = useState(null); // {id, year, make, model}
  const [busy, setBusy] = useState(false);

  const fetchData = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      const [sellerResp, listingsResp] = await Promise.all([
        axios.get(`${API}/vehicle-sellers/me`, { headers: { Authorization: `Bearer ${token}` } }).catch(() => null),
        axios.get(`${API}/vehicles/my/listings`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      setSellerProfile(sellerResp?.data || null);
      setListings(listingsResp.data.listings || []);
    } catch (err) {
      toast.error(extractErrorMessage(err) || (isFr ? 'Échec du chargement' : 'Failed to load listings'));
    } finally {
      setLoading(false);
    }
  }, [token, isFr]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filtered = listings.filter((l) => matchTab(activeTab, l.status));

  const counts = TABS.reduce((acc, t) => {
    acc[t.id] = listings.filter((l) => matchTab(t.id, l.status)).length;
    return acc;
  }, {});

  const handleEdit = (listing) => {
    navigate(`/vehicle-auctions/edit/${listing.id}`);
  };

  const handleDuplicate = async (listing) => {
    if (busy) return;
    setBusy(true);
    try {
      const resp = await axios.post(
        `${API}/vehicles/${listing.id}/duplicate`,
        {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(isFr ? 'Annonce dupliquée en tant que brouillon' : 'Listing duplicated as a new draft');
      await fetchData();
      // Optional: jump to the edit page for the new draft
      if (resp.data?.id) {
        // Don't auto-navigate — user may want to duplicate several. Just switch tab.
        setActiveTab('draft');
      }
    } catch (err) {
      toast.error(extractErrorMessage(err) || (isFr ? 'Échec de la duplication' : 'Failed to duplicate listing'));
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
      toast.success(isFr ? 'Annonce retirée' : 'Listing retired');
      setRetireTarget(null);
      await fetchData();
    } catch (err) {
      toast.error(extractErrorMessage(err) || (isFr ? 'Échec du retrait' : 'Failed to retire listing'));
    } finally {
      setBusy(false);
    }
  };

  /* ------------------------ render --------------------------------- */

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12" data-testid="my-vehicles-loading">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
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
              {isFr ? tab.fr : tab.en} ({count})
            </button>
          );
        })}
      </div>

      {/* Empty state or grid */}
      {isEmpty ? (
        <Card className="p-10 text-center" data-testid="my-vehicles-empty">
          <Car className="h-14 w-14 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg sm:text-xl font-semibold mb-2">
            {isFr ? 'Aucune annonce pour le moment' : 'No listings yet'}
          </h3>
          <p className="text-sm text-slate-500 mb-6 max-w-md mx-auto">
            {isFr
              ? 'Commencez à vendre en publiant votre premier véhicule aux enchères.'
              : 'Get started by publishing your first vehicle for auction.'}
          </p>
          {canCreate ? (
            <Button
              onClick={() => navigate('/vehicle-auctions/create')}
              className="min-h-[44px]"
              data-testid="my-vehicles-create-first-cta"
            >
              <Plus className="h-4 w-4 mr-2" />
              {isFr ? 'Créer ma première annonce' : 'Create Your First Listing'}
            </Button>
          ) : (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 inline-block">
              {isFr
                ? 'La vérification concessionnaire doit être approuvée avant de créer une annonce.'
                : 'Dealer verification must be approved before creating a listing.'}
            </p>
          )}
        </Card>
      ) : filtered.length === 0 ? (
        <Card className="p-10 text-center" data-testid="my-vehicles-tab-empty">
          <Car className="h-14 w-14 text-slate-300 mx-auto mb-4" />
          <p className="text-sm text-slate-500">
            {isFr ? `Aucune annonce dans cette catégorie.` : `No listings in this tab.`}
          </p>
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
              isFr={isFr}
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
            <AlertDialogTitle>
              {isFr ? 'Retirer cette annonce ?' : 'Retire this listing?'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {retireTarget && (
                <span className="block font-medium text-slate-900 dark:text-slate-100 mb-2">
                  {retireTarget.year} {retireTarget.make} {retireTarget.model}
                </span>
              )}
              {isFr
                ? "L'annonce sera archivée et retirée du marché public. Vous pourrez toujours la consulter sous l'onglet Retirés, mais elle ne pourra pas être réactivée. Les annonces vendues ne peuvent pas être retirées."
                : 'The listing will be archived and removed from the public marketplace. You can still view it under the Retired tab, but it cannot be reactivated. Sold listings cannot be retired.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="my-vehicles-retire-cancel">
              {isFr ? 'Annuler' : 'Cancel'}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRetireConfirm}
              disabled={busy}
              className="bg-rose-600 hover:bg-rose-700 text-white"
              data-testid="my-vehicles-retire-confirm"
            >
              {isFr ? 'Oui, la retirer' : 'Yes, retire it'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
};

export default MyVehiclesModule;
