/**
 * VehicleComingSoonPage — iter176
 * =================================
 * Branded "Coming Soon" for /vehicle-auctions when the feature flag
 * `vehicle_auctions_enabled` is false.
 *
 * Bill 96: every visible label, button, teaser pill shows EN + FR.
 * Fully responsive (centered max-w-2xl, inputs stack on mobile).
 */
import React, { useState } from 'react';

import axios from 'axios';
import API_BASE from '../../config';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';
import {
  Loader2, Mail, CheckCircle2, Car, ShieldCheck, Zap, ArrowLeft,
} from 'lucide-react';
import { LangLink } from '../../components/LangLink';

const API = API_BASE;

const VehicleComingSoonPage = () => {
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [lang, setLang] = useState('en'); // user-chosen language preference for the email, just client-side

  const handleSubmit = async (e) => {
    e?.preventDefault();
    const v = (email || '').trim().toLowerCase();
    if (!v || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) {
      toast.error('Please enter a valid email · Veuillez entrer une adresse valide');
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/waitlist/vehicle-auctions`, { email: v, lang });
      setDone(true);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Signup failed · Échec de l\'inscription');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      data-testid="vehicle-coming-soon-page"
      className="min-h-screen flex flex-col items-center justify-center py-12 px-4 sm:px-8 relative overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%)' }}
    >
      {/* Animated floating orbs behind content */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden>
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-blue-500/10 blur-3xl animate-pulse" />
        <div className="absolute -bottom-24 -right-24 w-96 h-96 rounded-full bg-cyan-400/10 blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      </div>

      <div className="relative z-10 w-full max-w-2xl text-center text-white">
        {/* Logo */}
        <LangLink to="/" className="inline-block mb-8" data-testid="vehicle-coming-soon-logo-link">
          <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur rounded-xl px-4 py-2 border border-white/20">
            <span className="text-2xl font-black tracking-tight bg-gradient-to-r from-cyan-300 to-blue-300 bg-clip-text text-transparent">BidVex</span>
          </div>
        </LangLink>

        {/* Floating car illustration */}
        <div className="mb-8 flex justify-center" aria-hidden>
          <div
            className="relative inline-flex items-center justify-center"
            style={{ animation: 'coming-soon-float 3s ease-in-out infinite' }}
          >
            <div className="absolute inset-0 rounded-full bg-cyan-400/20 blur-2xl" />
            <div className="relative h-28 w-28 sm:h-36 sm:w-36 rounded-full bg-white/5 border-2 border-cyan-400/40 flex items-center justify-center">
              <Car className="h-14 w-14 sm:h-20 sm:w-20 text-cyan-300" strokeWidth={1.5} />
            </div>
          </div>
        </div>

        {/* Headlines */}
        <h1 className="text-3xl sm:text-5xl font-black tracking-tight leading-tight mb-2">
          Vehicle Auctions — Coming Soon
        </h1>
        <p className="text-lg sm:text-2xl font-bold text-cyan-300 italic mb-6">
          Enchères de véhicules — Bientôt disponible
        </p>

        <p className="text-sm sm:text-base text-blue-100/90 leading-relaxed mb-2 max-w-xl mx-auto">
          We're building something powerful. Be the first to know when vehicle auctions go live.
        </p>
        <p className="text-sm sm:text-base text-blue-200/80 italic leading-relaxed mb-8 max-w-xl mx-auto">
          Nous construisons quelque chose de puissant. Soyez le premier informé du lancement des enchères de véhicules.
        </p>

        {/* Waitlist form / success */}
        {done ? (
          <div
            data-testid="vehicle-waitlist-success"
            className="rounded-2xl bg-emerald-500/10 border border-emerald-400/40 p-6 sm:p-8 max-w-md mx-auto backdrop-blur"
          >
            <CheckCircle2 className="h-10 w-10 text-emerald-300 mx-auto mb-3" />
            <p className="font-bold text-emerald-100 mb-1">You're on the list! We'll email you at launch.</p>
            <p className="italic text-emerald-200/80 text-sm">Vous êtes sur la liste ! Nous vous enverrons un courriel au lancement.</p>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="max-w-md mx-auto flex flex-col sm:flex-row gap-3 items-stretch"
            data-testid="vehicle-waitlist-form"
          >
            <div className="flex-1 relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-blue-300/70" />
              <Input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                disabled={submitting}
                className="pl-9 h-12 bg-white/10 border-white/20 text-white placeholder:text-blue-200/50 rounded-full"
                data-testid="vehicle-waitlist-email-input"
              />
            </div>
            <Button
              type="submit"
              disabled={submitting}
              className="h-12 px-6 rounded-full bg-blue-600 hover:bg-blue-500 text-white font-bold transition-shadow hover:shadow-[0_0_24px_rgba(59,130,246,0.5)]"
              data-testid="vehicle-waitlist-submit-btn"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
              Notify Me · Me notifier
            </Button>
          </form>
        )}

        {/* Language choice nudge (tiny) */}
        {!done && (
          <div className="mt-3 text-xs text-blue-200/70 flex items-center justify-center gap-3">
            <span>Preferred email language · Langue préférée :</span>
            {['en', 'fr'].map((L) => (
              <button
                key={L}
                type="button"
                onClick={() => setLang(L)}
                className={`px-2 py-0.5 rounded-full uppercase text-[10px] font-bold tracking-wide transition ${
                  lang === L
                    ? 'bg-cyan-400 text-slate-900'
                    : 'bg-white/10 text-blue-100 hover:bg-white/20'
                }`}
                data-testid={`vehicle-waitlist-lang-${L}`}
              >
                {L}
              </button>
            ))}
          </div>
        )}

        {/* Teaser feature pills */}
        <div className="mt-10 sm:mt-14 grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-2xl mx-auto">
          {[
            { Icon: Car, en: 'Cars, trucks & motorcycles', fr: 'Voitures, camions & motos' },
            { Icon: ShieldCheck, en: 'Verified sellers only', fr: 'Vendeurs vérifiés uniquement' },
            { Icon: Zap, en: 'Real-time bidding', fr: 'Enchères en temps réel' },
          ].map((pill, i) => (
            <div
              key={pill.en}
              data-testid={`vehicle-waitlist-teaser-${i}`}
              className="rounded-2xl bg-white/5 border border-white/10 backdrop-blur px-4 py-4 text-left"
            >
              <pill.Icon className="h-5 w-5 text-cyan-300 mb-2" />
              <p className="text-sm font-semibold text-white">{pill.en}</p>
              <p className="text-xs italic text-blue-200/80 mt-0.5">{pill.fr}</p>
            </div>
          ))}
        </div>

        {/* Back link */}
        <div className="mt-10 text-xs text-blue-200/70">
          <LangLink to="/" className="inline-flex items-center gap-1 hover:text-white transition" data-testid="vehicle-coming-soon-back-home">
            <ArrowLeft className="h-3 w-3" />
            Back to BidVex · Retour à BidVex
          </LangLink>
        </div>
      </div>

      <style>{`
        @keyframes coming-soon-float {
          0%, 100% { transform: translateY(0); }
          50%      { transform: translateY(-12px); }
        }
      `}</style>
    </div>
  );
};

export default VehicleComingSoonPage;
