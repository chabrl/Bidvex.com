import API_BASE from '../../config';
import { extractErrorMessage } from '../../utils/errorHandler';
/**
 * My Vehicle Listings Page — iter303 Directive 2
 *
 * Full responsive overhaul:
 *   • Mobile (≤640px) — single column cards, stacked content,
 *     16:9 thumbnails, horizontally scrollable tabs, stacked header
 *     buttons + 2×2 stats grid, VIN tag truncated.
 *   • Tablet (640px–1024px) — two-column card grid with 40/60 split
 *     (image left, content right), inline header buttons, full
 *     stats row.
 *   • Desktop (≥1024px) — three-column card grid (image top, content
 *     below). All controls inline.
 */

import React, { useState, useEffect, useCallback } from 'react';
import SafeImage from '../../components/SafeImage';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import {
  Car, Plus, Clock, CheckCircle, XCircle, AlertTriangle, Eye,
  DollarSign, TrendingUp, Edit, Trash2, MoreVertical, Layers,
  BookmarkPlus, ShieldAlert, ArrowRight,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu';
import ListingChangeRequestModal from '../../components/listings/ListingChangeRequestModal';

const API = API_BASE;

const formatPrice = (price) => {
  const _n = Number.isFinite(Number(price)) ? Number(price) : 0;
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 0,
  }).format(_n);
};

const getStatusBadge = (status, isFr) => {
  const labels = {
    draft:            { en: 'Draft',            fr: 'Brouillon' },
    pending_approval: { en: 'Pending Approval', fr: 'En attente' },
    approved:         { en: 'Approved',         fr: 'Approuvée' },
    active:           { en: 'Active',           fr: 'Active' },
    ended:            { en: 'Ended',            fr: 'Terminée' },
    sold:             { en: 'Sold',             fr: 'Vendue' },
    rejected:         { en: 'Rejected',         fr: 'Refusée' },
    cancelled:        { en: 'Cancelled',        fr: 'Annulée' },
  };
  const colors = {
    draft:            'bg-slate-500',
    pending_approval: 'bg-yellow-500',
    approved:         'bg-blue-500',
    active:           'bg-green-500',
    ended:            'bg-slate-500',
    sold:             'bg-purple-500',
    rejected:         'bg-red-500',
    cancelled:        'bg-red-500',
  };
  const icons = {
    draft:            Edit,
    pending_approval: Clock,
    approved:         CheckCircle,
    active:           TrendingUp,
    ended:            Clock,
    sold:             DollarSign,
    rejected:         XCircle,
    cancelled:        XCircle,
  };
  const Icon = icons[status] || Edit;
  const label = labels[status] || labels.draft;
  return (
    <Badge className={`${colors[status] || 'bg-slate-500'} gap-1 text-white whitespace-nowrap`}>
      <Icon className="h-3 w-3" />
      {isFr ? label.fr : label.en}
    </Badge>
  );
};

