import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import EnhancedUserManager from './admin/EnhancedUserManager';
import LotsModeration from './admin/LotsModeration';
import AuctionControl from './admin/AuctionControl';
import CategoryManager from './admin/CategoryManager';
import PromotionManager from './admin/PromotionManager';
import AffiliateManager from './admin/AffiliateManager';
import ReportManager from './admin/ReportManager';
import AnalyticsDashboard from './admin/AnalyticsDashboard';
import MessagingOversight from './admin/MessagingOversight';
import TrustSafetyDashboard from './admin/TrustSafetyDashboard';
import AnnouncementManager from './admin/AnnouncementManager';
import AdminLogs from './admin/AdminLogs';
import CurrencyAppealsManager from './admin/CurrencyAppealsManager';
import { Users, Package, Gavel, Shield, TrendingUp, Bell, Settings, FileText, MessageSquare, DollarSign } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminDashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    totalUsers: 0,
    totalListings: 0,
    activeAuctions: 0,
    revenue: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      navigate('/auth');
      return;
    }

    // Check if user has admin or superadmin role
    if (user.role !== 'admin' && user.role !== 'superadmin') {
      toast.error('You do not have permission to access this page');
      navigate('/');
      return;
    }

    fetchDashboardStats();
  }, [user, navigate]);

  const fetchDashboardStats = async () => {
    try {
      const [usersRes, listingsRes, revenueRes] = await Promise.all([
        axios.get(`${API}/admin/users?limit=1`),
        axios.get(`${API}/listings?limit=1`),
        axios.get(`${API}/admin/stats/revenue`)
      ]);

      setStats({
        totalUsers: usersRes.data.total || 0,
        totalListings: listingsRes.data.total || 0,
        activeAuctions: listingsRes.data.active || 0,
        revenue: revenueRes.data.total_revenue || 0
      });
    } catch (error) {
      console.error('Failed to fetch dashboard stats:', error);
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
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold gradient-text">BidVex Admin Panel</h1>
            <p className="text-muted-foreground mt-2">Manage all aspects of your auction platform</p>
          </div>
          <Badge className="gradient-bg text-white border-0 text-lg px-6 py-2">
            {user.role === 'superadmin' ? 'Super Admin' : 'Admin'}
          </Badge>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Total Users</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.totalUsers.toLocaleString()}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Total Listings</CardTitle>
              <Package className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.totalListings.toLocaleString()}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Active Auctions</CardTitle>
              <Gavel className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.activeAuctions.toLocaleString()}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Total Revenue</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">${stats.revenue.toLocaleString()}</div>
            </CardContent>
          </Card>
        </div>

        {/* Main Tabs */}
        <Tabs defaultValue="users" className="space-y-6">
          <TabsList className="grid w-full grid-cols-2 lg:grid-cols-6 gap-2">
            <TabsTrigger value="users"><Users className="h-4 w-4 mr-2" />Users</TabsTrigger>
            <TabsTrigger value="lots"><Package className="h-4 w-4 mr-2" />Lots</TabsTrigger>
            <TabsTrigger value="auctions"><Gavel className="h-4 w-4 mr-2" />Auctions</TabsTrigger>
            <TabsTrigger value="trust"><Shield className="h-4 w-4 mr-2" />Trust & Safety</TabsTrigger>
            <TabsTrigger value="analytics"><TrendingUp className="h-4 w-4 mr-2" />Analytics</TabsTrigger>
            <TabsTrigger value="settings"><Settings className="h-4 w-4 mr-2" />Settings</TabsTrigger>
          </TabsList>

          <TabsContent value="users">
            <EnhancedUserManager />
          </TabsContent>

          <TabsContent value="lots">
            <LotsModeration />
          </TabsContent>

          <TabsContent value="auctions">
            <AuctionControl />
          </TabsContent>

          <TabsContent value="trust">
            <TrustSafetyDashboard />
          </TabsContent>

          <TabsContent value="analytics">
            <AnalyticsDashboard />
          </TabsContent>

          <TabsContent value="settings" className="space-y-6">
            <Tabs defaultValue="categories" className="space-y-4">
              <TabsList>
                <TabsTrigger value="categories">Categories</TabsTrigger>
                <TabsTrigger value="promotions">Promotions</TabsTrigger>
                <TabsTrigger value="affiliates">Affiliates</TabsTrigger>
                <TabsTrigger value="currency-appeals"><DollarSign className="h-4 w-4 mr-1" />Currency Appeals</TabsTrigger>
                <TabsTrigger value="reports">Reports</TabsTrigger>
                <TabsTrigger value="messages">Messages</TabsTrigger>
                <TabsTrigger value="announcements">Announcements</TabsTrigger>
                <TabsTrigger value="logs">Logs</TabsTrigger>
              </TabsList>

              <TabsContent value="categories">
                <CategoryManager />
              </TabsContent>

              <TabsContent value="promotions">
                <PromotionManager />
              </TabsContent>

              <TabsContent value="affiliates">
                <AffiliateManager />
              </TabsContent>

              <TabsContent value="reports">
                <ReportManager />
              </TabsContent>

              <TabsContent value="messages">
                <MessagingOversight />
              </TabsContent>

              <TabsContent value="announcements">
                <AnnouncementManager />
              </TabsContent>

              <TabsContent value="logs">
                <AdminLogs />
              </TabsContent>
            </Tabs>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default AdminDashboard;