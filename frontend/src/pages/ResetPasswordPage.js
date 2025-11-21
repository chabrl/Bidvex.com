import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { Loader2, Lock, CheckCircle, XCircle, Eye, EyeOff } from 'lucide-react';

const ResetPasswordPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [tokenMessage, setTokenMessage] = useState('');
  const [expiresInMinutes, setExpiresInMinutes] = useState(0);
  const [resetSuccess, setResetSuccess] = useState(false);

  const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

  useEffect(() => {
    if (!token) {
      setVerifying(false);
      setTokenValid(false);
      setTokenMessage(t('auth.noResetToken') || 'No reset token provided');
      return;
    }
    
    verifyToken();
  }, [token]);

  const verifyToken = async () => {
    try {
      const response = await axios.get(`${API}/auth/verify-reset-token/${token}`);
      
      setTokenValid(response.data.valid);
      setTokenMessage(response.data.message);
      setExpiresInMinutes(response.data.expires_in_minutes || 0);
      
      if (!response.data.valid) {
        toast.error(response.data.message || t('auth.invalidToken'));
      }
    } catch (error) {
      console.error('Token verification error:', error);
      setTokenValid(false);
      setTokenMessage(t('auth.tokenVerificationFailed') || 'Failed to verify token');
      toast.error(t('auth.tokenVerificationError') || 'Error verifying reset token');
    } finally {
      setVerifying(false);
    }
  };

  const validatePasswords = () => {
    if (newPassword.length < 6) {
      toast.error(t('auth.passwordTooShort') || 'Password must be at least 6 characters');
      return false;
    }
    
    if (newPassword !== confirmPassword) {
      toast.error(t('auth.passwordsDontMatch') || 'Passwords do not match');
      return false;
    }
    
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validatePasswords()) {
      return;
    }
    
    setLoading(true);
    
    try {
      const response = await axios.post(`${API}/auth/reset-password`, {
        token,
        new_password: newPassword
      });
      
      if (response.data.success) {
        setResetSuccess(true);
        toast.success(t('auth.passwordResetSuccess') || 'Password reset successful');
        
        // Redirect to login after 3 seconds
        setTimeout(() => {
          navigate('/auth', { 
            state: { message: t('auth.passwordResetSuccessMessage') } 
          });
        }, 3000);
      }
    } catch (error) {
      console.error('Password reset error:', error);
      toast.error(
        error.response?.data?.detail || 
        t('auth.passwordResetFailed') || 
        'Failed to reset password'
      );
    } finally {
      setLoading(false);
    }
  };

  if (verifying) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 py-12">
        <Card className="w-full max-w-md glassmorphism">
          <CardContent className="py-12">
            <div className="flex flex-col items-center space-y-4">
              <Loader2 className="h-12 w-12 animate-spin text-primary" />
              <p className="text-center text-muted-foreground">
                {t('auth.verifyingToken') || 'Verifying reset token...'}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!tokenValid) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 py-12">
        <Card className="w-full max-w-md glassmorphism">
          <CardHeader className="space-y-4">
            <div className="flex justify-center">
              <XCircle className="h-16 w-16 text-red-500" />
            </div>
            <CardTitle className="text-2xl font-bold text-center text-red-600">
              {t('auth.invalidResetLink') || 'Invalid Reset Link'}
            </CardTitle>
            <CardDescription className="text-center">
              {tokenMessage}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-800">
              <p className="font-medium mb-2">
                {t('auth.possibleReasons') || 'Possible reasons:'}
              </p>
              <ul className="list-disc list-inside space-y-1">
                <li>{t('auth.linkExpired') || 'The link has expired (valid for 1 hour)'}</li>
                <li>{t('auth.linkAlreadyUsed') || 'The link has already been used'}</li>
                <li>{t('auth.linkInvalid') || 'The link is invalid or malformed'}</li>
              </ul>
            </div>
            
            <Link to="/forgot-password">
              <Button className="w-full gradient-button text-white border-0">
                {t('auth.requestNewLink') || 'Request New Reset Link'}
              </Button>
            </Link>
            
            <Link to="/auth">
              <Button variant="outline" className="w-full">
                {t('auth.backToLogin') || 'Back to Login'}
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (resetSuccess) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 py-12">
        <Card className="w-full max-w-md glassmorphism">
          <CardHeader className="space-y-4">
            <div className="flex justify-center">
              <CheckCircle className="h-16 w-16 text-green-500" />
            </div>
            <CardTitle className="text-2xl font-bold text-center text-green-600">
              {t('auth.passwordResetComplete') || 'Password Reset Complete'}
            </CardTitle>
            <CardDescription className="text-center">
              {t('auth.passwordResetCompleteDesc') || 
                'Your password has been successfully reset. You can now log in with your new password.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
              <p className="text-sm text-green-800">
                {t('auth.redirectingToLogin') || 'Redirecting to login page...'}
              </p>
            </div>
            
            <Link to="/auth">
              <Button className="w-full gradient-button text-white border-0">
                {t('auth.goToLogin') || 'Go to Login'}
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12" data-testid="reset-password-page">
      <Card className="w-full max-w-md glassmorphism">
        <CardHeader className="space-y-4">
          {/* BidVex Icon */}
          <div className="flex justify-center">
            <img 
              src="/bidvex-icon.png" 
              alt="BidVex" 
              className="h-16 w-16"
            />
          </div>
          
          <CardTitle className="text-2xl font-bold text-center">
            {t('auth.resetPassword') || 'Reset Your Password'}
          </CardTitle>
          <CardDescription className="text-center">
            {t('auth.resetPasswordDesc') || 'Enter your new password below.'}
          </CardDescription>
          
          {expiresInMinutes > 0 && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-center">
              <p className="text-sm text-yellow-800">
                {t('auth.linkExpiresIn') || 'This link expires in'}{' '}
                <strong>{expiresInMinutes} {t('common.minutes') || 'minutes'}</strong>
              </p>
            </div>
          )}
        </CardHeader>
        
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="new-password" className="flex items-center gap-2">
                <Lock className="h-4 w-4" />
                {t('auth.newPassword') || 'New Password'}
              </Label>
              <div className="relative">
                <Input
                  id="new-password"
                  name="new-password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder={t('auth.enterNewPassword') || 'Enter new password'}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  autoFocus
                  minLength={6}
                  aria-label="New password"
                  aria-required="true"
                  data-testid="new-password-input"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              <p className="text-xs text-muted-foreground">
                {t('auth.passwordMinLength') || 'Minimum 6 characters'}
              </p>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="confirm-password" className="flex items-center gap-2">
                <Lock className="h-4 w-4" />
                {t('auth.confirmPassword') || 'Confirm Password'}
              </Label>
              <div className="relative">
                <Input
                  id="confirm-password"
                  name="confirm-password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  placeholder={t('auth.confirmNewPassword') || 'Confirm new password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={6}
                  aria-label="Confirm password"
                  aria-required="true"
                  data-testid="confirm-password-input"
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            
            {newPassword && confirmPassword && newPassword !== confirmPassword && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <p className="text-sm text-red-800">
                  {t('auth.passwordsMustMatch') || 'Passwords must match'}
                </p>
              </div>
            )}
            
            <Button
              type="submit"
              className="w-full gradient-button text-white border-0"
              disabled={loading || !newPassword || !confirmPassword}
              data-testid="submit-reset-password-btn"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('auth.resettingPassword') || 'Resetting Password...'}
                </>
              ) : (
                <>
                  <Lock className="mr-2 h-4 w-4" />
                  {t('auth.resetPasswordBtn') || 'Reset Password'}
                </>
              )}
            </Button>
          </form>
          
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                {t('common.or') || 'Or'}
              </span>
            </div>
          </div>
          
          <Link to="/auth">
            <Button variant="ghost" className="w-full">
              {t('auth.backToLogin') || 'Back to Login'}
            </Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
};

export default ResetPasswordPage;
