import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { DollarSign, CheckCircle, Users } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AffiliateManager = () => {
  const [affiliates, setAffiliates] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [affiliatesRes, payoutsRes, usersRes] = await Promise.all([
        axios.get(`${API}/admin/affiliates`),
        axios.get(`${API}/admin/affiliate/payouts`),
        axios.get(`${API}/admin/users`)
      ]);
      setAffiliates(affiliatesRes.data);
      setPayouts(payoutsRes.data);
      setUsers(usersRes.data);
    } catch (error) {
      toast.error('Failed to load affiliate data');
    } finally {
      setLoading(false);
    }
  };

  const handleSetAffiliateStatus = async (userId, isAffiliate) => {
    try {
      await axios.put(`${API}/admin/users/${userId}/affiliate`, { is_affiliate: !isAffiliate });
      toast.success(`Affiliate status ${!isAffiliate ? 'enabled' : 'disabled'}`);
      fetchData();
    } catch (error) {
      toast.error('Failed to update affiliate status');
    }
  };

  const handleApprovePayout = async (payoutId) => {
    if (window.confirm('Approve this payout request?')) {
      try {
        await axios.put(`${API}/admin/affiliate/payouts/${payoutId}/approve`);
        toast.success('Payout approved');
        fetchData();
      } catch (error) {
        toast.error('Failed to approve payout');
      }
    }
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  const totalCommissions = affiliates.reduce((sum, aff) => sum + (aff.total_earnings || 0), 0);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2"><DollarSign className="h-6 w-6" />Affiliate Program Management</h2>
        <p className="text-muted-foreground">Manage affiliates and approve payouts</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card><CardContent className="p-6"><div className="flex items-center gap-4"><Users className="h-8 w-8 text-blue-600" /><div><p className="text-2xl font-bold">{affiliates.length}</p><p className="text-sm text-muted-foreground">Active Affiliates</p></div></div></CardContent></Card>
        <Card><CardContent className="p-6"><div className="flex items-center gap-4"><DollarSign className="h-8 w-8 text-green-600" /><div><p className="text-2xl font-bold">${totalCommissions.toFixed(2)}</p><p className="text-sm text-muted-foreground">Total Commissions</p></div></div></CardContent></Card>
        <Card><CardContent className="p-6"><div className="flex items-center gap-4"><CheckCircle className="h-8 w-8 text-yellow-600" /><div><p className="text-2xl font-bold">{payouts.filter(p => p.status === 'pending').length}</p><p className="text-sm text-muted-foreground">Pending Payouts</p></div></div></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Payout Requests</CardTitle></CardHeader>
        <CardContent>
          {payouts.length > 0 ? (
            <div className="space-y-2">
              {payouts.map(payout => (
                <div key={payout.id} className="flex justify-between items-center p-4 border rounded-lg">
                  <div>
                    <p className="font-semibold">${payout.amount}</p>
                    <p className="text-sm text-muted-foreground">User: {payout.user_id}</p>
                    <p className="text-xs text-muted-foreground">{new Date(payout.created_at).toLocaleDateString()}</p>
                  </div>
                  <div className="flex gap-2">
                    <Badge className={payout.status === 'approved' ? 'bg-green-600 text-white' : 'bg-yellow-600 text-white'}>{payout.status}</Badge>
                    {payout.status === 'pending' && (
                      <Button size="sm" className="bg-green-600 hover:bg-green-700 text-white" onClick={() => handleApprovePayout(payout.id)}><CheckCircle className="h-4 w-4 mr-1" />Approve</Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">No payout requests</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Manage Affiliate Status</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-2">
            {users.slice(0, 20).map(user => {
              const isAffiliate = affiliates.some(aff => aff.user_id === user.id);
              return (
                <div key={user.id} className="flex justify-between items-center p-4 border rounded-lg">
                  <div>
                    <p className="font-semibold">{user.name}</p>
                    <p className="text-sm text-muted-foreground">{user.email}</p>
                  </div>
                  <Button size="sm" variant={isAffiliate ? 'default' : 'outline'} onClick={() => handleSetAffiliateStatus(user.id, isAffiliate)} className={isAffiliate ? 'gradient-button text-white border-0' : ''}>
                    {isAffiliate ? 'Affiliate' : 'Make Affiliate'}
                  </Button>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AffiliateManager;