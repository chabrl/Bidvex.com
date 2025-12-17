import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Badge } from './ui/badge';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import BuyNowButton from './BuyNowButton';
import { 
  Clock, 
  Gavel, 
  Package, 
  TrendingUp, 
  Star,
  Sparkles,
  MapPin 
} from 'lucide-react';
import { toast } from 'sonner';

/**
 * Decomposed Marketplace - Item-Centric Discovery
 * Features:
 * - Individual items from multi-item lots
 * - Promoted items appear first
 * - Staggered end times displayed
 * - Buy Now functionality
 * - Analytics tracking (impressions, clicks)
 */
const DecomposedMarketplace = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    search: '',
    category: '',
    min_price: '',
    max_price: '',
    condition: '',
    sort: '-promoted'
  });
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  const API_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  useEffect(() => {
    fetchItems();
  }, [filters]);

  const fetchItems = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      
      if (filters.search) params.append('search', filters.search);
      if (filters.category) params.append('category', filters.category);
      if (filters.min_price) params.append('min_price', filters.min_price);
      if (filters.max_price) params.append('max_price', filters.max_price);
      if (filters.condition) params.append('condition', filters.condition);
      params.append('sort', filters.sort);
      params.append('limit', '50');
      params.append('skip', '0');
      params.append('track_impression', 'true');  // Track impressions for analytics

      const response = await axios.get(`${API_URL}/api/marketplace/items?${params.toString()}`);
      
      setItems(response.data.items);
      setTotal(response.data.total);
      setHasMore(response.data.has_more);
    } catch (error) {
      console.error('Error fetching marketplace items:', error);
      toast.error('Failed to load marketplace items');
    } finally {
      setLoading(false);
    }
  };

  const trackClick = async (itemId) => {
    try {
      await axios.post(`${API_URL}/api/marketplace/items/${itemId}/track-click`);
    } catch (error) {
      console.error('Error tracking click:', error);
    }
  };

  const formatTimeRemaining = (endDate) => {
    if (!endDate) return 'N/A';
    
    const end = new Date(endDate);
    const now = new Date();
    const diff = end - now;
    
    if (diff <= 0) return 'Ended';
    
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  const getPromotionBadge = (item) => {
    if (item.promotion_tier === 'premium') {
      return (
        <Badge className="bg-gradient-to-r from-yellow-400 to-orange-500 text-white font-bold">
          <Sparkles className="h-3 w-3 mr-1" />
          PREMIUM
        </Badge>
      );
    }
    if (item.promotion_tier === 'standard') {
      return (
        <Badge className="bg-gradient-to-r from-blue-500 to-purple-500 text-white font-bold">
          <Star className="h-3 w-3 mr-1" />
          FEATURED
        </Badge>
      );
    }
    if (item.promotion_tier === 'basic' || item.is_promoted) {
      return (
        <Badge className="bg-gradient-to-r from-gray-600 to-gray-700 text-white">
          <TrendingUp className="h-3 w-3 mr-1" />
          Sponsored
        </Badge>
      );
    }
    return null;
  };

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Marketplace</h1>
        <p className="text-muted-foreground">
          Browse individual items from active auctions
        </p>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <input
          type="text"
          placeholder="Search items..."
          value={filters.search}
          onChange={(e) => setFilters({...filters, search: e.target.value})}
          className="border rounded px-4 py-2"
        />
        
        <select
          value={filters.sort}
          onChange={(e) => setFilters({...filters, sort: e.target.value})}
          className="border rounded px-4 py-2"
        >
          <option value="-promoted">Promoted First</option>
          <option value="ending_soon">Ending Soon</option>
          <option value="price">Price: Low to High</option>
          <option value="-price">Price: High to Low</option>
          <option value="-created_at">Newest First</option>
        </select>

        <select
          value={filters.condition}
          onChange={(e) => setFilters({...filters, condition: e.target.value})}
          className="border rounded px-4 py-2"
        >
          <option value="">All Conditions</option>
          <option value="new">New</option>
          <option value="like_new">Like New</option>
          <option value="good">Good</option>
          <option value="fair">Fair</option>
          <option value="poor">Poor</option>
        </select>

        <Button onClick={fetchItems} variant="outline">
          Apply Filters
        </Button>
      </div>

      {/* Results Count */}
      <div className="mb-4 text-sm text-muted-foreground">
        Showing {items.length} of {total} items
      </div>

      {/* Items Grid */}
      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full mx-auto"></div>
          <p className="text-muted-foreground mt-4">Loading items...</p>
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <Package className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-lg text-muted-foreground">No items found</p>
          <p className="text-sm text-muted-foreground mt-2">
            Try adjusting your filters
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {items.map((item) => (
            <Card 
              key={item.id} 
              className="hover:shadow-lg transition-shadow relative overflow-hidden"
            >
              {/* Promotion Badge */}
              {getPromotionBadge(item) && (
                <div className="absolute top-2 right-2 z-10">
                  {getPromotionBadge(item)}
                </div>
              )}

              {/* Image */}
              <Link
                to={`/multi-item-auction/${item.auction_id}`}
                onClick={() => trackClick(item.id)}
              >
                <div className="relative h-48 bg-gray-100">
                  {item.images && item.images[0] ? (
                    <img
                      src={item.images[0]}
                      alt={item.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full">
                      <Package className="h-12 w-12 text-gray-400" />
                    </div>
                  )}

                  {/* Quantity Badge */}
                  {item.quantity > 1 && (
                    <Badge className="absolute bottom-2 left-2 bg-black/70 text-white">
                      <Package className="h-3 w-3 mr-1" />
                      Qty: {item.available_quantity}/{item.quantity}
                    </Badge>
                  )}
                </div>
              </Link>

              <CardContent className="p-4 space-y-3">
                {/* Title */}
                <Link
                  to={`/multi-item-auction/${item.auction_id}`}
                  onClick={() => trackClick(item.id)}
                >
                  <h3 className="font-semibold text-lg line-clamp-2 hover:text-primary">
                    {item.title}
                  </h3>
                </Link>

                {/* Location */}
                {item.city && (
                  <div className="flex items-center text-sm text-muted-foreground">
                    <MapPin className="h-3 w-3 mr-1" />
                    {item.city}, {item.region}
                  </div>
                )}

                {/* Pricing */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Current Bid:</span>
                    <span className="text-lg font-bold text-primary">
                      ${(item.current_price || 0).toFixed(2)}
                    </span>
                  </div>

                  {item.buy_now_enabled && item.buy_now_price && (
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Buy Now:</span>
                      <span className="font-semibold text-green-600">
                        ${item.buy_now_price.toFixed(2)}
                      </span>
                    </div>
                  )}

                  {item.bid_count > 0 && (
                    <div className="text-xs text-muted-foreground flex items-center gap-1">
                      <Gavel className="h-3 w-3" />
                      {item.bid_count} {item.bid_count === 1 ? 'bid' : 'bids'}
                    </div>
                  )}
                </div>

                {/* Time Remaining */}
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center text-muted-foreground">
                    <Clock className="h-3 w-3 mr-1" />
                    Ends in:
                  </div>
                  <span className="font-medium">
                    {formatTimeRemaining(item.auction_end_date)}
                  </span>
                </div>

                {/* Parent Lot Info */}
                <div className="text-xs text-muted-foreground">
                  Part of: <Link
                    to={`/multi-item-auction/${item.auction_id}`}
                    className="text-primary hover:underline"
                  >
                    {item.parent_auction_title}
                  </Link>
                  {' '}(Lot #{item.lot_number}/{item.total_lots_in_auction})
                </div>

                {/* Actions */}
                <div className="space-y-2 pt-2">
                  <BuyNowButton
                    lot={item}
                    auctionId={item.auction_id}
                    onPurchaseComplete={() => fetchItems()}
                  />
                  
                  <Link to={`/multi-item-auction/${item.auction_id}`}>
                    <Button
                      variant="outline"
                      className="w-full"
                      onClick={() => trackClick(item.id)}
                    >
                      <Gavel className="h-4 w-4 mr-2" />
                      View & Bid
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Load More */}
      {hasMore && !loading && (
        <div className="text-center mt-8">
          <Button onClick={fetchItems} variant="outline">
            Load More Items
          </Button>
        </div>
      )}
    </div>
  );
};

export default DecomposedMarketplace;
