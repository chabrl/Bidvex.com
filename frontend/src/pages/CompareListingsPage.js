import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { formatCurrency } from '../utils/currencyFormatter';
import {
  ArrowLeft, X, Plus, Search, Clock, MapPin, Eye,
  Package, Gavel, Scale, ChevronDown, ChevronUp, ExternalLink
} from 'lucide-react';
import { toast } from 'sonner';
import SEO from '../components/SEO';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const MAX_COMPARE = 4;

const CompareListingsPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [expandedSections, setExpandedSections] = useState({
    pricing: true, details: true, shipping: true, auction: true,
  });

  // Load listings from URL params on mount
  useEffect(() => {
    const ids = searchParams.get('ids');
    if (ids) {
      const idArray = ids.split(',').slice(0, MAX_COMPARE);
      fetchListings(idArray);
    }
  }, []);

  const fetchListings = async (ids) => {
    setLoading(true);
    try {
      const results = await Promise.all(
        ids.map(id =>
          axios.get(`${API}/listings/${id}`).then(r => r.data).catch(() => null)
        )
      );
      setListings(results.filter(Boolean));
    } catch (err) {
      toast.error('Failed to load listings');
    } finally {
      setLoading(false);
    }
  };

  const addListing = useCallback((listing) => {
    if (listings.length >= MAX_COMPARE) {
      toast.error(`Maximum ${MAX_COMPARE} items to compare`);
      return;
    }
    if (listings.find(l => l.id === listing.id)) {
      toast.error('Already in comparison');
      return;
    }
    const next = [...listings, listing];
    setListings(next);
    setSearchParams({ ids: next.map(l => l.id).join(',') });
    setShowSearch(false);
    setSearchQuery('');
    setSearchResults([]);
  }, [listings, setSearchParams]);

  const removeListing = useCallback((id) => {
    const next = listings.filter(l => l.id !== id);
    setListings(next);
    if (next.length > 0) {
      setSearchParams({ ids: next.map(l => l.id).join(',') });
    } else {
      setSearchParams({});
    }
  }, [listings, setSearchParams]);

  const searchListings = useCallback(async (q) => {
    if (!q || q.length < 2) { setSearchResults([]); return; }
    setSearching(true);
    try {
      const { data } = await axios.get(`${API}/listings`, { params: { search: q, limit: 8 } });
      const existing = new Set(listings.map(l => l.id));
      setSearchResults((data || []).filter(l => !existing.has(l.id)));
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }, [listings]);

  useEffect(() => {
    const timer = setTimeout(() => searchListings(searchQuery), 350);
    return () => clearTimeout(timer);
  }, [searchQuery, searchListings]);

  const toggleSection = (key) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const timeLeft = (endDate) => {
    if (!endDate) return 'N/A';
    const diff = new Date(endDate) - new Date();
    if (diff <= 0) return 'Ended';
    const d = Math.floor(diff / 86400000);
    const h = Math.floor((diff % 86400000) / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    if (d > 0) return `${d}d ${h}h`;
    return `${h}h ${m}m`;
  };

  const colWidth = listings.length > 0
    ? `${Math.floor(100 / Math.max(listings.length, 1))}%`
    : '100%';

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900" data-testid="compare-page">
      <SEO title="Compare Listings — BidVex" description="Compare auction listings side by side" path="/compare" />

      {/* Header */}
      <div className="bg-gradient-to-r from-blue-900 via-slate-900 to-cyan-900">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="flex items-center gap-4 mb-3">
            <Button variant="ghost" size="icon" onClick={() => navigate(-1)} className="text-white hover:bg-white/10" data-testid="compare-back-btn">
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div className="p-2.5 bg-cyan-500/20 backdrop-blur rounded-xl border border-cyan-400/30">
              <Scale className="h-7 w-7 text-cyan-300" />
            </div>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-white">Compare Listings</h1>
              <p className="text-blue-200/80 text-sm">{listings.length}/{MAX_COMPARE} items selected</p>
            </div>
          </div>
        </div>
      </div>

      {/* Empty state */}
      {listings.length === 0 && !loading && (
        <div className="max-w-2xl mx-auto px-4 py-20 text-center" data-testid="compare-empty-state">
          <Scale className="h-16 w-16 mx-auto mb-6 text-slate-300 dark:text-slate-600" />
          <h2 className="text-xl font-semibold text-slate-700 dark:text-slate-200 mb-2">No items to compare</h2>
          <p className="text-slate-500 dark:text-slate-400 mb-8">Search for listings to start a side-by-side comparison.</p>
          <Button onClick={() => setShowSearch(true)} className="bg-cyan-600 hover:bg-cyan-700 text-white" data-testid="compare-add-first-btn">
            <Plus className="h-4 w-4 mr-2" /> Add First Listing
          </Button>
        </div>
      )}

      {/* Main comparison area */}
      {(listings.length > 0 || loading) && (
        <div className="max-w-7xl mx-auto px-4 py-6">
          {/* Add more button */}
          {listings.length < MAX_COMPARE && (
            <div className="flex justify-end mb-4">
              <Button variant="outline" onClick={() => setShowSearch(true)} className="border-cyan-500 text-cyan-600 hover:bg-cyan-50 dark:hover:bg-cyan-900/20" data-testid="compare-add-btn">
                <Plus className="h-4 w-4 mr-1" /> Add Listing
              </Button>
            </div>
          )}

          {/* ── Desktop: Side-by-side table ── */}
          <div className="hidden md:block overflow-x-auto" data-testid="compare-desktop-table">
            <table className="w-full border-collapse">
              {/* Images row */}
              <thead>
                <tr>
                  {listings.map(l => (
                    <th key={l.id} style={{ width: colWidth }} className="p-3 align-top">
                      <CompareCard listing={l} onRemove={removeListing} navigate={navigate} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* Pricing section */}
                <SectionHeader title="Pricing" section="pricing" expanded={expandedSections.pricing} toggle={toggleSection} cols={listings.length} />
                {expandedSections.pricing && (
                  <>
                    <CompareRow label="Current Price" listings={listings} render={l => (
                      <span className="text-lg font-bold text-cyan-600 dark:text-cyan-400">{formatCurrency(l.current_price)}</span>
                    )} />
                    <CompareRow label="Starting Price" listings={listings} render={l => formatCurrency(l.starting_price)} />
                    <CompareRow label="Buy Now Price" listings={listings} render={l => l.buy_now_price ? formatCurrency(l.buy_now_price) : <span className="text-slate-400">—</span>} />
                    <CompareRow label="Total Bids" listings={listings} render={l => l.total_bids || l.bid_count || 0} />
                  </>
                )}

                {/* Details section */}
                <SectionHeader title="Details" section="details" expanded={expandedSections.details} toggle={toggleSection} cols={listings.length} />
                {expandedSections.details && (
                  <>
                    <CompareRow label="Category" listings={listings} render={l => <Badge variant="outline">{l.category || 'N/A'}</Badge>} />
                    <CompareRow label="Condition" listings={listings} render={l => l.condition || 'N/A'} />
                    <CompareRow label="Location" listings={listings} render={l => [l.city, l.region].filter(Boolean).join(', ') || 'N/A'} />
                    <CompareRow label="Views" listings={listings} render={l => (
                      <span className="flex items-center gap-1"><Eye className="h-3.5 w-3.5" /> {l.views || 0}</span>
                    )} />
                  </>
                )}

                {/* Auction section */}
                <SectionHeader title="Auction" section="auction" expanded={expandedSections.auction} toggle={toggleSection} cols={listings.length} />
                {expandedSections.auction && (
                  <>
                    <CompareRow label="Time Left" listings={listings} render={l => {
                      const tl = timeLeft(l.auction_end_date);
                      const urgent = tl.includes('h') && !tl.includes('d') && tl !== 'Ended';
                      return <Badge className={urgent ? 'bg-red-500 text-white' : 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200'}>{tl}</Badge>;
                    }} />
                    <CompareRow label="Status" listings={listings} render={l => (
                      <Badge className={l.status === 'active' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-slate-200 text-slate-600'}>
                        {l.status || 'active'}
                      </Badge>
                    )} />
                    <CompareRow label="Listing Type" listings={listings} render={l => l.listing_type === 'private_sale' ? 'Private Sale' : 'Business Sale'} />
                  </>
                )}

                {/* Shipping section */}
                <SectionHeader title="Shipping" section="shipping" expanded={expandedSections.shipping} toggle={toggleSection} cols={listings.length} />
                {expandedSections.shipping && (
                  <CompareRow label="Shipping Info" listings={listings} render={l => {
                    if (!l.shipping_info) return 'Contact seller';
                    if (typeof l.shipping_info === 'string') return l.shipping_info;
                    // Handle object shipping_info
                    const methods = l.shipping_info.methods?.join(', ') || '';
                    return methods || (l.shipping_info.available ? 'Available' : 'Contact seller');
                  }} />
                )}
              </tbody>
            </table>
          </div>

          {/* ── Mobile: Stacked cards ── */}
          <div className="md:hidden space-y-4" data-testid="compare-mobile-cards">
            {listings.map(l => (
              <MobileCompareCard key={l.id} listing={l} onRemove={removeListing} timeLeft={timeLeft} navigate={navigate} />
            ))}
          </div>
        </div>
      )}

      {/* Search overlay */}
      {showSearch && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-start justify-center pt-20" onClick={() => setShowSearch(false)}>
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl w-full max-w-lg mx-4 max-h-[70vh] overflow-hidden" onClick={e => e.stopPropagation()} data-testid="compare-search-modal">
            <div className="p-4 border-b dark:border-slate-700">
              <div className="flex items-center gap-2">
                <Search className="h-5 w-5 text-slate-400" />
                <Input
                  autoFocus
                  placeholder="Search listings to compare..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="border-0 focus-visible:ring-0 text-base"
                  data-testid="compare-search-input"
                />
                <Button variant="ghost" size="icon" onClick={() => setShowSearch(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div className="overflow-y-auto max-h-[55vh] p-2">
              {searching && <p className="text-center text-sm text-slate-500 py-4">Searching...</p>}
              {!searching && searchResults.length === 0 && searchQuery.length >= 2 && (
                <p className="text-center text-sm text-slate-500 py-4">No results found</p>
              )}
              {searchResults.map(item => (
                <button
                  key={item.id}
                  onClick={() => addListing(item)}
                  className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-left"
                  data-testid={`compare-search-result-${item.id}`}
                >
                  <div className="w-14 h-14 rounded-lg overflow-hidden bg-slate-100 dark:bg-slate-700 shrink-0">
                    {item.images?.[0] ? (
                      <img src={item.images[0]} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center"><Package className="h-6 w-6 text-slate-400" /></div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-sm truncate text-slate-900 dark:text-slate-100">{item.title}</p>
                    <p className="text-sm font-semibold text-cyan-600 dark:text-cyan-400">{formatCurrency(item.current_price)}</p>
                  </div>
                  <Plus className="h-5 w-5 text-cyan-500 shrink-0" />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/* ── Sub-components ── */

const CompareCard = ({ listing, onRemove, navigate }) => (
  <Card className="relative overflow-hidden border-0 shadow-lg dark:bg-slate-800/50 h-full">
    <button onClick={() => onRemove(listing.id)} className="absolute top-2 right-2 z-10 bg-slate-900/60 hover:bg-red-500 text-white rounded-full p-1 transition-colors" data-testid={`compare-remove-${listing.id}`}>
      <X className="h-3.5 w-3.5" />
    </button>
    <div className="relative h-40 bg-slate-100 dark:bg-slate-700 cursor-pointer" onClick={() => navigate(`/listing/${listing.id}`)}>
      {listing.images?.[0] ? (
        <img src={listing.images[0]} alt={listing.title} className="w-full h-full object-cover" />
      ) : (
        <div className="w-full h-full flex items-center justify-center"><Package className="h-10 w-10 text-slate-400" /></div>
      )}
    </div>
    <CardContent className="p-3">
      <h3 className="font-semibold text-sm line-clamp-2 text-slate-900 dark:text-slate-100 mb-1">{listing.title}</h3>
      <Button size="sm" variant="outline" className="w-full text-xs" onClick={() => navigate(`/listing/${listing.id}`)} data-testid={`compare-view-${listing.id}`}>
        <ExternalLink className="h-3 w-3 mr-1" /> View Listing
      </Button>
    </CardContent>
  </Card>
);

const SectionHeader = ({ title, section, expanded, toggle, cols }) => (
  <tr>
    <td colSpan={cols} className="pt-4">
      <button onClick={() => toggle(section)} className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors">
        <span className="font-semibold text-sm text-slate-700 dark:text-slate-200">{title}</span>
        {expanded ? <ChevronUp className="h-4 w-4 text-slate-400 ml-auto" /> : <ChevronDown className="h-4 w-4 text-slate-400 ml-auto" />}
      </button>
    </td>
  </tr>
);

const CompareRow = ({ label, listings, render }) => (
  <tr className="border-b dark:border-slate-700/50">
    {listings.map(l => (
      <td key={l.id} className="p-3 align-top">
        <div className="text-xs text-slate-500 dark:text-slate-400 mb-1">{label}</div>
        <div className="text-sm text-slate-900 dark:text-slate-100">{render(l)}</div>
      </td>
    ))}
  </tr>
);

const MobileCompareCard = ({ listing, onRemove, timeLeft, navigate }) => {
  const tl = timeLeft(listing.auction_end_date);
  return (
    <Card className="overflow-hidden border-0 shadow-lg dark:bg-slate-800/50" data-testid={`compare-mobile-card-${listing.id}`}>
      <div className="flex">
        <div className="w-28 h-28 shrink-0 bg-slate-100 dark:bg-slate-700 cursor-pointer" onClick={() => navigate(`/listing/${listing.id}`)}>
          {listing.images?.[0] ? (
            <img src={listing.images[0]} alt={listing.title} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center"><Package className="h-8 w-8 text-slate-400" /></div>
          )}
        </div>
        <CardContent className="p-3 flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-semibold text-sm line-clamp-1 text-slate-900 dark:text-slate-100">{listing.title}</h3>
            <button onClick={() => onRemove(listing.id)} className="text-slate-400 hover:text-red-500 shrink-0">
              <X className="h-4 w-4" />
            </button>
          </div>
          <p className="text-lg font-bold text-cyan-600 dark:text-cyan-400 mt-1">{formatCurrency(listing.current_price)}</p>
          <div className="flex flex-wrap gap-2 mt-2">
            <Badge variant="outline" className="text-xs">{listing.category || 'N/A'}</Badge>
            <Badge className={tl === 'Ended' ? 'bg-slate-200 text-slate-600 text-xs' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 text-xs'}>
              <Clock className="h-3 w-3 mr-1" /> {tl}
            </Badge>
          </div>
          <div className="flex gap-2 mt-2 text-xs text-slate-500">
            <span><Eye className="h-3 w-3 inline" /> {listing.views || 0}</span>
            <span><Gavel className="h-3 w-3 inline" /> {listing.total_bids || listing.bid_count || 0} bids</span>
            {listing.city && <span><MapPin className="h-3 w-3 inline" /> {listing.city}</span>}
          </div>
        </CardContent>
      </div>
    </Card>
  );
};

export default CompareListingsPage;
