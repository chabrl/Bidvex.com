import API_BASE from '../../config';
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
  Users, CheckCircle, MessageCircleOff, Search, UserPlus, Gavel, 
  Copy, Check, Eye, EyeOff, Building2, User, Shield, Mail,
  Phone, AlertTriangle, X, Ban, Trash2, MapPin, MoreVertical,
  Key, Edit, Crown, Theater, CreditCard, Receipt, Star,
  Headphones, LogIn,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel,
} from '../../components/ui/dropdown-menu';
import { extractErrorMessage } from '../../utils/errorHandler';

const API = API_BASE;

const EnhancedUserManager = () => {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers] = useState([]);
  const [filteredUsers, setFilteredUsers] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [analytics, setAnalytics] = useState({});
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState('created_at');
  const [sortDir, setSortDir] = useState('desc');

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

  // iter301 — Buyer Reviews modal (reviews received as a buyer; admin view)
  const [buyerReviewsModal, setBuyerReviewsModal] = useState({ open: false, user: null, data: null, loading: false });

  const openBuyerReviews = async (user) => {
    setBuyerReviewsModal({ open: true, user, data: null, loading: true });
    try {
      const res = await axios.get(`${API}/reviews/buyer/${user.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setBuyerReviewsModal({ open: true, user, data: res.data, loading: false });
    } catch (e) {
      toast.error('Failed to load buyer reviews');
      setBuyerReviewsModal({ open: false, user: null, data: null, loading: false });
    }
  };

  const softDeleteReview = async (reviewId) => {
    try {
      await axios.delete(`${API}/reviews/${reviewId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success('Review removed');
      if (buyerReviewsModal.user) openBuyerReviews(buyerReviewsModal.user);
    } catch (e) {
      toast.error('Failed to remove review');
    }
  };

  // Success Dialog State (shows temporary password)
  const [successDialogOpen, setSuccessDialogOpen] = useState(false);
  const [createdUserInfo, setCreatedUserInfo] = useState(null);
  const [passwordCopied, setPasswordCopied] = useState(false);
  const [showPassword, setShowPassword] = useState(true);

  useEffect(() => {
    fetchData();
  }, [filter, sortBy, sortDir]);

  useEffect(() => {
    // Real-time search filtering (client-side within the current page)
    if (searchQuery.trim() === '') {
      setFilteredUsers(users);
    } else {
      const query = searchQuery.toLowerCase();
      const filtered = users.filter(user =>
        user.name?.toLowerCase().includes(query) ||
        user.email?.toLowerCase().includes(query) ||
        user.id?.toLowerCase().includes(query) ||
        user.company_name?.toLowerCase().includes(query) ||
        user.phone?.toLowerCase().includes(query) ||
        user.city?.toLowerCase().includes(query)
      );
      setFilteredUsers(filtered);
    }
  }, [searchQuery, users]);

  const fetchData = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const qp = `sort_by=${encodeURIComponent(sortBy)}&sort_dir=${encodeURIComponent(sortDir)}&limit=200`;
      const endpoint =
        filter === 'all'
          ? `/admin/users?${qp}`
          : `/admin/users/filter?account_type=${filter}`;
      const [usersRes, analyticsRes] = await Promise.all([
        axios.get(`${API}${endpoint}`, { headers }),
        axios.get(`${API}/admin/analytics/users`, { headers })
      ]);
      const usersData = Array.isArray(usersRes.data) ? usersRes.data : (usersRes.data.users || []);
      setUsers(usersData);
      setFilteredUsers(usersData);
      setAnalytics(analyticsRes.data);
    } catch (error) {
      toast.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const toggleSort = (column) => {
    if (sortBy === column) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(column);
      setSortDir('asc');
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
      await axios.put(`${API}/admin/users/${userId}/messaging`, { suspended: !isSuspended }, { headers });      toast.success(`Messaging ${!isSuspended ? 'suspended' : 'restored'}`);
      fetchData();
    } catch (error) {
      toast.error('Failed to update messaging status');
    }
  };

  // iter316-C — Promote / Demote dialer contractor role.
  const handlePromoteToContractor = async (u) => {
    if (!window.confirm(`Promote ${u.email} to a dialer contractor? They will gain access to the BidVex Dialer and earn referral commissions.`)) return;
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.post(`${API}/twilio/admin/users/${u.id}/promote-to-contractor`, {}, { headers });
      toast.success(`${u.email} promoted to contractor`);
      fetchData();
    } catch (error) {
      const d = error?.response?.data?.detail;
      toast.error((typeof d === 'object' ? d.message_en : d) || 'Failed to promote');
    }
  };

  const handleDemoteFromContractor = async (u) => {
    if (!window.confirm(`Demote ${u.email} from contractor? Commission history will be preserved.`)) return;
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const r = await axios.post(`${API}/twilio/admin/users/${u.id}/demote-from-contractor`, {}, { headers });
      toast.success(`Demoted — reverted to ${r.data.reverted_to_role}`);
      fetchData();
    } catch (error) {
      const d = error?.response?.data?.detail;
      toast.error((typeof d === 'object' ? d.message_en : d) || 'Failed to demote');
    }
  };

  // iter300 P1 — lift (or set) a buyer's bidding suspension (overdue-payment escalation)
  const handleBiddingSuspension = async (userId, isSuspended) => {
    if (!window.confirm(isSuspended
      ? 'Lift this user\'s bidding suspension? They will be notified and can bid again.'
      : 'Suspend this user\'s bidding privileges?')) return;
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.post(`${API}/admin/users/${userId}/bidding-suspension?suspended=${!isSuspended}`, {}, { headers });
      toast.success(isSuspended ? 'Bidding suspension lifted — user notified' : 'Bidding privileges suspended');
      fetchData();
    } catch (error) {
      toast.error(extractErrorMessage(error) || 'Failed to update bidding suspension');
    }
  };

  const handleSuspendAccount = async (userId, currentStatus) => {
    const isSuspended = currentStatus === 'suspended';
    const action = isSuspended ? 'reactivate' : 'suspend';
    if (!window.confirm(`Are you sure you want to ${action} this account?`)) return;
    try {
      const headers = { Authorization: `Bearer ${token}` };
      await axios.put(`${API}/admin/users/${userId}/suspend`, {
        suspended: !isSuspended,
        reason: isSuspended ? '' : 'Admin action'
      }, { headers });
      toast.success(`Account ${isSuspended ? 'reactivated' : 'suspended'} successfully`);
      fetchData();
    } catch (error) {
      toast.error(extractErrorMessage(error) || `Failed to ${action} account`);
    }
  };

  const [deleteUserModal, setDeleteUserModal] = useState({ open: false, user: null });

  // iter214 P2 — Notify + Request-Documents modals
  const [notifyModal, setNotifyModal] = useState({ open: false, user: null });
  const [notifyForm, setNotifyForm] = useState({
    notification_type: 'general', subject: '', body_en: '', body_fr: '',
    send_via: 'both',
    // iter266 Mission 3D — attachment-request fields.
    requires_attachment: false,
    attachment_request_label: '',
    attachment_request_label_fr: '',
    attachment_types: 'PDF, JPG, PNG',
    attachment_max_mb: 1.0,
  });
  const [notifyBusy, setNotifyBusy] = useState(false);

  const [docReqModal, setDocReqModal] = useState({ open: false, user: null });
  const [docReqForm, setDocReqForm] = useState({
    document_types: [], deadline: '', message: '',
  });
  const [docReqBusy, setDocReqBusy] = useState(false);

  // iter258 Mission 1 — Request Payment modal state.
  const [reqPayModal, setReqPayModal] = useState({ open: false, user: null });
  const [reqPayForm, setReqPayForm] = useState({
    subtotal: '',
    tax_type: 'gst_qst',
    custom_tax_rate: '',
    description: '',
    internal_notes: '',
    send_email: true,
    send_notification: true,
    expiry_hours: 48,
  });
  const [reqPayBusy, setReqPayBusy] = useState(false);
  const [reqPayHistory, setReqPayHistory] = useState([]);
  const [reqPayHistoryUser, setReqPayHistoryUser] = useState(null);

  const TAX_RATES = {
    none: 0, gst: 5, qst: 9.975, gst_qst: 14.975, hst_on: 13, custom: null,
  };
  const reqPayResolvedRate = () => {
    if (reqPayForm.tax_type === 'custom') {
      const v = parseFloat(reqPayForm.custom_tax_rate);
      return Number.isFinite(v) && v >= 0 ? v : 0;
    }
    return TAX_RATES[reqPayForm.tax_type] ?? 0;
  };
  const reqPayCalcTotal = () => {
    const sub = parseFloat(reqPayForm.subtotal);
    if (!Number.isFinite(sub) || sub <= 0) return 0;
    return Math.round((sub + (sub * reqPayResolvedRate()) / 100) * 100) / 100;
  };

  const submitRequestPayment = async () => {
    if (!reqPayModal.user) return;
    // iter260 — Guard against contact-only stubs that have no account
    // ID. The admin users list returns these rows alongside real users
    // (they're created by marketing-list imports + unsubscribe-link
    // visits) — and clicking Request Payment on one of them would
    // have produced `/api/admin/users/undefined/request-payment`.
    if (!reqPayModal.user.id) {
      toast.error('This contact has no registered account — Request Payment is unavailable.');
      return;
    }
    const total = reqPayCalcTotal();
    if (!total || total <= 0) {
      toast.error('Subtotal must be a positive number');
      return;
    }
    if (!reqPayForm.description.trim()) {
      toast.error('Description is required');
      return;
    }
    setReqPayBusy(true);
    try {
      const body = {
        subtotal: parseFloat(reqPayForm.subtotal),
        tax_type: reqPayForm.tax_type,
        custom_tax_rate: reqPayForm.tax_type === 'custom' ? parseFloat(reqPayForm.custom_tax_rate) : null,
        total_amount: total,
        description: reqPayForm.description.trim(),
        internal_notes: reqPayForm.internal_notes.trim(),
        send_email: !!reqPayForm.send_email,
        send_notification: !!reqPayForm.send_notification,
        expiry_hours: reqPayForm.expiry_hours === 'none' || reqPayForm.expiry_hours === 0
          ? null
          : Number(reqPayForm.expiry_hours),
      };
      const r = await axios.post(
        `${API}/admin/users/${reqPayModal.user.id}/request-payment`,
        body,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const warning = r.data?.warning;
      toast.success(
        `Payment link created — $${r.data.total_amount.toFixed(2)} CAD${warning ? ` (${warning})` : ''}`,
      );
      setReqPayModal({ open: false, user: null });
      setReqPayForm({
        subtotal: '', tax_type: 'gst_qst', custom_tax_rate: '',
        description: '', internal_notes: '',
        send_email: true, send_notification: true, expiry_hours: 48,
      });
    } catch (e) {
      // iter260 — Surface the real backend error so admins don't see a
      // generic toast. Bubble validation messages (422 array, 400/404
      // detail strings, network errors).
      console.error('[request-payment] error:', e?.response?.status, e?.response?.data);
      const detail = e?.response?.data?.detail;
      let msg = 'Failed to create payment request';
      if (Array.isArray(detail) && detail[0]?.msg) {
        msg = `Validation: ${detail.map((d) => `${(d.loc || []).join('.')}: ${d.msg}`).join('; ')}`;
      } else if (typeof detail === 'string' && detail.trim()) {
        msg = detail;
      } else if (e?.message) {
        msg = e.message;
      }
      toast.error(msg);
    } finally {
      setReqPayBusy(false);
    }
  };

  const openPaymentHistory = async (user) => {
    setReqPayHistoryUser(user);
    setReqPayHistory([]);
    try {
      const r = await axios.get(
        `${API}/admin/users/${user.id}/payment-requests`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setReqPayHistory(Array.isArray(r.data?.items) ? r.data.items : []);
    } catch (e) {
      toast.error('Failed to load payment request history');
    }
  };

  const submitNotify = async () => {
    if (!notifyModal.user) return;
    if (!notifyForm.subject.trim() || !notifyForm.body_en.trim()) {
      toast.error('Subject and English body are required');
      return;
    }
    setNotifyBusy(true);
    try {
      await axios.post(`${API}/admin/users/${notifyModal.user.id}/send-notification`, notifyForm, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success('Notification sent · Notification envoyée');
      setNotifyModal({ open: false, user: null });
      setNotifyForm({
        notification_type: 'general', subject: '', body_en: '', body_fr: '',
        send_via: 'both',
        requires_attachment: false,
        attachment_request_label: '',
        attachment_request_label_fr: '',
        attachment_types: 'PDF, JPG, PNG',
        attachment_max_mb: 1.0,
      });
    } catch (e) {
      toast.error(extractErrorMessage(e) || extractErrorMessage(e) || 'Send failed');
    } finally {
      setNotifyBusy(false);
    }
  };

  const submitDocReq = async () => {
    if (!docReqModal.user) return;
    if (docReqForm.document_types.length === 0 || !docReqForm.deadline) {
      toast.error('Pick at least one document type and a deadline');
      return;
    }
    setDocReqBusy(true);
    try {
      await axios.post(`${API}/admin/users/${docReqModal.user.id}/request-documents`, docReqForm, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success('Document request sent · Demande envoyée');
      setDocReqModal({ open: false, user: null });
      setDocReqForm({ document_types: [], deadline: '', message: '' });
    } catch (e) {
      toast.error(extractErrorMessage(e) || extractErrorMessage(e) || 'Request failed');
    } finally {
      setDocReqBusy(false);
    }
  };

  const toggleDocType = (t) => setDocReqForm((p) => ({
    ...p,
    document_types: p.document_types.includes(t)
      ? p.document_types.filter((x) => x !== t)
      : [...p.document_types, t],
  }));

  const DOC_TYPES = [
    { v: 'government_id',         l: 'Government-issued ID' },
    { v: 'business_registration', l: 'Business registration certificate' },
    { v: 'dealer_licence',        l: 'Dealer licence' },
    { v: 'neq_proof',             l: 'NEQ proof' },
    { v: 'insurance_certificate', l: 'Insurance certificate' },
    { v: 'other',                 l: 'Other document' },
  ];

  // iter215 — Edit Profile / Change Tier / View Txns / View Subscription modals
  const [editProfileModal, setEditProfileModal] = useState({ open: false, user: null });
  const [editForm, setEditForm] = useState({});
  const [editBusy, setEditBusy] = useState(false);

  const [changeTierModal, setChangeTierModal] = useState({ open: false, user: null });
  const [newTier, setNewTier] = useState('standard');
  const [tierBusy, setTierBusy] = useState(false);

  const [viewTxnModal, setViewTxnModal] = useState({ open: false, user: null });
  const [txnRows, setTxnRows] = useState([]);
  const [txnLoading, setTxnLoading] = useState(false);

  const [viewSubModal, setViewSubModal] = useState({ open: false, user: null });
  const [subStatus, setSubStatus] = useState(null);
  const [subLoading, setSubLoading] = useState(false);

  const openEditProfile = (u) => {
    setEditForm({
      name: u.name || '', email: u.email || '', phone: u.phone || '',
      company_name: u.company_name || '', province: u.province || '',
    });
    setEditProfileModal({ open: true, user: u });
  };

  const submitEditProfile = async () => {
    if (!editProfileModal.user) return;
    setEditBusy(true);
    try {
      await axios.patch(
        `${API}/admin/users/${editProfileModal.user.id}/profile`,
        editForm,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success('Profile updated');
      setEditProfileModal({ open: false, user: null });
      fetchData();
    } catch (e) {
      toast.error(extractErrorMessage(e) || extractErrorMessage(e)?.message || 'Update failed');
    } finally {
      setEditBusy(false);
    }
  };

  const handleResetPassword = async (u) => {
    if (!window.confirm(`Send password reset email to ${u.email}?`)) return;
    try {
      await axios.post(
        `${API}/admin/users/${u.id}/reset-password`, {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(`Reset email sent to ${u.email}`);
    } catch (e) {
      toast.error('Reset failed');
    }
  };

  // iter344 — Admin impersonation: swap to a 1-hour user-scoped JWT.
  const handleImpersonate = async (u) => {
    if (!window.confirm(`Log in as ${u.email}? You will act as this user until you exit impersonation (max 1 hour).`)) return;
    try {
      const r = await axios.post(
        `${API}/admin/impersonate/${u.id}`, {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const impTok = r.data?.access_token;
      if (!impTok) throw new Error('no token');
      localStorage.setItem('bidvex_admin_backup_token', localStorage.getItem('token') || '');
      const rt = localStorage.getItem('refresh_token');
      if (rt) {
        localStorage.setItem('bidvex_admin_backup_refresh', rt);
        localStorage.removeItem('refresh_token');
      }
      localStorage.setItem('bidvex_impersonation', JSON.stringify({
        target_user_id: u.id,
        target_name: u.name,
        target_email: u.email,
        started_at: Date.now(),
      }));
      localStorage.setItem('token', impTok);
      window.location.href = '/';
    } catch (e) {
      toast.error(extractErrorMessage(e) || extractErrorMessage(e) || 'Impersonation failed');
    }
  };

  const openChangeTier = (u) => {
    setNewTier(u.buyer_tier || 'standard');
    setChangeTierModal({ open: true, user: u });
  };

  const submitChangeTier = async () => {
    if (!changeTierModal.user) return;
    setTierBusy(true);
    try {
      await axios.post(
        `${API}/admin/users/${changeTierModal.user.id}/change-tier`,
        { tier: newTier },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(`Tier set to ${newTier}`);
      setChangeTierModal({ open: false, user: null });
      fetchData();
    } catch (e) {
      toast.error('Tier change failed');
    } finally {
      setTierBusy(false);
    }
  };

  const handleConvertDemo = async (u) => {
    const action = u.is_demo_account ? 'remove the demo flag from' : 'convert to a demo account';
    if (!window.confirm(`${action} ${u.email}?`)) return;
    try {
      const r = await axios.post(
        `${API}/admin/users/${u.id}/convert-to-demo`, {},
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(r.data.is_demo_account ? 'User is now a Demo account' : 'Demo flag removed');
      fetchData();
    } catch (e) {
      toast.error('Update failed');
    }
  };

  const openViewTransactions = async (u) => {
    setViewTxnModal({ open: true, user: u });
    setTxnLoading(true);
    setTxnRows([]);
    try {
      const r = await axios.get(
        `${API}/admin/users/${u.id}/transactions?limit=50`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setTxnRows(r.data?.transactions || []);
    } catch (e) {
      toast.error('Failed to load transactions');
    } finally {
      setTxnLoading(false);
    }
  };

  const openViewSubscription = async (u) => {
    setViewSubModal({ open: true, user: u });
    setSubLoading(true);
    setSubStatus(null);
    try {
      const r = await axios.get(
        `${API}/admin/users/${u.id}/subscription-status`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setSubStatus(r.data);
    } catch (e) {
      toast.error('Failed to load subscription status');
    } finally {
      setSubLoading(false);
    }
  };
  const [deleting, setDeleting] = useState(false);

  const handleDeleteUser = async () => {
    const targetUser = deleteUserModal.user;
    if (!targetUser) return;
    setDeleting(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await axios.delete(`${API}/admin/users/${targetUser.id}`, { headers });
      const deleted = res.data.deleted || {};
      const summary = Object.entries(deleted).map(([k, v]) => `${k}: ${v}`).join(', ');
      toast.success(`User deleted. Cascade: ${summary}`);
      setDeleteUserModal({ open: false, user: null });
      fetchData();
    } catch (error) {
      toast.error(extractErrorMessage(error) || 'Failed to delete user');
    } finally {
      setDeleting(false);
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
          variant={filter === 'individual' ? 'default' : 'outline'} 
          onClick={() => setFilter('individual')} 
          className={`${filter === 'individual' ? 'gradient-button text-white border-0' : ''} text-xs sm:text-sm`}
          data-testid="filter-individual"
        >
          Individual
        </Button>
        <Button 
          size="sm"
          variant={filter === 'partner' ? 'default' : 'outline'} 
          onClick={() => setFilter('partner')} 
          className={`${filter === 'partner' ? 'gradient-button text-white border-0' : ''} text-xs sm:text-sm`}
          data-testid="filter-partner"
        >
          Partner
        </Button>
        <Button 
          size="sm"
          variant={filter === 'vehicle_dealer' ? 'default' : 'outline'} 
          onClick={() => setFilter('vehicle_dealer')} 
          className={`${filter === 'vehicle_dealer' ? 'gradient-button text-white border-0' : ''} text-xs sm:text-sm`}
          data-testid="filter-vehicle-dealer"
        >
          Vehicle Dealer
        </Button>
        <Button 
          size="sm"
          variant={filter === 'storage_facility' ? 'default' : 'outline'} 
          onClick={() => setFilter('storage_facility')} 
          className={`${filter === 'storage_facility' ? 'gradient-button text-white border-0' : ''} text-xs sm:text-sm`}
          data-testid="filter-storage-facility"
        >
          Storage Facility
        </Button>
        <Button 
          size="sm"
          variant={filter === 'demo' ? 'default' : 'outline'} 
          onClick={() => setFilter('demo')} 
          className={`${filter === 'demo' ? 'gradient-button text-white border-0' : ''} text-xs sm:text-sm`}
          data-testid="filter-demo"
        >
          Demo
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
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <CardTitle className="text-base sm:text-lg">
              Users ({filteredUsers.length}{searchQuery && ` of ${users.length}`})
            </CardTitle>
            {/* Sortable column bar */}
            <div className="flex flex-wrap items-center gap-1 text-xs" data-testid="user-sort-bar">
              <span className="text-muted-foreground mr-1">Sort:</span>
              {[
                { key: 'name', label: 'Name' },
                { key: 'email', label: 'Email' },
                { key: 'phone', label: 'Phone' },
                { key: 'city', label: 'City' },
                { key: 'role', label: 'Role' },
                { key: 'created_at', label: 'Created' },
              ].map(col => {
                const active = sortBy === col.key;
                return (
                  <button
                    key={col.key}
                    type="button"
                    onClick={() => toggleSort(col.key)}
                    className={`px-2 py-1 rounded border transition-colors ${
                      active
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-card text-muted-foreground border-border hover:bg-accent'
                    }`}
                    data-testid={`sort-by-${col.key}`}
                    aria-pressed={active}
                  >
                    {col.label}{active && (sortDir === 'asc' ? ' ▲' : ' ▼')}
                  </button>
                );
              })}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-3 sm:p-6 pt-0">
          <div className="space-y-3">
            {filteredUsers.map((user, userIdx) => (
              <div 
                key={user.id || user.email || `user-${userIdx}`} 
                className="flex flex-col gap-3 p-3 sm:p-4 border rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                data-testid={`user-row-${user.id}`}
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
                  {/* Phone + City — new iteration 168 fields */}
                  <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1" data-testid={`user-phone-${user.id}`}>
                      <Phone className="h-3 w-3" />
                      {user.phone ? (
                        <a href={`tel:${user.phone}`} className="hover:underline">{user.phone}</a>
                      ) : (
                        <span className="italic opacity-60">no phone</span>
                      )}
                    </span>
                    <span className="flex items-center gap-1" data-testid={`user-city-${user.id}`}>
                      <MapPin className="h-3 w-3" />
                      {user.city || <span className="italic opacity-60">no city</span>}
                      {user.province && <span className="text-[10px] ml-1 opacity-70">({user.province})</span>}
                    </span>
                  </div>
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
                    {/* iter217 Phase 3 — Documents Overdue indicator */}
                    {user.document_request_overdue && (
                      <Badge
                        className="text-xs gap-1"
                        style={{ background: '#dc2626', color: 'white' }}
                        data-testid="documents-overdue-badge"
                        title={user.document_request_deadline}
                      >
                        ⚠️ Documents Overdue
                      </Badge>
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
                  {/* iter300 P1 — bidding suspension (overdue-payment escalation) */}
                  <Button
                    size="sm"
                    variant={user.bidding_suspended ? 'destructive' : 'outline'}
                    onClick={() => handleBiddingSuspension(user.id, user.bidding_suspended)}
                    title={user.bidding_suspended ? 'Lift bidding suspension' : 'Suspend bidding privileges'}
                    data-testid={`bidding-suspension-${user.id}`}
                    className="text-xs sm:text-sm"
                  >
                    <Gavel className="h-3.5 w-3.5 mr-1" />
                    {user.bidding_suspended ? 'Bid Locked' : 'Bidding'}
                  </Button>
                  <Button 
                    size="sm" 
                    variant={user.status === 'suspended' ? 'destructive' : 'outline'} 
                    onClick={() => handleSuspendAccount(user.id, user.status)}
                    title={user.status === 'suspended' ? 'Reactivate account' : 'Suspend account'}
                    data-testid={`suspend-user-${user.id}`}
                  >
                    <Ban className="h-3.5 w-3.5 mr-1" />
                    {user.status === 'suspended' ? 'Suspended' : 'Suspend'}
                  </Button>
                  {/* iter214 P2 — Send Notification + Request Documents */}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setNotifyModal({ open: true, user })}
                    title="Send notification (email + in-app)"
                    data-testid={`notify-user-${user.id}`}
                  >
                    <Mail className="h-3.5 w-3.5 mr-1" />
                    Notify
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => setReqPayModal({ open: true, user })}
                    disabled={!user.id}
                    title={user.id ? 'Request payment from this user' : 'Contact-only record — no account ID. Request Payment is unavailable.'}
                    data-testid={`request-payment-user-${user.id || user.email}`}
                    style={{
                      backgroundColor: user.id ? '#0055FF' : '#9aa6b3',
                      color: 'white',
                      fontWeight: 700,
                      borderRadius: 6,
                      padding: '6px 14px',
                      fontSize: 12,
                      cursor: user.id ? 'pointer' : 'not-allowed',
                    }}
                    className="hover:opacity-90 transition-opacity"
                  >
                    <CreditCard className="h-3.5 w-3.5 mr-1" />
                    Request Payment
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setDocReqModal({ open: true, user })}
                    title="Request documents"
                    data-testid={`request-docs-user-${user.id}`}
                  >
                    <AlertTriangle className="h-3.5 w-3.5 mr-1" />
                    Request Docs
                  </Button>
                  <Button 
                    size="sm" 
                    variant="destructive"
                    onClick={() => setDeleteUserModal({ open: true, user })}
                    title="Permanently delete user and all related data"
                    data-testid={`delete-user-${user.id}`}
                  >
                    <Trash2 className="h-3.5 w-3.5 mr-1" />
                    Delete
                  </Button>
                  {/* iter215 — More-Actions dropdown (Edit / Reset Password / Tier / Demo / Txns / Subscription) */}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button size="sm" variant="outline" data-testid={`more-actions-${user.id}`} title="More actions">
                        <MoreVertical className="h-3.5 w-3.5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-56">
                      <DropdownMenuLabel className="text-xs">User actions</DropdownMenuLabel>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => openEditProfile(user)} data-testid={`edit-profile-${user.id}`}>
                        <Edit className="h-3.5 w-3.5 mr-2" /> Edit Profile
                      </DropdownMenuItem>
                      {/* iter344 — impersonation (never offered for admin accounts) */}
                      {!(user.role === 'admin' || user.role === 'super_admin' || user.is_admin) && (
                        <DropdownMenuItem
                          onClick={() => handleImpersonate(user)}
                          className="text-red-600 focus:text-red-700"
                          data-testid={`impersonate-user-${user.id}`}
                        >
                          <LogIn className="h-3.5 w-3.5 mr-2" /> Login As User
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuItem onClick={() => handleResetPassword(user)} data-testid={`reset-password-${user.id}`}>
                        <Key className="h-3.5 w-3.5 mr-2" /> Reset Password
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => openChangeTier(user)} data-testid={`change-tier-${user.id}`}>
                        <Crown className="h-3.5 w-3.5 mr-2" /> Change Tier
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => handleConvertDemo(user)} data-testid={`convert-demo-${user.id}`}>
                        <Theater className="h-3.5 w-3.5 mr-2" />
                        {user.is_demo_account ? 'Remove Demo Flag' : 'Convert to Demo'}
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => openViewTransactions(user)} data-testid={`view-txns-${user.id}`}>
                        <Receipt className="h-3.5 w-3.5 mr-2" /> View Transactions
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => openViewSubscription(user)} data-testid={`view-sub-${user.id}`}>
                        <CreditCard className="h-3.5 w-3.5 mr-2" /> View Subscription Status
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => openPaymentHistory(user)} data-testid={`view-payment-requests-${user.id}`}>
                        <Receipt className="h-3.5 w-3.5 mr-2" /> Payment Requests
                      </DropdownMenuItem>
                      {/* iter301 — reviews received as a buyer (seller→buyer) */}
                      <DropdownMenuItem onClick={() => openBuyerReviews(user)} data-testid={`view-buyer-reviews-${user.id}`}>
                        <Star className="h-3.5 w-3.5 mr-2" /> Buyer Reviews
                      </DropdownMenuItem>
                      {/* iter316-C — Contractor role management (iter316-E: hide for admins) */}
                      <DropdownMenuSeparator />
                      {user.role === 'dialer_contractor' ? (
                        <>
                          <DropdownMenuItem
                            onClick={() => navigate(`/admin/contractors/${user.id}`)}
                            data-testid={`view-contractor-profile-${user.id}`}
                          >
                            <Eye className="h-3.5 w-3.5 mr-2" /> View Contractor Profile
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => handleDemoteFromContractor(user)}
                            className="text-rose-600 focus:text-rose-700"
                            data-testid={`demote-contractor-${user.id}`}
                          >
                            <Trash2 className="h-3.5 w-3.5 mr-2" /> Demote from Contractor
                          </DropdownMenuItem>
                        </>
                      ) : (user.role === 'admin' || user.role === 'super_admin' || user.is_admin) ? (
                        // iter316-E SAFEGUARD: never offer "Promote to Contractor"
                        // for an admin user; mistakes here lock the admin out of
                        // the panel.
                        null
                      ) : (
                        <DropdownMenuItem
                          onClick={() => handlePromoteToContractor(user)}
                          data-testid={`promote-contractor-${user.id}`}
                        >
                          <Headphones className="h-3.5 w-3.5 mr-2" /> Promote to Contractor
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
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

      {/* iter301 — Buyer Reviews Modal (admin view) */}
      <Dialog open={buyerReviewsModal.open} onOpenChange={(o) => !o && setBuyerReviewsModal({ open: false, user: null, data: null, loading: false })}>
        <DialogContent className="sm:max-w-[560px] max-h-[80vh] overflow-y-auto" data-testid="buyer-reviews-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Star className="h-5 w-5 text-amber-500" /> Buyer Reviews
            </DialogTitle>
            <DialogDescription>
              Reviews <strong>{buyerReviewsModal.user?.name}</strong> received as a buyer (from sellers).
              {buyerReviewsModal.data?.average_rating != null && (
                <span className="ml-2 font-semibold text-amber-600">★ {buyerReviewsModal.data.average_rating}/5</span>
              )}
            </DialogDescription>
          </DialogHeader>
          {buyerReviewsModal.loading ? (
            <div className="py-8 text-center text-muted-foreground">Loading…</div>
          ) : (buyerReviewsModal.data?.reviews || []).length === 0 ? (
            <div className="py-8 text-center text-muted-foreground" data-testid="buyer-reviews-empty">
              No buyer reviews yet
            </div>
          ) : (
            <div className="space-y-3">
              {buyerReviewsModal.data.reviews.map((r) => (
                <div key={r.id} className={`p-3 border rounded-lg ${r.status !== 'active' ? 'opacity-50' : ''}`}
                  data-testid={`buyer-review-${r.id}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1">
                      {[1, 2, 3, 4, 5].map((s) => (
                        <Star key={s} className={`h-4 w-4 ${s <= r.rating ? 'fill-amber-400 text-amber-400' : 'text-slate-300'}`} />
                      ))}
                      {r.status !== 'active' && <Badge variant="outline" className="ml-2 text-xs">Removed</Badge>}
                    </div>
                    {r.status === 'active' && (
                      <Button size="sm" variant="ghost" className="text-red-600 hover:text-red-700 h-7 px-2"
                        onClick={() => softDeleteReview(r.id)} data-testid={`delete-review-${r.id}`}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                  {r.comment && <p className="text-sm mt-1">{r.comment}</p>}
                  <p className="text-xs text-muted-foreground mt-1">
                    By {r.reviewer_display_name || r.reviewer_id?.slice(0, 8)} · {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}
                  </p>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete User Confirmation Modal */}
      {deleteUserModal.open && deleteUserModal.user && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg border-2 border-red-600" data-testid="delete-user-modal">
            <CardHeader className="bg-red-50 dark:bg-red-900/20">
              <CardTitle className="text-red-600 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Permanently Delete User
              </CardTitle>
              <CardDescription className="text-red-500/80">
                This will cascade-delete ALL related data. This cannot be undone.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5 space-y-4">
              <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                <p className="font-semibold text-slate-900 dark:text-slate-100">{deleteUserModal.user.name}</p>
                <p className="text-sm text-muted-foreground">{deleteUserModal.user.email}</p>
                <p className="text-xs text-muted-foreground mt-1">ID: {deleteUserModal.user.id}</p>
              </div>
              <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800 text-sm text-amber-800 dark:text-amber-300">
                <p className="font-medium mb-1">The following will also be deleted:</p>
                <ul className="list-disc list-inside text-xs space-y-0.5">
                  <li>All listings & multi-item listings</li>
                  <li>All bids placed by this user</li>
                  <li>All messages (sent & received)</li>
                  <li>All notifications & watchlist items</li>
                  <li>All payment methods & escrow entries</li>
                  <li>All community questions & replies</li>
                </ul>
              </div>
              <div className="flex gap-2 justify-end pt-2 border-t">
                <Button variant="outline" onClick={() => setDeleteUserModal({ open: false, user: null })} data-testid="cancel-delete-user">
                  Cancel
                </Button>
                <Button variant="destructive" onClick={handleDeleteUser} disabled={deleting} data-testid="confirm-delete-user">
                  {deleting ? (
                    <><div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2" />Deleting...</>
                  ) : (
                    <><Trash2 className="h-4 w-4 mr-2" />Delete User & All Data</>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* iter215 — Edit Profile Modal */}
      <Dialog open={editProfileModal.open} onOpenChange={(o) => !o && setEditProfileModal({ open: false, user: null })}>
        <DialogContent data-testid="edit-profile-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Edit className="h-5 w-5 text-blue-600" /> Edit User Profile
            </DialogTitle>
            <DialogDescription>
              {editProfileModal.user && (<span>ID: <strong className="font-mono">{editProfileModal.user.id?.slice(0, 12)}</strong></span>)}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {['name', 'email', 'phone', 'company_name', 'province'].map((field) => (
              <div key={field}>
                <Label className="capitalize">{field.replace('_', ' ')}</Label>
                <Input
                  value={editForm[field] || ''}
                  onChange={(e) => setEditForm((p) => ({ ...p, [field]: e.target.value }))}
                  data-testid={`edit-field-${field}`}
                />
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditProfileModal({ open: false, user: null })}>Cancel</Button>
            <Button onClick={submitEditProfile} disabled={editBusy} data-testid="edit-profile-submit">
              {editBusy ? 'Saving…' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* iter215 — Change Buyer Tier Modal */}
      <Dialog open={changeTierModal.open} onOpenChange={(o) => !o && setChangeTierModal({ open: false, user: null })}>
        <DialogContent data-testid="change-tier-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Crown className="h-5 w-5 text-amber-600" /> Change Buyer Tier
            </DialogTitle>
            <DialogDescription>
              {changeTierModal.user && (<span>For <strong>{changeTierModal.user.email}</strong></span>)}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label>New tier</Label>
            <Select value={newTier} onValueChange={setNewTier}>
              <SelectTrigger data-testid="new-tier-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="standard">Standard</SelectItem>
                <SelectItem value="premium">Premium</SelectItem>
                <SelectItem value="vip_elite">VIP Elite</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Current: <strong>{changeTierModal.user?.buyer_tier || 'standard'}</strong>
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setChangeTierModal({ open: false, user: null })}>Cancel</Button>
            <Button onClick={submitChangeTier} disabled={tierBusy} data-testid="change-tier-submit">
              {tierBusy ? 'Updating…' : 'Apply'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* iter215 — View Transactions Modal */}
      <Dialog open={viewTxnModal.open} onOpenChange={(o) => !o && setViewTxnModal({ open: false, user: null })}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-auto" data-testid="view-txn-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Receipt className="h-5 w-5 text-emerald-600" /> Transactions
            </DialogTitle>
            <DialogDescription>
              {viewTxnModal.user && (<span>For <strong>{viewTxnModal.user.email}</strong></span>)}
            </DialogDescription>
          </DialogHeader>
          {txnLoading ? (
            <p className="text-sm text-muted-foreground py-6 text-center">Loading…</p>
          ) : txnRows.length === 0 ? (
            <p className="text-sm text-muted-foreground py-6 text-center">No transactions</p>
          ) : (
            <table className="w-full text-xs" data-testid="txn-table">
              <thead className="text-[10px] uppercase text-muted-foreground border-b">
                <tr>
                  <th className="text-left p-1">ID</th>
                  <th className="text-left p-1">Listing</th>
                  <th className="text-left p-1">Side</th>
                  <th className="text-right p-1">Amount</th>
                  <th className="text-left p-1">Method</th>
                  <th className="text-left p-1">Date</th>
                </tr>
              </thead>
              <tbody>
                {txnRows.map((t, idx) => (
                  <tr key={t.id || `txn-${idx}`} className="border-b">
                    <td className="p-1 font-mono">{(t.id || '').slice(0, 8)}</td>
                    <td className="p-1 truncate max-w-[180px]">{t.listing_title || t.listing_id}</td>
                    <td className="p-1">{viewTxnModal.user?.id === t.buyer_id ? 'Buyer' : 'Seller'}</td>
                    <td className="p-1 text-right">CA${(t.hammer_price || t.amount || 0).toLocaleString()}</td>
                    <td className="p-1">{t.payment_method || '—'}</td>
                    <td className="p-1">{(t.created_at || '').slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </DialogContent>
      </Dialog>

      {/* iter215 — View Subscription Status Modal */}
      <Dialog open={viewSubModal.open} onOpenChange={(o) => !o && setViewSubModal({ open: false, user: null })}>
        <DialogContent data-testid="view-sub-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CreditCard className="h-5 w-5 text-violet-600" /> Subscription Status
            </DialogTitle>
            <DialogDescription>
              {viewSubModal.user && (<span>For <strong>{viewSubModal.user.email}</strong></span>)}
            </DialogDescription>
          </DialogHeader>
          {subLoading ? (
            <p className="text-sm text-muted-foreground py-6 text-center">Loading…</p>
          ) : !subStatus ? (
            <p className="text-sm text-muted-foreground py-6 text-center">No subscription data</p>
          ) : (
            <div className="space-y-3 text-sm">
              {subStatus.is_vehicle_dealer && (
                <div className="rounded-md border border-slate-200 dark:border-slate-700 p-3">
                  <h4 className="font-semibold mb-1.5">🚗 Vehicle Dealer</h4>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>Status: <strong>{subStatus.dealer_subscription_status || (subStatus.dealer_subscription_active ? 'active' : 'unpaid')}</strong></div>
                    <div>Active: <strong>{subStatus.dealer_subscription_active ? 'Yes ✓' : 'No ✗'}</strong></div>
                    <div>Start: {subStatus.dealer_subscription_start?.slice(0, 10) || '—'}</div>
                    <div>Renews: {subStatus.dealer_subscription_renewal?.slice(0, 10) || '—'}</div>
                    <div>Method: {subStatus.dealer_subscription_manual_method || 'auto'}</div>
                    <div>Ref: {subStatus.dealer_subscription_manual_reference || '—'}</div>
                    <div>Suspended: <strong>{subStatus.vehicle_dealer_suspended ? 'Yes' : 'No'}</strong></div>
                  </div>
                </div>
              )}
              {subStatus.is_licensed_partner && (
                <div className="rounded-md border border-slate-200 dark:border-slate-700 p-3">
                  <h4 className="font-semibold mb-1.5">🏅 Partner</h4>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>Status: <strong>{subStatus.partner_subscription_status || (subStatus.partner_subscription_active ? 'active' : 'unpaid')}</strong></div>
                    <div>Active: <strong>{subStatus.partner_subscription_active ? 'Yes ✓' : 'No ✗'}</strong></div>
                    <div>Start: {subStatus.partner_subscription_start?.slice(0, 10) || '—'}</div>
                    <div>Renews: {subStatus.partner_subscription_renewal?.slice(0, 10) || '—'}</div>
                  </div>
                </div>
              )}
              {subStatus.is_storage_facility && (
                <div className="rounded-md border border-slate-200 dark:border-slate-700 p-3">
                  <h4 className="font-semibold mb-1.5">📦 Storage Facility</h4>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>Status: <strong>{subStatus.storage_subscription_status || 'free tier'}</strong></div>
                    <div>Active: <strong>{subStatus.storage_subscription_active ? 'Yes ✓' : 'N/A'}</strong></div>
                    <div>Renews: {subStatus.storage_subscription_renewal?.slice(0, 10) || '—'}</div>
                  </div>
                </div>
              )}
              <div className="rounded-md border border-slate-200 dark:border-slate-700 p-3">
                <h4 className="font-semibold mb-1.5">👑 Buyer Tier</h4>
                <p className="text-xs">{subStatus.buyer_tier || 'standard'}</p>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* iter214 P2 — Send Notification Dialog */}
      <Dialog open={notifyModal.open} onOpenChange={(o) => !o && setNotifyModal({ open: false, user: null })}>
        <DialogContent data-testid="notify-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5 text-blue-600" /> Send Notification
            </DialogTitle>
            <DialogDescription>
              {notifyModal.user && (<span>To: <strong>{notifyModal.user.email}</strong></span>)}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Notification type</Label>
              <Select
                value={notifyForm.notification_type}
                onValueChange={(v) => setNotifyForm((p) => ({ ...p, notification_type: v }))}
              >
                <SelectTrigger data-testid="notify-type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="upload_required">📁 Upload Required</SelectItem>
                  <SelectItem value="invoice">📄 Invoice / Statement</SelectItem>
                  <SelectItem value="warning">⚠️ Account Warning</SelectItem>
                  <SelectItem value="approval">✅ Approval Confirmation</SelectItem>
                  <SelectItem value="rejection">❌ Rejection Notice</SelectItem>
                  <SelectItem value="general">📢 General Message</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Subject *</Label>
              <Input
                value={notifyForm.subject}
                onChange={(e) => setNotifyForm((p) => ({ ...p, subject: e.target.value }))}
                data-testid="notify-subject"
              />
            </div>
            <div>
              <Label>Body (English) *</Label>
              <textarea
                rows={4} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={notifyForm.body_en}
                onChange={(e) => setNotifyForm((p) => ({ ...p, body_en: e.target.value }))}
                data-testid="notify-body-en"
              />
            </div>
            <div>
              <Label>Body (French) <span className="text-xs text-muted-foreground">(optional — auto-falls-back to EN)</span></Label>
              <textarea
                rows={4} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={notifyForm.body_fr}
                onChange={(e) => setNotifyForm((p) => ({ ...p, body_fr: e.target.value }))}
                data-testid="notify-body-fr"
              />
            </div>
            <div>
              <Label>Send via</Label>
              <Select
                value={notifyForm.send_via}
                onValueChange={(v) => setNotifyForm((p) => ({ ...p, send_via: v }))}
              >
                <SelectTrigger data-testid="notify-channel"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="email">Email only</SelectItem>
                  <SelectItem value="in_app">In-app only</SelectItem>
                  <SelectItem value="both">Both</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* iter266 Mission 3D — Attachment request toggle. */}
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 space-y-2" data-testid="notify-attachment-block">
              <label className="flex items-center gap-2 text-sm font-semibold text-amber-900 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!!notifyForm.requires_attachment}
                  onChange={(e) => setNotifyForm((p) => ({ ...p, requires_attachment: e.target.checked }))}
                  data-testid="notify-requires-attachment"
                />
                📎 Request an attachment from the user
              </label>
              {notifyForm.requires_attachment && (
                <div className="space-y-2 mt-2">
                  <div>
                    <Label className="text-xs">Attachment label (EN)</Label>
                    <Input
                      placeholder='e.g. "Please upload your NEQ certificate"'
                      value={notifyForm.attachment_request_label || ''}
                      onChange={(e) => setNotifyForm((p) => ({ ...p, attachment_request_label: e.target.value }))}
                      data-testid="notify-attachment-label-en"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Attachment label (FR)</Label>
                    <Input
                      placeholder='ex. "Veuillez téléverser votre certificat NEQ"'
                      value={notifyForm.attachment_request_label_fr || ''}
                      onChange={(e) => setNotifyForm((p) => ({ ...p, attachment_request_label_fr: e.target.value }))}
                      data-testid="notify-attachment-label-fr"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <Label className="text-xs">Accepted types</Label>
                      <Input
                        placeholder="PDF, JPG, PNG"
                        value={notifyForm.attachment_types || 'PDF, JPG, PNG'}
                        onChange={(e) => setNotifyForm((p) => ({ ...p, attachment_types: e.target.value }))}
                        data-testid="notify-attachment-types"
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Max size (MB)</Label>
                      <Input
                        type="number"
                        min="0.1"
                        max="25"
                        step="0.1"
                        value={notifyForm.attachment_max_mb || 1.0}
                        onChange={(e) => setNotifyForm((p) => ({ ...p, attachment_max_mb: parseFloat(e.target.value) || 1.0 }))}
                        data-testid="notify-attachment-max-mb"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNotifyModal({ open: false, user: null })}>Cancel</Button>
            <Button onClick={submitNotify} disabled={notifyBusy} data-testid="notify-submit">
              {notifyBusy ? 'Sending…' : 'Send'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* iter258 Mission 1 — Request Payment Dialog */}
      <Dialog open={reqPayModal.open} onOpenChange={(o) => !o && setReqPayModal({ open: false, user: null })}>
        <DialogContent data-testid="request-payment-modal" className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CreditCard className="h-5 w-5 text-[#0055FF]" />
              💳 Request Payment from {reqPayModal.user?.name || reqPayModal.user?.email}
            </DialogTitle>
            <DialogDescription>
              Generate a Stripe Payment Link and send it to the user.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
            <div>
              <Label className="text-xs">Subtotal Amount (CAD) *</Label>
              <Input
                type="number" step="0.01" min="0.01" placeholder="0.00"
                value={reqPayForm.subtotal}
                onChange={(e) => setReqPayForm({ ...reqPayForm, subtotal: e.target.value })}
                data-testid="request-payment-subtotal"
              />
            </div>
            <div>
              <Label className="text-xs">Tax Type *</Label>
              <div className="grid grid-cols-1 gap-1 mt-1 text-sm">
                {[
                  { v: 'none',    l: 'No Tax (0%)' },
                  { v: 'gst',     l: 'GST only (5%)' },
                  { v: 'qst',     l: 'QST only (9.975%)' },
                  { v: 'gst_qst', l: 'GST + QST (14.975%)' },
                  { v: 'hst_on',  l: 'HST — Ontario (13%)' },
                  { v: 'custom',  l: 'Custom Tax %' },
                ].map((opt) => (
                  <label key={opt.v} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      checked={reqPayForm.tax_type === opt.v}
                      onChange={() => setReqPayForm({ ...reqPayForm, tax_type: opt.v })}
                      data-testid={`request-payment-tax-${opt.v}`}
                    />
                    <span>{opt.l}</span>
                  </label>
                ))}
              </div>
              {reqPayForm.tax_type === 'custom' && (
                <Input
                  type="number" step="0.001" min="0" placeholder="e.g. 7.5"
                  className="mt-2"
                  value={reqPayForm.custom_tax_rate}
                  onChange={(e) => setReqPayForm({ ...reqPayForm, custom_tax_rate: e.target.value })}
                  data-testid="request-payment-custom-rate"
                />
              )}
            </div>
            <div className="rounded-md bg-slate-50 border border-slate-200 p-2 text-sm font-bold flex items-center justify-between">
              <span className="text-slate-600 font-medium">Calculated Total:</span>
              <span className="text-lg text-[#0055FF]" data-testid="request-payment-calculated-total">
                ${reqPayCalcTotal().toFixed(2)} CAD
              </span>
            </div>
            <div>
              <Label className="text-xs">Payment Reason / Description *</Label>
              <Input
                value={reqPayForm.description}
                onChange={(e) => setReqPayForm({ ...reqPayForm, description: e.target.value })}
                placeholder='e.g. "Outstanding balance for lot #4821"'
                data-testid="request-payment-description"
              />
            </div>
            <div>
              <Label className="text-xs">Internal Notes (admin only)</Label>
              <Input
                value={reqPayForm.internal_notes}
                onChange={(e) => setReqPayForm({ ...reqPayForm, internal_notes: e.target.value })}
                placeholder="Not visible to the user"
                data-testid="request-payment-notes"
              />
            </div>
            <div>
              <Label className="text-xs">Delivery Method</Label>
              <div className="flex flex-col gap-1 mt-1 text-sm">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={reqPayForm.send_email}
                    onChange={(e) => setReqPayForm({ ...reqPayForm, send_email: e.target.checked })}
                    data-testid="request-payment-send-email"
                  />
                  <span>Send by Email</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={reqPayForm.send_notification}
                    onChange={(e) => setReqPayForm({ ...reqPayForm, send_notification: e.target.checked })}
                    data-testid="request-payment-send-notif"
                  />
                  <span>Send Platform Notification</span>
                </label>
              </div>
            </div>
            <div>
              <Label className="text-xs">Payment Link Expiry</Label>
              <div className="flex flex-wrap gap-3 mt-1 text-sm">
                {[
                  { v: 24,     l: '24 hours' },
                  { v: 48,     l: '48 hours' },
                  { v: 168,    l: '7 days' },
                  { v: 'none', l: 'No expiry' },
                ].map((opt) => (
                  <label key={String(opt.v)} className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      checked={String(reqPayForm.expiry_hours) === String(opt.v)}
                      onChange={() => setReqPayForm({ ...reqPayForm, expiry_hours: opt.v })}
                      data-testid={`request-payment-expiry-${opt.v}`}
                    />
                    <span>{opt.l}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setReqPayModal({ open: false, user: null })}
              data-testid="request-payment-cancel"
            >
              Cancel
            </Button>
            <Button
              onClick={submitRequestPayment}
              disabled={reqPayBusy}
              style={{ backgroundColor: '#0055FF', color: 'white' }}
              data-testid="request-payment-submit"
            >
              {reqPayBusy ? 'Sending…' : 'Send Payment Request →'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* iter258 Mission 1 — Payment Requests history drawer (per-user). */}
      {/* iter262 Mission 3 — Colored status badges + Re-issue action +
          New Request CTA in header (opens the existing modal pre-filled). */}
      <Dialog open={!!reqPayHistoryUser} onOpenChange={(o) => !o && setReqPayHistoryUser(null)}>
        <DialogContent data-testid="payment-requests-history-modal" className="max-w-3xl">
          <DialogHeader>
            <div className="flex items-center justify-between gap-3">
              <DialogTitle className="flex items-center gap-2">
                <Receipt className="h-5 w-5 text-[#0055FF]" />
                💳 Payment Requests — {reqPayHistoryUser?.name || reqPayHistoryUser?.email}
              </DialogTitle>
              <Button
                size="sm"
                style={{ backgroundColor: '#0055FF', color: 'white' }}
                onClick={() => {
                  const u = reqPayHistoryUser;
                  setReqPayHistoryUser(null);
                  setReqPayModal({ open: true, user: u });
                }}
                data-testid="payment-history-new-request-btn"
                disabled={!reqPayHistoryUser?.id}
                title={reqPayHistoryUser?.id ? 'New payment request' : 'Contact-only record — unavailable'}
              >
                + New Request
              </Button>
            </div>
          </DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto">
            {reqPayHistory.length === 0 ? (
              <p className="text-sm text-slate-500 text-center py-6" data-testid="payment-requests-history-empty">
                No payment requests sent to this user yet.
              </p>
            ) : (
              <table className="w-full text-sm" data-testid="payment-requests-history-table">
                <thead>
                  <tr className="border-b border-slate-200 text-xs text-slate-500 uppercase">
                    <th className="text-left py-2">Date</th>
                    <th className="text-right">Amount</th>
                    <th className="text-left px-2">Description</th>
                    <th className="text-center">Status</th>
                    <th className="text-right pr-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {reqPayHistory.map((pr, idx) => {
                    const desc = (pr.description || '');
                    const shortDesc = desc.length > 40 ? `${desc.slice(0, 40)}…` : desc;
                    const badgeStyle = pr.status === 'paid' ? {
                      backgroundColor: '#f0fff4', color: '#276749',
                      border: '1px solid #c6f6d5', borderRadius: 4,
                      padding: '2px 8px', fontWeight: 700, fontSize: 11,
                    } : pr.status === 'expired' ? {
                      backgroundColor: '#f7fafc', color: '#718096',
                      border: '1px solid #e2e8f0', borderRadius: 4,
                      padding: '2px 8px', fontWeight: 700, fontSize: 11,
                    } : {
                      backgroundColor: '#fff0f0', color: '#e53e3e',
                      border: '1px solid #fed7d7', borderRadius: 4,
                      padding: '2px 8px', fontWeight: 700, fontSize: 11,
                    };
                    return (
                      <tr key={pr.id || `req-${idx}`} className="border-b border-slate-100" data-testid={`payment-request-row-${pr.id}`}>
                        <td className="py-2 text-xs">{(pr.created_at || '').slice(0, 10)}</td>
                        <td className="text-right font-mono font-bold" data-testid={`payment-request-amount-${pr.id}`}>
                          ${Number(pr.total_amount).toFixed(2)}
                        </td>
                        <td className="px-2 truncate max-w-[220px]" title={desc}>{shortDesc}</td>
                        <td className="text-center">
                          <span style={badgeStyle} data-testid={`payment-request-status-${pr.id}`}>
                            {pr.status === 'paid' && '✅ '}
                            {String(pr.status || 'pending').toUpperCase()}
                          </span>
                        </td>
                        <td className="text-right pr-2 space-x-1">
                          <Button
                            size="icon" variant="ghost"
                            onClick={async () => {
                              try {
                                await navigator.clipboard.writeText(pr.payment_url || pr.stripe_payment_link || '');
                                toast.success('Link copied');
                              } catch { /* noop */ }
                            }}
                            title="Copy payment link"
                            data-testid={`copy-payment-link-${pr.id}`}
                          >
                            <Copy className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            size="icon" variant="ghost"
                            onClick={() => {
                              // Re-issue: open modal pre-filled with same amount + description.
                              const u = reqPayHistoryUser;
                              setReqPayForm({
                                ...reqPayForm,
                                subtotal: String(pr.subtotal || pr.total_amount || ''),
                                tax_type: pr.tax_type || 'none',
                                custom_tax_rate: pr.tax_type === 'custom' ? String(pr.tax_rate || '') : '',
                                description: pr.description || '',
                              });
                              setReqPayHistoryUser(null);
                              setReqPayModal({ open: true, user: u });
                            }}
                            title="Re-issue with same amount"
                            data-testid={`reissue-payment-request-${pr.id}`}
                          >
                            <Receipt className="h-3.5 w-3.5" />
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* iter214 P2 — Request Documents Dialog */}
      <Dialog open={docReqModal.open} onOpenChange={(o) => !o && setDocReqModal({ open: false, user: null })}>
        <DialogContent data-testid="doc-req-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-600" /> Request Documents
            </DialogTitle>
            <DialogDescription>
              {docReqModal.user && (<span>From: <strong>{docReqModal.user.email}</strong></span>)}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Document type(s)</Label>
              <div className="space-y-2 mt-1">
                {DOC_TYPES.map((d) => (
                  <label key={d.v} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={docReqForm.document_types.includes(d.v)}
                      onChange={() => toggleDocType(d.v)}
                      data-testid={`doc-type-${d.v}`}
                    />
                    <span>{d.l}</span>
                  </label>
                ))}
              </div>
            </div>
            <div>
              <Label>Deadline *</Label>
              <Input
                type="date"
                value={docReqForm.deadline}
                onChange={(e) => setDocReqForm((p) => ({ ...p, deadline: e.target.value }))}
                data-testid="doc-deadline"
              />
            </div>
            <div>
              <Label>Custom message (optional)</Label>
              <textarea
                rows={3} className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={docReqForm.message}
                onChange={(e) => setDocReqForm((p) => ({ ...p, message: e.target.value }))}
                data-testid="doc-message"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDocReqModal({ open: false, user: null })}>Cancel</Button>
            <Button onClick={submitDocReq} disabled={docReqBusy} data-testid="doc-req-submit">
              {docReqBusy ? 'Sending…' : 'Send Request'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
