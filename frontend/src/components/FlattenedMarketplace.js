import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Badge } from './ui/badge';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Separator } from './ui/separator';
import BidConfirmationDialog from './BidConfirmationDialog';
import { 
  Clock, 
  Gavel, 
  Package, 
  TrendingUp, 
  Star,
  Sparkles,
  MapPin,
  User,
  Search,
  Filter,
  ShieldCheck,
  Zap,
  ChevronRight,
  Eye,
  DollarSign,
  Timer,
  ExternalLink,
  Receipt,
  Scale,
  X
} from 'lucide-react';
import { toast } from 'sonner';
import { formatCurrency } from '../utils/currencyFormatter';
import { useCategories } from '../hooks/useCategories';
import { useMarketplaceItems } from '../hooks/useMarketplaceItems';
import { SellerRatingInline } from './SellerReputation';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * FlattenedMarketplace - Item-Centric Discovery View
 * 
 * Key Features:
 * - Displays individual items/lots as standalone cards
 * - Dynamic Private Sale / Business Sale badges
 * - Live countdown timers per item
 * - Quick Bid functionality without leaving page
 * - "Show Private Sales Only" filter toggle
 * - Universal search across all lots
 * - Link to parent auction for related items
 */
const FlattenedMarketplace = ({ 
  limit = 50, 
  showFilters = true,
  showHeader = true,
  variant = 'full', // 'full', 'compact', 'homepage'
  externalFilters = {}
}) => {
  const { t } = useTranslation();
  const { user, token } = useAuth();
  const navigate = useNavigate();
  
  // Filters
  const [filters, setFilters] = useState({
    search: '',
    category: '',
    min_price: '',
    max_price: '',
    condition: '',
    sort: '-promoted',
    private_sales_only: false // New filter for tax savings
  });
  
  // Quick Bid Modal State
  const [quickBidOpen, setQuickBidOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [bidAmount, setBidAmount] = useState('');
  const [bidConfirmOpen, setBidConfirmOpen] = useState(false);
  const [placingBid, setPlacingBid] = useState(false);

  // Compare mode state
  const [compareIds, setCompareIds] = useState([]);
  const toggleCompare = (id) => {
    setCompareIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : prev.length < 4 ? [...prev, id] : prev
    );
  };
  
  // React Query: categories
  const { data: categories = [] } = useCategories();
  
  // Debounced filters — prevents API call on every keystroke
  const [debouncedFilters, setDebouncedFilters] = useState(filters);
  const debounceTimerRef = useRef(null);

  // Debounce filter changes by 300ms
  useEffect(() => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(() => {
      setDebouncedFilters(filters);
    }, 300);
    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, [filters]);

  // React Query: infinite marketplace items with cursor pagination
  const {
    data: marketplaceData,
    isLoading: loading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch: refetchItems,
  } = useMarketplaceItems(debouncedFilters, limit);

  // Flatten pages into a single items array
  const allItems = (marketplaceData?.pages ?? []).flatMap((page) => page.items ?? []);
  const items = filters.private_sales_only
    ? allItems.filter((item) => !item.seller_is_business)
    : allItems;
  const total = marketplaceData?.pages?.[0]?.total ?? 0;
  const hasMore = hasNextPage;

  // Batch-fetch seller reputations for all visible items
  const [sellerReps, setSellerReps] = useState({});
  useEffect(() => {
    const sellerIds = [...new Set(allItems.map(i => i.seller_id).filter(Boolean))];
    if (sellerIds.length === 0) return;
    axios.post(`${API}/reviews/reputation/batch`, { seller_ids: sellerIds })
      .then(res => setSellerReps(res.data.reputations || {}))
      .catch(() => {});
  }, [allItems.length]); // re-fetch when items change

  const trackClick = async (itemId) => {
    try {
      await axios.post(`${API}/marketplace/items/${itemId}/track-click`);
    } catch (error) {
      console.error('Error tracking click:', error);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const openQuickBid = (item, e) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (!token) {
      navigate('/auth', { state: { from: { pathname: '/marketplace' } } });
      return;
    }
    
    setSelectedItem(item);
    const minBid = (item.current_price || item.starting_price || 0) + 10;
    setBidAmount(minBid.toFixed(2));
    setQuickBidOpen(true);
  };

  const handleQuickBidSubmit = () => {
    const amount = parseFloat(bidAmount);
    if (isNaN(amount) || amount <= 0) {
      toast.error('Please enter a valid bid amount');
      return;
    }
    
    if (amount <= (selectedItem?.current_price || 0)) {
      toast.error('Bid must be higher than current price');
      return;
    }
    
    // Show cost breakdown confirmation
    setBidConfirmOpen(true);
  };

  const confirmBid = async () => {
    if (!selectedItem || !token) return;
    
    setPlacingBid(true);
    try {
      const response = await axios.post(
        `${API}/multi-item-listings/${selectedItem.auction_id}/lots/${selectedItem.lot_number}/bid`,
        { amount: parseFloat(bidAmount) },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      toast.success('Bid placed successfully!');
      setBidConfirmOpen(false);
      setQuickBidOpen(false);
      setSelectedItem(null);
      setBidAmount('');
      
      // Refresh items via React Query
      refetchItems();
    } catch (error) {
      const detail = error.response?.data?.detail;
      let message = 'Failed to place bid';
      if (typeof detail === 'string') {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail.map(e => (typeof e === 'string' ? e : e?.msg || '')).filter(Boolean).join(', ') || message;
      } else if (detail && typeof detail === 'object') {
        message = detail.msg || JSON.stringify(detail);
      }
      toast.error(message);
    } finally {
      setPlacingBid(false);
    }
  };

  return (
    <div className={`overflow-x-hidden ${variant === 'homepage' ? '' : variant === 'full' ? '' : 'container mx-auto px-4 py-8'}`}>
      {/* Header */}
      {showHeader && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-cyan-500 bg-clip-text text-transparent">
                {t('marketplace.browseItems', 'Browse Individual Items')}
              </h1>
              <p className="text-slate-600 dark:text-slate-400">
                {t('marketplace.itemsFromAuctions', 'Individual lots from active auctions')}
              </p>
            </div>
            <Badge className="bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-green-200 dark:border-green-700">
              {total} items
            </Badge>
          </div>
        </div>
      )}

      {/* Filters — sticky horizontal bar */}
      {showFilters && (
        <div className="sticky top-0 z-10 bg-white/95 dark:bg-slate-900/95 backdrop-blur -mx-4 px-4 py-3 mb-4 border-b border-slate-200 dark:border-slate-700">
          {/* Scrollable filter row */}
          <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide items-center" style={{ WebkitOverflowScrolling: 'touch' }}>
            {/* Private Sales Toggle */}
            <Button
              variant={filters.private_sales_only ? 'default' : 'outline'}
              onClick={() => handleFilterChange('private_sales_only', !filters.private_sales_only)}
              className={`gap-1.5 flex-shrink-0 text-xs h-9 ${filters.private_sales_only ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white' : ''}`}
              size="sm"
            >
              <User className="h-3.5 w-3.5" />
              {filters.private_sales_only ? 'Private Sales' : 'Private Sales'}
            </Button>

            {/* Search */}
            <div className="relative flex-shrink-0 w-44 sm:w-56">
              <Search className="absolute left-2.5 top-1/2 transform -translate-y-1/2 text-muted-foreground h-3.5 w-3.5" />
              <Input
                placeholder="Search items..."
                value={filters.search}
                onChange={(e) => handleFilterChange('search', e.target.value)}
                className="pl-8 h-9 text-xs"
              />
            </div>

            {/* Category */}
            <select
              value={filters.category}
              onChange={(e) => handleFilterChange('category', e.target.value)}
              className="px-3 py-1.5 border border-input rounded-md bg-background text-xs h-9 flex-shrink-0"
            >
              <option value="">{t("marketplace.allCategories")}</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.name_en}>{cat.name_en}</option>
              ))}
            </select>

            {/* Condition */}
            <select
              value={filters.condition}
              onChange={(e) => handleFilterChange('condition', e.target.value)}
              className="px-3 py-1.5 border border-input rounded-md bg-background text-xs h-9 flex-shrink-0"
            >
              <option value="">{t("marketplace.allConditions")}</option>
              <option value="new">New</option>
              <option value="like_new">{t("marketplace.likeNew")}</option>
              <option value="excellent">{t("marketplace.excellent")}</option>
              <option value="good">Good</option>
              <option value="fair">Fair</option>
            </select>

            {/* Sort */}
            <select
              value={filters.sort}
              onChange={(e) => handleFilterChange('sort', e.target.value)}
              className="px-3 py-1.5 border border-input rounded-md bg-background text-xs h-9 flex-shrink-0"
            >
              <option value="-promoted">{t("marketplace.featuredFirst")}</option>
              <option value="ending_soon">{t("marketplace.endingSoon")}</option>
              <option value="price">Price: Low → High</option>
              <option value="-price">Price: High → Low</option>
              <option value="-created_at">{t("marketplace.newestFirst")}</option>
            </select>

            {/* Min / Max Price */}
            <Input
              type="number"
              placeholder="Min $"
              value={filters.min_price}
              onChange={(e) => handleFilterChange('min_price', e.target.value)}
              className="w-20 flex-shrink-0 h-9 text-xs"
            />
            <Input
              type="number"
              placeholder="Max $"
              value={filters.max_price}
              onChange={(e) => handleFilterChange('max_price', e.target.value)}
              className="w-20 flex-shrink-0 h-9 text-xs"
            />
          </div>
        </div>
      )}

      {/* Items Grid */}
      {loading && items.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[...Array(6)].map((_, i) => (
            <Card key={i} className="animate-pulse">
              <div className="h-52 bg-gray-200 dark:bg-slate-700 rounded-t-lg"></div>
              <CardContent className="p-4 space-y-2">
                <div className="h-4 bg-gray-200 dark:bg-slate-700 rounded"></div>
                <div className="h-4 bg-gray-200 dark:bg-slate-700 rounded w-3/4"></div>
                <div className="h-8 bg-gray-200 dark:bg-slate-700 rounded mt-4"></div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 bg-slate-50 dark:bg-slate-800 rounded-xl">
          <Package className="h-16 w-16 text-slate-400 dark:text-slate-500 mx-auto mb-4" />
          <h3 className="text-xl font-semibold mb-2 text-slate-900 dark:text-white">No items found</h3>
          <p className="text-slate-600 dark:text-slate-400 mb-4">
            Try adjusting your filters or search terms
          </p>
          <Button onClick={() => setFilters({
            search: '',
            category: '',
            min_price: '',
            max_price: '',
            condition: '',
            sort: '-promoted',
            private_sales_only: false
          })} className="bg-blue-600 text-white hover:bg-blue-700">
            Clear All Filters
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {items.map((item) => (
            <ItemCard 
              key={item.id} 
              item={item} 
              onQuickBid={openQuickBid}
              trackClick={trackClick}
              isComparing={compareIds.includes(item.id)}
              onToggleCompare={toggleCompare}
              sellerRep={sellerReps[item.seller_id]}
            />
          ))}
        </div>
      )}

      {/* Load More */}
      {hasMore && !loading && (
        <div className="text-center mt-8">
          <Button 
            onClick={() => fetchNextPage()} 
            variant="outline"
            className="px-8"
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? 'Loading...' : 'Load More Items'}
          </Button>
        </div>
      )}

      {/* Quick Bid Modal */}
      <Dialog open={quickBidOpen} onOpenChange={setQuickBidOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-cyan-500" />
              Quick Bid
            </DialogTitle>
            <DialogDescription>
              Place a bid on &quot;{selectedItem?.title}&quot;
            </DialogDescription>
          </DialogHeader>

          {selectedItem && (
            <div className="space-y-4">
              {/* Item Preview */}
              <div className="flex gap-4 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                {selectedItem.images?.[0] && (
                  <img 
                    src={selectedItem.images[0]} 
                    alt={selectedItem.title}
                    width={80}
                    height={80}
                    className="w-20 h-20 object-cover rounded-lg"
                  />
                )}
                <div className="flex-1">
                  <h4 className="font-semibold line-clamp-1">{selectedItem.title}</h4>
                  <p className="text-sm text-muted-foreground">
                    Current: {formatCurrency(selectedItem.current_price)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {selectedItem.bid_count || 0} bids
                  </p>
                </div>
              </div>

              {/* Seller Type Badge */}
              {!selectedItem.seller_is_business && (
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-green-600" />
                    <span className="font-medium text-green-700 dark:text-green-400">
                      Private Sale - No tax on hammer price!
                    </span>
                  </div>
                </div>
              )}

              {/* Bid Input */}
              <div>
                <label className="text-sm font-medium mb-2 block">Your Bid Amount ($)</label>
                <Input
                  type="number"
                  step="0.01"
                  min={(selectedItem.current_price || 0) + 1}
                  value={bidAmount}
                  onChange={(e) => setBidAmount(e.target.value)}
                  placeholder={`Min: ${formatCurrency((selectedItem.current_price || 0) + 10)}`}
                  className="text-lg font-semibold"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Minimum bid: {formatCurrency((selectedItem.current_price || 0) + 10)}
                </p>
              </div>
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setQuickBidOpen(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleQuickBidSubmit}
              className="bg-gradient-to-r from-blue-600 to-cyan-500 text-white"
            >
              <Receipt className="h-4 w-4 mr-2" />
              Review Total Cost
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bid Confirmation Dialog with Cost Breakdown */}
      {selectedItem && (
        <BidConfirmationDialog
          isOpen={bidConfirmOpen}
          onClose={() => setBidConfirmOpen(false)}
          onConfirm={confirmBid}
          bidAmount={parseFloat(bidAmount) || 0}
          listingTitle={selectedItem.title}
          sellerIsBusiness={selectedItem.seller_is_business || false}
          region={selectedItem.region || 'QC'}
          loading={placingBid}
        />
      )}

      {/* Floating Compare Bar */}
      {compareIds.length > 0 && (
        <div className="fixed bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-40 bg-slate-900 dark:bg-slate-800 text-white rounded-full shadow-2xl px-5 py-3 flex items-center gap-3 border border-cyan-500/30" data-testid="compare-floating-bar">
          <Scale className="h-4 w-4 text-cyan-400 shrink-0" />
          <span className="text-sm font-medium whitespace-nowrap">{compareIds.length} selected</span>
          <Button
            size="sm"
            onClick={() => navigate(`/compare?ids=${compareIds.join(',')}`)}
            className="bg-cyan-500 hover:bg-cyan-600 text-white rounded-full h-8 px-4 text-xs font-bold"
            data-testid="compare-go-btn"
          >
            Compare
          </Button>
          <button onClick={() => setCompareIds([])} className="text-slate-400 hover:text-white" data-testid="compare-clear-btn">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
};

/**
 * ItemCard - Individual item card component
 */
const ItemCard = ({ item, onQuickBid, trackClick, isComparing, onToggleCompare, sellerRep }) => {
  const [timeLeft, setTimeLeft] = useState('');
  const [isUrgent, setIsUrgent] = useState(false);

  useEffect(() => {
    const calculateTimeLeft = () => {
      if (!item.auction_end_date) return 'N/A';
      
      const end = new Date(item.auction_end_date);
      const now = new Date();
      const diff = end - now;
      
      if (diff <= 0) return 'Ended';
      
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);
      
      // Set urgent if less than 1 hour
      setIsUrgent(diff < 60 * 60 * 1000);
      
      if (days > 0) return `${days}d ${hours}h`;
      if (hours > 0) return `${hours}h ${minutes}m`;
      return `${minutes}m ${seconds}s`;
    };

    setTimeLeft(calculateTimeLeft());
    const timer = setInterval(() => setTimeLeft(calculateTimeLeft()), 1000);
    return () => clearInterval(timer);
  }, [item.auction_end_date]);

  const getPromotionBadge = () => {
    if (item.promotion_tier === 'premium') {
      return (
        <Badge className="bg-gradient-to-r from-yellow-400 to-orange-500 text-white font-bold text-xs">
          <Sparkles className="h-3 w-3 mr-1" />
          PREMIUM
        </Badge>
      );
    }
    if (item.promotion_tier === 'standard' || item.is_featured) {
      return (
        <Badge className="bg-gradient-to-r from-blue-500 to-purple-500 text-white font-bold text-xs">
          <Star className="h-3 w-3 mr-1" />
          FEATURED
        </Badge>
      );
    }
    if (item.is_promoted) {
      return (
        <Badge className="bg-slate-600 text-white text-xs">
          <TrendingUp className="h-3 w-3 mr-1" />
          Sponsored
        </Badge>
      );
    }
    return null;
  };

  const isPrivateSale = !item.seller_is_business;
  // Smart routing: standalone listings go to /listing/:id, multi-lot items go to /lots/:auctionId
  const detailLink = item.auction_id ? `/lots/${item.auction_id}` : `/listing/${item.id}`;

  return (
    <Card className="group hover:shadow-xl transition-all duration-300 overflow-hidden border-0 shadow-md flex flex-col" data-testid="marketplace-item-card">
      {/* Image Container */}
      <Link
        to={detailLink}
        onClick={() => trackClick(item.id)}
        className="block"
      >
        <div className="relative h-52 bg-slate-100 dark:bg-slate-800 overflow-hidden">
          {item.images?.[0] ? (
            <img
              src={item.images[0]}
              alt={item.title}
              width={400}
              height={208}
              loading="lazy"
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Package className="h-16 w-16 text-gray-300" />
            </div>
          )}

          {/* Top Left - Badges stack */}
          <div className="absolute top-3 left-3 z-10 flex flex-col gap-1.5">
            {isPrivateSale ? (
              <Badge className="bg-gradient-to-r from-green-500 to-emerald-500 text-white border-0 shadow-lg text-xs">
                <User className="h-3 w-3 mr-1" />
                Private Sale
              </Badge>
            ) : (
              <Badge className="bg-blue-100 text-blue-700 border-blue-200 text-xs">
                <ShieldCheck className="h-3 w-3 mr-1" />
                Business
              </Badge>
            )}
            {/* Verified Partner Badge */}
            {item.is_partner_listing && (
              <Badge className="bg-violet-600 text-white border-0 shadow-lg text-xs" data-testid="partner-badge">
                <ShieldCheck className="h-3 w-3 mr-1" />
                Verified Partner
              </Badge>
            )}
          </div>

          {/* Top Right - Promotion Badge */}
          {getPromotionBadge() && (
            <div className="absolute top-3 right-3 z-10">
              {getPromotionBadge()}
            </div>
          )}

          {/* Compare checkbox */}
          <button
            onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggleCompare(item.id); }}
            className={`absolute ${getPromotionBadge() ? 'top-10' : 'top-3'} right-3 z-20 w-7 h-7 rounded-full flex items-center justify-center transition-all shadow-md ${
              isComparing
                ? 'bg-cyan-500 text-white scale-110'
                : 'bg-white/80 dark:bg-slate-800/80 text-slate-500 opacity-0 group-hover:opacity-100'
            }`}
            data-testid={`compare-toggle-${item.id}`}
            title="Add to compare"
          >
            <Scale className="h-3.5 w-3.5" />
          </button>

          {/* Bottom - Timer */}
          <div className="absolute bottom-3 left-3 right-3 flex justify-between items-center">
            <div className={`px-3 py-1.5 rounded-full text-xs font-bold flex items-center gap-1.5 shadow-lg ${
              isUrgent 
                ? 'bg-red-500 text-white animate-pulse' 
                : 'bg-slate-900/80 backdrop-blur text-white'
            }`}>
              <Timer className="h-3.5 w-3.5" />
              {timeLeft}
            </div>
            
            {item.bid_count > 0 && (
              <div className="bg-slate-900/80 backdrop-blur text-white px-2 py-1 rounded-full text-xs">
                <Gavel className="h-3 w-3 inline mr-1" />
                {item.bid_count} bids
              </div>
            )}
          </div>
        </div>
      </Link>

      <CardContent className="p-4 flex flex-col flex-1 gap-2.5" data-testid="item-card">
        {/* Title */}
        <Link
          to={detailLink}
          onClick={() => trackClick(item.id)}
          className="block"
        >
          <h3 
            className="font-semibold text-base line-clamp-2 text-slate-900 dark:text-white hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors"
            data-testid="item-title"
          >
            {item.title}
          </h3>
        </Link>

        {/* Seller Rating */}
        <SellerRatingInline sellerId={item.seller_id} reputation={sellerRep} />

        {/* Location */}
        {item.city && (
          <div className="flex items-center text-sm text-slate-500 dark:text-slate-400">
            <MapPin className="h-3.5 w-3.5 mr-1 flex-shrink-0" />
            <span className="truncate">{item.city}, {item.region}</span>
          </div>
        )}

        {/* Tax Savings Banner (Private Sale) */}
        {isPrivateSale && (
          <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg px-3 py-1.5 text-xs">
            <span className="font-medium text-green-700 dark:text-green-400">
              Save ~15% - No tax on item price!
            </span>
          </div>
        )}

        {/* Spacer to push pricing and actions to the bottom */}
        <div className="flex-1" />

        {/* Pricing */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider">Current Bid</span>
            <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-cyan-500 bg-clip-text text-transparent">
              {formatCurrency(item.current_price || item.starting_price || 0)}
            </span>
          </div>

          {item.buy_now_enabled && item.buy_now_price && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600 dark:text-slate-400">Buy Now</span>
              <span className="font-semibold text-green-600 dark:text-green-400">
                {formatCurrency(item.buy_now_price)}
              </span>
            </div>
          )}
        </div>

        {/* Parent Auction Link */}
        {item.auction_id && item.lot_number && (
          <div className="text-xs text-slate-500 dark:text-slate-400 pt-1 border-t border-slate-200 dark:border-slate-700">
            Lot #{item.lot_number} of{' '}
            <Link
              to={`/lots/${item.auction_id}`}
              className="text-cyan-600 dark:text-cyan-400 hover:underline inline-flex items-center gap-1"
            >
              {item.parent_auction_title || 'Auction'}
              <ExternalLink className="h-3 w-3" />
            </Link>
          </div>
        )}

        {/* Actions — always at bottom */}
        <div className="flex gap-2 pt-1">
          <Button
            onClick={(e) => onQuickBid(item, e)}
            size="sm"
            className="flex-1 bg-gradient-to-r from-blue-600 to-cyan-500 text-white hover:from-blue-700 hover:to-cyan-600 h-9 text-sm"
            data-testid="quick-bid-btn"
          >
            <Zap className="h-3.5 w-3.5 mr-1 flex-shrink-0" />
            Quick Bid
          </Button>
          <Link to={detailLink} className="flex-1">
            <Button variant="outline" size="sm" className="w-full border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200 h-9 text-sm" data-testid="view-item-btn">
              <Eye className="h-3.5 w-3.5 mr-1 flex-shrink-0" />
              View
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
};

export default FlattenedMarketplace;
