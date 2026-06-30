/**
 * iter323 — Contractor dashboard add-ons:
 *   • Extension card (prominent display of "Your Extension: 1220 — share this with clients")
 *   • Personal phone number editor (E.164)
 *   • Profile photo upload (reuses S3 image pipeline)
 *   • Inbound call log (date/time, duration, outcome)
 *   • Leaderboard (rank, name, photo, overlay rate %, trend) — caller highlighted
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Phone, PhoneIncoming, Camera, Trophy, ArrowUp, ArrowDown, Minus,
  Loader2, Save, Copy, CheckCircle2, X,
} from 'lucide-react';
import API_BASE from '../../config';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';

const E164_RE = /^\+[1-9]\d{6,14}$/;

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function initials(name) {
  if (!name) return 'BP';
  const parts = String(name).trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase()).join('') || 'BP';
}

function ProfileAvatar({ photoUrl, name, size = 48 }) {
  if (photoUrl) {
    return (
      <img
        src={photoUrl}
        alt={name || 'profile'}
        className="rounded-full object-cover ring-2 ring-white shadow"
        style={{ width: size, height: size }}
        data-testid="contractor-profile-avatar"
      />
    );
  }
  return (
    <div
      className="rounded-full flex items-center justify-center font-bold text-white bg-gradient-to-br from-indigo-500 to-rose-500 ring-2 ring-white shadow"
      style={{ width: size, height: size, fontSize: size * 0.4 }}
      data-testid="contractor-profile-avatar-placeholder"
    >
      {initials(name)}
    </div>
  );
}

// ─── Extension card ──────────────────────────────────────────────────────

function ExtensionCard({ profile, fr }) {
  const [copied, setCopied] = useState(false);
  if (!profile) return null;
  const ext = profile.extension_number;
  const shareText = fr
    ? `+1 (450) 634-3099 poste ${ext}`
    : `+1 (450) 634-3099 ext. ${ext}`;
  const doCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareText);
      setCopied(true);
      toast.success(fr ? 'Copié !' : 'Copied!');
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error(fr ? 'Impossible de copier' : 'Could not copy');
    }
  };
  return (
    <Card
      className="border-2 border-emerald-300 bg-gradient-to-br from-emerald-50 to-sky-50"
      data-testid="contractor-extension-card"
    >
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-emerald-700 font-bold">
              {fr ? 'Votre poste BidVex' : 'Your BidVex Extension'}
            </p>
            <p
              className="text-4xl font-extrabold text-emerald-700 mt-1 tracking-wider"
              data-testid="contractor-extension-number"
            >
              {ext || (fr ? '— en attente —' : '— pending —')}
            </p>
          </div>
          <Phone className="h-12 w-12 text-emerald-400" />
        </div>
        <p className="text-[13px] text-slate-700 mt-3">
          {fr
            ? `Partagez ce numéro avec vos clients afin qu'ils puissent vous joindre directement.`
            : `Share this number with your clients so they can reach you directly.`}
        </p>
        <div className="mt-3 flex items-center gap-2 bg-white rounded-md p-2 border border-emerald-200">
          <span className="font-mono text-sm flex-1" data-testid="contractor-extension-share-text">
            {shareText}
          </span>
          <Button
            size="sm"
            variant="outline"
            onClick={doCopy}
            disabled={!ext}
            data-testid="contractor-extension-copy-btn"
          >
            {copied ? <CheckCircle2 className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
            {copied ? (fr ? 'Copié' : 'Copied') : (fr ? 'Copier' : 'Copy')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Profile (photo + personal phone) ────────────────────────────────────

function ProfileEditorCard({ profile, token, fr, onChange }) {
  const [photoUploading, setPhotoUploading] = useState(false);
  const [phone, setPhone] = useState(profile?.personal_phone_number || '');
  const [savingPhone, setSavingPhone] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    setPhone(profile?.personal_phone_number || '');
  }, [profile?.personal_phone_number]);

  const photoChangeHandler = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast.error(fr ? 'Image trop volumineuse (max 5 Mo).' : 'Image too large (max 5MB).');
      return;
    }
    setPhotoUploading(true);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await axios.post(`${API_BASE}/twilio/contractor/profile/photo`, fd, {
        headers: { ...authHeaders(token), 'Content-Type': 'multipart/form-data' },
      });
      toast.success(fr ? 'Photo téléversée !' : 'Photo uploaded!');
      onChange?.({ ...profile, profile_photo_url: r.data?.profile_photo_url });
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(d?.message_en || (fr ? 'Échec du téléversement' : 'Upload failed'));
    } finally {
      setPhotoUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const savePhone = async () => {
    const trimmed = phone.trim();
    if (!E164_RE.test(trimmed)) {
      toast.error(fr
        ? "Format E.164 requis (ex. +14501234567)."
        : "E.164 format required (e.g. +14501234567).");
      return;
    }
    setSavingPhone(true);
    try {
      const r = await axios.patch(
        `${API_BASE}/twilio/contractor/profile/me`,
        { personal_phone_number: trimmed },
        { headers: authHeaders(token) },
      );
      onChange?.(r.data);
      toast.success(fr ? 'Téléphone enregistré' : 'Phone saved');
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(d?.message_en || (fr ? 'Échec' : 'Save failed'));
    } finally {
      setSavingPhone(false);
    }
  };

  return (
    <Card data-testid="contractor-profile-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Camera className="h-4 w-4" />
          {fr ? 'Mon profil' : 'My Profile'}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-4">
          <ProfileAvatar photoUrl={profile?.profile_photo_url} name={profile?.name} size={72} />
          <div className="flex-1">
            <div className="font-semibold text-base">{profile?.name || profile?.email}</div>
            <div className="text-xs text-slate-500">{profile?.email}</div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={photoChangeHandler}
              className="hidden"
              data-testid="contractor-photo-input"
            />
            <Button
              size="sm"
              variant="outline"
              className="mt-2"
              onClick={() => fileInputRef.current?.click()}
              disabled={photoUploading}
              data-testid="contractor-photo-upload-btn"
            >
              {photoUploading
                ? <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                : <Camera className="h-3 w-3 mr-1" />}
              {fr ? 'Téléverser une photo de profil' : 'Upload Profile Photo'}
            </Button>
          </div>
        </div>

        <div>
          <label className="text-xs uppercase tracking-wide text-slate-500 font-semibold">
            {fr ? 'Téléphone personnel (E.164)' : 'Personal Phone (E.164)'}
          </label>
          <p className="text-[11px] text-slate-500 mb-1">
            {fr
              ? "Les appels entrants à votre poste seront transférés ici."
              : "Inbound calls to your extension will forward to this number."}
          </p>
          <div className="flex gap-2">
            <Input
              type="tel"
              placeholder="+14506343099"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="flex-1 font-mono"
              data-testid="contractor-personal-phone-input"
            />
            <Button
              onClick={savePhone}
              disabled={savingPhone || !phone.trim()}
              data-testid="contractor-personal-phone-save-btn"
            >
              {savingPhone ? <Loader2 className="h-3 w-3 mr-1 animate-spin" /> : <Save className="h-3 w-3 mr-1" />}
              {fr ? 'Enregistrer' : 'Save'}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Leaderboard ─────────────────────────────────────────────────────────

function LeaderboardCard({ token, fr }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(
          `${API_BASE}/twilio/contractor/leaderboard`,
          { headers: authHeaders(token) },
        );
        if (!cancelled) setRows(r.data?.rows || []);
      } catch {
        if (!cancelled) setRows([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  return (
    <Card data-testid="contractor-leaderboard-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Trophy className="h-4 w-4 text-amber-500" />
          {fr ? 'Classement des partenaires' : 'Partner Leaderboard'}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="text-xs text-slate-500 py-4 text-center">
            {fr ? 'Chargement…' : 'Loading…'}
          </div>
        ) : rows.length === 0 ? (
          <div className="text-xs text-slate-500 py-4 text-center">
            {fr ? 'Aucun partenaire actif pour le moment.' : 'No active partners yet.'}
          </div>
        ) : (
          <div className="space-y-2" data-testid="contractor-leaderboard-rows">
            {rows.map((r) => {
              const trendIcon = r.trend === '▲'
                ? <ArrowUp className="h-3 w-3 text-emerald-600" />
                : r.trend === '▼'
                ? <ArrowDown className="h-3 w-3 text-rose-600" />
                : <Minus className="h-3 w-3 text-slate-400" />;
              return (
                <div
                  key={`${r.rank}-${r.display_name}`}
                  className={`flex items-center gap-3 rounded-lg p-2 transition ${
                    r.is_self
                      ? 'bg-amber-50 ring-2 ring-amber-300'
                      : 'bg-slate-50 hover:bg-slate-100'
                  }`}
                  data-testid={r.is_self ? 'contractor-leaderboard-self-row' : `contractor-leaderboard-row-${r.rank}`}
                >
                  <span className="font-bold text-slate-500 w-6 text-center">#{r.rank}</span>
                  <ProfileAvatar photoUrl={r.profile_photo_url} name={r.display_name} size={36} />
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-sm truncate">
                      {r.display_name}
                      {r.is_self && (
                        <Badge variant="outline" className="ml-2 text-[9px] uppercase">
                          {fr ? 'Moi' : 'You'}
                        </Badge>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      ext. {r.extension_number || '—'} · {fr ? 'Volume' : 'Volume'}: {r.weekly_volume_score}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold text-emerald-600">
                      {Number(r.leaderboard_overlay_rate * 100).toFixed(2)}%
                    </div>
                    <div className="flex items-center justify-end gap-1 text-[10px] text-slate-500">
                      {trendIcon}
                      <span>{fr ? 'tendance' : 'trend'}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <p className="text-[10px] text-slate-400 mt-3 italic">
          {fr
            ? 'Les revenus en dollars restent privés. Seuls le rang, le nom, la photo et le % de bonification sont partagés.'
            : 'Dollar earnings stay private. Only rank, name, photo, and overlay rate % are shared.'}
        </p>
      </CardContent>
    </Card>
  );
}

// ─── Inbound calls log ───────────────────────────────────────────────────

function InboundCallLogCard({ token, fr }) {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(
          `${API_BASE}/twilio/contractor/inbound-calls?limit=20`,
          { headers: authHeaders(token) },
        );
        if (!cancelled) setCalls(r.data?.items || []);
      } catch {
        if (!cancelled) setCalls([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
  }, [token]);

  return (
    <Card data-testid="contractor-inbound-calls-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <PhoneIncoming className="h-4 w-4 text-indigo-600" />
          {fr ? 'Appels entrants reçus à votre poste' : 'Inbound Calls to Your Extension'}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="text-xs text-slate-500 py-4 text-center">{fr ? 'Chargement…' : 'Loading…'}</div>
        ) : calls.length === 0 ? (
          <div className="text-xs text-slate-500 py-4 text-center">
            {fr ? 'Aucun appel entrant pour le moment.' : 'No inbound calls yet.'}
          </div>
        ) : (
          <ul className="divide-y text-sm" data-testid="contractor-inbound-calls-rows">
            {calls.map((c) => {
              const outcomeColor = c.outcome === 'answered'
                ? 'text-emerald-600'
                : c.outcome === 'missed' || c.outcome === 'no-answer'
                ? 'text-rose-600'
                : 'text-slate-500';
              return (
                <li key={c.id || c.call_sid} className="py-2 flex items-center gap-3">
                  <PhoneIncoming className={`h-4 w-4 ${outcomeColor}`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[12px] text-slate-700">
                      {(c.started_at || '').slice(0, 19).replace('T', ' ')}
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono truncate">
                      {c.from_number || '—'} · ext. {c.extension_dialed || '—'}
                    </div>
                  </div>
                  <div className={`text-[12px] font-semibold ${outcomeColor}`}>
                    {c.outcome || c.status || '—'}
                  </div>
                  {Number.isFinite(c.duration_seconds) && c.duration_seconds > 0 && (
                    <div className="text-[10px] text-slate-400 ml-2">
                      {Math.floor(c.duration_seconds / 60)}m {c.duration_seconds % 60}s
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Wrapper exposed to ContractorDashboard ──────────────────────────────

export default function ContractorIter323Panel({ token, fr }) {
  const [profile, setProfile] = useState(null);

  const refreshProfile = useCallback(async () => {
    if (!token) return;
    try {
      const r = await axios.get(`${API_BASE}/twilio/contractor/profile/me`, {
        headers: authHeaders(token),
      });
      setProfile(r.data);
    } catch { /* noop */ }
  }, [token]);

  useEffect(() => { refreshProfile(); }, [refreshProfile]);

  return (
    <div className="space-y-4" data-testid="contractor-iter323-panel">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ExtensionCard profile={profile} fr={fr} />
        <ProfileEditorCard
          profile={profile}
          token={token}
          fr={fr}
          onChange={setProfile}
        />
      </div>
      <LeaderboardCard token={token} fr={fr} />
      <InboundCallLogCard token={token} fr={fr} />
    </div>
  );
}
