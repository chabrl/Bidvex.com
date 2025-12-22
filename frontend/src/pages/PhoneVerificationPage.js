import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { 
  Phone, Shield, CheckCircle2, ArrowRight, Loader2, 
  RefreshCw, Sparkles, Lock, AlertCircle
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// ========== OTP INPUT COMPONENT ==========
const OTPInput = ({ length = 6, value, onChange, disabled }) => {
  const inputRefs = useRef([]);
  
  useEffect(() => {
    // Focus first input on mount
    if (inputRefs.current[0]) {
      inputRefs.current[0].focus();
    }
  }, []);
  
  const handleChange = (index, e) => {
    const val = e.target.value;
    
    // Only allow digits
    if (!/^\d*$/.test(val)) return;
    
    // Take only last character if multiple pasted
    const digit = val.slice(-1);
    
    // Update value
    const newValue = value.split('');
    newValue[index] = digit;
    onChange(newValue.join(''));
    
    // Auto-focus next input
    if (digit && index < length - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  };
  
  const handleKeyDown = (index, e) => {
    // Handle backspace
    if (e.key === 'Backspace' && !value[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
    
    // Handle arrow keys
    if (e.key === 'ArrowLeft' && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
    if (e.key === 'ArrowRight' && index < length - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  };
  
  const handlePaste = (e) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').slice(0, length);
    if (/^\d+$/.test(pastedData)) {
      onChange(pastedData.padEnd(length, '').slice(0, length));
      // Focus the next empty input or last input
      const nextIndex = Math.min(pastedData.length, length - 1);
      inputRefs.current[nextIndex]?.focus();
    }
  };
  
  return (
    <div className="flex justify-center gap-2 sm:gap-3">
      {Array.from({ length }, (_, index) => (
        <input
          key={index}
          ref={(el) => (inputRefs.current[index] = el)}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={value[index] || ''}
          onChange={(e) => handleChange(index, e)}
          onKeyDown={(e) => handleKeyDown(index, e)}
          onPaste={handlePaste}
          disabled={disabled}
          className={`
            w-12 h-14 sm:w-14 sm:h-16 text-center text-2xl font-bold rounded-xl
            border-2 transition-all duration-200 outline-none
            ${disabled ? 'bg-slate-100 dark:bg-slate-800 cursor-not-allowed' : 'bg-white dark:bg-slate-900'}
            ${value[index] 
              ? 'border-[#06B6D4] ring-2 ring-[#06B6D4]/20' 
              : 'border-slate-300 dark:border-slate-600 hover:border-[#1E3A8A] focus:border-[#06B6D4] focus:ring-2 focus:ring-[#06B6D4]/20'}
            text-slate-900 dark:text-white
          `}
          aria-label={`Digit ${index + 1}`}
        />
      ))}
    </div>
  );
};

// ========== MAIN VERIFICATION PAGE ==========
const PhoneVerificationPage = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { user, token, refreshUser } = useAuth();
  
  const [step, setStep] = useState(1); // 1 = phone input, 2 = OTP verification
  const [phoneNumber, setPhoneNumber] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  
  const language = i18n.language?.startsWith('fr') ? 'fr' : 'en';
  
  // Countdown timer for resend
  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [resendCooldown]);
  
  // Send OTP
  const handleSendOTP = async () => {
    if (!phoneNumber.trim()) {
      setError(language === 'fr' 
        ? 'Veuillez entrer votre numéro de téléphone' 
        : 'Please enter your phone number');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      const response = await axios.post(`${API}/sms/send-otp`, {
        phone_number: phoneNumber,
        user_id: user?.id,
        language
      });
      
      toast.success(response.data.message);
      setStep(2);
      setResendCooldown(response.data.cooldown_seconds || 60);
      
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 
        (language === 'fr' ? 'Échec de l\'envoi du code' : 'Failed to send code');
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };
  
  // Resend OTP
  const handleResendOTP = async () => {
    if (resendCooldown > 0) return;
    
    setLoading(true);
    setError('');
    
    try {
      const response = await axios.post(`${API}/sms/send-otp`, {
        phone_number: phoneNumber,
        user_id: user?.id,
        language
      });
      
      toast.success(language === 'fr' ? 'Code renvoyé!' : 'Code resent!');
      setResendCooldown(response.data.cooldown_seconds || 60);
      setOtpCode('');
      
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 
        (language === 'fr' ? 'Échec du renvoi' : 'Failed to resend');
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };
  
  // Verify OTP
  const handleVerifyOTP = async () => {
    if (otpCode.length !== 6) {
      setError(language === 'fr' 
        ? 'Veuillez entrer les 6 chiffres' 
        : 'Please enter all 6 digits');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      const response = await axios.post(`${API}/sms/verify-otp`, {
        phone_number: phoneNumber,
        code: otpCode,
        user_id: user?.id
      });
      
      if (response.data.valid) {
        setSuccess(true);
        toast.success(language === 'fr' ? response.data.message_fr : response.data.message);
        
        // Refresh user data to get updated phone_verified status
        if (refreshUser) {
          await refreshUser();
        }
        
        // Redirect after short delay
        setTimeout(() => {
          navigate('/dashboard');
        }, 2000);
      } else {
        setError(language === 'fr' ? response.data.message_fr : response.data.message);
        setOtpCode('');
      }
      
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 
        (language === 'fr' ? 'Échec de la vérification' : 'Verification failed');
      setError(errorMsg);
      toast.error(errorMsg);
      setOtpCode('');
    } finally {
      setLoading(false);
    }
  };
  
  // Auto-verify when 6 digits entered
  useEffect(() => {
    if (otpCode.length === 6 && step === 2 && !loading) {
      handleVerifyOTP();
    }
  }, [otpCode]);
  
  // Success state
  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#1E3A8A] via-slate-900 to-[#0F172A] p-4">
        <Card className="w-full max-w-md overflow-hidden border-0 shadow-2xl animate-in zoom-in-95 duration-500">
          <CardContent className="p-8 text-center">
            <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-green-500 to-emerald-500 flex items-center justify-center animate-bounce">
              <CheckCircle2 className="h-10 w-10 text-white" />
            </div>
            <h2 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
              {language === 'fr' ? 'Vérifié!' : 'Verified!'}
            </h2>
            <p className="text-slate-600 dark:text-slate-300 mb-6">
              {language === 'fr' 
                ? 'Votre numéro de téléphone a été vérifié avec succès.'
                : 'Your phone number has been successfully verified.'}
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {language === 'fr' ? 'Redirection...' : 'Redirecting...'}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#1E3A8A] via-slate-900 to-[#0F172A] p-4 relative overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 -left-32 w-96 h-96 bg-[#06B6D4] rounded-full blur-[150px] opacity-20" />
        <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-[#1E3A8A] rounded-full blur-[150px] opacity-30" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-r from-[#06B6D4]/10 to-[#1E3A8A]/10 rounded-full blur-[100px]" />
      </div>
      
      <Card className="relative w-full max-w-md overflow-hidden border-0 shadow-2xl bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl">
        {/* Header */}
        <div className="bg-gradient-to-r from-[#1E3A8A] to-[#06B6D4] p-6 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-white/10 backdrop-blur flex items-center justify-center">
            {step === 1 ? (
              <Phone className="h-8 w-8 text-white" />
            ) : (
              <Lock className="h-8 w-8 text-white" />
            )}
          </div>
          <h1 className="text-2xl font-bold text-white mb-1">
            {step === 1 
              ? (language === 'fr' ? 'Vérifiez votre téléphone' : 'Verify Your Phone')
              : (language === 'fr' ? 'Entrez le code' : 'Enter Code')}
          </h1>
          <p className="text-white/80 text-sm">
            {step === 1
              ? (language === 'fr' 
                  ? 'Nous vous enverrons un code de vérification' 
                  : 'We\'ll send you a verification code')
              : (language === 'fr'
                  ? `Code envoyé à ${phoneNumber.slice(0, 6)}***`
                  : `Code sent to ${phoneNumber.slice(0, 6)}***`)}
          </p>
        </div>
        
        <CardContent className="p-6 space-y-6">
          {/* Step 1: Phone Input */}
          {step === 1 && (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  {language === 'fr' ? 'Numéro de téléphone' : 'Phone Number'}
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
                  <input
                    type="tel"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder="+1 (555) 123-4567"
                    className="w-full pl-10 pr-4 py-3 rounded-xl border-2 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:border-[#06B6D4] focus:ring-2 focus:ring-[#06B6D4]/20 outline-none transition-all"
                    disabled={loading}
                  />
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                  {language === 'fr' 
                    ? 'Entrez votre numéro avec l\'indicatif pays (ex: +1 pour USA/Canada)'
                    : 'Enter your number with country code (e.g., +1 for USA/Canada)'}
                </p>
              </div>
              
              {error && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm">
                  <AlertCircle className="h-4 w-4 flex-shrink-0" />
                  {error}
                </div>
              )}
              
              <Button
                onClick={handleSendOTP}
                disabled={loading || !phoneNumber.trim()}
                className="w-full py-6 text-lg font-bold bg-gradient-to-r from-[#06B6D4] to-[#1E3A8A] hover:opacity-90 text-white shadow-lg shadow-[#06B6D4]/30"
              >
                {loading ? (
                  <><Loader2 className="h-5 w-5 mr-2 animate-spin" /> {language === 'fr' ? 'Envoi...' : 'Sending...'}</>
                ) : (
                  <>{language === 'fr' ? 'Envoyer le code' : 'Send Code'} <ArrowRight className="h-5 w-5 ml-2" /></>
                )}
              </Button>
            </>
          )}
          
          {/* Step 2: OTP Verification */}
          {step === 2 && (
            <>
              <div className="space-y-4">
                <p className="text-center text-slate-600 dark:text-slate-300">
                  {language === 'fr' 
                    ? 'Entrez le code à 6 chiffres envoyé à votre téléphone'
                    : 'Enter the 6-digit code sent to your phone'}
                </p>
                
                <OTPInput
                  length={6}
                  value={otpCode}
                  onChange={setOtpCode}
                  disabled={loading}
                />
              </div>
              
              {error && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm">
                  <AlertCircle className="h-4 w-4 flex-shrink-0" />
                  {error}
                </div>
              )}
              
              <Button
                onClick={handleVerifyOTP}
                disabled={loading || otpCode.length !== 6}
                className="w-full py-6 text-lg font-bold bg-gradient-to-r from-[#06B6D4] to-[#1E3A8A] hover:opacity-90 text-white shadow-lg shadow-[#06B6D4]/30"
              >
                {loading ? (
                  <><Loader2 className="h-5 w-5 mr-2 animate-spin" /> {language === 'fr' ? 'Vérification...' : 'Verifying...'}</>
                ) : (
                  <><Shield className="h-5 w-5 mr-2" /> {language === 'fr' ? 'Vérifier' : 'Verify'}</>
                )}
              </Button>
              
              {/* Resend Code */}
              <div className="text-center">
                <p className="text-sm text-slate-500 dark:text-slate-400 mb-2">
                  {language === 'fr' ? 'Vous n\'avez pas reçu le code?' : 'Didn\'t receive the code?'}
                </p>
                <button
                  onClick={handleResendOTP}
                  disabled={resendCooldown > 0 || loading}
                  className={`inline-flex items-center gap-2 text-sm font-medium transition-colors ${
                    resendCooldown > 0
                      ? 'text-slate-400 cursor-not-allowed'
                      : 'text-[#06B6D4] hover:text-[#1E3A8A]'
                  }`}
                >
                  <RefreshCw className={`h-4 w-4 ${resendCooldown > 0 ? '' : 'hover:animate-spin'}`} />
                  {resendCooldown > 0
                    ? `${language === 'fr' ? 'Renvoyer dans' : 'Resend in'} ${resendCooldown}s`
                    : (language === 'fr' ? 'Renvoyer le code' : 'Resend Code')}
                </button>
              </div>
              
              {/* Back button */}
              <button
                onClick={() => { setStep(1); setOtpCode(''); setError(''); }}
                className="w-full text-center text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
              >
                {language === 'fr' ? '← Changer de numéro' : '← Change Number'}
              </button>
            </>
          )}
          
          {/* Security Note */}
          <div className="flex items-start gap-3 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50">
            <Sparkles className="h-5 w-5 text-[#06B6D4] flex-shrink-0 mt-0.5" />
            <div className="text-xs text-slate-500 dark:text-slate-400">
              <p className="font-medium text-slate-700 dark:text-slate-300 mb-1">
                {language === 'fr' ? 'Pourquoi vérifier?' : 'Why verify?'}
              </p>
              {language === 'fr' 
                ? 'La vérification du téléphone protège votre compte et garantit la confiance sur BidVex.'
                : 'Phone verification protects your account and ensures trust on BidVex.'}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default PhoneVerificationPage;
