import API_BASE from '../../config';
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Skeleton } from '../../components/ui/skeleton';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import { toast } from 'sonner';
import { MessageCircle, Trash2, Ban, Search, RefreshCw, Flag, Eye, CheckCircle2, Users } from 'lucide-react';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../../components/ui/dialog';

const API = API_BASE;

// iter301 — Reported (abusive) conversation queue + all-threads browser
const ReportedThreadsSection = () => {
  const [status, setStatus] = useState('pending');
  const [threads, setThreads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [viewer, setViewer] = useState(null); // {conversation, messages}
  const [viewerLoading, setViewerLoading] = useState(false);

  const fetchThreads = async (s = status) => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/admin/messages/reported-threads?status=${s}`);
      setThreads(res.data.threads || []);
    } catch (e) {
      toast.error('Failed to load reported threads');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchThreads(status); }, [status]); // eslint-disable-line

  const openThread = async (conversationId) => {
    setViewerLoading(true);
    try {
      const res = await axios.get(`${API}/admin/messages/thread/${conversationId}`);
      setViewer(res.data);
    } catch {
      toast.error('Failed to load thread');
    } finally {
      setViewerLoading(false);
    }
  };

  const resolveThread = async (conversationId) => {
    try {
      await axios.post(`${API}/admin/messages/reported-threads/${conversationId}/resolve`);
      toast.success('Report resolved');
      fetchThreads();
    } catch {
      toast.error('Failed to resolve report');
    }
  };

  return (
    <Card data-testid="reported-threads-section">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Flag className="h-5 w-5 text-red-600" /> Reported Threads ({threads.length})
        </CardTitle>
        <div className="flex gap-1">
          {['pending', 'resolved', 'all'].map((s) => (
            <Button
              key={s}
              size="sm"
              variant={status === s ? 'default' : 'outline'}
              onClick={() => setStatus(s)}
              data-testid={`reported-filter-${s}`}
              className="capitalize"
            >
              {s}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-16 w-full" />
        ) : threads.length === 0 ? (
          <p className="text-center text-muted-foreground py-6">No reported threads</p>
        ) : (
          <div className="space-y-3">
            {threads.map((t) => (
              <div key={t.id} className="flex flex-col md:flex-row justify-between gap-3 p-4 border rounded-lg"
                data-testid={`reported-thread-${t.id}`}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <Badge variant={t.flag_status === 'resolved' ? 'outline' : 'destructive'}>
                      {t.flag_status === 'resolved' ? 'Resolved' : 'Pending'}
                    </Badge>
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Users className="h-3 w-3" />
                      {(t.participants_detail || []).map((p) => p.name || p.email).join(' ↔ ') || t.participants?.join(' ↔ ')}
                    </span>
                  </div>
                  <p className="text-sm"><span className="font-medium">Reason:</span> {t.flag_reason}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Reported {t.flagged_at ? new Date(t.flagged_at).toLocaleString() : '—'}
                    {t.listing_id && <> · Listing {String(t.listing_id).slice(0, 8)}…</>}
                  </p>
                </div>
                <div className="flex gap-2 items-start">
                  <Button size="sm" variant="outline" onClick={() => openThread(t.id)}
                    data-testid={`view-thread-${t.id}`}>
                    <Eye className="h-4 w-4 mr-1" /> View
                  </Button>
                  {t.flag_status !== 'resolved' && (
                    <Button size="sm" onClick={() => resolveThread(t.id)}
                      data-testid={`resolve-thread-${t.id}`}>
                      <CheckCircle2 className="h-4 w-4 mr-1" /> Resolve
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>

      <Dialog open={!!viewer || viewerLoading} onOpenChange={(o) => !o && setViewer(null)}>
        <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto" data-testid="thread-viewer-dialog">
          <DialogHeader>
            <DialogTitle>Thread Messages</DialogTitle>
            <DialogDescription>
              {viewer?.conversation?.participants?.join(' ↔ ')}
            </DialogDescription>
          </DialogHeader>
          {viewerLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <div className="space-y-2">
              {(viewer?.messages || []).map((m) => (
                <div key={m.id} className="p-2 border rounded text-sm">
                  <p className="text-xs text-muted-foreground font-mono mb-1">
                    {m.sender_id?.slice(0, 8)}… · {m.created_at ? new Date(m.created_at).toLocaleString() : ''}
                  </p>
                  <p>{m.content || (m.attachments?.length ? `📎 ${m.attachments[0]?.name}` : '')}</p>
                </div>
              ))}
              {(viewer?.messages || []).length === 0 && (
                <p className="text-center text-muted-foreground py-4">No messages</p>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </Card>
  );
};

const MessagingOversight = () => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [confirm, setConfirm] = useState(null);

  const fetchMessages = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/admin/messages/flagged`);
      const d = response.data;
      setMessages(Array.isArray(d) ? d : d.messages || []);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to load flagged messages');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchMessages(); }, []);

  const deleteMessage = (msg) => {
    setConfirm({
      title: 'Delete this message?',
      description: `The message from ${msg.sender_id} will be permanently removed.\n\nLe message sera définitivement supprimé.`,
      variant: 'destructive',
      confirmText: 'Delete',
      successMessage: 'Message deleted',
      onConfirm: async () => {
        await axios.delete(`${API}/admin/messages/${msg.id}`);
        fetchMessages();
      },
    });
  };

  const suspendMessaging = (userId) => {
    setConfirm({
      title: 'Suspend messaging for this user?',
      description: `User ${userId.slice(0,8)}… will no longer be able to send platform messages. They keep all other account functions.\n\nL'utilisateur ne pourra plus envoyer de messages.`,
      variant: 'destructive',
      confirmText: 'Suspend Messaging',
      successMessage: 'User messaging suspended',
      onConfirm: async () => {
        await axios.put(`${API}/admin/users/${userId}/messaging`, { suspended: true });
      },
    });
  };

  const filtered = messages.filter(m =>
    !search ||
    (m.content || '').toLowerCase().includes(search.toLowerCase()) ||
    (m.sender_id || '').toLowerCase().includes(search.toLowerCase()) ||
    (m.recipient_id || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6" data-testid="messaging-oversight">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2"><MessageCircle className="h-6 w-6" />Messaging Oversight</h2>
          <p className="text-muted-foreground">Monitor and moderate flagged messages and reported threads</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by user or keyword…" className="pl-9"
              data-testid="messaging-search" />
          </div>
          <Button variant="outline" size="sm" onClick={fetchMessages} disabled={loading}
            data-testid="messaging-refresh">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* iter301 — reported (abusive) conversation queue */}
      <ReportedThreadsSection />

      <Card>
        <CardHeader><CardTitle>Flagged Messages ({filtered.length}{filtered.length !== messages.length ? ` / ${messages.length}` : ''})</CardTitle></CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              {Array.from({length: 3}).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
            </div>
          ) : filtered.length > 0 ? (
            <div className="space-y-3">
              {filtered.map(msg => (
                <div key={msg.id} className="flex flex-col md:flex-row justify-between gap-4 p-4 border rounded-lg"
                  data-testid={`message-row-${msg.id}`}>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <Badge variant="destructive">Flagged</Badge>
                      <span className="text-xs text-muted-foreground font-mono">From: {msg.sender_id?.slice(0, 10)}…</span>
                      {msg.recipient_id && <span className="text-xs text-muted-foreground font-mono">To: {msg.recipient_id?.slice(0, 10)}…</span>}
                    </div>
                    <p className="text-sm">{msg.content}</p>
                    <p className="text-xs text-muted-foreground mt-1">{msg.created_at ? new Date(msg.created_at).toLocaleString() : '—'}</p>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => deleteMessage(msg)}
                      data-testid={`delete-message-${msg.id}`} title="Delete message">
                      <Trash2 className="h-4 w-4" />
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => suspendMessaging(msg.sender_id)}
                      data-testid={`suspend-messaging-${msg.sender_id}`} title="Suspend sender's messaging">
                      <Ban className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">
              {search ? 'No messages match your search' : 'No flagged messages'}
              <br /><span className="text-xs">Aucun message signalé</span>
            </p>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog state={confirm} onClose={() => setConfirm(null)} />
    </div>
  );
};

export default MessagingOversight;
