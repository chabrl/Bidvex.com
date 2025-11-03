import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import { TrendingUp, Download } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AnalyticsDashboard = () => {
  const [revenueData, setRevenueData] = useState([]);
  const [listingData, setListingData] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const [revenueRes, listingsRes] = await Promise.all([
        axios.get(`${API}/admin/analytics/revenue`),
        axios.get(`${API}/admin/analytics/listings`)
      ]);
      setRevenueData(revenueRes.data);
      setListingData(listingsRes.data);
    } catch (error) {
      toast.error('Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  const exportToCSV = () => {
    const csv = [
      ['Date', 'Revenue'],
      ...revenueData.map(d => [d.date, d.revenue])
    ].map(row => row.join(',')).join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bidvex-analytics-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    toast.success('Analytics exported to CSV');
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  const totalRevenue = revenueData.reduce((sum, d) => sum + d.revenue, 0);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2"><TrendingUp className="h-6 w-6" />Advanced Analytics</h2>
          <p className="text-muted-foreground">Revenue trends and platform insights</p>
        </div>
        <Button onClick={exportToCSV} variant="outline"><Download className="h-4 w-4 mr-2" />Export CSV</Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card><CardContent className="p-6"><div><p className="text-2xl font-bold gradient-text">${totalRevenue.toFixed(2)}</p><p className="text-sm text-muted-foreground">Total Revenue (30d)</p></div></CardContent></Card>
        <Card><CardContent className="p-6"><div><p className="text-2xl font-bold text-green-600">{listingData.active || 0}</p><p className="text-sm text-muted-foreground">Active Listings</p></div></CardContent></Card>
        <Card><CardContent className="p-6"><div><p className="text-2xl font-bold text-blue-600">{listingData.sold || 0}</p><p className="text-sm text-muted-foreground">Sold Listings</p></div></CardContent></Card>
        <Card><CardContent className="p-6"><div><p className="text-2xl font-bold text-yellow-600">{listingData.pending || 0}</p><p className="text-sm text-muted-foreground">Pending Review</p></div></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Revenue Trend (Last 30 Days)</CardTitle></CardHeader>
        <CardContent>
          {revenueData.length > 0 ? (
            <div className="space-y-2">
              {revenueData.slice().reverse().slice(0, 10).map(data => (
                <div key={data.date} className="flex justify-between items-center p-3 border rounded-lg">
                  <span className="text-sm font-medium">{new Date(data.date).toLocaleDateString()}</span>
                  <span className="text-lg font-bold gradient-text">${data.revenue.toFixed(2)}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">No revenue data yet</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Listing Status Distribution</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 border rounded-lg">
              <p className="text-3xl font-bold text-green-600">{listingData.active || 0}</p>
              <p className="text-sm text-muted-foreground">Active</p>
            </div>
            <div className="text-center p-4 border rounded-lg">
              <p className="text-3xl font-bold text-blue-600">{listingData.sold || 0}</p>
              <p className="text-sm text-muted-foreground">Sold</p>
            </div>
            <div className="text-center p-4 border rounded-lg">
              <p className="text-3xl font-bold text-yellow-600">{listingData.pending || 0}</p>
              <p className="text-sm text-muted-foreground">Pending</p>
            </div>
            <div className="text-center p-4 border rounded-lg">
              <p className="text-3xl font-bold text-red-600">{listingData.cancelled || 0}</p>
              <p className="text-sm text-muted-foreground">Cancelled</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AnalyticsDashboard;