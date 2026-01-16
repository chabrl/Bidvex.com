import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { Package, Search, Edit2, Trash2, Pause, Archive, XCircle, Eye } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ManageAllAuctions = () => {
  const navigate = useNavigate();
  const [singleListings, setSingleListings] = useState([]);
  const [multiListings, setMultiListings] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all'); // 'all', 'single', 'multi'
  const [statusFilter, setStatusFilter] = useState('all'); // 'all', 'active', 'draft', 'ended'
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAllListings();
  }, []);

  const fetchAllListings = async () => {
    try {
      const [singleRes, multiRes] = await Promise.all([
        axios.get(`${API}/admin/listings/all`),
        axios.get(`${API}/admin/multi-item-listings/all`)
      ]);
      setSingleListings(singleRes.data || []);
      setMultiListings(multiRes.data || []);
    } catch (error) {
      console.error('Failed to load listings:', error);
      toast.error('Failed to load auctions');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id, isMultiItem) => {
    if (!window.confirm('Are you sure you want to delete this auction? This action cannot be undone.')) {
      return;
    }

    try {
      const endpoint = isMultiItem ? `multi-item-listings/${id}` : `listings/${id}`;
      await axios.delete(`${API}/admin/${endpoint}`);
      toast.success('Auction deleted successfully');
      fetchAllListings();
    } catch (error) {
      toast.error('Failed to delete auction');
    }
  };

  const handleStatusChange = async (id, newStatus, isMultiItem) => {
    try {
      const endpoint = isMultiItem ? `multi-item-listings/${id}` : `listings/${id}`;
      await axios.put(`${API}/admin/${endpoint}/status`, { status: newStatus });
      toast.success(`Auction status updated to ${newStatus}`);
      fetchAllListings();
    } catch (error) {
      toast.error('Failed to update status');
    }
  };

  // Combine and filter listings
  const combinedListings = [
    ...singleListings.map(l => ({ ...l, type: 'single' })),
    ...multiListings.map(l => ({ ...l, type: 'multi' }))
  ];

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
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Package className="h-6 w-6" />
          Manage All Auctions
        </h2>
        <p className="text-muted-foreground">Unified view of all single and multi-item listings</p>
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
            <p className="text-2xl font-bold text-blue-600">{singleListings.length}</p>
            <p className="text-sm text-muted-foreground">Single Items</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <p className="text-2xl font-bold text-purple-600">{multiListings.length}</p>
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

      {/* Listings Table */}
      <Card>
        <CardHeader>
          <CardTitle>Auctions ({filteredListings.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {filteredListings.length > 0 ? (
            <div className="space-y-3">
              {filteredListings.map((listing) => (
                <div
                  key={listing.id}
                  className="flex flex-col md:flex-row justify-between gap-4 p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
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
                    </div>
                    <p className="text-sm text-muted-foreground mb-2">{listing.category} • {listing.city}, {listing.region}</p>
                    <div className="flex gap-4 text-sm">
                      <span className="text-green-600 font-semibold">
                        ${listing.type === 'multi'
                          ? listing.lots?.reduce((sum, lot) => sum + (lot.starting_price || 0), 0).toFixed(2)
                          : listing.current_price?.toFixed(2)}
                      </span>
                      <span className="text-muted-foreground">
                        {listing.type === 'multi'
                          ? `${listing.lots?.reduce((sum, lot) => sum + (lot.bid_count || 0), 0)} total bids`
                          : `${listing.bid_count || 0} bids`}
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => navigate(listing.type === 'multi' ? `/lots/${listing.id}` : `/listing/${listing.id}`)}
                    >
                      <Eye className="h-4 w-4 mr-1" />
                      View
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
                      onClick={() => handleDelete(listing.id, listing.type === 'multi')}
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      Delete
                    </Button>
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
    </div>
  );
};

export default ManageAllAuctions;