const VehicleListingCard = ({ listing, onView, onEdit, onPromote, onDeleteDraft, isFr = false }) => {
  const [modal, setModal] = useState({ open: false, type: 'delete' });
  const [scheduleTime, setScheduleTime] = useState('');
  const [vinExpanded, setVinExpanded] = useState(false);
  const mainImage = listing.media?.find((m) => m.category === 'front')?.url
    || listing.media?.[0]?.url
    || listing.images?.[0]?.url
    || (Array.isArray(listing.images) ? listing.images[0] : null);
  const isDraft = listing.status === 'draft';
  const isMultiLot = listing._kind === 'multi_lot';

  return (
    <Card
      className="overflow-hidden hover:shadow-lg transition-shadow flex flex-col sm:flex-row lg:flex-col w-full"
      data-testid={`vehicle-listing-card-${listing.id}`}
    >
      {/* Image — full width on mobile, 40% width on tablet, full width again on desktop */}
      <div className="w-full sm:w-2/5 lg:w-full aspect-[16/9] sm:aspect-[4/3] lg:aspect-[16/10] bg-slate-100 flex-shrink-0">
        {mainImage ? (
          <SafeImage src={mainImage} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center" data-testid={`vehicle-listing-image-empty-${listing.id}`}>
            {isMultiLot
              ? <Layers className="h-10 w-10 sm:h-12 sm:w-12 text-slate-300" />
              : <Car className="h-10 w-10 sm:h-12 sm:w-12 text-slate-300" />}
          </div>
        )}
      </div>

      {/* Content — adapts to layout */}
      <CardContent className="flex-1 p-3 sm:p-4 w-full sm:w-3/5 lg:w-full min-w-0">
        <div className="flex items-start justify-between gap-2 min-w-0">
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-base sm:text-lg leading-snug line-clamp-2 break-words" data-testid={`vehicle-listing-title-${listing.id}`}>
              {listing.year} {listing.make} {listing.model}
            </h3>
            <p className="text-xs sm:text-sm text-slate-500 line-clamp-1 mt-0.5">{listing.title}</p>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="flex-shrink-0 h-9 w-9 p-0" data-testid={`vehicle-card-menu-${listing.id}`}>
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onView(listing.id)} data-testid={`vehicle-card-view-${listing.id}`}>
                <Eye className="h-4 w-4 mr-2" /> {isFr ? 'Voir' : 'View'}
              </DropdownMenuItem>
              {isDraft && !isMultiLot && (
                <DropdownMenuItem onClick={() => onEdit(listing.id)}>
                  <Edit className="h-4 w-4 mr-2" /> {isFr ? 'Modifier' : 'Edit'}
                </DropdownMenuItem>
              )}
              {isDraft && onPromote && (
                <DropdownMenuItem
                  onClick={() => onPromote(listing.id, 'live')}
                  data-testid={`vehicle-promote-live-${listing.id}`}
                  className="text-emerald-700 focus:text-emerald-800"
                >
                  <CheckCircle className="h-4 w-4 mr-2" /> {isFr ? 'Mettre en ligne' : 'Go Live Now'}
                </DropdownMenuItem>
              )}
              {isDraft && onDeleteDraft && (
                <DropdownMenuItem
                  onClick={() => onDeleteDraft(listing.id)}
                  data-testid={`vehicle-delete-draft-${listing.id}`}
                  className="text-rose-600 focus:text-rose-700"
                >
                  <Trash2 className="h-4 w-4 mr-2" /> {isFr ? 'Supprimer le brouillon' : 'Delete Draft'}
                </DropdownMenuItem>
              )}
              {!isDraft && (
                <DropdownMenuItem
                  onClick={() => setModal({ open: true, type: 'edit' })}
                  data-testid={`vehicle-request-edit-${listing.id}`}
                >
                  <Edit className="h-4 w-4 mr-2" />
                  {isFr ? 'Demander une modification' : 'Edit Listing'}
                </DropdownMenuItem>
              )}
              {!isDraft && (
                <DropdownMenuItem
                  onClick={() => setModal({ open: true, type: 'delete' })}
                  data-testid={`vehicle-request-delete-${listing.id}`}
                  className="text-rose-600 focus:text-rose-700"
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  {isFr ? 'Demande de suppression' : 'Request Deletion'}
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Status + VIN row */}
        <div className="flex items-center flex-wrap gap-2 mt-3">
          {getStatusBadge(listing.status, isFr)}
          {listing.vin && (
            <button
              type="button"
              onClick={() => setVinExpanded((v) => !v)}
              className="text-[11px] sm:text-xs text-slate-600 bg-slate-100 hover:bg-slate-200 px-2 py-0.5 rounded-full max-w-[140px] truncate"
              title={listing.vin}
              data-testid={`vehicle-vin-tag-${listing.id}`}
            >
              {vinExpanded ? `VIN: ${listing.vin}` : `VIN: …${String(listing.vin).slice(-6)}`}
            </button>
          )}
        </div>

        {/* Schedule promotion row (drafts only) */}
        {isDraft && onPromote && (
          <div className="mt-3 flex flex-wrap items-center gap-2" data-testid={`vehicle-schedule-row-${listing.id}`}>
            <span className="text-xs text-slate-500 w-full sm:w-auto">{isFr ? 'Programmer :' : 'Schedule:'}</span>
            <input
              type="datetime-local"
              value={scheduleTime}
              onChange={(e) => setScheduleTime(e.target.value)}
              className="text-xs sm:text-sm border rounded px-2 py-2 min-h-[40px] flex-1 sm:flex-none min-w-0"
              data-testid={`vehicle-schedule-input-${listing.id}`}
            />
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                if (!scheduleTime) return;
                onPromote(listing.id, 'schedule', new Date(scheduleTime).toISOString());
              }}
              disabled={!scheduleTime}
              className="min-h-[40px]"
              data-testid={`vehicle-schedule-promote-${listing.id}`}
            >
              <Clock className="h-3 w-3 mr-1" /> {isFr ? 'Programmer' : 'Schedule'}
            </Button>
          </div>
        )}

        {/* Stats row — wraps gracefully */}
        <div className="flex items-center flex-wrap gap-x-3 gap-y-1.5 mt-3 text-xs sm:text-sm text-slate-500" data-testid={`vehicle-stats-row-${listing.id}`}>
          <span className="flex items-center gap-1">
            <Eye className="h-3.5 w-3.5 sm:h-4 sm:w-4" /> {listing.views_count || 0} {isFr ? 'vues' : 'views'}
          </span>
          <span className="flex items-center gap-1">
            <TrendingUp className="h-3.5 w-3.5 sm:h-4 sm:w-4" /> {listing.bid_count || 0} {isFr ? 'enchères' : 'bids'}
          </span>
          <span className="flex items-center gap-1 font-medium">
            <DollarSign className="h-3.5 w-3.5 sm:h-4 sm:w-4" /> {formatPrice(listing.current_bid || listing.starting_price)}
          </span>
        </div>

        {listing.status === 'rejected' && listing.rejection_reason && (
          <div className="mt-3 p-2 bg-red-50 rounded text-xs sm:text-sm text-red-600">
            <AlertTriangle className="h-4 w-4 inline mr-1" />
            {listing.rejection_reason}
          </div>
        )}
      </CardContent>

      <ListingChangeRequestModal
        listingId={listing.id}
        listingLabel={`${listing.year || ''} ${listing.make || ''} ${listing.model || ''}`.trim()}
        requestType={modal.type}
        isFr={isFr}
        open={modal.open}
        onClose={() => setModal({ open: false, type: modal.type })}
      />
    </Card>
  );
};

const MyVehicleListingsPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const isFr = (i18n.language || '').toLowerCase().startsWith('fr');
  const { token } = useAuth();
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sellerProfile, setSellerProfile] = useState(null);
  const [activeTab, setActiveTab] = useState('all');

  const fetchData = useCallback(async () => {
    if (!token) {
      navigate('/auth');
      return;
    }
    try {
      const sellerResp = await axios.get(`${API}/vehicle-sellers/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setSellerProfile(sellerResp.data);

      const listingsResp = await axios.get(`${API}/vehicles/my/listings`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const singles = (listingsResp.data.listings || []).map((l) => ({ ...l, _kind: 'single' }));

      let multiLotDrafts = [];
      try {
        const mlResp = await axios.get(`${API}/vehicle-multi-lot-auctions/my-drafts`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        multiLotDrafts = (mlResp.data?.data || []).map((e) => ({
          ...e,
          _kind: 'multi_lot',
          status: e.status,
          year: e.lots?.[0]?.year || '',
          make: `${isFr ? 'Multi-lots' : 'Multi-Lot'} · ${(e.lots || []).length} ${(e.lots || []).length === 1 ? (isFr ? 'lot' : 'lot') : (isFr ? 'lots' : 'lots')}`,
          model: e.title,
          media: e.lots?.[0]?.media || [],
        }));
      } catch (_e) {
        // dealer-only endpoint; 403 for non-dealer accounts
      }
      setListings([...singles, ...multiLotDrafts]);
    } catch (error) {
      if (error.response?.status === 404) {
        toast.error(isFr ? "Veuillez d'abord vous inscrire comme vendeur de véhicules" : 'Please register as a vehicle seller first');
        navigate('/vehicle-auctions/seller/register');
      } else {
        toast.error(isFr ? 'Échec du chargement' : 'Failed to load data');
      }
    } finally {
      setLoading(false);
    }
  }, [token, navigate, isFr]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filteredListings = listings.filter((listing) => {
    if (activeTab === 'all') return true;
    if (activeTab === 'drafts') return listing.status === 'draft';
    if (activeTab === 'active') return listing.status === 'active';
    if (activeTab === 'pending') return ['pending_approval', 'approved'].includes(listing.status);
    if (activeTab === 'ended') return ['ended', 'sold', 'cancelled'].includes(listing.status);
    return true;
  });

  const stats = {
    total: listings.length,
    drafts: listings.filter((l) => l.status === 'draft').length,
    active: listings.filter((l) => l.status === 'active').length,
    pending: listings.filter((l) => ['pending_approval'].includes(l.status)).length,
    sold: listings.filter((l) => l.status === 'sold').length,
  };

  const handlePromote = async (listingId, intent, startISO) => {
    const draft = listings.find((l) => l.id === listingId);
    const isMultiLot = draft?._kind === 'multi_lot';
    try {
      const params = new URLSearchParams({ intent });
      if (intent === 'schedule' && startISO) params.set('start_time', startISO);
      const path = isMultiLot
        ? `${API}/vehicle-multi-lot-auctions/${listingId}/activate?${params.toString()}`
        : `${API}/vehicles/${listingId}/activate?${params.toString()}`;
      await axios.post(path, {}, { headers: { Authorization: `Bearer ${token}` } });
      toast.success(intent === 'live'
        ? (isFr ? 'Annonce en ligne' : 'Listing is now LIVE')
        : (isFr ? 'Annonce programmée' : 'Listing scheduled'));
      fetchData();
    } catch (err) {
      toast.error(extractErrorMessage(err) || (isFr ? "Échec de l'activation" : 'Failed to activate draft'));
    }
  };

  const handleDeleteDraft = async (listingId) => {
    const draft = listings.find((l) => l.id === listingId);
    const isMultiLot = draft?._kind === 'multi_lot';
    if (!window.confirm(isFr ? 'Supprimer définitivement ce brouillon ?' : 'Delete this draft permanently? This cannot be undone.')) return;
    try {
      if (isMultiLot) {
        await axios.delete(`${API}/vehicle-multi-lot-auctions/${listingId}`, { headers: { Authorization: `Bearer ${token}` } });
      } else {
        await axios.delete(`${API}/vehicles/${listingId}/draft`, { headers: { Authorization: `Bearer ${token}` } });
      }
      toast.success(isFr ? 'Brouillon supprimé' : 'Draft deleted');
      fetchData();
    } catch (err) {
      toast.error(extractErrorMessage(err) || (isFr ? 'Échec de la suppression' : 'Failed to delete draft'));
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  const TABS = [
    { id: 'all',     en: 'All',     fr: 'Tous',       count: stats.total },
    { id: 'drafts',  en: '📝 Drafts',fr: '📝 Brouillons',count: stats.drafts },
    { id: 'active',  en: 'Active',  fr: 'Actives',    count: stats.active },
    { id: 'pending', en: 'Pending', fr: 'En attente', count: stats.pending },
    { id: 'ended',   en: 'Ended',   fr: 'Terminées',  count: listings.filter((l) => ['ended', 'sold'].includes(l.status)).length },
  ];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="my-listings-page">
      {/* Header */}
      <div className="bg-white dark:bg-slate-900 border-b">
        <div className="max-w-6xl mx-auto px-4 py-5 sm:py-6">
          {/* Title + CTAs */}
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
            <div className="min-w-0">
              <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold text-slate-900 dark:text-white leading-tight" data-testid="my-listings-title">
                {t('vehicleListings.title', isFr ? 'Mes annonces de véhicules' : 'My Vehicle Listings')}
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 mt-1">
                {t('vehicleListings.subtitle', isFr ? 'Gérez vos annonces de vente aux enchères de véhicules' : 'Manage your vehicle auction listings')}
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
              <Button
                onClick={() => navigate('/vehicle-auctions/create')}
                className="gap-2 min-h-[44px] w-full sm:w-auto"
                disabled={sellerProfile?.verification_status !== 'approved'}
                data-testid="create-vehicle-btn"
              >
                <Plus className="h-4 w-4" /> {isFr ? '+ Créer une annonce de véhicule' : '+ Create a Vehicle Listing'}
              </Button>
              <Button
                onClick={() => navigate('/vehicle-multi-lot/create')}
                variant="outline"
                className="gap-2 min-h-[44px] w-full sm:w-auto border-indigo-600 text-indigo-700 hover:bg-indigo-50"
                disabled={sellerProfile?.verification_status !== 'approved'}
                data-testid="create-multi-lot-btn"
              >
                <Plus className="h-4 w-4" /> {isFr ? '+ Enchère multi-lots' : '+ Create Multi-Lot Vehicle Auction'}
              </Button>
              {/* iter304 — Lot Templates manager link */}
              <Button
                onClick={() => navigate('/vehicle-auctions/lot-templates')}
                variant="ghost"
                className="gap-2 min-h-[44px] w-full sm:w-auto text-blue-700 hover:bg-blue-50"
                data-testid="lot-templates-link"
              >
                <BookmarkPlus className="h-4 w-4" /> {isFr ? 'Modèles de lots' : 'Lot Templates'}
              </Button>
            </div>
          </div>

          {/* iter427 — Inline "Verify Dealer" banner. Shown whenever
             the seller profile is missing OR not yet approved OR the
             dealer is suspended. Replaces the previous silent
             `disabled` state that gave users no indication why the
             Create buttons were greyed out or where to fix it. */}
          {sellerProfile && sellerProfile.verification_status !== 'approved' ? (
            <Card className="mt-4 border-amber-200 bg-amber-50" data-testid="dealer-verify-banner">
              <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center gap-3">
                <ShieldAlert className="h-6 w-6 text-amber-700 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-amber-900">
                    {isFr ? 'Vérification concessionnaire requise' : 'Dealer verification required'}
                  </p>
                  <p className="text-sm text-amber-800 mt-0.5">
                    {sellerProfile.verification_status === 'rejected'
                      ? (isFr
                          ? 'Votre demande a été refusée. Corrigez et soumettez à nouveau vos documents pour publier des annonces.'
                          : 'Your application was rejected. Resubmit your documents to publish listings.')
                      : (isFr
                          ? 'Votre demande est en cours d’examen. Une fois approuvée, vous pourrez créer et publier des annonces de véhicules.'
                          : 'Your application is under review. Once approved you can create and publish vehicle listings.')}
                  </p>
                </div>
                <Button
                  onClick={() => navigate('/vehicle-auctions/seller/register')}
                  className="bg-amber-600 hover:bg-amber-700 text-white flex-shrink-0"
                  data-testid="verify-dealer-cta"
                >
                  <ShieldAlert className="h-4 w-4 mr-1" />
                  {isFr ? 'Vérifier concessionnaire' : 'Verify Dealer'}
                  <ArrowRight className="h-4 w-4 ml-1" />
                </Button>
              </CardContent>
            </Card>
          ) : null}

          {/* Stats — 2×2 on mobile, single row on tablet+ */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5" data-testid="my-listings-stats">
            <Card>
              <CardContent className="p-3 sm:p-4">
                <p className="text-xl sm:text-2xl font-bold">{stats.total}</p>
                <p className="text-[11px] sm:text-sm text-slate-500 leading-tight">{isFr ? 'Total des annonces' : 'Total Listings'}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 sm:p-4">
                <p className="text-xl sm:text-2xl font-bold text-green-600">{stats.active}</p>
                <p className="text-[11px] sm:text-sm text-slate-500 leading-tight">{isFr ? 'Enchères actives' : 'Active Auctions'}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 sm:p-4">
                <p className="text-xl sm:text-2xl font-bold text-yellow-600">{stats.pending}</p>
                <p className="text-[11px] sm:text-sm text-slate-500 leading-tight">{isFr ? 'En attente' : 'Pending'}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 sm:p-4">
                <p className="text-xl sm:text-2xl font-bold text-purple-600">{stats.sold}</p>
                <p className="text-[11px] sm:text-sm text-slate-500 leading-tight">{isFr ? 'Vendues' : 'Sold'}</p>
              </CardContent>
            </Card>
          </div>

          {/* Monthly Limit + Licensed badge — stacked on mobile, inline on tablet+ */}
          {sellerProfile && (
            <div className="mt-4 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2" data-testid="monthly-limit-row">
              <span className="text-xs sm:text-sm text-slate-600">
                {isFr ? 'Annonces mensuelles : ' : 'Monthly Listings: '}
                {sellerProfile.monthly_listing_count} / {sellerProfile.monthly_listing_limit}
              </span>
              <Badge variant="outline" className="w-fit">
                {sellerProfile.seller_type === 'dealer'     ? (isFr ? 'Concessionnaire autorisé' : 'Licensed Dealer')
                  : sellerProfile.seller_type === 'auctioneer' ? (isFr ? 'Commissaire-priseur vérifié' : 'Verified Auctioneer')
                  : (isFr ? 'Vendeur privé' : 'Private Seller')}
              </Badge>
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-4 py-6 sm:py-8">
        {/* Horizontally-scrollable tab bar */}
        <div
          className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1 mb-4 sm:mb-6"
          style={{ WebkitOverflowScrolling: 'touch' }}
          data-testid="my-vehicles-tabs"
          role="tablist"
        >
          {TABS.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-shrink-0 min-w-[80px] px-3 py-2 rounded-lg text-xs sm:text-sm font-semibold whitespace-nowrap transition-colors ${
                  isActive
                    ? 'bg-[#0055FF] text-white shadow-sm'
                    : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 hover:bg-slate-50'
                }`}
                data-testid={`tab-${tab.id}`}
              >
                {isFr ? tab.fr : tab.en} ({tab.count})
              </button>
            );
          })}
        </div>

        {filteredListings.length === 0 ? (
          <Card className="p-8 sm:p-12 text-center">
            <Car className="h-14 w-14 sm:h-16 sm:w-16 text-slate-300 mx-auto mb-4" />
            <h3 className="text-lg sm:text-xl font-semibold mb-2">
              {isFr ? 'Aucune annonce trouvée' : 'No Listings Found'}
            </h3>
            <p className="text-sm text-slate-500 mb-6">
              {activeTab === 'all'
                ? (isFr ? "Vous n'avez pas encore créé d'annonces de véhicules." : "You haven't created any vehicle listings yet.")
                : (isFr ? `Aucune annonce ${activeTab}.` : `No ${activeTab} listings.`)}
            </p>
            {sellerProfile?.verification_status === 'approved' && (
              <Button onClick={() => navigate('/vehicle-auctions/create')} className="min-h-[44px]">
                <Plus className="h-4 w-4 mr-2" /> {isFr ? 'Créer ma première annonce' : 'Create Your First Listing'}
              </Button>
            )}
          </Card>
        ) : (
          <div
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4"
            data-testid="my-listings-grid"
          >
            {filteredListings.map((listing) => (
              <VehicleListingCard
                key={listing.id}
                listing={listing}
                isFr={isFr}
                onView={(id) => navigate(
                  listing._kind === 'multi_lot'
                    ? `/vehicle-multi-lot/${id}`
                    : `/vehicle-auctions/${id}`,
                )}
                onEdit={(id) => navigate(`/vehicle-auctions/edit/${id}`)}
                onPromote={handlePromote}
                onDeleteDraft={handleDeleteDraft}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default MyVehicleListingsPage;
