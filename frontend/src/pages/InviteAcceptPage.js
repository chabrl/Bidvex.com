import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { Loader2, CheckCircle, Eye, EyeOff, UserPlus, Shield, AlertTriangle } from 'lucide-react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const InviteAcceptPage = () => {
  const { t } = useTranslation();
  const { token } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [invite, setInvite] = useState(null);
  const [error, setError] = useState(null);
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    fetchInviteInfo();
  }, [token]);

  const fetchInviteInfo = async () => {
    try {
      const res = await axios.get(`${API}/team/invite/${token}/info`);
      setInvite(res.data);
    } catch (err) {
      const status = err.response?.status;
      if (status === 410) setError('This invitation has expired. Please ask your admin to send a new one.');
      else if (status === 404) setError('Invitation not found or already used.');
      else setError('Failed to load invitation details.');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (password.length < 8) { toast.error('Password must be at least 8 characters'); return; }
    if (password !== confirmPassword) { toast.error('Passwords do not match'); return; }

    setSubmitting(true);
    try {
      await axios.post(`${API}/team/invite/${token}/accept`, { name, password });
      setSuccess(true);
      toast.success('Account created! Redirecting to login...');
      setTimeout(() => navigate('/auth'), 3000);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to accept invitation');
    } finally {
      setSubmitting(false);
    }
  };

  const roleColors = { admin: 'bg-red-100 text-red-700', manager: 'bg-blue-100 text-blue-700', support: 'bg-green-100 text-green-700' };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <Card className="w-full max-w-md" data-testid="invite-error">
          <CardContent className="pt-6 text-center space-y-4">
            <AlertTriangle className="h-12 w-12 text-amber-500 mx-auto" />
            <h2 className="text-xl font-bold">Invitation Issue</h2>
            <p className="text-muted-foreground">{error}</p>
            <Button onClick={() => navigate('/auth')} variant="outline">Go to Login</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <Card className="w-full max-w-md" data-testid="invite-success">
          <CardContent className="pt-6 text-center space-y-4">
            <CheckCircle className="h-12 w-12 text-green-500 mx-auto" />
            <h2 className="text-xl font-bold">Welcome to the Team!</h2>
            <p className="text-muted-foreground">Your account has been set up. Redirecting to login...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12" data-testid="invite-accept-page">
      <Card className="w-full max-w-md glassmorphism">
        <CardHeader className="space-y-4 text-center">
          <div className="flex justify-center">
            <div className="p-3 bg-primary/10 rounded-full">
              <UserPlus className="h-8 w-8 text-primary" />
            </div>
          </div>
          <CardTitle className="text-2xl font-bold">Join the BidVex Team</CardTitle>
          <CardDescription>
            <span className="font-medium">{invite.invited_by_name}</span> has invited you to join as
          </CardDescription>
          <Badge className={`${roleColors[invite.role] || ''} text-sm px-3 py-1`} data-testid="invite-role-badge">
            <Shield className="h-3 w-3 mr-1" />
            {invite.role.charAt(0).toUpperCase() + invite.role.slice(1)}
          </Badge>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label>Email</Label>
              <Input value={invite.email} disabled className="bg-muted" data-testid="invite-email" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">{t("auth.fullNameLabel")}</Label>
              <Input id="name" value={name} onChange={e => setName(e.target.value)} required placeholder="Your full name" data-testid="invite-name-input" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">{t("auth.passwordLabel")}</Label>
              <div className="relative">
                <Input
                  id="password" type={showPassword ? 'text' : 'password'} value={password}
                  onChange={e => setPassword(e.target.value)} required minLength={8}
                  placeholder="Min 8 characters" className="pr-10" data-testid="invite-password-input"
                />
                <Button type="button" variant="ghost" size="sm" className="absolute right-1 top-1/2 -translate-y-1/2 h-7"
                  onClick={() => setShowPassword(!showPassword)}>
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">{t("auth.confirmPasswordLabel")}</Label>
              <Input id="confirmPassword" type="password" value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)} required placeholder="Confirm password"
                data-testid="invite-confirm-password-input" />
              {confirmPassword && password !== confirmPassword && <p className="text-sm text-red-500">Passwords do not match</p>}
            </div>
            <Button type="submit" className="w-full gradient-button text-white border-0" disabled={submitting || password.length < 8 || password !== confirmPassword}
              data-testid="invite-accept-btn">
              {submitting ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Setting up...</> : 'Accept & Create Account'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default InviteAcceptPage;
