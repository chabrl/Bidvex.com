import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import { Users, Flag, TrendingUp, Activity, Package, DollarSign, CheckCircle, XCircle, Eye, Search, FolderOpen, Gavel } from 'lucide-react';
import PromotionManager from './admin/PromotionManager';
import CategoryManager from './admin/CategoryManager';
import AuctionControl from './admin/AuctionControl';
import AffiliateManager from './admin/AffiliateManager';
import EnhancedUserManager from './admin/EnhancedUserManager';
import LotsModeration from './admin/LotsModeration';
import ReportManager from './admin/ReportManager';
import AnalyticsDashboard from './admin/AnalyticsDashboard';
import MessagingOversight from './admin/MessagingOversight';
import AdminLogs from './admin/AdminLogs';
import AnnouncementManager from './admin/AnnouncementManager';
import TrustSafetyDashboard from './admin/TrustSafetyDashboard';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminDashboard = () => {
  const [users, setUsers] = useState([]);
  const [reports, setReports] = useState([]);
  const [listings, setListings] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [analytics, setAnalytics] = useState({});
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [usersRes, reportsRes, listingsRes, transactionsRes, analyticsRes] = await Promise.all([
        axios.get(`${API}/admin/users`),
        axios.get(`${API}/admin/reports`),
        axios.get(`${API}/admin/listings/pending`),
        axios.get(`${API}/admin/transactions`),
        axios.get(`${API}/admin/analytics`)
      ]);
      setUsers(usersRes.data);
      setReports(reportsRes.data);
      setListings(listingsRes.data);
      setTransactions(transactionsRes.data);
      setAnalytics(analyticsRes.data);
    } catch (error) {
      console.error('Failed to load admin data:', error);
      toast.error(error.response?.data?.detail || 'Failed to load admin data');
    } finally {
      setLoading(false);
    }
  };

  const handleUserStatus = async (userId, status) => {
    try {
      await axios.put(`${API}/admin/users/${userId}/status`, { status });
      toast.success('User status updated');
      fetchData();
    } catch (error) {
      toast.error('Failed to update user');
    }
  };

  const handleListingAction = async (listingId, action) => {
    try {
      await axios.put(`${API}/admin/listings/${listingId}/moderate`, { action });
      toast.success(`Listing ${action}d successfully`);
      fetchData();
    } catch (error) {
      toast.error(`Failed to ${action} listing`);
    }
  };

  const filteredUsers = users.filter(user => 
    user.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center"><div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div></div>;
  }

  return (
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-7xl mx-auto space-y-8">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold gradient-text">Bazario Admin Panel</h1>
            <p className="text-muted-foreground mt-1">Platform Management & Moderation</p>
          </div>
          <Badge className="gradient-bg text-white border-0">Admin Access</Badge>
        </div>

        {/* Analytics KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card className="glassmorphism">
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <Users className="h-8 w-8 text-blue-600" />
                <div>
                  <p className="text-2xl font-bold">{users.length}</p>
                  <p className="text-sm text-muted-foreground">Total Users</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card className="glassmorphism">
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <Package className="h-8 w-8 text-purple-600" />
                <div>
                  <p className="text-2xl font-bold">{analytics.active_listings || 0}</p>
                  <p className="text-sm text-muted-foreground">Active Listings</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="glassmorphism">
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <DollarSign className="h-8 w-8 text-green-600" />
                <div>
                  <p className="text-2xl font-bold">${analytics.total_revenue?.toFixed(2) || '0.00'}</p>
                  <p className="text-sm text-muted-foreground">Total Revenue</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="glassmorphism">
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <Flag className="h-8 w-8 text-red-600" />
                <div>
                  <p className="text-2xl font-bold">{listings.length}</p>
                  <p className="text-sm text-muted-foreground">Pending Moderation</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Tabs for Different Admin Sections */}
        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList className="grid w-full grid-cols-6 lg:grid-cols-13 h-auto gap-1">
            <TabsTrigger value="overview" className="text-xs">Overview</TabsTrigger>
            <TabsTrigger value="trust-safety" className="text-xs bg-blue-600 text-white">Trust & Safety</TabsTrigger>
            <TabsTrigger value="users" className="text-xs">Users</TabsTrigger>
            <TabsTrigger value="moderation" className="text-xs">Listings</TabsTrigger>
            <TabsTrigger value="lots" className="text-xs">Lots</TabsTrigger>
            <TabsTrigger value="promotions" className="text-xs">Promotions</TabsTrigger>
            <TabsTrigger value="categories" className="text-xs">Categories</TabsTrigger>
            <TabsTrigger value="auctions" className="text-xs">Auctions</TabsTrigger>
            <TabsTrigger value="affiliates" className="text-xs">Affiliates</TabsTrigger>
            <TabsTrigger value="reports" className="text-xs">Reports</TabsTrigger>
            <TabsTrigger value="analytics" className="text-xs">Analytics</TabsTrigger>
            <TabsTrigger value="messages" className="text-xs">Messages</TabsTrigger>
            <TabsTrigger value="logs" className="text-xs">Logs</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <CardHeader><CardTitle>Quick Stats</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex justify-between"><span>Total Users:</span><span className="font-bold">{users.length}</span></div>
                  <div className="flex justify-between"><span>Active Listings:</span><span className="font-bold">{analytics.active_listings || 0}</span></div>
                  <div className="flex justify-between"><span>Total Revenue:</span><span className="font-bold">${analytics.total_revenue?.toFixed(2) || '0.00'}</span></div>
                  <div className="flex justify-between"><span>Pending Moderation:</span><span className="font-bold">{listings.length}</span></div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle>Recent Activity</CardTitle></CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">Latest transactions: {transactions.length}</p>
                  <p className="text-sm text-muted-foreground">New reports: {reports.length}</p>
                  <p className="text-sm text-muted-foreground">Platform status: Operational</p>
                </CardContent>
              </Card>
            </div>
            <Card>
              <CardHeader><CardTitle>Quick Actions</CardTitle></CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <Button variant="outline" onClick={() => document.querySelector('[value=\"users\"]').click()}>Manage Users</Button>
                  <Button variant="outline" onClick={() => document.querySelector('[value=\"promotions\"]').click()}>Create Promotion</Button>
                  <Button variant="outline" onClick={() => document.querySelector('[value=\"analytics\"]').click()}>View Analytics</Button>
                  <Button variant="outline" className="gradient-button text-white border-0" onClick={() => setShowCreate(true)}>New Announcement</Button>
                </div>
              </CardContent>
            </Card>
            <AnnouncementManager />
          </TabsContent>

          {/* Promotions Tab */}
          <TabsContent value="promotions">
            <PromotionManager />
          </TabsContent>

          {/* Categories Tab */}
          <TabsContent value="categories">
            <CategoryManager />
          </TabsContent>

          {/* Auctions Tab */}
          <TabsContent value="auctions">
            <AuctionControl />
          </TabsContent>

          {/* Affiliates Tab */}
          <TabsContent value="affiliates">
            <AffiliateManager />
          </TabsContent>

          {/* Enhanced Users Tab */}
          <TabsContent value="users">
            <EnhancedUserManager />
          </TabsContent>

          {/* Lots Moderation Tab */}
          <TabsContent value="lots">
            <LotsModeration />
          </TabsContent>

          {/* Reports Tab */}
          <TabsContent value="reports">
            <ReportManager />
          </TabsContent>

          {/* Analytics Tab */}
          <TabsContent value="analytics">
            <AnalyticsDashboard />
          </TabsContent>

          {/* Messaging Oversight Tab */}
          <TabsContent value="messages">
            <MessagingOversight />
          </TabsContent>

          {/* Admin Logs Tab */}
          <TabsContent value="logs">
            <AdminLogs />
          </TabsContent>

          {/* Listing Moderation Tab */}
          <TabsContent value="moderation" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Package className="h-5 w-5" />
                  Pending Listings
                </CardTitle>
              </CardHeader>
              <CardContent>
                {listings.length > 0 ? (
                  <div className="space-y-4">
                    {listings.map(listing => (
                      <div key={listing.id} className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 p-4 border rounded-lg">
                        <div className="flex-1">
                          <p className="font-semibold">{listing.title}</p>
                          <p className="text-sm text-muted-foreground line-clamp-2">{listing.description}</p>
                          <div className="flex gap-2 mt-2">
                            <Badge variant="outline">{listing.category}</Badge>
                            <Badge variant="outline">${listing.starting_price}</Badge>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" onClick={() => window.open(`/listing/${listing.id}`, '_blank')}>
                            <Eye className="h-4 w-4 mr-1" /> View
                          </Button>
                          <Button size="sm" className="bg-green-600 hover:bg-green-700 text-white" onClick={() => handleListingAction(listing.id, 'approve')}>
                            <CheckCircle className="h-4 w-4 mr-1" /> Approve
                          </Button>
                          <Button size="sm" variant="destructive" onClick={() => handleListingAction(listing.id, 'reject')}>
                            <XCircle className="h-4 w-4 mr-1" /> Reject
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-center text-muted-foreground py-8">No pending listings</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* User Management Tab */}
          <TabsContent value="users" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  User Management
                </CardTitle>
                <div className="relative mt-4">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
                  <Input
                    placeholder="Search users by name or email..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {filteredUsers.slice(0, 20).map(user => (
                    <div key={user.id} className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 p-4 border rounded-lg">
                      <div className="flex-1">
                        <p className="font-semibold">{user.name}</p>
                        <p className="text-sm text-muted-foreground">{user.email}</p>
                      </div>
                      <div className="flex gap-2">
                        <Badge>{user.account_type}</Badge>
                        {user.status === 'suspended' ? (
                          <Button size="sm" variant="outline" className="bg-green-600 hover:bg-green-700 text-white" onClick={() => handleUserStatus(user.id, 'active')}>
                            Activate
                          </Button>
                        ) : (
                          <Button size="sm" variant="destructive" onClick={() => handleUserStatus(user.id, 'suspended')}>
                            Suspend
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Announcements Tab - under Overview */}
          <TabsContent value="announcements">
            <AnnouncementManager />
          </TabsContent>

          {/* Transactions Tab */}
          <TabsContent value="transactions" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <DollarSign className="h-5 w-5" />
                  Recent Transactions
                </CardTitle>
              </CardHeader>
              <CardContent>
                {transactions.length > 0 ? (
                  <div className="space-y-2">
                    {transactions.map(tx => (
                      <div key={tx.session_id} className="flex justify-between items-center p-4 border rounded-lg">
                        <div>
                          <p className="font-semibold">${tx.amount} {tx.currency.toUpperCase()}</p>
                          <p className="text-sm text-muted-foreground">Session: {tx.session_id.substring(0, 20)}...</p>
                          <p className="text-xs text-muted-foreground">{new Date(tx.created_at).toLocaleString()}</p>
                        </div>
                        <Badge className={tx.payment_status === 'paid' ? 'bg-green-600 text-white' : 'bg-yellow-600 text-white'}>
                          {tx.payment_status}
                        </Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-center text-muted-foreground py-8">No transactions yet</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Reports Tab */}
          <TabsContent value="reports" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Flag className="h-5 w-5" />
                  User Reports
                </CardTitle>
              </CardHeader>
              <CardContent>
                {reports.length > 0 ? (
                  <div className="space-y-2">
                    {reports.slice(0, 10).map(report => (
                      <div key={report.id} className="flex justify-between items-center p-4 border rounded-lg">
                        <div>
                          <p className="font-semibold">{report.category}</p>
                          <p className="text-sm text-muted-foreground">{report.description}</p>
                        </div>
                        <Badge>{report.status}</Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-center text-muted-foreground py-8">No reports</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default AdminDashboard;
