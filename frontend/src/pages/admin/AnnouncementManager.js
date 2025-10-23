import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { Megaphone, Plus, Trash2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AnnouncementManager = () => {
  const [announcements, setAnnouncements] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    message: '',
    target_audience: 'all',
    scheduled_for: ''
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnnouncements();
  }, []);

  const fetchAnnouncements = async () => {
    try {
      const response = await axios.get(`${API}/admin/announcements`);
      setAnnouncements(response.data);
    } catch (error) {
      toast.error('Failed to load announcements');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!formData.title || !formData.message) {
      toast.error('Title and message are required');
      return;
    }

    try {
      await axios.post(`${API}/admin/announcements`, formData);
      toast.success('Announcement created');
      setShowCreate(false);
      setFormData({ title: '', message: '', target_audience: 'all', scheduled_for: '' });
      fetchAnnouncements();
    } catch (error) {
      toast.error('Failed to create announcement');
    }
  };

  const handleDelete = async (announcementId) => {
    if (window.confirm('Delete this announcement?')) {
      try {
        await axios.delete(`${API}/admin/announcements/${announcementId}`);
        toast.success('Announcement deleted');
        fetchAnnouncements();
      } catch (error) {
        toast.error('Failed to delete announcement');
      }
    }
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2"><Megaphone className="h-6 w-6" />Platform Announcements</h2>
          <p className="text-muted-foreground">Create and manage system-wide announcements</p>
        </div>
        <Button onClick={() => setShowCreate(!showCreate)} className="gradient-button text-white border-0">
          <Plus className="h-4 w-4 mr-2" />New Announcement
        </Button>
      </div>

      {showCreate && (
        <Card className="border-2 border-primary">
          <CardHeader><CardTitle>Create Announcement</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">Title</label>
              <Input value={formData.title} onChange={(e) => setFormData({...formData, title: e.target.value})} placeholder="Important Update" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Message</label>
              <textarea value={formData.message} onChange={(e) => setFormData({...formData, message: e.target.value})} placeholder="Announcement details..." className="w-full px-3 py-2 border rounded-md" rows={4} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Target Audience</label>
                <select value={formData.target_audience} onChange={(e) => setFormData({...formData, target_audience: e.target.value})} className="w-full px-3 py-2 border rounded-md">
                  <option value="all">All Users</option>
                  <option value="buyers">Buyers Only</option>
                  <option value="sellers">Sellers Only</option>
                  <option value="business">Business Accounts</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Schedule For (Optional)</label>
                <Input type="datetime-local" value={formData.scheduled_for} onChange={(e) => setFormData({...formData, scheduled_for: e.target.value})} />
              </div>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleCreate} className="gradient-button text-white border-0">Create</Button>
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle>Active Announcements ({announcements.length})</CardTitle></CardHeader>
        <CardContent>
          {announcements.length > 0 ? (
            <div className="space-y-3">
              {announcements.map(announcement => (
                <div key={announcement.id} className="flex justify-between items-start p-4 border rounded-lg">
                  <div className="flex-1">
                    <p className="font-semibold">{announcement.title}</p>
                    <p className="text-sm text-muted-foreground">{announcement.message}</p>
                    <div className="flex gap-2 mt-2">
                      <Badge>{announcement.target_audience}</Badge>
                      <Badge className="bg-green-600 text-white">{announcement.status}</Badge>
                    </div>
                  </div>
                  <Button size="sm" variant="destructive" onClick={() => handleDelete(announcement.id)}><Trash2 className="h-4 w-4" /></Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">No announcements</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default AnnouncementManager;