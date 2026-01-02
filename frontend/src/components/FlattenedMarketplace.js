import React, { useState, useEffect, useCallback } from 'react';
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
  Receipt
} from 'lucide-react';
import { toast } from 'sonner';

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
  variant = 'full' // 'full', 'compact', 'homepage'
}) => {
  const { t } = useTranslation();
  const { user, token } = useAuth();
  const navigate = useNavigate();
  
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [skip, setSkip] = useState(0);
  
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
  
  // Categories
  const [categories, setCategories] = useState([]);

  useEffect(() => {
    fetchCategories();
  }, []);

  useEffect(() => {
    fetchItems();
  }, [filters]);

  const fetchCategories = async () => {
    try {
      const response = await axios.get(`${API}/categories`);
      setCategories(response.data);
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    }
  };

  const fetchItems = async (loadMore = false) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      
      if (filters.search) params.append('search', filters.search);
      if (filters.category) params.append('category', filters.category);
      if (filters.min_price) params.append('min_price', filters.min_price);
      if (filters.max_price) params.append('max_price', filters.max_price);
      if (filters.condition) params.append('condition', filters.condition);
      params.append('sort', filters.sort);
      params.append('limit', limit.toString());
      params.append('skip', loadMore ? skip.toString() : '0');
      params.append('track_impression', 'true');

      const response = await axios.get(`${API}/marketplace/items?${params.toString()}`);
      
      let fetchedItems = response.data.items || [];
      
      // Apply Private Sales Only filter client-side
      if (filters.private_sales_only) {
        fetchedItems = fetchedItems.filter(item => !item.seller_is_business);
      }
      
      if (loadMore) {
        setItems(prev => [...prev, ...fetchedItems]);
        setSkip(prev => prev + limit);
      } else {
        setItems(fetchedItems);
        setSkip(limit);
      }
      
      setTotal(response.data.total || fetchedItems.length);
      setHasMore(response.data.has_more || false);
    } catch (error) {
      console.error('Error fetching marketplace items:', error);
      toast.error('Failed to load marketplace items');
    } finally {
      setLoading(false);
    }
  };

  const trackClick = async (itemId) => {
    try {
      await axios.post(`${API}/marketplace/items/${itemId}/track-click`);
    } catch (error) {
      console.error('Error tracking click:', error);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setSkip(0);
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
      
      toast.success('🎉 Bid placed successfully!');
      setBidConfirmOpen(false);
      setQuickBidOpen(false);
      setSelectedItem(null);
      setBidAmount('');
      
      // Refresh items
      fetchItems();
    } catch (error) {
      const message = error.response?.data?.detail || 'Failed to place bid';
      toast.error(message);
    } finally {
      setPlacingBid(false);
    }
  };

  return (
    <div className={variant === 'homepage' ? '' : 'container mx-auto px-4 py-8'}>
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

      {/* Filters */}
      {showFilters && (
        <div className="space-y-4 mb-6">
          {/* Search Bar */}
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-5 w-5" />
              <Input
                placeholder="Search items (e.g., 'Drill', 'MacBook', 'Sofa')..."
                value={filters.search}
                onChange={(e) => handleFilterChange('search', e.target.value)}
                className="pl-10"
              />
            </div>
            
            {/* Private Sales Toggle */}
            <Button
              variant={filters.private_sales_only ? 'default' : 'outline'}
              onClick={() => handleFilterChange('private_sales_only', !filters.private_sales_only)}
              className={`gap-2 ${filters.private_sales_only ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white' : ''}`}
            >
              <User className="h-4 w-4" />
              {filters.private_sales_only ? '✓ Private Sales Only' : 'Show Private Sales Only'}
              {filters.private_sales_only && (
                <Badge className="bg-white/20 text-white text-xs ml-1">Save ~15% Tax</Badge>
              )}
            </Button>
          </div>

          {/* Filter Row */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <select
              value={filters.category}
              onChange={(e) => handleFilterChange('category', e.target.value)}
              className="px-4 py-2 border border-input rounded-md bg-background text-sm"
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat.id} value={cat.name_en}>
                  {cat.name_en}
                </option>
              ))}
            </select>

            <select
              value={filters.condition}
              onChange={(e) => handleFilterChange('condition', e.target.value)}
              className="px-4 py-2 border border-input rounded-md bg-background text-sm"
            >
              <option value="">All Conditions</option>
              <option value="new">New</option>
              <option value="like_new">Like New</option>
              <option value="excellent">Excellent</option>
              <option value="good">Good</option>
              <option value="fair">Fair</option>
            </select>

            <select
              value={filters.sort}
              onChange={(e) => handleFilterChange('sort', e.target.value)}
              className="px-4 py-2 border border-input rounded-md bg-background text-sm"
            >
              <option value="-promoted">Featured First</option>
              <option value="ending_soon">Ending Soon</option>
              <option value="price">Price: Low to High</option>
              <option value="-price">Price: High to Low</option>
              <option value="-created_at">Newest First</option>
            </select>

            <div className="flex gap-2 col-span-2 md:col-span-2">
              <Input
                type="number"
                placeholder="Min $"
                value={filters.min_price}
                onChange={(e) => handleFilterChange('min_price', e.target.value)}
                className="flex-1"
              />
              <Input
                type="number"
                placeholder="Max $"
                value={filters.max_price}
                onChange={(e) => handleFilterChange('max_price', e.target.value)}
                className="flex-1"
              />
            </div>
          </div>
        </div>
      )}

      {/* Items Grid */}
      {loading && items.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {[...Array(8)].map((_, i) => (
            <Card key={i} className="animate-pulse">
              <div className="h-48 bg-gray-200 rounded-t-lg"></div>
              <CardContent className="p-4 space-y-2">
                <div className="h-4 bg-gray-200 rounded"></div>
                <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                <div className="h-8 bg-gray-200 rounded mt-4"></div>
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {items.map((item) => (
            <ItemCard 
              key={item.id} 
              item={item} 
              onQuickBid={openQuickBid}
              trackClick={trackClick}
            />
          ))}
        </div>
      )}

      {/* Load More */}
      {hasMore && !loading && (
        <div className="text-center mt-8">
          <Button 
            onClick={() => fetchItems(true)} 
            variant="outline"
            className="px-8"
          >
            Load More Items
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
                    className="w-20 h-20 object-cover rounded-lg"
                  />
                )}
                <div className="flex-1">
                  <h4 className="font-semibold line-clamp-1">{selectedItem.title}</h4>
                  <p className="text-sm text-muted-foreground">
                    Current: ${selectedItem.current_price?.toFixed(2)}
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
                  placeholder={`Min: $${((selectedItem.current_price || 0) + 10).toFixed(2)}`}
                  className="text-lg font-semibold"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Minimum bid: ${((selectedItem.current_price || 0) + 10).toFixed(2)}
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
    </div>
  );
};

