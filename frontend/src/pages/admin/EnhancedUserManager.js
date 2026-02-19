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
  Phone, AlertTriangle, X
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

  // Validation State
  const [validationErrors, setValidationErrors] = useState({});

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

  // Validation function
  const validateForm = () => {
    const errors = {};
    
    if (!newUserData.name.trim()) {
      errors.name = 'Full name is required';
    }
    
    if (!newUserData.email.trim()) {
      errors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(newUserData.email)) {
      errors.email = 'Please enter a valid email address';
    }
    
    if (newUserData.account_type === 'business' && !newUserData.company_name.trim()) {
      errors.company_name = 'Company name is required for business accounts';
    }
    
    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleCreateUser = async () => {
    if (!validateForm()) {
      toast.error('Please fix the validation errors');
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
      setValidationErrors({});
      
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

  const copyAllCredentials = () => {
    if (createdUserInfo) {
      const text = `Email: ${createdUserInfo.email}\nTemporary Password: ${createdUserInfo.temporary_password}`;
      navigator.clipboard.writeText(text);
      toast.success('All credentials copied to clipboard');
    }
  };

  const closeSuccessDialog = () => {
    // Clear sensitive data when closing
    setCreatedUserInfo(null);
    setSuccessDialogOpen(false);
  };

  const resetCreateForm = () => {
    setNewUserData({
      email: '',
      name: '',
      phone: '',
      account_type: 'personal',
      company_name: '',
      admin_verified: false
    });
    setValidationErrors({});
    setCreateDialogOpen(false);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header - Responsive */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
            <Users className="h-5 w-5 sm:h-6 sm:w-6" />
            User Management
          </h2>
          <p className="text-sm text-muted-foreground mt-1">Create, filter, verify, and manage users</p>
        </div>
        <Button 
          onClick={() => setCreateDialogOpen(true)}
          className="w-full sm:w-auto gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700"
          data-testid="create-user-btn"
        >
          <UserPlus className="h-4 w-4" />
          Create New User
        </Button>
      </div>

      {/* Stats Cards - Responsive Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="w-8 h-8 sm:w-10 sm:h-10 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center flex-shrink-0">
                <Users className="h-4 w-4 sm:h-5 sm:w-5 text-blue-600" />
              </div>
              <div className="min-w-0">
                <p className="text-lg sm:text-2xl font-bold">{analytics.total || 0}</p>
                <p className="text-xs sm:text-sm text-muted-foreground truncate">Total Users</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="w-8 h-8 sm:w-10 sm:h-10 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center flex-shrink-0">
                <User className="h-4 w-4 sm:h-5 sm:w-5 text-green-600" />
              </div>
              <div className="min-w-0">
                <p className="text-lg sm:text-2xl font-bold">{analytics.personal || 0}</p>
                <p className="text-xs sm:text-sm text-muted-foreground truncate">Individual</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="w-8 h-8 sm:w-10 sm:h-10 bg-purple-100 dark:bg-purple-900 rounded-full flex items-center justify-center flex-shrink-0">
                <Building2 className="h-4 w-4 sm:h-5 sm:w-5 text-purple-600" />
              </div>
              <div className="min-w-0">
                <p className="text-lg sm:text-2xl font-bold">{analytics.business || 0}</p>
                <p className="text-xs sm:text-sm text-muted-foreground truncate">Business</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="w-8 h-8 sm:w-10 sm:h-10 bg-amber-100 dark:bg-amber-900 rounded-full flex items-center justify-center flex-shrink-0">
                <Shield className="h-4 w-4 sm:h-5 sm:w-5 text-amber-600" />
              </div>
              <div className="min-w-0">
                <p className="text-lg sm:text-2xl font-bold">{users.filter(u => u.admin_verified).length}</p>
                <p className="text-xs sm:text-sm text-muted-foreground truncate">Verified</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter Buttons - Responsive */}
      <div className="flex flex-wrap gap-2">
        <Button 
          size="sm"
          variant={filter === 'all' ? 'default' : 'outline'} 
          onClick={() => setFilter('all')} 
          className={`${filter === 'all' ? 'gradient-button text-white border-0' : ''} text-xs sm:text-sm`}
        >
          All Users
        </Button>
        <Button 
          size="sm"
          variant={filter === 'personal' ? 'default' : 'outline'} 
          onClick={() => setFilter('personal')} 
          className={`${filter === 'personal' ? 'gradient-button text-white border-0' : ''} text-xs sm:text-sm`}
        >
          Individual
        </Button>
        <Button 
          size="sm"
          variant={filter === 'business' ? 'default' : 'outline'} 
          onClick={() => setFilter('business')} 
          className={`${filter === 'business' ? 'gradient-button text-white border-0' : ''} text-xs sm:text-sm`}
        >
          Business
        </Button>
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

      {/* User List - Responsive */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base sm:text-lg">
            Users ({filteredUsers.length}{searchQuery && ` of ${users.length}`})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-3 sm:p-6 pt-0">
          <div className="space-y-3">
            {filteredUsers.map(user => (
              <div 
                key={user.id} 
                className="flex flex-col gap-3 p-3 sm:p-4 border rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
              >
                {/* User Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold truncate">{user.name}</p>
                    {user.admin_verified && (
                      <Badge className="bg-amber-500 text-white gap-1 text-xs">
                        <Shield className="h-3 w-3" /> Verified
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground truncate">{user.email}</p>
                  {user.company_name && (
                    <p className="text-sm text-blue-600 dark:text-blue-400 truncate">{user.company_name}</p>
                  )}
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    <Badge variant="outline" className="text-xs">
                      {user.account_type === 'business' ? 'Business' : 'Individual'}
                    </Badge>
                    <Badge variant="outline" className="text-xs">{user.subscription_tier || 'free'}</Badge>
                    {user.email_verified && (
                      <Badge className="bg-green-600 text-white text-xs">Email ✓</Badge>
                    )}
                    {user.password_reset_required && (
                      <Badge variant="destructive" className="text-xs">Reset Required</Badge>
                    )}
                  </div>
                </div>
                
                {/* Action Buttons */}
                <div className="flex gap-2 flex-wrap">
                  <Button 
                    size="sm" 
                    variant={user.admin_verified ? 'default' : 'outline'} 
                    onClick={() => handleAdminVerify(user.id, user.admin_verified)}
                    className={`${user.admin_verified ? 'bg-amber-500 hover:bg-amber-600' : ''} text-xs sm:text-sm`}
                    title="Toggle admin-verified badge"
                  >
                    <Shield className="h-3.5 w-3.5 mr-1" />
                    {user.admin_verified ? 'Verified' : 'Verify'}
                  </Button>
                  <Button 
                    size="sm" 
                    variant={user.messaging_suspended ? 'destructive' : 'outline'} 
                    onClick={() => handleSuspendMessaging(user.id, user.messaging_suspended)}
                    title="Suspend/restore messaging"
                  >
                    <MessageCircleOff className="h-3.5 w-3.5" />
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

      {/* Create User Dialog - Fully Responsive */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="w-[95vw] max-w-[500px] max-h-[90vh] overflow-y-auto p-0 gap-0">
          {/* Fixed Header */}
          <DialogHeader className="sticky top-0 bg-background z-10 p-4 sm:p-6 pb-4 border-b">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                  <UserPlus className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <DialogTitle className="text-lg">Create New User</DialogTitle>
                  <DialogDescription className="text-sm mt-0.5">
                    A secure password will be auto-generated
                  </DialogDescription>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0 rounded-full"
                onClick={resetCreateForm}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </DialogHeader>
          
          {/* Scrollable Content */}
          <div className="p-4 sm:p-6 space-y-6 overflow-y-auto">
            {/* Section 1: Account Type */}
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wide">
                <span className="w-5 h-5 bg-slate-200 dark:bg-slate-700 rounded-full flex items-center justify-center text-xs">1</span>
                Account Type
              </div>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setNewUserData(prev => ({ ...prev, account_type: 'personal' }))}
                  className={`p-4 rounded-xl border-2 transition-all ${
                    newUserData.account_type === 'personal'
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30'
                      : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                  }`}
                >
                  <User className={`h-6 w-6 mx-auto mb-2 ${newUserData.account_type === 'personal' ? 'text-blue-600' : 'text-slate-400'}`} />
                  <p className={`text-sm font-medium ${newUserData.account_type === 'personal' ? 'text-blue-700 dark:text-blue-300' : ''}`}>
                    Individual
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">Personal account</p>
                </button>
                <button
                  type="button"
                  onClick={() => setNewUserData(prev => ({ ...prev, account_type: 'business' }))}
                  className={`p-4 rounded-xl border-2 transition-all ${
                    newUserData.account_type === 'business'
                      ? 'border-purple-500 bg-purple-50 dark:bg-purple-950/30'
                      : 'border-slate-200 dark:border-slate-700 hover:border-slate-300'
                  }`}
                >
                  <Building2 className={`h-6 w-6 mx-auto mb-2 ${newUserData.account_type === 'business' ? 'text-purple-600' : 'text-slate-400'}`} />
                  <p className={`text-sm font-medium ${newUserData.account_type === 'business' ? 'text-purple-700 dark:text-purple-300' : ''}`}>
                    Business
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">Company account</p>
                </button>
              </div>
            </div>

            {/* Section 2: Personal Information */}
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wide">
                <span className="w-5 h-5 bg-slate-200 dark:bg-slate-700 rounded-full flex items-center justify-center text-xs">2</span>
                Personal Information
              </div>
              
              {/* Full Name */}
              <div className="space-y-2">
                <Label htmlFor="name" className="text-sm">
                  Full Name <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="name"
                  value={newUserData.name}
                  onChange={(e) => {
                    setNewUserData(prev => ({ ...prev, name: e.target.value }));
                    if (validationErrors.name) {
                      setValidationErrors(prev => ({ ...prev, name: null }));
                    }
                  }}
                  placeholder="John Smith"
                  className={validationErrors.name ? 'border-red-500 focus:ring-red-500' : ''}
                />
                {validationErrors.name && (
                  <p className="text-xs text-red-500 flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    {validationErrors.name}
                  </p>
                )}
              </div>

              {/* Email */}
              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm">
                  Email Address <span className="text-red-500">*</span>
                </Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    value={newUserData.email}
                    onChange={(e) => {
                      setNewUserData(prev => ({ ...prev, email: e.target.value }));
                      if (validationErrors.email) {
                        setValidationErrors(prev => ({ ...prev, email: null }));
                      }
                    }}
                    placeholder="john@example.com"
                    className={`pl-10 ${validationErrors.email ? 'border-red-500 focus:ring-red-500' : ''}`}
                  />
                </div>
                {validationErrors.email && (
                  <p className="text-xs text-red-500 flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    {validationErrors.email}
                  </p>
                )}
              </div>

              {/* Phone */}
              <div className="space-y-2">
                <Label htmlFor="phone" className="text-sm">Phone Number</Label>
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
            </div>

            {/* Section 3: Business Information (Conditional) */}
            <div 
              className={`space-y-4 transition-all duration-300 ease-in-out overflow-hidden ${
                newUserData.account_type === 'business' 
                  ? 'max-h-40 opacity-100' 
                  : 'max-h-0 opacity-0'
              }`}
            >
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wide">
                <span className="w-5 h-5 bg-purple-200 dark:bg-purple-800 rounded-full flex items-center justify-center text-xs">3</span>
                Business Information
              </div>
              
              {/* Company Name */}
              <div className="space-y-2">
                <Label htmlFor="company_name" className="text-sm">
                  Company Name <span className="text-red-500">*</span>
                </Label>
                <div className="relative">
                  <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="company_name"
                    value={newUserData.company_name}
                    onChange={(e) => {
                      setNewUserData(prev => ({ ...prev, company_name: e.target.value }));
                      if (validationErrors.company_name) {
                        setValidationErrors(prev => ({ ...prev, company_name: null }));
                      }
                    }}
                    placeholder="Acme Corporation Inc."
                    className={`pl-10 ${validationErrors.company_name ? 'border-red-500 focus:ring-red-500' : ''}`}
                  />
                </div>
                {validationErrors.company_name && (
                  <p className="text-xs text-red-500 flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    {validationErrors.company_name}
                  </p>
                )}
              </div>
            </div>

            {/* Section: Admin Verified Toggle */}
            <div className="flex items-center justify-between p-4 bg-amber-50 dark:bg-amber-950/30 rounded-xl border border-amber-200 dark:border-amber-800">
              <div className="flex items-center gap-3">
                <Shield className="h-5 w-5 text-amber-600 flex-shrink-0" />
                <div>
                  <Label htmlFor="admin_verified" className="font-medium text-sm cursor-pointer">
                    Admin Verified
                  </Label>
                  <p className="text-xs text-muted-foreground mt-0.5">Mark as trusted seller</p>
                </div>
              </div>
              <Switch
                id="admin_verified"
                checked={newUserData.admin_verified}
                onCheckedChange={(checked) => setNewUserData(prev => ({ ...prev, admin_verified: checked }))}
              />
            </div>

            {/* Info Notice */}
            <div className="flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-950/30 rounded-xl text-sm">
              <AlertTriangle className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
              <div className="text-blue-700 dark:text-blue-300">
                <p className="font-medium">Password will be auto-generated</p>
                <p className="text-xs mt-1">User must change it on first login</p>
              </div>
            </div>
          </div>

          {/* Fixed Footer */}
          <DialogFooter className="sticky bottom-0 bg-background z-10 p-4 sm:p-6 pt-4 border-t flex-col sm:flex-row gap-2">
            <Button 
              variant="outline" 
              onClick={resetCreateForm}
              className="w-full sm:w-auto order-2 sm:order-1"
            >
              Cancel
            </Button>
            <Button 
              onClick={handleCreateUser} 
              disabled={creating}
              className="w-full sm:w-auto gap-2 order-1 sm:order-2"
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

      {/* Success Dialog - Responsive */}
      <Dialog open={successDialogOpen} onOpenChange={closeSuccessDialog}>
        <DialogContent className="w-[95vw] max-w-[450px] max-h-[90vh] overflow-y-auto p-0 gap-0">
          {/* Header */}
          <DialogHeader className="p-4 sm:p-6 pb-4 border-b">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center">
                <CheckCircle className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <DialogTitle className="text-lg text-green-600">Account Created!</DialogTitle>
                <DialogDescription className="text-sm mt-0.5">
                  Share the credentials below with the user
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>
          
          {createdUserInfo && (
            <div className="p-4 sm:p-6 space-y-4">
              {/* User Info Card */}
              <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-xl space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Name</span>
                  <span className="font-medium text-sm">{createdUserInfo.name}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Email</span>
                  <span className="font-medium text-sm truncate max-w-[180px]">{createdUserInfo.email}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Type</span>
                  <Badge variant="outline" className="text-xs">{createdUserInfo.account_type}</Badge>
                </div>
              </div>

              {/* Temporary Password Section */}
              <div className="space-y-3">
                <Label className="text-red-600 font-semibold text-sm flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" />
                  Temporary Password (shown once)
                </Label>
                <div className="space-y-2">
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Input
                        type={showPassword ? "text" : "password"}
                        value={createdUserInfo.temporary_password}
                        readOnly
                        className="pr-12 font-mono text-sm bg-amber-50 dark:bg-amber-950/30 border-amber-300"
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                        onClick={() => setShowPassword(!showPassword)}
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </Button>
                    </div>
                    <Button
                      onClick={copyPassword}
                      variant={passwordCopied ? "default" : "outline"}
                      className={`flex-shrink-0 ${passwordCopied ? "bg-green-600" : ""}`}
                      size="sm"
                    >
                      {passwordCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                    </Button>
                  </div>
                  <Button
                    onClick={copyAllCredentials}
                    variant="outline"
                    className="w-full text-sm"
                    size="sm"
                  >
                    <Copy className="h-4 w-4 mr-2" />
                    Copy All Credentials
                  </Button>
                </div>
              </div>

              {/* Email Status */}
              <div className={`flex items-center gap-2 p-3 rounded-xl text-sm ${
                createdUserInfo.email_sent 
                  ? 'bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-300' 
                  : 'bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300'
              }`}>
                <Mail className="h-4 w-4 flex-shrink-0" />
                <span className="text-xs sm:text-sm">
                  {createdUserInfo.email_sent 
                    ? 'Welcome email sent to user' 
                    : 'Email not sent - share credentials manually'}
                </span>
              </div>

              {/* Warning */}
              <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-950/30 rounded-xl">
                <AlertTriangle className="h-4 w-4 text-red-600 mt-0.5 flex-shrink-0" />
                <div className="text-xs sm:text-sm text-red-700 dark:text-red-300">
                  <p className="font-semibold">Password won't be shown again!</p>
                  <p className="mt-0.5">Copy it before closing this dialog.</p>
                </div>
              </div>
            </div>
          )}

          <DialogFooter className="p-4 sm:p-6 pt-4 border-t">
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
