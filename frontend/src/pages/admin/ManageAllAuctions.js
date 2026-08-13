import API_BASE from '../../config';
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Checkbox } from '../../components/ui/checkbox';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription } from '../../components/ui/dialog';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import { AsyncButton } from '../../components/ui/async-button';
import { toast } from 'sonner';
import { Package, Search, Edit2, Trash2, Pause, Archive, XCircle, Eye, AlertTriangle, Download, Star, Play, Clock, FileDown, Loader2 } from 'lucide-react';
import { formatCurrency } from '../../utils/currencyFormatter';
import AdminLotEditorModal from './AdminLotEditorModal';
import { extractErrorMessage } from '../../utils/errorHandler';

const API = API_BASE;

const ManageAllAuctions = () => {
  const navigate = useNavigate();
  const { token } = useAuth();
  const headers = { Authorization: `Bearer ${token}` };
  const [allListings, setAllListings] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [deleteModal, setDeleteModal] = useState({ open: false, listing: null });
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [bulkConfirm, setBulkConfirm] = useState(null);
  const [editModal, setEditModal] = useState({ open: false, listing: null, form: {} });
  // FEATURE PATCH v9 / Feature 1 — Edit auction end time
  const [endTimeModal, setEndTimeModal] = useState({ open: false, listing: null, newEndTime: '', reason: '', history: [] });
  // iter343 BUG-4 — per-lot editor for multi-lot auctions
  const [lotEditor, setLotEditor] = useState({ open: false, listing: null });
  // iter311 — performance + capacity telemetry from the unified endpoint
  const [perfMeta, setPerfMeta] = useState({ total: 0, server_ms: 0, by_section: {} });
  // iter482+ — Admin CSV Export state (per-row)
  const [csvExportingId, setCsvExportingId] = useState(null);

  const handleAdminCsvExport = async (listing) => {
    setCsvExportingId(listing.id);
    try {
      const { downloadLotCsv, csvLocale } = await import('../../utils/lotCsvExport');
      const lang = (typeof window !== 'undefined' && window.localStorage.getItem('i18nextLng')) || 'en';
      const L = csvLocale(lang);
      await downloadLotCsv({
        auctionId: listing.id,
        surface: 'admin',
        token,
        apiBase: API,
        lang,
        onSuccess: () => toast.success(L.success),
        onError: (err) => toast.error(err.message || L.failed),
      });
    } catch (_) {
      /* toast shown */
    } finally {
      setCsvExportingId(null);
    }
  };

  useEffect(() => {
    fetchAllListings();
  }, []);

  // iter311 — Unified server-aggregated fetch.
  // Replaces the old fan-out of 2-4 client-side round-trips with ONE
  // call to /api/admin/listings/all-collections, which merges + sorts +
  // counts across `listings`, `vehicle_listings`,
  // `vehicle_multi_lot_auctions`, and `multi_item_listings` server-side.
  // Each row arrives normalized with a `_section` tag we map to the
  // existing `type` prop so the rest of the JSX is untouched.
  const fetchAllListings = async () => {
    setLoading(true);
    try {
      const res = await axios.get(
        `${API}/admin/listings/all-collections?limit=500&sort=created_at_desc`,
        { headers },
      );
      const { rows = [], total = 0, by_section = {}, perf_ms = 0 } = res.data || {};
      // Map _section → type so existing filters / actions keep working.
      //   _section ∈ {marketplace, vehicle, vehicle_multi, lots}
      //   type     ∈ {single, multi}
      const decorated = rows.map(r => ({
        ...r,
        // Each row needs a `type` (the existing All/Single/Multi filter
        // hinges on this). Single-vehicle counts as single; multi-lot
        // events and multi-item parents count as multi.
        type: (r._section === 'marketplace' || r._section === 'vehicle')
          ? 'single' : 'multi',
      }));
      setAllListings(decorated);
      setPerfMeta({ total, server_ms: perf_ms, by_section });
      if (total > rows.length) {
        toast.info(
          `Showing ${rows.length} of ${total} listings — refine the filter to narrow down.`,
        );
      }
    } catch (error) {
      console.error('Failed to load listings:', error);
      toast.error('Failed to load auctions');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (listing) => {
    setDeleteModal({ open: true, listing });
  };
  
  const confirmDelete = async () => {
    const { listing } = deleteModal;
    if (!listing) return;
    
    try {
      // iter290 — Cross-collection delete routing. Storage + vehicle +
      // lots rows live in different directories — DELETE to the right
      // admin endpoint so the cascade fires on the correct collection.
      const sec = listing._section || (listing.type === 'multi' ? 'lots' : 'marketplace');
      const endpoint =
        sec === 'vehicle' ? `vehicles/${listing.id}` :
        sec === 'storage' ? `storage-auctions/${listing.id}` :
        sec === 'lots'    ? `multi-item-listings/${listing.id}` :
                            `listings/${listing.id}`;
      await axios.delete(`${API}/admin/${endpoint}`, { headers });
      toast.success('Auction deleted successfully');
      setDeleteModal({ open: false, listing: null });
      fetchAllListings();
    } catch (error) {
      toast.error(extractErrorMessage(error) || 'Failed to delete auction');
    }
  };

  const handleToggleFeature = async (listing) => {
    try {
      await axios.put(`${API}/admin/listings/${listing.id}/feature`,
        { is_featured: !listing.is_featured }, { headers });
      toast.success(listing.is_featured ? 'Listing unfeatured' : 'Listing featured');
      fetchAllListings();
    } catch (error) {
      toast.error(extractErrorMessage(error) || 'Failed to toggle feature');
    }
  };

  // ── Bulk selection ──
  const toggleSelect = (id) =>
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const selectAllVisible = (ids) => setSelectedIds(prev => {
    const allSelected = ids.every(id => prev.has(id));
    if (allSelected) return new Set();
    const next = new Set(prev);
    ids.forEach(id => next.add(id));
    return next;
  });

  const clearSelection = () => setSelectedIds(new Set());

  const runBulkAction = async (action) => {
    if (selectedIds.size === 0) throw new Error('Nothing selected');
    const ids = [...selectedIds];
    const res = await axios.post(`${API}/admin/listings/bulk-action`,
      { action, listing_ids: ids }, { headers });
    const { succeeded_count, failed_count } = res.data;
    if (failed_count > 0) {
      toast.warning(`${succeeded_count} succeeded, ${failed_count} failed`);
    } else {
      toast.success(`${action} applied to ${succeeded_count} listing(s)`);
    }
    clearSelection();
    fetchAllListings();
  };

  // ── Edit listing ──
  // iter290 — Vehicle + storage rows live in different collections and
  // have collection-specific schemas (year/make/model for vehicles,
  // facility/unit for storage). The inline marketplace Edit modal can't
  // safely round-trip those — instead route the admin to the dedicated
  // panel that already owns the full edit experience.
  const openEditModal = (listing) => {
    const sec = listing._section || (listing.type === 'multi' ? 'lots' : 'marketplace');
    if (sec === 'vehicle') {
      navigate('/admin?tab=vehicle-admin');
      toast.info('Opened Vehicle Admin — find this listing to edit it.');
      return;
    }
    if (sec === 'storage') {
      navigate('/admin?tab=storage-auctions-admin');
      toast.info('Opened Storage Auctions Admin — find this listing to edit it.');
      return;
    }
    if (sec === 'lots') {
      navigate('/admin?tab=listings-moderation');
      toast.info('Opened Listings Moderation — find this listing to edit it.');
      return;
    }
    setEditModal({
      open: true,
      listing,
      form: {
        title: listing.title || '',
        description: listing.description || '',
        category: listing.category || '',
        starting_price: listing.starting_price || listing.current_price || 0,
        reserve_price: listing.reserve_price || '',
        buy_now_price: listing.buy_now_price || '',
        city: listing.city || '',
        region: listing.region || '',
        // iter220 Task 4 — Image asset array for in-place admin management.
        // Frontend builds the FINAL desired list (additions appended, deletions
        // filtered out) and the backend writes it atomically.
        images: Array.isArray(listing.images) ? [...listing.images] : [],
      },
    });
  };

  const saveEdit = async () => {
    const { listing, form } = editModal;
    if (!form.title?.trim()) {
      toast.error('Title is required / Le titre est requis');
      throw new Error('validation');
    }
    const body = {
      title: form.title,
      description: form.description,
      category: form.category,
      starting_price: Number(form.starting_price) || 0,
      reserve_price: form.reserve_price === '' ? null : Number(form.reserve_price),
      buy_now_price: form.buy_now_price === '' ? null : Number(form.buy_now_price),
      city: form.city,
      region: form.region,
      // iter220 Task 4 — full-array replacement of images
      images: Array.isArray(form.images) ? form.images : [],
    };
    const endpoint = listing.type === 'multi'
      ? `multi-item-listings/${listing.id}`
      : `listings/${listing.id}`;
    await axios.put(`${API}/admin/${endpoint}`, body, { headers });
    setEditModal({ open: false, listing: null, form: {} });
    fetchAllListings();
  };

  // iter220 Task 4 — Add/Remove images in the admin Edit modal.
  // `addEditImage` accepts a URL OR a File (uploads via existing /uploads
  // multipart endpoint then appends the returned URL).
  const addEditImageUrl = (url) => {
    const u = (url || '').trim();
    if (!u) return;
    setEditModal((m) => ({
      ...m,
      form: { ...m.form, images: [...(m.form.images || []), u].slice(0, 30) },
    }));
  };
  const removeEditImage = (idx) => {
    setEditModal((m) => ({
      ...m,
      form: {
        ...m.form,
        images: (m.form.images || []).filter((_, i) => i !== idx),
      },
    }));
  };
  const uploadEditImageFile = async (file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await axios.post(`${API}/uploads/image`, fd, {
        headers: { ...headers, 'Content-Type': 'multipart/form-data' },
      });
      const u = r.data?.url || r.data?.image_url || r.data?.s3_url;
      if (u) {
        addEditImageUrl(u);
        toast.success('Image added');
      } else {
        toast.error('Upload returned no URL');
      }
    } catch (err) {
      toast.error(extractErrorMessage(err) || 'Image upload failed');
    }
  };

  // FEATURE PATCH v9 / Feature 1 — Edit end time
  const openEndTimeModal = async (listing) => {
    const currentEnd = listing.auction_end_date ? new Date(listing.auction_end_date) : null;
    // Local datetime string (yyyy-MM-ddThh:mm) for <input type="datetime-local">
    const initial = currentEnd ? new Date(currentEnd.getTime() - currentEnd.getTimezoneOffset() * 60000).toISOString().slice(0, 16) : '';
    let history = [];
    try {
      const r = await axios.get(`${API}/admin/auctions/${listing.id}/end-time-history`, { headers });
      history = r.data?.history || [];
    } catch (_) { /* not critical */ }
    setEndTimeModal({ open: true, listing, newEndTime: initial, reason: '', history });
  };

  const saveEndTime = async () => {
    const { listing, newEndTime, reason } = endTimeModal;
    if (!newEndTime) {
      toast.error('Please choose a new end time');
      throw new Error('validation');
    }
    const iso = new Date(newEndTime).toISOString();
    const body = {
      new_end_time: iso,
      reason: reason || '',
      listing_type: listing.type === 'multi' ? 'multi' : 'single',
    };
    const r = await axios.patch(`${API}/admin/auctions/${listing.id}/end-time`, body, { headers });
    const notified = r.data?.notified || {};
    toast.success(`End time updated · ${notified.bidders || 0} bidders · ${notified.watchlist || 0} watchers notified`);
    setEndTimeModal({ open: false, listing: null, newEndTime: '', reason: '', history: [] });
    fetchAllListings();
  };

  const handleStatusChange = async (id, newStatus, isMultiItem) => {
    try {
      const endpoint = isMultiItem ? `multi-item-listings/${id}` : `listings/${id}`;
      await axios.put(`${API}/admin/${endpoint}/status`, { status: newStatus }, { headers });
      toast.success(`Auction status updated to ${newStatus}`);
      fetchAllListings();
    } catch (error) {
      toast.error(extractErrorMessage(error) || 'Failed to update status');
    }
  };

  // iter312 — server-streamed CSV export. Hits
  // GET /api/admin/listings/export which re-uses the same $unionWith
  // aggregation as the list view (minus pagination + facet) and streams
  // the response. Honours the admin's current filter state — type /
  // status / search are mapped 1:1 to the backend's section / status /
  // q params so what the admin SEES is what the admin EXPORTS, even
  // when the visible window is paginated at 500.
  const [exportPending, setExportPending] = useState(false);
  const exportToCsv = async () => {
    if (perfMeta.total === 0) {
      toast.error('Nothing to export with current filters');
      return;
    }
    setExportPending(true);
    try {
      // Map the client filter state → server params.
      // typeFilter: 'all' | 'single' | 'multi'  →  section: undefined | 'marketplace,vehicle' | 'vehicle_multi,lots'
      const params = new URLSearchParams();
      if (typeFilter === 'single') params.set('section', 'marketplace,vehicle');
      else if (typeFilter === 'multi') params.set('section', 'vehicle_multi,lots');
      if (statusFilter && statusFilter !== 'all') params.set('status', statusFilter);
      const q = (searchQuery || '').trim();
      if (q) params.set('q', q);
      params.set('hard_cap', '50000');

      const res = await axios.get(
        `${API}/admin/listings/export?${params.toString()}`,
        { headers, responseType: 'blob' },
      );

      // Pull filename from Content-Disposition if present, else build one.
      const cd = res.headers['content-disposition'] || '';
      let filename = `bidvex-listings-${new Date().toISOString().slice(0, 10)}.csv`;
      const m = /filename="?([^"]+)"?/.exec(cd);
      if (m) filename = m[1];

      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      // Count rows in the downloaded blob (subtract 1 for header line)
      const text = await blob.text();
      const rowCount = Math.max(0, (text.split('\n').length - 1) - 1);
      toast.success(`Exported ${rowCount} auction(s) to ${filename}`);
    } catch (err) {
      console.error('CSV export failed:', err);
      toast.error('Export failed — see console');
    } finally {
      setExportPending(false);
    }
  };

  // iter311 — combined view is now just the single state array. The
  // server already normalized + sorted + tagged each row with `_section`,
  // and `fetchAllListings` mapped that to a `type` field. Type / status /
  // search filters still run client-side over the already-paged window
  // so admins can flip filters without round-tripping.
  const combinedListings = allListings;

  const filteredListings = combinedListings.filter(listing => {
    // Type filter
    if (typeFilter !== 'all' && listing.type !== typeFilter) return false;
    
    // Status filter
    if (statusFilter !== 'all' && listing.status !== statusFilter) return false;
    
    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      return (
        listing.title?.toLowerCase().includes(query) ||
        listing.category?.toLowerCase().includes(query) ||
        listing.seller_id?.toLowerCase().includes(query)
      );
    }
    
    return true;
  });

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Package className="h-6 w-6" />
            Manage All Auctions
          </h2>
          <p className="text-muted-foreground">Unified view of all single and multi-item listings</p>
        </div>
        <Button
          variant="outline"
          onClick={exportToCsv}
          disabled={perfMeta.total === 0 || exportPending}
          data-testid="export-auctions-csv"
          title="Streams the full filtered result set from the server — not capped at the 500-row view."
        >
          <Download className="h-4 w-4 mr-2" />
          {exportPending
            ? 'Exporting…'
            : `Export CSV (${perfMeta.total || filteredListings.length})`}
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6">
            <p className="text-2xl font-bold">{combinedListings.length}</p>
            <p className="text-sm text-muted-foreground">Total Auctions</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <p className="text-2xl font-bold text-green-600">{combinedListings.filter(l => l.status === 'active').length}</p>
            <p className="text-sm text-muted-foreground">Active</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <p className="text-2xl font-bold text-blue-600">{combinedListings.filter(l => l.type === 'single').length}</p>
            <p className="text-sm text-muted-foreground">Single Items</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <p className="text-2xl font-bold text-purple-600">{combinedListings.filter(l => l.type === 'multi').length}</p>
            <p className="text-sm text-muted-foreground">Multi-Item</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="flex gap-2">
          <Button
            variant={typeFilter === 'all' ? 'default' : 'outline'}
            onClick={() => setTypeFilter('all')}
            className={typeFilter === 'all' ? 'gradient-button text-white border-0' : ''}
          >
            All Types
          </Button>
          <Button
            variant={typeFilter === 'single' ? 'default' : 'outline'}
            onClick={() => setTypeFilter('single')}
            className={typeFilter === 'single' ? 'gradient-button text-white border-0' : ''}
          >
            Single
          </Button>
          <Button
            variant={typeFilter === 'multi' ? 'default' : 'outline'}
            onClick={() => setTypeFilter('multi')}
            className={typeFilter === 'multi' ? 'gradient-button text-white border-0' : ''}
          >
            Multi-Item
          </Button>
        </div>

        <div className="flex gap-2">
          <Button
            variant={statusFilter === 'all' ? 'default' : 'outline'}
            onClick={() => setStatusFilter('all')}
            size="sm"
          >
            All Status
          </Button>
          <Button
            variant={statusFilter === 'active' ? 'default' : 'outline'}
            onClick={() => setStatusFilter('active')}
            size="sm"
          >
            Active
          </Button>
          <Button
            variant={statusFilter === 'draft' ? 'default' : 'outline'}
            onClick={() => setStatusFilter('draft')}
            size="sm"
          >
            Draft
          </Button>
          <Button
            variant={statusFilter === 'ended' ? 'default' : 'outline'}
            onClick={() => setStatusFilter('ended')}
            size="sm"
          >
            Ended
          </Button>
        </div>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search by title, category, or seller ID..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10 text-slate-900 dark:text-slate-100"
        />
      </div>

      {/* Bulk Action Bar */}
      {selectedIds.size > 0 && (
        <Card className="border-primary bg-primary/5" data-testid="bulk-action-bar">
          <CardContent className="p-3 flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3">
              <Badge className="bg-primary text-white">{selectedIds.size} selected</Badge>
              <Button variant="ghost" size="sm" onClick={clearSelection} data-testid="bulk-clear-btn">
                Clear
              </Button>
            </div>
            <div className="flex gap-2 flex-wrap">
              <AsyncButton size="sm" variant="outline" data-testid="bulk-feature-btn"
                onAction={() => runBulkAction('feature')}>
                <Star className="h-3.5 w-3.5 mr-1" />Feature
              </AsyncButton>
              <AsyncButton size="sm" variant="outline" data-testid="bulk-unfeature-btn"
                onAction={() => runBulkAction('unfeature')}>
                Unfeature
              </AsyncButton>
              <AsyncButton size="sm" variant="outline" data-testid="bulk-pause-btn"
                onAction={() => runBulkAction('pause')}>
                <Pause className="h-3.5 w-3.5 mr-1" />Pause
              </AsyncButton>
              <AsyncButton size="sm" variant="outline" data-testid="bulk-resume-btn"
                onAction={() => runBulkAction('resume')}>
                <Play className="h-3.5 w-3.5 mr-1" />Resume
              </AsyncButton>
              <AsyncButton size="sm" variant="outline" data-testid="bulk-archive-btn"
                onAction={() => runBulkAction('archive')}>
                <Archive className="h-3.5 w-3.5 mr-1" />Archive
              </AsyncButton>
              <Button size="sm" variant="destructive" data-testid="bulk-delete-btn"
                onClick={() => setBulkConfirm({
                  title: `Delete ${selectedIds.size} listing(s) permanently?`,
                  description: `This cannot be undone. ${selectedIds.size} auction(s) will be removed from the database.\n\nCette action est irréversible.`,
                  variant: 'destructive',
                  confirmText: `Delete ${selectedIds.size}`,
                  successMessage: `${selectedIds.size} listing(s) deleted`,
                  onConfirm: () => runBulkAction('delete'),
                })}>
                <Trash2 className="h-3.5 w-3.5 mr-1" />Delete
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Listings Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <CardTitle>Auctions ({filteredListings.length})</CardTitle>
            {filteredListings.length > 0 && (
              <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
                <Checkbox
                  checked={filteredListings.every(l => selectedIds.has(l.id)) && filteredListings.length > 0}
                  onCheckedChange={() => selectAllVisible(filteredListings.map(l => l.id))}
                  data-testid="select-all-checkbox"
                />
                Select all visible
              </label>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {filteredListings.length > 0 ? (
            <div className="space-y-3">
              {filteredListings.map((listing) => (
                <div
                  key={listing.id}
                  className={`flex flex-col md:flex-row justify-between gap-4 p-4 border rounded-lg hover:bg-accent/50 transition-colors ${selectedIds.has(listing.id) ? 'ring-1 ring-primary bg-primary/5' : ''}`}
                >
                  <div className="flex items-start gap-3 flex-1">
                    <Checkbox
                      className="mt-1.5"
                      checked={selectedIds.has(listing.id)}
                      onCheckedChange={() => toggleSelect(listing.id)}
                      data-testid={`select-listing-${listing.id}`}
                    />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2 flex-wrap">
                        <h3 className="font-semibold text-slate-900 dark:text-slate-100">{listing.title}</h3>
                      <Badge variant={listing.type === 'multi' ? 'default' : 'secondary'}>
                        {listing.type === 'multi' ? `Multi (${listing.lots?.length || 0} lots)` : 'Single'}
                      </Badge>
                      <Badge variant={
                        listing.status === 'active' ? 'default' :
                        listing.status === 'draft' ? 'secondary' :
                        'outline'
                      }>
                        {listing.status}
                      </Badge>
                      {listing.is_featured && <Badge className="bg-amber-100 text-amber-900 border border-amber-300" data-testid={`featured-badge-${listing.id}`}>★ Featured</Badge>}
                      {/* iter290 — Section badge tagged by the backend
                          aggregator. Lets admins see at-a-glance which
                          directory the listing lives in. */}
                      {listing._section && (
                        <Badge
                          variant="outline"
                          className={
                            listing._section === 'vehicle' ? 'border-blue-300 bg-blue-50 text-blue-900' :
                            listing._section === 'storage' ? 'border-teal-300 bg-teal-50 text-teal-900' :
                            listing._section === 'lots'    ? 'border-orange-300 bg-orange-50 text-orange-900' :
                            listing._section === 'vehicle_multi_lot' ? 'border-indigo-300 bg-indigo-50 text-indigo-900' :
                            'border-slate-300 bg-slate-50 text-slate-700'
                          }
                          data-testid={`section-badge-${listing.id}`}
                        >
                          {listing._section === 'vehicle' ? '🚗 Vehicle'
                            : listing._section === 'storage' ? '🏪 Storage'
                            : listing._section === 'lots'    ? '📦 Lots'
                            : listing._section === 'vehicle_multi_lot' ? '🚚 Multi-Lot Vehicle'
                            : '🛒 Marketplace'}
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground mb-2">{listing.category} • {listing.city}, {listing.region}</p>
                    <div className="flex gap-4 text-sm">
                      <span className="text-green-600 font-semibold">
                        {formatCurrency(listing.type === 'multi'
                          ? listing.lots?.reduce((sum, lot) => sum + (lot.starting_price || 0), 0)
                          : listing.current_price)}
                      </span>
                      <span className="text-muted-foreground">
                        {listing.type === 'multi'
                          ? `${listing.lots?.reduce((sum, lot) => sum + (lot.bid_count || 0), 0)} total bids`
                          : `${listing.bid_count || 0} bids`}
                      </span>
                      {listing.auction_end_date && (
                        <span className="text-slate-500" data-testid={`end-time-display-${listing.id}`}>
                          <Clock className="inline h-3.5 w-3.5 mr-1" />
                          Ends: {new Date(listing.auction_end_date).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        // iter290 — Cross-collection View routing.
                        // Storage / vehicle / lots rows live in different
                        // directories — link to the right detail page.
                        const sec = listing._section || (listing.type === 'multi' ? 'lots' : 'marketplace');
                        const path =
                          sec === 'vehicle' ? `/vehicle-auctions/${listing.id}` :
                          sec === 'storage' ? `/storage-auctions/${listing.id}` :
                          sec === 'lots'    ? `/lots/${listing.id}` :
                          sec === 'vehicle_multi_lot' ? `/vehicle-multi-lot/${listing.id}` :
                                              `/listing/${listing.id}`;
                        navigate(path);
                      }}
                      data-testid={`view-btn-${listing.id}`}
                    >
                      <Eye className="h-4 w-4 mr-1" />
                      View
                    </Button>
                    {/* iter482+ — Admin Lot CSV Export.  Uses the
                        canonical /api/exports/lots endpoint with
                        surface=admin so it also emits winner_user_id,
                        hammer_price, sold_at, seller_id. */}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleAdminCsvExport(listing)}
                      disabled={csvExportingId === listing.id}
                      data-testid={`admin-export-csv-btn-${listing.id}`}
                      title="Download admin CSV export (includes hammer_price, winner, sold_at, seller_id)"
                      className="border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                    >
                      {csvExportingId === listing.id
                        ? <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                        : <FileDown className="h-4 w-4 mr-1" />}
                      Export CSV (Admin)
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => openEditModal(listing)}
                      data-testid={`edit-btn-${listing.id}`}
                      title={
                        (listing._section === 'vehicle') ? 'Edit in Vehicle Admin panel' :
                        (listing._section === 'storage') ? 'Edit in Storage Auctions Admin panel' :
                        (listing._section === 'lots' || listing.type === 'multi') ? 'Edit in Listings Moderation panel' :
                        'Edit listing details'
                      }
                    >
                      <Edit2 className="h-4 w-4 mr-1" />
                      Edit
                    </Button>
                    {/* iter343 BUG-4 — per-lot editor for multi-lot auctions */}
                    {(listing.type === 'multi' || ['lots', 'vehicle_multi', 'vehicle_multi_lot'].includes(listing._section)) && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-cyan-300 text-cyan-700 hover:bg-cyan-50"
                        onClick={() => setLotEditor({ open: true, listing })}
                        data-testid={`edit-lots-btn-${listing.id}`}
                        title="Edit individual lots (title, quantity, prices…)"
                      >
                        <Edit2 className="h-4 w-4 mr-1" />
                        Lots
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => openEndTimeModal(listing)}
                      disabled={['closed','settled','ended','completed','archived','rejected'].includes((listing.status || '').toLowerCase())}
                      data-testid={`edit-end-time-btn-${listing.id}`}
                      title="Edit auction end time"
                    >
                      <Clock className="h-4 w-4 mr-1" />
                      End Time
                    </Button>
                    <Button
                      size="sm"
                      variant={listing.is_featured ? 'default' : 'outline'}
                      className={listing.is_featured ? 'bg-amber-500 hover:bg-amber-600 text-white' : ''}
                      onClick={() => handleToggleFeature(listing)}
                      data-testid={`feature-btn-${listing.id}`}
                      title="Feature this listing on the homepage"
                    >
                      <Star className="h-4 w-4 mr-1" />
                      {listing.is_featured ? 'Featured' : 'Feature'}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleStatusChange(listing.id, 'paused', listing.type === 'multi')}
                      disabled={listing.status !== 'active'}
                    >
                      <Pause className="h-4 w-4 mr-1" />
                      Pause
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleStatusChange(listing.id, 'archived', listing.type === 'multi')}
                    >
                      <Archive className="h-4 w-4 mr-1" />
                      Archive
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleDelete(listing)}
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      Delete
                    </Button>
                  </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">
              {searchQuery ? 'No auctions match your search' : 'No auctions found'}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Admin Deletion Warning Modal - Bilingual */}
      {deleteModal.open && deleteModal.listing && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-2xl border-2 border-red-600">
            <CardHeader className="bg-red-50 dark:bg-red-900/20">
              <CardTitle className="text-red-600 flex items-center gap-2">
                <AlertTriangle className="h-6 w-6" />
                ⚠️ WARNING: Irreversible Action / AVERTISSEMENT : Action Irréversible
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="space-y-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-700">
                <p className="font-semibold text-slate-900 dark:text-slate-100">English:</p>
                <p className="text-sm text-slate-700 dark:text-slate-300">
                  You are about to <strong>permanently delete</strong> a live auction. This action <strong>cannot be undone</strong>. 
                  Deleting an active listing may result in <strong>loss of bidder trust</strong> and <strong>potential legal disputes</strong>. 
                  Are you absolutely sure you wish to proceed?
                </p>
              </div>
              
              <div className="space-y-3 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-700">
                <p className="font-semibold text-slate-900 dark:text-slate-100">Français:</p>
                <p className="text-sm text-slate-700 dark:text-slate-300">
                  Vous êtes sur le point de <strong>supprimer définitivement</strong> une enchère en cours. Cette action est <strong>permanente et irréversible</strong>. 
                  La suppression d'une annonce active peut entraîner une <strong>perte de confiance des enchérisseurs</strong> et des <strong>litiges juridiques potentiels</strong>. 
                  Êtes-vous absolument sûr de vouloir continuer ?
                </p>
              </div>

              <div className="p-4 bg-gray-100 dark:bg-gray-800 rounded-lg border border-gray-300 dark:border-gray-700">
                <p className="font-semibold text-red-900 dark:text-red-300 mb-2">
                  Deleting: {deleteModal.listing.title}
                </p>
                <p className="text-sm text-muted-foreground">
                  Type: {deleteModal.listing.type === 'multi' ? `Multi-Item (${deleteModal.listing.lots?.length || 0} lots)` : 'Single Item'}
                </p>
                <p className="text-sm text-muted-foreground">
                  Status: {deleteModal.listing.status}
                </p>
              </div>

              <div className="flex gap-2 justify-end pt-4 border-t">
                <Button
                  variant="outline"
                  onClick={() => setDeleteModal({ open: false, listing: null })}
                >
                  Cancel / Annuler
                </Button>
                <Button
                  variant="destructive"
                  onClick={confirmDelete}
                  className="bg-red-600 hover:bg-red-700 text-white"
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Confirm Deletion / Confirmer la Suppression
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Edit Listing Modal */}
      <Dialog open={editModal.open} onOpenChange={(v) => !v && setEditModal({ open: false, listing: null, form: {} })}>
        <DialogContent className="max-w-2xl" data-testid="edit-listing-modal">
          <DialogHeader>
            <DialogTitle>Edit Listing</DialogTitle>
            <DialogDescription>
              {editModal.listing?.title || ''}
              <span className="block text-[11px] text-muted-foreground mt-1">
                Modifier l'annonce — les modifications sont journalisées dans Admin Logs.
              </span>
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 py-2">
            <div className="md:col-span-2 space-y-1">
              <label className="text-xs text-muted-foreground">Title *</label>
              <Input value={editModal.form.title || ''} onChange={(e) => setEditModal(m => ({ ...m, form: { ...m.form, title: e.target.value } }))} data-testid="edit-title-input" />
            </div>
            <div className="md:col-span-2 space-y-1">
              <label className="text-xs text-muted-foreground">Description</label>
              <textarea className="w-full h-24 px-3 py-2 text-sm border rounded-md bg-background"
                value={editModal.form.description || ''}
                onChange={(e) => setEditModal(m => ({ ...m, form: { ...m.form, description: e.target.value } }))}
                data-testid="edit-description-input" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Category</label>
              <Input value={editModal.form.category || ''} onChange={(e) => setEditModal(m => ({ ...m, form: { ...m.form, category: e.target.value } }))} />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Starting Price (CAD)</label>
              <Input type="number" step="0.01" value={editModal.form.starting_price || 0} onChange={(e) => setEditModal(m => ({ ...m, form: { ...m.form, starting_price: e.target.value } }))} data-testid="edit-starting-price" />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Reserve Price (optional)</label>
              <Input type="number" step="0.01" value={editModal.form.reserve_price ?? ''} onChange={(e) => setEditModal(m => ({ ...m, form: { ...m.form, reserve_price: e.target.value } }))} />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Buy Now (optional)</label>
              <Input type="number" step="0.01" value={editModal.form.buy_now_price ?? ''} onChange={(e) => setEditModal(m => ({ ...m, form: { ...m.form, buy_now_price: e.target.value } }))} />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">City</label>
              <Input value={editModal.form.city || ''} onChange={(e) => setEditModal(m => ({ ...m, form: { ...m.form, city: e.target.value } }))} />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Region / Province</label>
              <Input value={editModal.form.region || ''} onChange={(e) => setEditModal(m => ({ ...m, form: { ...m.form, region: e.target.value } }))} />
            </div>

            {/* iter220 Task 4 — Image Asset Manager (admin only).
                Append new uploads or delete bad ones inline. Saved atomically
                with the rest of the form via /admin/(multi-item-)listings/:id. */}
            <div className="md:col-span-2 space-y-2 pt-2 border-t" data-testid="edit-images-manager">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-muted-foreground">
                  Images ({(editModal.form.images || []).length}/30)
                </label>
                <label className="text-xs font-semibold text-cyan-600 hover:text-cyan-700 cursor-pointer">
                  + Upload
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) uploadEditImageFile(f);
                      e.target.value = '';
                    }}
                    data-testid="edit-images-upload-input"
                  />
                </label>
              </div>
              {(editModal.form.images || []).length === 0 ? (
                <p className="text-xs text-muted-foreground italic">No images yet. Upload one or paste a URL below.</p>
              ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-2" data-testid="edit-images-grid">
                  {(editModal.form.images || []).map((src, idx) => (
                    <div key={`${src}-${idx}`} className="relative group rounded-md overflow-hidden border border-slate-200">
                      <img
                        src={src}
                        alt={`asset-${idx}`}
                        className="aspect-square object-cover w-full"
                        onError={(e) => { e.currentTarget.style.opacity = '0.3'; }}
                      />
                      <button
                        type="button"
                        onClick={() => removeEditImage(idx)}
                        className="absolute top-1 right-1 inline-flex items-center justify-center w-6 h-6 rounded-full bg-red-600 text-white opacity-0 group-hover:opacity-100 transition-opacity text-xs font-bold"
                        title="Remove image"
                        data-testid={`edit-image-remove-${idx}`}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <Input
                  placeholder="Paste image URL (https://…)"
                  className="flex-1 text-xs"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addEditImageUrl(e.currentTarget.value);
                      e.currentTarget.value = '';
                    }
                  }}
                  data-testid="edit-images-url-input"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditModal({ open: false, listing: null, form: {} })}>Cancel</Button>
            <AsyncButton onAction={saveEdit} successMessage="Listing updated"
              data-testid="edit-save-btn">Save Changes</AsyncButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog state={bulkConfirm} onClose={() => setBulkConfirm(null)} />

      {/* FEATURE PATCH v9 / Feature 1 — Edit End Time Modal */}
      <Dialog open={endTimeModal.open} onOpenChange={(v) => !v && setEndTimeModal({ open: false, listing: null, newEndTime: '', reason: '', history: [] })}>
        <DialogContent className="max-w-xl" data-testid="end-time-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-cyan-600" /> Edit Auction End Time
            </DialogTitle>
            <DialogDescription>
              {endTimeModal.listing?.title || ''}
              <span className="block text-[11px] text-muted-foreground mt-1">
                Modifier l'heure de fin · The seller, all bidders (active + outbid), and watchlist users will be notified by email + in-app.
              </span>
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {endTimeModal.listing?.auction_end_date && (
              <div className="rounded-md bg-slate-50 border border-slate-200 px-3 py-2 text-sm">
                <span className="text-muted-foreground">Current end time: </span>
                <span className="font-medium" data-testid="end-time-current">
                  {new Date(endTimeModal.listing.auction_end_date).toLocaleString()}
                </span>
              </div>
            )}
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">New end time *</label>
              <Input
                type="datetime-local"
                value={endTimeModal.newEndTime}
                onChange={(e) => setEndTimeModal((m) => ({ ...m, newEndTime: e.target.value }))}
                data-testid="end-time-input"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Reason (recorded in audit log)</label>
              <Input
                placeholder="e.g. Extending by 24h due to platform outage"
                value={endTimeModal.reason}
                onChange={(e) => setEndTimeModal((m) => ({ ...m, reason: e.target.value }))}
                data-testid="end-time-reason-input"
                maxLength={500}
              />
            </div>
            {endTimeModal.history && endTimeModal.history.length > 0 && (
              <div className="rounded-md bg-amber-50 border border-amber-200 p-3" data-testid="end-time-history-list">
                <p className="text-xs font-semibold text-amber-900 mb-2">Recent edits ({endTimeModal.history.length})</p>
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {endTimeModal.history.slice(0, 5).map((h) => (
                    <div key={h.id} className="text-[11px] text-slate-700">
                      <span className="font-mono">{new Date(h.timestamp).toLocaleString()}</span>
                      {' · '}
                      <span className="font-medium">{h.admin_email}</span>
                      {' · '}
                      <span>
                        {h.old_end_time ? new Date(h.old_end_time).toLocaleString() : '—'} → {new Date(h.new_end_time).toLocaleString()}
                      </span>
                      {h.reason && <span className="italic"> · {h.reason}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEndTimeModal({ open: false, listing: null, newEndTime: '', reason: '', history: [] })}>
              Cancel
            </Button>
            <AsyncButton onAction={saveEndTime} successMessage="End time updated" data-testid="end-time-save-btn">
              Update End Time
            </AsyncButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* iter343 BUG-4 — per-lot editor */}
      <AdminLotEditorModal
        open={lotEditor.open}
        onOpenChange={(o) => setLotEditor((m) => ({ ...m, open: o }))}
        listing={lotEditor.listing}
        headers={headers}
      />
    </div>
  );
};

export default ManageAllAuctions;
