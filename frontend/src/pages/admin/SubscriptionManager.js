import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import SubscriptionBadge from '../../components/SubscriptionBadge';
import { toast } from 'sonner';
import { Crown, Star, User as UserIcon, Search, TrendingUp, DollarSign, Calendar } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SubscriptionManager = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [stats, setStats] = useState({
    total: 0,
    free: 0,
    premium: 0,
    vip: 0,
    revenue: 0
  });

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await axios.get(`${API}/admin/users`);
      const allUsers = response.data.users || [];
      setUsers(allUsers);
      calculateStats(allUsers);
    } catch (error) {
      console.error('Failed to fetch users:', error);
      toast.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = (userList) => {
    const free = userList.filter(u => (u.subscription_tier || 'free') === 'free').length;
    const premium = userList.filter(u => u.subscription_tier === 'premium').length;
    const vip = userList.filter(u => u.subscription_tier === 'vip').length;
    const revenue = (premium * 9.99) + (vip * 29.99);

    setStats({
      total: userList.length,
      free,
      premium,
      vip,
      revenue
    });
  };

  const updateUserSubscription = async (userId, newTier) => {
    try {
      await axios.put(`${API}/admin/users/${userId}`, {
        subscription_tier: newTier,
        subscription_status: 'active',
        subscription_start_date: new Date().toISOString(),
        subscription_end_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString() // 30 days
      });
      
      toast.success(`User subscription updated to ${newTier.toUpperCase()}`);
      fetchUsers();
    } catch (error) {
      console.error('Failed to update subscription:', error);
      toast.error(error.response?.data?.detail || 'Failed to update subscription');
    }
  };

  const filteredUsers = users.filter(user => 
    user.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.email?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <Card>
        <CardContent className="p-12 text-center">
          <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading subscription data...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Total Users</p>
                <p className="text-3xl font-bold">{stats.total}</p>
              </div>
              <UserIcon className="h-10 w-10 text-gray-400" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Free Tier</p>
                <p className="text-3xl font-bold">{stats.free}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {((stats.free / stats.total) * 100).toFixed(1)}%
                </p>
              </div>
              <UserIcon className="h-10 w-10 text-gray-400" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-purple-50 dark:bg-purple-900/20">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-purple-700 dark:text-purple-300 mb-1">Premium</p>
                <p className="text-3xl font-bold text-purple-700 dark:text-purple-300">{stats.premium}</p>
                <p className="text-xs text-purple-600 dark:text-purple-400 mt-1">
                  {((stats.premium / stats.total) * 100).toFixed(1)}%
                </p>
              </div>
              <Star className="h-10 w-10 text-purple-400" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-r from-yellow-50 to-orange-50 dark:from-yellow-900/20 dark:to-orange-900/20">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-orange-700 dark:text-orange-300 mb-1">VIP</p>
                <p className="text-3xl font-bold text-orange-700 dark:text-orange-300">{stats.vip}</p>
                <p className="text-xs text-orange-600 dark:text-orange-400 mt-1">
                  {((stats.vip / stats.total) * 100).toFixed(1)}%
                </p>
              </div>
              <Crown className="h-10 w-10 text-yellow-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Revenue Card */}
      <Card className="bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800">
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-green-700 dark:text-green-300 mb-1">Monthly Recurring Revenue (MRR)</p>
              <p className="text-4xl font-bold text-green-700 dark:text-green-300">
                ${stats.revenue.toFixed(2)}
              </p>
              <p className="text-sm text-green-600 dark:text-green-400 mt-2">
                Based on current subscriptions: {stats.premium} Premium ($9.99) + {stats.vip} VIP ($29.99)
              </p>
            </div>
            <TrendingUp className="h-12 w-12 text-green-500" />
          </div>
        </CardContent>
      </Card>

      {/* User Management */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Crown className="h-5 w-5 text-yellow-500" />
            User Subscription Management
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Search */}
          <div className="mb-4">
            <Label htmlFor="search">Search Users</Label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="search"
                type="text"
                placeholder="Search by name or email..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>

          {/* Users Table */}
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="text-left p-3 font-semibold">User</th>
                  <th className="text-left p-3 font-semibold">Email</th>
                  <th className="text-center p-3 font-semibold">Current Tier</th>
                  <th className="text-center p-3 font-semibold">Status</th>
                  <th className="text-center p-3 font-semibold">Expires</th>
                  <th className="text-center p-3 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.length > 0 ? (
                  filteredUsers.map((user) => (
                    <tr key={user.id} className="border-t hover:bg-gray-50 dark:hover:bg-gray-900/50">
                      <td className="p-3">{user.name}</td>
                      <td className="p-3 text-sm text-muted-foreground">{user.email}</td>
                      <td className="p-3 text-center">
                        <SubscriptionBadge tier={user.subscription_tier || 'free'} size="small" />
                      </td>
                      <td className="p-3 text-center">
                        <Badge variant={user.subscription_status === 'active' ? 'default' : 'secondary'}>
                          {user.subscription_status || 'active'}
                        </Badge>
                      </td>
                      <td className="p-3 text-center text-sm text-muted-foreground">
                        {user.subscription_end_date 
                          ? new Date(user.subscription_end_date).toLocaleDateString()
                          : '-'
                        }
                      </td>
                      <td className="p-3">
                        <div className="flex justify-center gap-1">
                          {(user.subscription_tier || 'free') !== 'free' && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => updateUserSubscription(user.id, 'free')}
                            >
                              Free
                            </Button>
                          )}
                          {user.subscription_tier !== 'premium' && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="border-purple-300 text-purple-700 hover:bg-purple-50"
                              onClick={() => updateUserSubscription(user.id, 'premium')}
                            >
                              Premium
                            </Button>
                          )}
                          {user.subscription_tier !== 'vip' && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="border-yellow-300 text-yellow-700 hover:bg-yellow-50"
                              onClick={() => updateUserSubscription(user.id, 'vip')}
                            >
                              VIP
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="6" className="p-12 text-center text-muted-foreground">
                      No users found matching "{searchTerm}"
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-4 text-sm text-muted-foreground">
            Showing {filteredUsers.length} of {users.length} users
          </div>
        </CardContent>
      </Card>

      {/* Info Box */}
      <Card className="bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <CardContent className="p-4">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            💡 <strong>Admin Note:</strong> Subscription changes made here are instant. 
            When Stripe is integrated, billing will be handled automatically through webhooks.
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default SubscriptionManager;
