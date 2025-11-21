import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { Loader2, ArrowLeft, Mail, CheckCircle } from 'lucide-react';

const ForgotPasswordPage = () => {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [emailSent, setEmailSent] = useState(false);

  const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!email) {
      toast.error(t('auth.emailRequired') || 'Email is required');
      return;
    }
    
    setLoading(true);
    
    try {
      const response = await axios.post(`${API}/auth/forgot-password`, { email });
      
      if (response.data.success) {
        setEmailSent(true);
        toast.success(t('auth.resetEmailSent') || 'Password reset instructions sent to your email');
      }
    } catch (error) {
      // Even on error, show success message to prevent email enumeration
      setEmailSent(true);
      console.error('Forgot password error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12" data-testid="forgot-password-page">
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
          
          {!emailSent ? (
            <>
              <CardTitle className="text-2xl font-bold text-center">
                {t('auth.forgotPassword') || 'Forgot Password?'}
              </CardTitle>
              <CardDescription className="text-center">
                {t('auth.forgotPasswordDesc') || 
                  "Enter your email address and we'll send you instructions to reset your password."}
              </CardDescription>
            </>
          ) : (
            <>
              <div className="flex justify-center">
                <CheckCircle className="h-16 w-16 text-green-500" />
              </div>
              <CardTitle className="text-2xl font-bold text-center text-green-600">
                {t('auth.checkYourEmail') || 'Check Your Email'}
              </CardTitle>
              <CardDescription className="text-center">
                {t('auth.resetEmailSentDesc') || 
                  `If an account exists for ${email}, you will receive password reset instructions shortly.`}
              </CardDescription>
            </>
          )}
        </CardHeader>
        
        <CardContent className="space-y-4">
          {!emailSent ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="flex items-center gap-2">
                  <Mail className="h-4 w-4" />
                  {t('auth.email') || 'Email Address'}
                </Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  placeholder={t('auth.emailPlaceholder') || 'you@example.com'}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoFocus
                  aria-label="Email address"
                  aria-required="true"
                  data-testid="email-input"
                  className="w-full"
                />
              </div>
              
              <Button
                type="submit"
                className="w-full gradient-button text-white border-0"
                disabled={loading}
                data-testid="submit-forgot-password-btn"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t('common.sending') || 'Sending...'}
                  </>
                ) : (
                  <>
                    <Mail className="mr-2 h-4 w-4" />
                    {t('auth.sendResetLink') || 'Send Reset Link'}
                  </>
                )}
              </Button>
            </form>
          ) : (
            <div className="space-y-4">
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-800">
                <p className="font-medium mb-2">
                  {t('auth.whatToDoNext') || 'What to do next:'}
                </p>
                <ul className="list-disc list-inside space-y-1">
                  <li>{t('auth.checkInbox') || 'Check your email inbox'}</li>
                  <li>{t('auth.checkSpam') || 'Check your spam/junk folder'}</li>
                  <li>{t('auth.clickResetLink') || 'Click the reset link in the email'}</li>
                  <li>{t('auth.linkExpires') || 'The link expires in 1 hour'}</li>
                </ul>
              </div>
              
              <Button
                variant="outline"
                className="w-full"
                onClick={() => setEmailSent(false)}
                data-testid="send-another-email-btn"
              >
                {t('auth.sendAnotherEmail') || 'Send Another Email'}
              </Button>
            </div>
          )}
          
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
            <Button
              variant="ghost"
              className="w-full"
              data-testid="back-to-login-btn"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              {t('auth.backToLogin') || 'Back to Login'}
            </Button>
          </Link>
          
          {!emailSent && (
            <div className="text-center text-sm text-muted-foreground">
              <p>
                {t('auth.noAccount') || "Don't have an account?"}{' '}
                <Link to="/auth" className="text-primary hover:underline">
                  {t('auth.signUp') || 'Sign up'}
                </Link>
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default ForgotPasswordPage;
