import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { Users, CheckCircle, MessageCircleOff, Search } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EnhancedUserManager = () => {
  const [users, setUsers] = useState([]);
  const [filter, setFilter] = useState('all');
  const [analytics, setAnalytics] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, [filter]);

  const fetchData = async () => {
    try {
      const endpoint = filter === 'all' ? '/admin/users' : `/admin/users/filter?account_type=${filter}`;
      const [usersRes, analyticsRes] = await Promise.all([
        axios.get(`${API}${endpoint}`),
        axios.get(`${API}/admin/analytics/users`)
      ]);
      setUsers(usersRes.data);
      setAnalytics(analyticsRes.data);
    } catch (error) {
      toast.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (userId, isVerified) => {
    try {
      await axios.put(`${API}/admin/users/${userId}/verify`, { is_verified: !isVerified });
      toast.success(`User ${!isVerified ? 'verified' : 'unverified'}`);
      fetchData();
    } catch (error) {
      toast.error('Failed to update verification');
    }
  };

  const handleSuspendMessaging = async (userId, isSuspended) => {
    try {
      await axios.put(`${API}/admin/users/${userId}/messaging`, { suspended: !isSuspended });
      toast.success(`Messaging ${!isSuspended ? 'suspended' : 'restored'}`);
      fetchData();
    } catch (error) {
      toast.error('Failed to update messaging status');
    }
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2"><Users className="h-6 w-6" />Enhanced User Management</h2>
        <p className="text-muted-foreground">Filter, verify, and manage users by type</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card><CardContent className="p-6"><div><p className="text-2xl font-bold">{analytics.total || 0}</p><p className="text-sm text-muted-foreground">Total Users</p></div></CardContent></Card>
        <Card><CardContent className="p-6"><div><p className="text-2xl font-bold">{analytics.personal || 0}</p><p className="text-sm text-muted-foreground">Personal Accounts</p></div></CardContent></Card>
        <Card><CardContent className="p-6"><div><p className="text-2xl font-bold">{analytics.business || 0}</p><p className="text-sm text-muted-foreground">Business Accounts</p></div></CardContent></Card>
      </div>

      <div className="flex gap-2">
        <Button variant={filter === 'all' ? 'default' : 'outline'} onClick={() => setFilter('all')} className={filter === 'all' ? 'gradient-button text-white border-0' : ''}>All Users</Button>
        <Button variant={filter === 'personal' ? 'default' : 'outline'} onClick={() => setFilter('personal')} className={filter === 'personal' ? 'gradient-button text-white border-0' : ''}>Personal</Button>
        <Button variant={filter === 'business' ? 'default' : 'outline'} onClick={() => setFilter('business')} className={filter === 'business' ? 'gradient-button text-white border-0' : ''}>Business</Button>
      </div>

      <Card>
        <CardHeader><CardTitle>Users ({users.length})</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-2">
            {users.map(user => (
              <div key={user.id} className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 p-4 border rounded-lg">
                <div className="flex-1">
                  <p className="font-semibold">{user.name}</p>
                  <p className="text-sm text-muted-foreground">{user.email}</p>
                  <div className="flex gap-2 mt-1">
                    <Badge>{user.account_type}</Badge>
                    {user.verified && <Badge className="bg-green-600 text-white">Verified</Badge>}
                    {user.messaging_suspended && <Badge variant="destructive">Messaging Suspended</Badge>}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant={user.verified ? 'default' : 'outline'} onClick={() => handleVerify(user.id, user.verified)}>
                    <CheckCircle className="h-4 w-4 mr-1" />{user.verified ? 'Verified' : 'Verify'}
                  </Button>
                  <Button size="sm" variant={user.messaging_suspended ? 'destructive' : 'outline'} onClick={() => handleSuspendMessaging(user.id, user.messaging_suspended)}>
                    <MessageCircleOff className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default EnhancedUserManager;