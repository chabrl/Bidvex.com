import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { Package, CheckCircle, XCircle } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const LotsModeration = () => {
  const [lots, setLots] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLots();
  }, []);

  const fetchLots = async () => {
    try {
      const response = await axios.get(`${API}/admin/lots/pending`);
      setLots(response.data);
    } catch (error) {
      toast.error('Failed to load lots');
    } finally {
      setLoading(false);
    }
  };

  const handleModerate = async (lotId, action) => {
    try {
      await axios.put(`${API}/admin/lots/${lotId}/moderate`, { action });
      toast.success(`Lot ${action}d successfully`);
      fetchLots();
    } catch (error) {
      toast.error(`Failed to ${action} lot`);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2"><Package className="h-6 w-6" />Lots Auction Moderation</h2>
        <p className="text-muted-foreground">Review and moderate multi-item listings</p>
      </div>

      <Card>
        <CardHeader><CardTitle>Pending Lots ({lots.length})</CardTitle></CardHeader>
        <CardContent>
          {lots.length > 0 ? (
            <div className="space-y-3">
              {lots.map(lot => (
                <div key={lot.id} className="flex flex-col md:flex-row justify-between gap-4 p-4 border rounded-lg">
                  <div className="flex-1">
                    <p className="font-semibold">{lot.title}</p>
                    <p className="text-sm text-muted-foreground line-clamp-2">{lot.description}</p>
                    <div className="flex gap-2 mt-2">
                      <Badge>{lot.total_lots} items</Badge>
                      <Badge variant="outline">{lot.category}</Badge>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" className="bg-green-600 hover:bg-green-700 text-white" onClick={() => handleModerate(lot.id, 'approve')}>
                      <CheckCircle className="h-4 w-4 mr-1" />Approve
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => handleModerate(lot.id, 'reject')}>
                      <XCircle className="h-4 w-4 mr-1" />Reject
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">No pending lots</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default LotsModeration;