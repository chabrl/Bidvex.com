/**
 * iter238 Mission 1.2 — Post-Google-signin onboarding wizard (3 steps).
 *
 * Step 1: Set a BidVex password (skippable).
 * Step 2: Auto-detect location via navigator.geolocation + Nominatim
 *         reverse-geocode; user confirms / edits city, province, postal.
 * Step 3: Completion screen with "Go to Marketplace" CTA.
 *
 * Backend: POST /api/onboarding/complete  body: { password?, city?,
 *          province?, postal_code?, skip_all? }
 *          Returns { status: "ok", onboarding_complete: true }.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { Loader2, MapPin, Lock, PartyPopper } from 'lucide-react';
import { getAuthToken } from '../utils/authToken';

const PROVINCES = [
  { code: 'QC', en: 'Quebec', fr: 'Québec' },
  { code: 'ON', en: 'Ontario', fr: 'Ontario' },
  { code: 'BC', en: 'British Columbia', fr: 'Colombie-Britannique' },
  { code: 'AB', en: 'Alberta', fr: 'Alberta' },
  { code: 'MB', en: 'Manitoba', fr: 'Manitoba' },
  { code: 'SK', en: 'Saskatchewan', fr: 'Saskatchewan' },
  { code: 'NS', en: 'Nova Scotia', fr: 'Nouvelle-Écosse' },
  { code: 'NB', en: 'New Brunswick', fr: 'Nouveau-Brunswick' },
  { code: 'NL', en: 'Newfoundland and Labrador', fr: 'Terre-Neuve-et-Labrador' },
  { code: 'PE', en: 'Prince Edward Island', fr: 'Île-du-Prince-Édouard' },
  { code: 'YT', en: 'Yukon', fr: 'Yukon' },
  { code: 'NT', en: 'Northwest Territories', fr: 'Territoires du Nord-Ouest' },
  { code: 'NU', en: 'Nunavut', fr: 'Nunavut' },
];

export default function OnboardingPage() {
  const navigate = useNavigate();
  const backendUrl = process.env.REACT_APP_BACKEND_URL
    ? `${process.env.REACT_APP_BACKEND_URL}/api`
    : '/api';

  const [step, setStep] = useState(1);
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [city, setCity] = useState('');
  const [province, setProvince] = useState('QC');
  const [postal, setPostal] = useState('');
  const [busy, setBusy] = useState(false);
  const [detecting, setDetecting] = useState(false);

  // Auto-detect on Step 2 mount.
  useEffect(() => {
    if (step !== 2 || city) return;
    if (typeof navigator === 'undefined' || !navigator.geolocation) return;
    setDetecting(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const r = await fetch(
            `https://nominatim.openstreetmap.org/reverse?lat=${pos.coords.latitude}&lon=${pos.coords.longitude}&format=json`,
            { headers: { 'User-Agent': 'BidVex/1.0 (support@bidvex.com)' } },
          );
          if (r.ok) {
            const data = await r.json();
            const addr = data?.address || {};
            const detectedCity = addr.city || addr.town || addr.village || '';
            const detectedProvince = addr.state || '';
            const detectedPostal = addr.postcode || '';
            if (detectedCity) setCity(detectedCity);
            const provCode = PROVINCES.find((p) =>
              detectedProvince.toLowerCase().includes(p.en.toLowerCase()) ||
              detectedProvince.toLowerCase().includes(p.fr.toLowerCase())
            )?.code;
            if (provCode) setProvince(provCode);
            if (detectedPostal) setPostal(detectedPostal.toUpperCase());
          }
        } catch { /* silent */ }
        setDetecting(false);
      },
      () => setDetecting(false),
      { timeout: 6000, enableHighAccuracy: true },
    );
  }, [step, city]);

  const validatePassword = () => {
    if (!password) return true; // empty = skip
    if (password.length < 8) return false;
    if (!/[A-Z]/.test(password)) return false;
    if (!/\d/.test(password)) return false;
    return password === confirm;
  };

  const submit = async (skipAll = false) => {
    setBusy(true);
    try {
      const body = {
        password: skipAll ? null : (password || null),
        city: skipAll ? null : (city || null),
        province: skipAll ? null : province,
        postal_code: skipAll ? null : (postal || null),
        skip_all: skipAll,
      };
      const res = await fetch(`${backendUrl}/onboarding/complete`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${getAuthToken() || ''}`,
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setStep(3);
    } catch (e) {
      toast.error('Could not save profile — please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900 px-4" data-testid="onboarding-page">
      <div className="w-full max-w-md rounded-2xl bg-white dark:bg-slate-800 shadow-xl border border-slate-200 dark:border-slate-700 p-7">
        {/* Step indicator */}
        <div className="flex gap-2 mb-6">
          {[1, 2, 3].map((n) => (
            <div key={n} className={`flex-1 h-1 rounded-full ${step >= n ? 'bg-[#2d6be4]' : 'bg-slate-200 dark:bg-slate-700'}`} />
          ))}
        </div>

        {step === 1 && (
          <div data-testid="onboarding-step-1">
            <div className="flex items-center gap-2 mb-2 text-[#2d6be4]"><Lock className="h-5 w-5" /><span className="text-xs font-semibold uppercase tracking-wider">Step 1 of 3</span></div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-white mb-1">Set a BidVex Password</h1>
            <p className="text-sm text-slate-600 dark:text-slate-300 mb-5">So you can also sign in with email in the future.</p>
            <div className="space-y-3">
              <div>
                <Label htmlFor="pw" className="text-xs">New Password</Label>
                <Input id="pw" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} data-testid="onboarding-password-input" />
              </div>
              <div>
                <Label htmlFor="pwc" className="text-xs">Confirm Password</Label>
                <Input id="pwc" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} data-testid="onboarding-password-confirm-input" />
              </div>
              <p className="text-[11px] text-slate-500">Min 8 chars · 1 uppercase · 1 digit.</p>
            </div>
            <div className="flex items-center justify-between mt-6">
              <Button variant="ghost" onClick={() => setStep(2)} data-testid="onboarding-skip-password-btn">Skip for now</Button>
              <Button
                onClick={() => {
                  if (!validatePassword()) { toast.error('Password too weak or mismatched.'); return; }
                  setStep(2);
                }}
                className="bg-[#2d6be4] hover:bg-[#1a4fc4] text-white"
                data-testid="onboarding-set-password-btn"
              >
                Set Password →
              </Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div data-testid="onboarding-step-2">
            <div className="flex items-center gap-2 mb-2 text-[#2d6be4]"><MapPin className="h-5 w-5" /><span className="text-xs font-semibold uppercase tracking-wider">Step 2 of 3</span></div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-white mb-1">Where are you located?</h1>
            <p className="text-sm text-slate-600 dark:text-slate-300 mb-5">
              {detecting ? <span className="inline-flex items-center gap-1.5"><Loader2 className="h-3.5 w-3.5 animate-spin" />Detecting your location…</span> : (city ? `We detected: ${city}, ${province} ✓` : 'Enter your city to discover nearby auctions.')}
            </p>
            <div className="space-y-3">
              <div>
                <Label className="text-xs">City</Label>
                <Input value={city} onChange={(e) => setCity(e.target.value)} placeholder="Sherbrooke" data-testid="onboarding-city-input" />
              </div>
              <div>
                <Label className="text-xs">Province</Label>
                <Select value={province} onValueChange={setProvince}>
                  <SelectTrigger data-testid="onboarding-province-select"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PROVINCES.map((p) => <SelectItem key={p.code} value={p.code}>{p.en}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Postal Code</Label>
                <Input value={postal} onChange={(e) => setPostal(e.target.value.toUpperCase())} placeholder="J1G 0A8" maxLength={7} data-testid="onboarding-postal-input" />
              </div>
            </div>
            <div className="flex items-center justify-between mt-6">
              <Button variant="ghost" onClick={() => submit(true)} disabled={busy} data-testid="onboarding-skip-location-btn">Skip</Button>
              <Button onClick={() => submit(false)} disabled={busy} className="bg-[#2d6be4] hover:bg-[#1a4fc4] text-white" data-testid="onboarding-confirm-location-btn">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Confirm Location →'}
              </Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="text-center" data-testid="onboarding-step-3">
            <PartyPopper className="h-12 w-12 text-[#f6c90e] mx-auto mb-3" />
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">You're all set!</h1>
            <p className="text-sm text-slate-600 dark:text-slate-300 mb-6">Welcome to BidVex. Start exploring auctions.</p>
            <Button onClick={() => navigate('/marketplace')} className="w-full h-11 bg-[#2d6be4] hover:bg-[#1a4fc4] text-white text-sm font-bold" data-testid="onboarding-go-to-marketplace-btn">
              Go to Marketplace
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
