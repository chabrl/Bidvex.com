import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Users, Flag, TrendingUp, Activity } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminDashboard = () => {
  const [users, setUsers] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [usersRes, reportsRes] = await Promise.all([
        axios.get(`${API}/admin/users`),
        axios.get(`${API}/admin/reports`)
      ]);
      setUsers(usersRes.data);
      setReports(reportsRes.data);
    } catch (error) {
      toast.error('Failed to load admin data');
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

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center"><div className="animate-spin rounded-full h-12 w-12 border-4 border-primary border-t-transparent"></div></div>;
  }

  return (
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-7xl mx-auto space-y-8">
        <h1 className="text-3xl font-bold">Admin Dashboard</h1>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <Card><CardContent className="p-6"><div className="flex items-center gap-4"><Users className="h-8 w-8 text-blue-600" /><div><p className="text-2xl font-bold">{users.length}</p><p className="text-sm text-muted-foreground">Total Users</p></div></div></CardContent></Card>
          <Card><CardContent className="p-6"><div className="flex items-center gap-4"><Flag className="h-8 w-8 text-red-600" /><div><p className="text-2xl font-bold">{reports.length}</p><p className="text-sm text-muted-foreground">Reports</p></div></div></CardContent></Card>
          <Card><CardContent className="p-6"><div className="flex items-center gap-4"><TrendingUp className="h-8 w-8 text-green-600" /><div><p className="text-2xl font-bold">$0</p><p className="text-sm text-muted-foreground">Revenue</p></div></div></CardContent></Card>
          <Card><CardContent className="p-6"><div className="flex items-center gap-4"><Activity className="h-8 w-8 text-purple-600" /><div><p className="text-2xl font-bold">0</p><p className="text-sm text-muted-foreground">Active Auctions</p></div></div></CardContent></Card>
        </div>

        <Card>
          <CardHeader><CardTitle>User Management</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {users.slice(0, 20).map(user => (
                <div key={user.id} className="flex justify-between items-center p-4 border rounded-lg">
                  <div>
                    <p className="font-semibold">{user.name}</p>
                    <p className="text-sm text-muted-foreground">{user.email}</p>
                  </div>
                  <div className="flex gap-2">
                    <Badge>{user.account_type}</Badge>
                    <Button size="sm" variant="outline" onClick={() => handleUserStatus(user.id, 'suspended')}>Suspend</Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Recent Reports</CardTitle></CardHeader>
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
      </div>
    </div>
  );
};

export default AdminDashboard;
