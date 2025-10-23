import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';
import { Flag, Save } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ReportManager = () => {
  const [reports, setReports] = useState([]);
  const [filter, setFilter] = useState({});
  const [editingId, setEditingId] = useState(null);
  const [editData, setEditData] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchReports();
  }, [filter]);

  const fetchReports = async () => {
    try {
      const params = new URLSearchParams(filter).toString();
      const response = await axios.get(`${API}/admin/reports${params ? `/filter?${params}` : ''}`);
      setReports(response.data);
    } catch (error) {
      toast.error('Failed to load reports');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (reportId) => {
    try {
      await axios.put(`${API}/admin/reports/${reportId}/update`, editData);
      toast.success('Report updated');
      setEditingId(null);
      setEditData({});
      fetchReports();
    } catch (error) {
      toast.error('Failed to update report');
    }
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2"><Flag className="h-6 w-6" />Report Management</h2>
        <p className="text-muted-foreground">Review and resolve user reports</p>
      </div>

      <div className="flex gap-2">
        <Button variant={!filter.status ? 'default' : 'outline'} onClick={() => setFilter({})} className={!filter.status ? 'gradient-button text-white border-0' : ''}>All</Button>
        <Button variant={filter.status === 'pending' ? 'default' : 'outline'} onClick={() => setFilter({ status: 'pending' })}>Pending</Button>
        <Button variant={filter.status === 'resolved' ? 'default' : 'outline'} onClick={() => setFilter({ status: 'resolved' })}>Resolved</Button>
      </div>

      <Card>
        <CardHeader><CardTitle>Reports ({reports.length})</CardTitle></CardHeader>
        <CardContent>
          {reports.length > 0 ? (
            <div className="space-y-3">
              {reports.map(report => (
                <div key={report.id} className="p-4 border rounded-lg">
                  {editingId === report.id ? (
                    <div className="space-y-3">
                      <Input placeholder="Admin notes..." value={editData.admin_notes || ''} onChange={(e) => setEditData({ ...editData, admin_notes: e.target.value })} />
                      <select value={editData.status || report.status} onChange={(e) => setEditData({ ...editData, status: e.target.value })} className="w-full px-3 py-2 border rounded-md">
                        <option value="pending">Pending</option>
                        <option value="in_review">In Review</option>
                        <option value="resolved">Resolved</option>
                      </select>
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => handleUpdate(report.id)}><Save className="h-4 w-4 mr-1" />Save</Button>
                        <Button size="sm" variant="outline" onClick={() => setEditingId(null)}>Cancel</Button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <p className="font-semibold">{report.category}</p>
                          <p className="text-sm text-muted-foreground">{report.description}</p>
                          {report.admin_notes && <p className="text-xs text-blue-600 mt-1">Admin: {report.admin_notes}</p>}
                        </div>
                        <div className="flex gap-2">
                          <Badge className={report.status === 'resolved' ? 'bg-green-600 text-white' : ''}>{report.status}</Badge>
                          <Button size="sm" variant="outline" onClick={() => { setEditingId(report.id); setEditData({ status: report.status, admin_notes: report.admin_notes || '' }); }}>Edit</Button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">No reports</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default ReportManager;