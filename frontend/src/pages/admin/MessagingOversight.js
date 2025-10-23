import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { MessageCircle, Trash2, Ban } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MessagingOversight = () => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMessages();
  }, []);

  const fetchMessages = async () => {
    try {
      const response = await axios.get(`${API}/admin/messages/flagged`);
      setMessages(response.data);
    } catch (error) {
      toast.error('Failed to load flagged messages');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (messageId) => {
    if (window.confirm('Delete this message?')) {
      try {
        await axios.delete(`${API}/admin/messages/${messageId}`);
        toast.success('Message deleted');
        fetchMessages();
      } catch (error) {
        toast.error('Failed to delete message');
      }
    }
  };

  const handleSuspendMessaging = async (userId) => {
    if (window.confirm('Suspend messaging for this user?')) {
      try {
        await axios.put(`${API}/admin/users/${userId}/messaging`, { suspended: true });
        toast.success('User messaging suspended');
      } catch (error) {
        toast.error('Failed to suspend messaging');
      }
    }
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2"><MessageCircle className="h-6 w-6" />Messaging Oversight</h2>
        <p className="text-muted-foreground">Monitor and moderate flagged messages</p>
      </div>

      <Card>
        <CardHeader><CardTitle>Flagged Messages ({messages.length})</CardTitle></CardHeader>
        <CardContent>
          {messages.length > 0 ? (
            <div className="space-y-3">
              {messages.map(msg => (
                <div key={msg.id} className="flex flex-col md:flex-row justify-between gap-4 p-4 border rounded-lg">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant="destructive">Flagged</Badge>
                      <span className="text-xs text-muted-foreground">From: {msg.sender_id}</span>
                    </div>
                    <p className="text-sm">{msg.content}</p>
                    <p className="text-xs text-muted-foreground mt-1">{new Date(msg.created_at).toLocaleString()}</p>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => handleDelete(msg.id)}><Trash2 className="h-4 w-4" /></Button>
                    <Button size="sm" variant="destructive" onClick={() => handleSuspendMessaging(msg.sender_id)}><Ban className="h-4 w-4" /></Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">No flagged messages</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default MessagingOversight;