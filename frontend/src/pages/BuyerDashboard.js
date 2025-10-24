import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { DollarSign, Gavel, Trophy, Heart, TrendingUp, TrendingDown, Eye } from 'lucide-react';
import { toast } from 'sonner';
import Countdown from 'react-countdown';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BuyerDashboard = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/buyer`);
      setDashboard(response.data);
    } catch (error) {
      console.error('Failed to fetch dashboard:', error);
      toast.error('Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen py-8 px-4" data-testid="buyer-dashboard">
      <div className="max-w-7xl mx-auto space-y-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">{t('dashboard.buyer.title')}</h1>
          <p className="text-muted-foreground">Track your bids and wins</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <StatCard
            icon={<Gavel className="h-6 w-6" />}
            title={t('dashboard.buyer.activeBids')}
            value={dashboard?.active_bids || 0}
            color="blue"
          />
          <StatCard
            icon={<Trophy className="h-6 w-6" />}
            title={t('dashboard.buyer.wonItems')}
            value={dashboard?.won_items || 0}
            color="green"
          />
          <StatCard
            icon={<DollarSign className="h-6 w-6" />}
            title="Total Bids"
            value={dashboard?.total_bids || 0}
            color="purple"
          />
        </div>

        <Card className="glassmorphism">
          <CardHeader>
            <CardTitle>Your Bids</CardTitle>
          </CardHeader>
          <CardContent>
            {dashboard?.bids && dashboard.bids.length > 0 ? (
              <div className="space-y-4">
                {dashboard.bids.map((bid) => {
                  const listing = dashboard.listings.find(l => l.id === bid.listing_id);
                  if (!listing) return null;
                  
                  return (
                    <div
                      key={bid.id}
                      className="flex flex-col sm:flex-row gap-4 p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                      data-testid={`bid-item-${bid.id}`}
                    >
                      <div className="w-full sm:w-24 h-24 rounded-lg overflow-hidden bg-gray-100 flex-shrink-0">
                        {listing.images && listing.images[0] ? (
                          <img src={listing.images[0]} alt={listing.title} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">📦</div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <h3 className="font-semibold truncate">{listing.title}</h3>
                          <Badge variant={listing.status === 'active' ? 'default' : 'secondary'}>
                            {listing.status}
                          </Badge>
                        </div>
                        <div className="flex flex-wrap gap-4 text-sm text-muted-foreground mb-2">
                          <span>Your Bid: ${bid.amount.toFixed(2)}</span>
                          <span>Current: ${listing.current_price.toFixed(2)}</span>
                          {bid.amount >= listing.current_price && listing.status === 'active' && (
                            <Badge variant="default" className="text-xs">Winning</Badge>
                          )}
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => navigate(`/listing/${listing.id}`)}
                        >
                          View Listing
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-12">
                <Gavel className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground mb-4">No bids yet</p>
                <Button onClick={() => navigate('/marketplace')} className="gradient-button text-white border-0">
                  Start Bidding
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

const StatCard = ({ icon, title, value, color }) => (
  <Card className="glassmorphism">
    <CardContent className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 rounded-xl bg-${color}-100 dark:bg-${color}-900/20 text-${color}-600`}>
          {icon}
        </div>
      </div>
      <p className="text-2xl font-bold mb-1">{value}</p>
      <p className="text-sm text-muted-foreground">{title}</p>
    </CardContent>
  </Card>
);

export default BuyerDashboard;
