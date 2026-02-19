import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Label } from '../../components/ui/label';
import { Switch } from '../../components/ui/switch';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription,
  DialogFooter 
} from '../../components/ui/dialog';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { toast } from 'sonner';
import { 
  Users, CheckCircle, MessageCircleOff, Search, UserPlus, 
  Copy, Check, Eye, EyeOff, Building2, User, Shield, Mail,
  Phone, AlertTriangle
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EnhancedUserManager = () => {
  const { token } = useAuth();
  const [users, setUsers] = useState([]);
  const [filteredUsers, setFilteredUsers] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [analytics, setAnalytics] = useState({});
  const [loading, setLoading] = useState(true);

  // Create User Dialog State
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newUserData, setNewUserData] = useState({
    email: '',
    name: '',
    phone: '',
    account_type: 'personal',
    company_name: '',
    admin_verified: false
  });

  // Success Dialog State (shows temporary password)
  const [successDialogOpen, setSuccessDialogOpen] = useState(false);
  const [createdUserInfo, setCreatedUserInfo] = useState(null);
  const [passwordCopied, setPasswordCopied] = useState(false);
  const [showPassword, setShowPassword] = useState(true);

  useEffect(() => {
    fetchData();
  }, [filter]);

  useEffect(() => {
    // Real-time search filtering
    if (searchQuery.trim() === '') {
      setFilteredUsers(users);
    } else {
      const query = searchQuery.toLowerCase();
      const filtered = users.filter(user => 
        user.name?.toLowerCase().includes(query) ||
        user.email?.toLowerCase().includes(query) ||
        user.id?.toLowerCase().includes(query) ||
        user.company_name?.toLowerCase().includes(query)
      );
      setFilteredUsers(filtered);
    }
  }, [searchQuery, users]);

  const fetchData = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const endpoint = filter === 'all' ? '/admin/users' : `/admin/users/filter?account_type=${filter}`;
      const [usersRes, analyticsRes] = await Promise.all([
        axios.get(`${API}${endpoint}`, { headers }),
        axios.get(`${API}/admin/analytics/users`, { headers })
      ]);
      setUsers(usersRes.data);
      setFilteredUsers(usersRes.data);
      setAnalytics(analyticsRes.data);
    } catch (error) {
      toast.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (userId, isVerified) => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.put(`${API}/admin/users/${userId}/verify`, { is_verified: !isVerified }, { headers });
      toast.success(`User ${!isVerified ? 'verified' : 'unverified'}`);
      fetchData();
    } catch (error) {
      toast.error('Failed to update verification');
    }
  };

  const handleAdminVerify = async (userId, currentStatus) => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.put(`${API}/admin/users/${userId}/admin-verify`, { admin_verified: !currentStatus }, { headers });
      toast.success(`Admin verification ${!currentStatus ? 'granted' : 'revoked'}`);
      fetchData();
    } catch (error) {
      toast.error('Failed to update admin verification');
    }
  };

  const handleSuspendMessaging = async (userId, isSuspended) => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.put(`${API}/admin/users/${userId}/messaging`, { suspended: !isSuspended }, { headers });
      toast.success(`Messaging ${!isSuspended ? 'suspended' : 'restored'}`);
      fetchData();
    } catch (error) {
      toast.error('Failed to update messaging status');
    }
  };

  const handleCreateUser = async () => {
    // Validation
    if (!newUserData.email || !newUserData.name) {
      toast.error('Email and name are required');
      return;
    }

    if (newUserData.account_type === 'business' && !newUserData.company_name) {
      toast.error('Company name is required for business accounts');
      return;
    }

    setCreating(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.post(`${API}/admin/users/create`, newUserData, { headers });
      
      // Store created user info for success dialog
      setCreatedUserInfo(response.data);
      setCreateDialogOpen(false);
      setSuccessDialogOpen(true);
      setPasswordCopied(false);
      setShowPassword(true);
      
      // Reset form
      setNewUserData({
        email: '',
        name: '',
        phone: '',
        account_type: 'personal',
        company_name: '',
        admin_verified: false
      });
      
      // Refresh user list
      fetchData();
      
      toast.success('User account created successfully');
    } catch (error) {
      const detail = error.response?.data?.detail || 'Failed to create user';
      toast.error(detail);
    } finally {
      setCreating(false);
    }
  };

  const copyPassword = () => {
    if (createdUserInfo?.temporary_password) {
      navigator.clipboard.writeText(createdUserInfo.temporary_password);
      setPasswordCopied(true);
      toast.success('Password copied to clipboard');
      setTimeout(() => setPasswordCopied(false), 3000);
    }
  };

  const closeSuccessDialog = () => {
    // Clear sensitive data when closing
    setCreatedUserInfo(null);
    setSuccessDialogOpen(false);
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Users className="h-6 w-6" />
            User Management
          </h2>
          <p className="text-muted-foreground">Create, filter, verify, and manage users</p>
        </div>
        <Button 
          onClick={() => setCreateDialogOpen(true)}
          className="gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
          data-testid="create-user-btn"
        >
          <UserPlus className="h-4 w-4" />
          Create New User
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                <Users className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{analytics.total || 0}</p>
                <p className="text-sm text-muted-foreground">Total Users</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center">
                <User className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{analytics.personal || 0}</p>
                <p className="text-sm text-muted-foreground">Individual</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-purple-100 dark:bg-purple-900 rounded-full flex items-center justify-center">
                <Building2 className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{analytics.business || 0}</p>
                <p className="text-sm text-muted-foreground">Business</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-amber-100 dark:bg-amber-900 rounded-full flex items-center justify-center">
                <Shield className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{users.filter(u => u.admin_verified).length}</p>
                <p className="text-sm text-muted-foreground">Admin Verified</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter Buttons */}
      <div className="flex gap-2">
        <Button variant={filter === 'all' ? 'default' : 'outline'} onClick={() => setFilter('all')} className={filter === 'all' ? 'gradient-button text-white border-0' : ''}>All Users</Button>
        <Button variant={filter === 'personal' ? 'default' : 'outline'} onClick={() => setFilter('personal')} className={filter === 'personal' ? 'gradient-button text-white border-0' : ''}>Individual</Button>
        <Button variant={filter === 'business' ? 'default' : 'outline'} onClick={() => setFilter('business')} className={filter === 'business' ? 'gradient-button text-white border-0' : ''}>Business</Button>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search by name, email, user ID, or company..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10 text-slate-900 dark:text-slate-100"
        />
      </div>

      {/* User List */}
      <Card>
        <CardHeader>
          <CardTitle>Users ({filteredUsers.length}{searchQuery && ` of ${users.length}`})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {filteredUsers.map(user => (
              <div key={user.id} className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 p-4 border rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold">{user.name}</p>
                    {user.admin_verified && (
                      <Badge className="bg-amber-500 text-white gap-1">
                        <Shield className="h-3 w-3" /> Verified Seller
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{user.email}</p>
                  {user.company_name && (
                    <p className="text-sm text-blue-600 dark:text-blue-400">{user.company_name}</p>
                  )}
                  <div className="flex gap-2 mt-1 flex-wrap">
                    <Badge variant="outline">{user.account_type === 'business' ? 'Business' : 'Individual'}</Badge>
                    <Badge variant="outline">{user.subscription_tier || 'free'}</Badge>
                    {user.email_verified && <Badge className="bg-green-600 text-white">Email Verified</Badge>}
                    {user.password_reset_required && <Badge variant="destructive">Password Reset Required</Badge>}
                    {user.messaging_suspended && <Badge variant="destructive">Messaging Suspended</Badge>}
                  </div>
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Button 
                    size="sm" 
                    variant={user.admin_verified ? 'default' : 'outline'} 
                    onClick={() => handleAdminVerify(user.id, user.admin_verified)}
                    className={user.admin_verified ? 'bg-amber-500 hover:bg-amber-600' : ''}
                    title="Toggle admin-verified badge (trusted seller)"
                  >
                    <Shield className="h-4 w-4 mr-1" />
                    {user.admin_verified ? 'Verified' : 'Verify'}
                  </Button>
                  <Button 
                    size="sm" 
                    variant={user.messaging_suspended ? 'destructive' : 'outline'} 
                    onClick={() => handleSuspendMessaging(user.id, user.messaging_suspended)}
                    title="Suspend/restore messaging"
                  >
                    <MessageCircleOff className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
            {filteredUsers.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                No users found matching your search
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Create User Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <UserPlus className="h-5 w-5" />
              Create New User Account
            </DialogTitle>
            <DialogDescription>
              Create a user account manually. A secure temporary password will be generated and sent to the user.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            {/* Account Type */}
            <div className="space-y-2">
              <Label>Account Type</Label>
              <Select 
                value={newUserData.account_type} 
                onValueChange={(value) => setNewUserData(prev => ({ ...prev, account_type: value }))}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="personal">
                    <span className="flex items-center gap-2">
                      <User className="h-4 w-4" /> Individual
                    </span>
                  </SelectItem>
                  <SelectItem value="business">
                    <span className="flex items-center gap-2">
                      <Building2 className="h-4 w-4" /> Business
                    </span>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Full Name */}
            <div className="space-y-2">
              <Label htmlFor="name">Full Name *</Label>
              <Input
                id="name"
                value={newUserData.name}
                onChange={(e) => setNewUserData(prev => ({ ...prev, name: e.target.value }))}
                placeholder="John Smith"
              />
            </div>

            {/* Email */}
            <div className="space-y-2">
              <Label htmlFor="email">Email *</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  value={newUserData.email}
                  onChange={(e) => setNewUserData(prev => ({ ...prev, email: e.target.value }))}
                  placeholder="john@example.com"
                  className="pl-10"
                />
              </div>
            </div>

            {/* Phone */}
            <div className="space-y-2">
              <Label htmlFor="phone">Phone</Label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="phone"
                  value={newUserData.phone}
                  onChange={(e) => setNewUserData(prev => ({ ...prev, phone: e.target.value }))}
                  placeholder="+1 (555) 123-4567"
                  className="pl-10"
                />
              </div>
            </div>

            {/* Company Name (Business only) */}
            {newUserData.account_type === 'business' && (
              <div className="space-y-2">
                <Label htmlFor="company_name">Company Name *</Label>
                <div className="relative">
                  <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="company_name"
                    value={newUserData.company_name}
                    onChange={(e) => setNewUserData(prev => ({ ...prev, company_name: e.target.value }))}
                    placeholder="Acme Corporation Inc."
                    className="pl-10"
                  />
                </div>
              </div>
            )}

            {/* Admin Verified Toggle */}
            <div className="flex items-center justify-between p-4 bg-amber-50 dark:bg-amber-950/30 rounded-lg border border-amber-200 dark:border-amber-800">
              <div className="flex items-center gap-3">
                <Shield className="h-5 w-5 text-amber-600" />
                <div>
                  <Label htmlFor="admin_verified" className="font-medium">Admin Verified</Label>
                  <p className="text-sm text-muted-foreground">Mark as trusted seller</p>
                </div>
              </div>
              <Switch
                id="admin_verified"
                checked={newUserData.admin_verified}
                onCheckedChange={(checked) => setNewUserData(prev => ({ ...prev, admin_verified: checked }))}
              />
            </div>

            {/* Info Notice */}
            <div className="flex items-start gap-2 p-3 bg-blue-50 dark:bg-blue-950/30 rounded-lg text-sm">
              <AlertTriangle className="h-4 w-4 text-blue-600 mt-0.5" />
              <div className="text-blue-700 dark:text-blue-300">
                <p>A secure temporary password will be auto-generated.</p>
                <p>The user will be required to change it on first login.</p>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleCreateUser} 
              disabled={creating}
              className="gap-2"
            >
              {creating ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                  Creating...
                </>
              ) : (
                <>
                  <UserPlus className="h-4 w-4" />
                  Create Account
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Success Dialog - Shows Temporary Password */}
      <Dialog open={successDialogOpen} onOpenChange={closeSuccessDialog}>
        <DialogContent className="sm:max-w-[450px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-green-600">
              <CheckCircle className="h-5 w-5" />
              Account Created Successfully
            </DialogTitle>
            <DialogDescription>
              The user account has been created. Share the credentials below with the user.
            </DialogDescription>
          </DialogHeader>
          
          {createdUserInfo && (
            <div className="space-y-4 py-4">
              {/* User Info */}
              <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Name:</span>
                  <span className="font-medium">{createdUserInfo.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Email:</span>
                  <span className="font-medium">{createdUserInfo.email}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Type:</span>
                  <Badge>{createdUserInfo.account_type}</Badge>
                </div>
              </div>

              {/* Temporary Password */}
              <div className="space-y-2">
                <Label className="text-red-600 font-semibold">Temporary Password (shown once)</Label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Input
                      type={showPassword ? "text" : "password"}
                      value={createdUserInfo.temporary_password}
                      readOnly
                      className="pr-20 font-mono bg-amber-50 dark:bg-amber-950/30 border-amber-300"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="absolute right-1 top-1/2 -translate-y-1/2 h-7"
                      onClick={() => setShowPassword(!showPassword)}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                  </div>
                  <Button
                    onClick={copyPassword}
                    variant={passwordCopied ? "default" : "outline"}
                    className={passwordCopied ? "bg-green-600" : ""}
                  >
                    {passwordCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              {/* Email Status */}
              <div className={`flex items-center gap-2 p-3 rounded-lg ${createdUserInfo.email_sent ? 'bg-green-50 dark:bg-green-950/30 text-green-700' : 'bg-amber-50 dark:bg-amber-950/30 text-amber-700'}`}>
                <Mail className="h-4 w-4" />
                <span className="text-sm">
                  {createdUserInfo.email_sent 
                    ? 'Welcome email with credentials has been sent' 
                    : 'Email not sent - please share credentials manually'}
                </span>
              </div>

              {/* Warning */}
              <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-950/30 rounded-lg text-sm text-red-700 dark:text-red-300">
                <AlertTriangle className="h-4 w-4 mt-0.5" />
                <div>
                  <p className="font-semibold">This password will not be shown again!</p>
                  <p>Make sure you copy it before closing this dialog.</p>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button onClick={closeSuccessDialog} className="w-full">
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default EnhancedUserManager;
