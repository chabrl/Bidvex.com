import API_BASE from '../config';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { extractErrorMessage } from '../utils/errorHandler';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { Loader2, Lock, Eye, EyeOff, AlertTriangle, CheckCircle, Square, CheckSquare } from 'lucide-react';
import axios from 'axios';

const API = API_BASE;

const AuthPage = () => {
  const { t } = useTranslation();
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: '',
    phone: '',
    account_type: 'personal',
    address: '',
    company_name: '',
    tax_number: '',
    terms_agreed: false,
    ai_disclosure_consent: false,
  });

  // Forced Password Reset State
  const [showForceReset, setShowForceReset] = useState(false);
  const [resetToken, setResetToken] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [resetting, setResetting] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      if (isLogin) {
        await login(formData.email, formData.password);
        toast.success(t('auth.welcomeMessage'));
        const from = location.state?.from?.pathname || '/marketplace';
        navigate(from, { replace: true });
      } else {
        await register(formData);
        toast.success(t('auth.accountCreatedMessage'));
        const from = location.state?.from?.pathname || '/marketplace';
        navigate(from, { replace: true });
      }
    } catch (error) {
      // Check for forced password reset
      if (error.message === 'PASSWORD_RESET_REQUIRED') {
        setResetToken(error.resetToken);
        setShowForceReset(true);
        toast.info('Please set a new password to continue');
      } else {
        const errorMessage = extractErrorMessage(error);
        toast.error(errorMessage || t('auth.authFailedMessage'));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleForceReset = async (e) => {
    e.preventDefault();
    
    // Validation
    if (newPassword.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }
    
    if (newPassword !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    setResetting(true);
    try {
      await axios.post(`${API}/auth/force-reset-password`, {
        reset_token: resetToken,
        new_password: newPassword
      });
      
      toast.success('Password updated! Please log in with your new password.');
      setShowForceReset(false);
      setResetToken(null);
      setNewPassword('');
      setConfirmPassword('');
      // Keep email filled for convenience
      setFormData(prev => ({ ...prev, password: '' }));
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Failed to reset password';
      toast.error(errorMessage);
    } finally {
      setResetting(false);
    }
  };

  const handleGoogleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    // Direct Google OAuth 2.0 — backend handles the consent flow.
    // The backend's GOOGLE_CALLBACK_URL env var controls what's sent to Google
    // and MUST match a value in Google Cloud Console → Authorized Redirect URIs.
    const desiredRedirect = '/marketplace';
    window.location.href = `${API_BASE}/auth/google?redirect=${encodeURIComponent(desiredRedirect)}`;
  };

  // Forced Password Reset Form
  if (showForceReset) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 pt-12 pb-40 sm:pb-48" data-testid="force-reset-page">
        <Card className="w-full max-w-md glassmorphism">
          <CardHeader className="space-y-4">
            <div className="flex justify-center">
              <div className="w-16 h-16 bg-amber-100 dark:bg-amber-900 rounded-full flex items-center justify-center">
                <Lock className="h-8 w-8 text-amber-600" />
              </div>
            </div>
            <CardTitle className="text-2xl font-bold text-center">
              Password Reset Required
            </CardTitle>
            <CardDescription className="text-center">
              Your account requires a password reset. Please choose a new secure password.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Warning Notice */}
            <div className="flex items-start gap-2 p-3 bg-amber-50 dark:bg-amber-950/30 rounded-lg text-sm">
              <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5" />
              <div className="text-amber-700 dark:text-amber-300">
                <p className="font-medium">First-time login</p>
                <p>An administrator created your account. You must set a new password before accessing your dashboard.</p>
              </div>
            </div>

            <form onSubmit={handleForceReset} className="space-y-4">
              {/* New Password */}
              <div className="space-y-2">
                <Label htmlFor="newPassword">{t("auth.newPasswordLabel")}</Label>
                <div className="relative">
                  <Input
                    id="newPassword"
                    type={showNewPassword ? "text" : "password"}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    minLength={8}
                    placeholder="Enter new password (min 8 characters)"
                    className="pr-10"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-7"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                  >
                    {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              {/* Confirm Password */}
              <div className="space-y-2">
                <Label htmlFor="confirmPassword">{t("auth.confirmPasswordLabel")}</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  placeholder="Confirm new password"
                />
                {confirmPassword && newPassword !== confirmPassword && (
                  <p className="text-sm text-red-500">Passwords do not match</p>
                )}
                {confirmPassword && newPassword === confirmPassword && newPassword.length >= 8 && (
                  <p className="text-sm text-green-600 flex items-center gap-1">
                    <CheckCircle className="h-3 w-3" /> Passwords match
                  </p>
                )}
              </div>

              <Button
                type="submit"
                className="w-full gradient-button text-white border-0"
                disabled={resetting || newPassword.length < 8 || newPassword !== confirmPassword}
              >
                {resetting ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Updating Password...</>
                ) : (
                  <>{t("auth.setNewPassword")}</>
                )}
              </Button>
            </form>

            <div className="text-center text-sm">
              <button
                type="button"
                onClick={() => {
                  setShowForceReset(false);
                  setResetToken(null);
                }}
                className="text-muted-foreground hover:underline"
              >
                Cancel and return to login
              </button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Regular Login/Register Form
  return (
    <div className="min-h-screen flex items-center justify-center px-4 pt-12 pb-40 sm:pb-48" data-testid="auth-page">
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
            {isLogin ? t('auth.welcomeBack') : t('auth.createAccount')}
          </CardTitle>
          <CardDescription className="text-center">
            {isLogin ? t('auth.signInPrompt') : t('auth.createAccountPrompt')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <div className="space-y-2">
                <Label htmlFor="name">{t('auth.name')}</Label>
                <Input
                  id="name"
                  name="name"
                  type="text"
                  value={formData.name}
                  onChange={handleChange}
                  required={!isLogin}
                  data-testid="name-input"
                />
              </div>
            )}
            
            <div className="space-y-2">
              <Label htmlFor="email">{t('auth.email')}</Label>
              <Input
                id="email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleChange}
                required
                data-testid="email-input"
              />
            </div>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">{t('auth.password')}</Label>
                {isLogin && (
                  <Link 
                    to="/forgot-password" 
                    className="text-sm text-primary hover:underline"
                    data-testid="forgot-password-link"
                  >
                    {t('auth.forgotPassword') || 'Forgot password?'}
                  </Link>
                )}
              </div>
              <Input
                id="password"
                name="password"
                type="password"
                value={formData.password}
                onChange={handleChange}
                required
                data-testid="password-input"
              />
            </div>

            {!isLogin && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="phone">{t('auth.phone')}</Label>
                  <Input
                    id="phone"
                    name="phone"
                    type="tel"
                    value={formData.phone}
                    onChange={handleChange}
                    required={!isLogin}
                    data-testid="phone-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="account_type">{t('auth.accountType')}</Label>
                  <select
                    id="account_type"
                    name="account_type"
                    value={formData.account_type}
                    onChange={handleChange}
                    className="w-full px-3 py-2 border border-input rounded-md bg-background"
                    data-testid="account-type-select"
                  >
                    <option value="personal">{t('auth.personal')}</option>
                    <option value="business">{t('auth.business')}</option>
                  </select>
                </div>

                {formData.account_type === 'business' && (
                  <>
                    <div className="space-y-2">
                      <Label htmlFor="company_name">{t('auth.companyName')}</Label>
                      <Input
                        id="company_name"
                        name="company_name"
                        type="text"
                        value={formData.company_name}
                        onChange={handleChange}
                        data-testid="company-name-input"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="tax_number">{t('auth.taxNumber')}</Label>
                      <Input
                        id="tax_number"
                        name="tax_number"
                        type="text"
                        value={formData.tax_number}
                        onChange={handleChange}
                        data-testid="tax-number-input"
                      />
                    </div>
                    {/* Partner Fee Disclosure for Business Accounts */}
                    <div className="rounded-lg border border-blue-200 dark:border-blue-500/30 bg-blue-50/60 dark:bg-blue-500/5 p-3 space-y-1.5" data-testid="partner-fee-signup-notice">
                      <p className="text-xs font-semibold text-blue-700 dark:text-blue-300">Partner Account Fees (CAD)</p>
                      <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                        If you apply as a Partner (licensed auctioneer/liquidator), the following fees apply:
                        <strong> $100.00 CAD/year</strong> platform access fee + <strong>3% commission</strong> on the final hammer price per item.
                        You set your own Buyer's Premium independently. All fees are subject to GST/QST.
                      </p>
                      <p className="text-[10px] text-amber-600 dark:text-amber-400">Partner accounts require manual verification of your federal or provincial business registration before listing.</p>
                    </div>
                  </>
                )}

                {/* Terms & Privacy Consent */}
                <div className="flex items-start gap-3 p-3 border rounded-lg bg-muted/30">
                  <button
                    type="button"
                    onClick={() => setFormData(prev => ({ ...prev, terms_agreed: !prev.terms_agreed }))}
                    className="mt-0.5 flex-shrink-0"
                    data-testid="terms-checkbox"
                  >
                    {formData.terms_agreed
                      ? <CheckSquare className="h-5 w-5 text-primary" />
                      : <Square className="h-5 w-5 text-muted-foreground" />
                    }
                  </button>
                  <label className="text-sm text-muted-foreground leading-relaxed">
                    I agree to the{' '}
                    <a href="/legal#terms" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline font-medium" data-testid="terms-link">
                      Terms of Service
                    </a>{' '}
                    and{' '}
                    <a href="/legal#privacy" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline font-medium" data-testid="privacy-link">
                      Privacy Policy
                    </a>
                  </label>
                </div>

                {/* AI Disclosure Consent — Law 25 / Loi 25 (Mandatory, standalone) */}
                <div className="flex items-start gap-3 p-3 border-2 border-purple-200 dark:border-purple-500/30 rounded-lg bg-purple-50/40 dark:bg-purple-500/5" data-testid="ai-disclosure-block">
                  <button
                    type="button"
                    onClick={() => setFormData(prev => ({ ...prev, ai_disclosure_consent: !prev.ai_disclosure_consent }))}
                    className="mt-0.5 flex-shrink-0"
                    data-testid="ai-disclosure-checkbox"
                  >
                    {formData.ai_disclosure_consent
                      ? <CheckSquare className="h-5 w-5 text-purple-600" />
                      : <Square className="h-5 w-5 text-muted-foreground" />
                    }
                  </button>
                  <div className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed space-y-2">
                    <p>I understand that BidVex uses automated processing and artificial intelligence (AI) to assist with customer support, listing categorization, and fraud detection. I understand that I have the right to request human review of any AI-assisted decision that affects me.</p>
                    <hr className="border-slate-200 dark:border-slate-700" />
                    <p>Je comprends que BidVex utilise des traitements automatisés et l'intelligence artificielle (IA) pour le support client, la catégorisation des annonces et la détection de fraude. Je comprends que j'ai le droit de demander une révision humaine de toute décision assistée par IA me concernant.</p>
                  </div>
                </div>
              </>
            )}
            
            <Button
              type="submit"
              className="w-full gradient-button text-white border-0"
              disabled={loading || (!isLogin && (!formData.terms_agreed || !formData.ai_disclosure_consent))}
              data-testid="submit-auth-btn"
            >
              {loading ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> {t('common.loading')}</>
              ) : (
                isLogin ? t('auth.loginBtn') : t('auth.registerBtn')
              )}
            </Button>
          </form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">Or</span>
            </div>
          </div>

          <Button
            variant="outline"
            className="w-full"
            onClick={handleGoogleLogin}
            data-testid="google-login-btn"
          >
            <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            {t('auth.googleLogin')}
          </Button>

          <div className="text-center text-sm">
            <button
              type="button"
              onClick={() => setIsLogin(!isLogin)}
              className="text-primary hover:underline"
              data-testid="toggle-auth-mode-btn"
            >
              {isLogin ? t('auth.noAccount') : t('auth.hasAccount')}
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AuthPage;
