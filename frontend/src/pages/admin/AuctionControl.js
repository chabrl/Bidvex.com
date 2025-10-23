import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';
import { Gavel, Pause, Play, Clock, X } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AuctionControl = () => {
  const [auctions, setAuctions] = useState([]);
  const [filter, setFilter] = useState('active');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAuctions();
  }, [filter]);

  const fetchAuctions = async () => {
    try {
      const response = await axios.get(`${API}/admin/auctions${filter ? `?status=${filter}` : ''}`);
      setAuctions(response.data);
    } catch (error) {
      toast.error('Failed to load auctions');
    } finally {
      setLoading(false);
    }
  };

  const handlePause = async (listingId) => {
    try {
      await axios.put(`${API}/admin/auctions/${listingId}/pause`);
      toast.success('Auction paused');
      fetchAuctions();
    } catch (error) {
      toast.error('Failed to pause auction');
    }
  };

  const handleResume = async (listingId) => {
    try {
      await axios.put(`${API}/admin/auctions/${listingId}/resume`);
      toast.success('Auction resumed');
      fetchAuctions();
    } catch (error) {
      toast.error('Failed to resume auction');
    }
  };

  const handleExtend = async (listingId) => {
    const days = prompt('Extend auction by how many days?');
    if (days) {
      const newEndDate = new Date();
      newEndDate.setDate(newEndDate.getDate() + parseInt(days));
      try {
        await axios.put(`${API}/admin/auctions/${listingId}/extend`, { new_end_date: newEndDate.toISOString() });
        toast.success(`Auction extended by ${days} days`);
        fetchAuctions();
      } catch (error) {
        toast.error('Failed to extend auction');
      }
    }
  };

  const handleCancel = async (listingId) => {
    if (window.confirm('Cancel this auction? This action cannot be undone.')) {
      try {
        await axios.delete(`${API}/admin/auctions/${listingId}/cancel`);
        toast.success('Auction cancelled');
        fetchAuctions();
      } catch (error) {
        toast.error('Failed to cancel auction');
      }
    }
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2"><Gavel className="h-6 w-6" />Auction Lifecycle Control</h2>
        <p className="text-muted-foreground">Manage auction status and timelines</p>
      </div>

      <div className="flex gap-2">
        {['active', 'paused', 'sold', 'cancelled'].map(status => (
          <Button key={status} variant={filter === status ? 'default' : 'outline'} onClick={() => setFilter(status)} className={filter === status ? 'gradient-button text-white border-0' : ''}>
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </Button>
        ))}
      </div>

      <Card>
        <CardHeader><CardTitle>{filter.charAt(0).toUpperCase() + filter.slice(1)} Auctions ({auctions.length})</CardTitle></CardHeader>
        <CardContent>
          {auctions.length > 0 ? (
            <div className="space-y-3">
              {auctions.map(auction => {
                const endDate = new Date(auction.auction_end_date);
                const isEnded = new Date() > endDate;
                return (
                  <div key={auction.id} className="flex flex-col md:flex-row justify-between gap-4 p-4 border rounded-lg">
                    <div className="flex-1">
                      <p className="font-semibold">{auction.title}</p>
                      <p className="text-sm text-muted-foreground">${auction.current_price} • {auction.bid_count} bids</p>
                      <p className="text-xs text-muted-foreground">Ends: {endDate.toLocaleString()}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge className={auction.status === 'active' ? 'bg-green-600 text-white' : ''}>{auction.status}</Badge>
                      {auction.status === 'active' && (
                        <>
                          <Button size="sm" variant="outline" onClick={() => handlePause(auction.id)}><Pause className="h-4 w-4" /></Button>
                          <Button size="sm" variant="outline" onClick={() => handleExtend(auction.id)}><Clock className="h-4 w-4" /></Button>
                          <Button size="sm" variant="destructive" onClick={() => handleCancel(auction.id)}><X className="h-4 w-4" /></Button>
                        </>
                      )}
                      {auction.status === 'paused' && (
                        <Button size="sm" variant="outline" onClick={() => handleResume(auction.id)}><Play className="h-4 w-4" /></Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">No {filter} auctions</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default AuctionControl;