import API_BASE from '../../config';
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';
import {
  Users, UserPlus, Shield, Mail, Trash2, Loader2, Copy, Clock, CheckCircle, XCircle, ChevronDown
} from 'lucide-react';
import axios from 'axios';

const API = API_BASE;

const ROLE_INFO = {
  admin: { color: 'bg-red-100 text-red-700 border-red-200', label: 'Admin', desc: 'Full access' },
  manager: { color: 'bg-blue-100 text-blue-700 border-blue-200', label: 'Manager', desc: 'Manage auctions, users & finance' },
  support: { color: 'bg-green-100 text-green-700 border-green-200', label: 'Support', desc: 'View-only access' },
};

const TeamManager = () => {
  const { token } = useAuth();
  const [members, setMembers] = useState([]);
  const [invitations, setInvitations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteName, setInviteName] = useState('');
  const [inviteRole, setInviteRole] = useState('support');
  const [sending, setSending] = useState(false);
  const [lastInviteLink, setLastInviteLink] = useState('');

  const headers = { Authorization: `Bearer ${token}` };

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [membersRes, invitesRes] = await Promise.all([
        axios.get(`${API}/team/members`, { headers }),
        axios.get(`${API}/team/invitations`, { headers }),
      ]);
      setMembers(membersRes.data.members || []);
      setInvitations(invitesRes.data.invitations || []);
    } catch (err) {
      toast.error('Failed to load team data');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleInvite = async (e) => {
    e.preventDefault();
    setSending(true);
    try {
      const res = await axios.post(`${API}/team/invite`, { email: inviteEmail, role: inviteRole, name: inviteName }, { headers });
      toast.success(res.data.message);
      setLastInviteLink(res.data.invite_link);
      setInviteEmail('');
      setInviteName('');
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to send invitation');
    } finally {
      setSending(false);
    }
  };

  const handleCancelInvite = async (id) => {
    try {
      await axios.delete(`${API}/team/invitations/${id}`, { headers });
      toast.success('Invitation cancelled');
      fetchData();
    } catch (err) {
      toast.error('Failed to cancel invitation');
    }
  };

  const handleRoleChange = async (userId, newRole) => {
    try {
      await axios.put(`${API}/team/members/${userId}/role`, { role: newRole }, { headers });
      toast.success('Role updated');
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update role');
    }
  };

  const handleRemoveMember = async (userId, name) => {
    if (!window.confirm(`Remove ${name} from the team? They will lose all admin access.`)) return;
    try {
      await axios.delete(`${API}/team/members/${userId}`, { headers });
      toast.success('Member removed');
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to remove member');
    }
  };

  const copyLink = (link) => {
    navigator.clipboard.writeText(link);
    toast.success('Invite link copied!');
  };

  if (loading) {
    return <div className="flex justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;
  }

  return (
    <div className="space-y-6" data-testid="team-manager">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2"><Users className="h-6 w-6" /> Team Management</h2>
          <p className="text-muted-foreground text-sm mt-1">{members.length} team member{members.length !== 1 ? 's' : ''}</p>
        </div>
        <Button onClick={() => setShowInvite(!showInvite)} className="gradient-button text-white border-0" data-testid="invite-member-btn">
          <UserPlus className="h-4 w-4 mr-2" /> Invite Member
        </Button>
      </div>

      {/* Invite Form */}
      {showInvite && (
        <Card data-testid="invite-form">
          <CardContent className="pt-6">
            <form onSubmit={handleInvite} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input type="email" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} required placeholder="team@example.com" data-testid="invite-email-input" />
                </div>
                <div className="space-y-2">
                  <Label>Name (optional)</Label>
                  <Input value={inviteName} onChange={e => setInviteName(e.target.value)} placeholder="John Doe" data-testid="invite-name-input" />
                </div>
                <div className="space-y-2">
                  <Label>Role</Label>
                  <select value={inviteRole} onChange={e => setInviteRole(e.target.value)}
                    className="w-full px-3 py-2 border border-input rounded-md bg-background" data-testid="invite-role-select">
                    <option value="admin">Admin - Full access</option>
                    <option value="manager">Manager - Manage operations</option>
                    <option value="support">Support - View only</option>
                  </select>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Button type="submit" disabled={sending} data-testid="send-invite-btn">
                  {sending ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Sending...</> : <><Mail className="h-4 w-4 mr-2" /> Send Invite</>}
                </Button>
                <Button type="button" variant="outline" onClick={() => setShowInvite(false)}>Cancel</Button>
              </div>
            </form>
            {lastInviteLink && (
              <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                <p className="text-sm font-medium text-green-700 dark:text-green-300 mb-2">Invite link generated! Share it with the team member:</p>
                <div className="flex items-center gap-2">
                  <Input value={lastInviteLink} readOnly className="text-xs bg-white dark:bg-background" data-testid="invite-link-display" />
                  <Button size="sm" variant="outline" onClick={() => copyLink(lastInviteLink)} data-testid="copy-invite-link-btn">
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Role Legend */}
      <div className="flex flex-wrap gap-3">
        {Object.entries(ROLE_INFO).map(([key, info]) => (
          <div key={key} className="flex items-center gap-2 text-sm">
            <Badge variant="outline" className={info.color}><Shield className="h-3 w-3 mr-1" />{info.label}</Badge>
            <span className="text-muted-foreground">{info.desc}</span>
          </div>
        ))}
      </div>

      {/* Members */}
      <Card>
        <CardHeader><CardTitle className="text-lg">Active Members</CardTitle></CardHeader>
        <CardContent>
          {members.length === 0 ? (
            <p className="text-muted-foreground text-center py-6">No team members yet. Invite your first member above.</p>
          ) : (
            <div className="space-y-3">
              {members.map(member => (
                <div key={member.id} className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition" data-testid={`team-member-${member.id}`}>
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center font-bold text-primary">
                      {(member.name || member.email)?.[0]?.toUpperCase()}
                    </div>
                    <div>
                      <p className="font-medium">{member.name || 'Unnamed'}</p>
                      <p className="text-sm text-muted-foreground">{member.email}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="relative">
                      <select
                        value={member.role}
                        onChange={e => handleRoleChange(member.id, e.target.value)}
                        className={`appearance-none pr-8 pl-3 py-1.5 rounded-full text-sm font-medium border cursor-pointer ${ROLE_INFO[member.role]?.color || 'bg-gray-100'}`}
                        data-testid={`role-select-${member.id}`}
                      >
                        <option value="admin">Admin</option>
                        <option value="manager">Manager</option>
                        <option value="support">Support</option>
                      </select>
                      <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3 w-3 pointer-events-none" />
                    </div>
                    <Button size="sm" variant="ghost" className="text-red-500 hover:text-red-700 hover:bg-red-50"
                      onClick={() => handleRemoveMember(member.id, member.name)} data-testid={`remove-member-${member.id}`}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pending Invitations */}
      <Card>
        <CardHeader><CardTitle className="text-lg">Pending Invitations</CardTitle></CardHeader>
        <CardContent>
          {invitations.filter(i => i.status === 'pending').length === 0 ? (
            <p className="text-muted-foreground text-center py-6">No pending invitations</p>
          ) : (
            <div className="space-y-3">
              {invitations.filter(i => i.status === 'pending').map(inv => (
                <div key={inv.id} className="flex items-center justify-between p-4 border rounded-lg border-dashed" data-testid={`invitation-${inv.id}`}>
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                      <Clock className="h-5 w-5 text-amber-600" />
                    </div>
                    <div>
                      <p className="font-medium">{inv.email}</p>
                      <p className="text-xs text-muted-foreground">
                        Invited {new Date(inv.created_at).toLocaleDateString()} &middot; Expires {new Date(inv.expires_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className={ROLE_INFO[inv.role]?.color}>{inv.role}</Badge>
                    <Button size="sm" variant="ghost" className="text-red-500" onClick={() => handleCancelInvite(inv.id)} data-testid={`cancel-invite-${inv.id}`}>
                      <XCircle className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Invitation History */}
      {invitations.filter(i => i.status !== 'pending').length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Invitation History</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2">
              {invitations.filter(i => i.status !== 'pending').slice(0, 10).map(inv => (
                <div key={inv.id} className="flex items-center justify-between p-3 border rounded-lg opacity-70">
                  <div className="flex items-center gap-3">
                    {inv.status === 'accepted' ? <CheckCircle className="h-4 w-4 text-green-500" /> : <XCircle className="h-4 w-4 text-red-500" />}
                    <span className="text-sm">{inv.email}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs">{inv.role}</Badge>
                    <Badge variant={inv.status === 'accepted' ? 'default' : 'secondary'} className="text-xs">{inv.status}</Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default TeamManager;