/**
 * ItemCard - Individual item card component
 */
const ItemCard = ({ item, onQuickBid, trackClick }) => {
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

  return (
    <Card className="group hover:shadow-xl transition-all duration-300 overflow-hidden border-0 shadow-md">
      {/* Image Container */}
      <Link
        to={`/lots/${item.auction_id}`}
        onClick={() => trackClick(item.id)}
        className="block"
      >
        <div className="relative h-52 bg-slate-100 dark:bg-slate-800 overflow-hidden">
          {item.images?.[0] ? (
            <img
              src={item.images[0]}
              alt={item.title}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Package className="h-16 w-16 text-gray-300" />
            </div>
          )}

          {/* Top Left - Seller Type Badge */}
          <div className="absolute top-3 left-3 z-10">
            {isPrivateSale ? (
              <Badge className="bg-gradient-to-r from-green-500 to-emerald-500 text-white border-0 shadow-lg">
                <User className="h-3 w-3 mr-1" />
                Private Sale
              </Badge>
            ) : (
              <Badge className="bg-blue-100 text-blue-700 border-blue-200">
                <ShieldCheck className="h-3 w-3 mr-1" />
                Business
              </Badge>
            )}
          </div>

          {/* Top Right - Promotion Badge */}
          {getPromotionBadge() && (
            <div className="absolute top-3 right-3 z-10">
              {getPromotionBadge()}
            </div>
          )}

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

      <CardContent className="p-4 space-y-3">
        {/* Title */}
        <Link
          to={`/lots/${item.auction_id}`}
          onClick={() => trackClick(item.id)}
          className="block"
        >
          <h3 
            className="font-semibold text-lg line-clamp-2 item-card-title hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors"
            style={{ color: 'var(--item-title-color, #1a1a1a)', fontWeight: 600 }}
            data-testid="item-title"
          >
            {item.title}
          </h3>
        </Link>

        {/* Location */}
        {item.city && (
          <div 
            className="flex items-center text-sm location-text"
            style={{ color: '#6b7280' }}
            data-location="true"
          >
            <MapPin className="h-3.5 w-3.5 mr-1" style={{ color: '#6b7280' }} />
            {item.city}, {item.region}
          </div>
        )}

        {/* Tax Savings Banner (Private Sale) */}
        {isPrivateSale && (
          <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg px-3 py-2 text-xs">
            <span className="font-medium" style={{ color: '#15803d' }}>
              🎉 Save ~15% - No tax on item price!
            </span>
          </div>
        )}

        {/* Pricing */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wider">Current Bid</span>
            <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-cyan-500 bg-clip-text text-transparent">
              ${(item.current_price || item.starting_price || 0).toFixed(2)}
            </span>
          </div>

          {item.buy_now_enabled && item.buy_now_price && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600 dark:text-slate-400">Buy Now</span>
              <span className="font-semibold text-green-600 dark:text-green-400">
                ${item.buy_now_price.toFixed(2)}
              </span>
            </div>
          )}
        </div>

        {/* Parent Auction Link */}
        <div className="text-xs text-slate-500 dark:text-slate-400 pt-1 border-t border-slate-200 dark:border-slate-700">
          Lot #{item.lot_number} of{' '}
          <Link
            to={`/lots/${item.auction_id}`}
            className="text-cyan-600 dark:text-cyan-400 hover:underline inline-flex items-center gap-1"
          >
            {item.parent_auction_title}
            <ExternalLink className="h-3 w-3" />
          </Link>
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          <Button
            onClick={(e) => onQuickBid(item, e)}
            className="flex-1 bg-gradient-to-r from-blue-600 to-cyan-500 text-white hover:from-blue-700 hover:to-cyan-600"
          >
            <Zap className="h-4 w-4 mr-1" />
            Quick Bid
          </Button>
          <Link to={`/lots/${item.auction_id}`} className="flex-1">
            <Button variant="outline" className="w-full border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-200">
              <Eye className="h-4 w-4 mr-1" />
              View
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
};

export default FlattenedMarketplace;
