import { extractErrorMessage } from '../../utils/errorHandler';
/**
 * iter334 — Admin AI Voice Calls console
 *
 * Lists BidVex AI Assistant calls (transcripts only — no audio storage).
 * Each row expands into the full speaker-labelled transcript on click.
 *
 * Endpoints:
 *   GET /api/admin/ai-voice/calls            → list summaries
 *   GET /api/admin/ai-voice/calls/{call_sid} → full transcript
 */
import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  PhoneCall, Loader2, Bot, User as UserIcon, ChevronDown, ChevronUp,
  RefreshCw, Clock, ArrowRightLeft, MessageSquare,
} from 'lucide-react';
import API_BASE from '../../config';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';

function fmtDuration(sec) {
  if (!sec && sec !== 0) return '—';
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${String(s).padStart(2, '0')}s`;
}

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function TranscriptView({ callSid, token }) {
  const [full, setFull] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const r = await axios.get(`${API_BASE}/admin/ai-voice/calls/${callSid}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!cancelled) setFull(r.data);
      } catch (e) {
        if (!cancelled) toast.error(`Failed to load transcript: ${extractErrorMessage(e) || e?.message}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [callSid, token]);

  if (loading) {
    return <div className="p-4 flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" /> Loading transcript…</div>;
  }
  if (!full) return null;
  const turns = full.transcript || [];
  if (turns.length === 0) {
    return <div className="p-4 text-sm text-slate-500">No transcript rows persisted for this call.</div>;
  }
  return (
    <div className="p-4 space-y-2 bg-slate-50 border-t" data-testid={`ai-voice-transcript-${callSid}`}>
      {turns.map((t, i) => (
        <div
          key={i}
          className={`flex gap-2 ${t.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          {t.role === 'assistant' && (
            <div className="w-6 h-6 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0">
              <Bot className="h-3 w-3 text-indigo-700" />
            </div>
          )}
          <div
            className={`max-w-[80%] rounded-xl px-3 py-2 text-sm ${
              t.role === 'user'
                ? 'bg-indigo-600 text-white'
                : 'bg-white border border-slate-200 text-slate-800'
            }`}
          >
            <div className="whitespace-pre-wrap">{t.text}</div>
            {t.ts && <div className="text-[10px] opacity-60 mt-0.5">{fmtDate(t.ts)}</div>}
          </div>
          {t.role === 'user' && (
            <div className="w-6 h-6 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0">
              <UserIcon className="h-3 w-3 text-slate-600" />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function AdminAIVoiceCalls() {
  const { token } = useAuth();
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/admin/ai-voice/calls?limit=100`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCalls(r.data?.calls || []);
    } catch (e) {
      toast.error(`Failed to load AI calls: ${extractErrorMessage(e) || e?.message}`);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const statusColor = (s) => {
    if (!s) return 'bg-slate-100 text-slate-700';
    if (s.startsWith('ended_transfer')) return 'bg-amber-100 text-amber-800 border-amber-300';
    if (s.startsWith('ended_time_limit')) return 'bg-rose-100 text-rose-800 border-rose-300';
    if (s.startsWith('ended_silence')) return 'bg-slate-100 text-slate-700';
    if (s.startsWith('ended_gemini_error')) return 'bg-rose-100 text-rose-800 border-rose-300';
    if (s.startsWith('ended')) return 'bg-emerald-100 text-emerald-800 border-emerald-300';
    return 'bg-indigo-100 text-indigo-800';
  };

  return (
    <div className="space-y-4" data-testid="admin-ai-voice-calls">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
            <PhoneCall className="h-6 w-6 text-indigo-600" />
            AI Voice Assistant — Calls
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Bilingual BidVex AI Assistant (Gemini Live). Transcripts only — no audio storage.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={load}
          disabled={loading}
          data-testid="ai-voice-refresh-btn"
        >
          {loading ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />}
          Refresh
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          <span>Loading…</span>
        </div>
      ) : calls.length === 0 ? (
        <Card data-testid="ai-voice-empty">
          <CardContent className="p-8 text-center text-slate-500">
            <MessageSquare className="w-10 h-10 mx-auto mb-3 text-slate-400" />
            <p>No AI Assistant calls yet. Callers who press 9 on the IVR will show up here.</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="ai-voice-table">
                <thead className="bg-slate-50">
                  <tr className="text-xs text-slate-500 text-left border-b">
                    <th className="px-4 py-3">Call SID</th>
                    <th className="px-4 py-3">From</th>
                    <th className="px-4 py-3">Lang</th>
                    <th className="px-4 py-3">Started</th>
                    <th className="px-4 py-3">Duration</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Handoff</th>
                    <th className="px-4 py-3">Summary</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {calls.map((c) => {
                    const isOpen = expanded === c.call_sid;
                    return (
                      <React.Fragment key={c.call_sid}>
                        <tr className="border-b last:border-b-0 hover:bg-slate-50" data-testid={`ai-voice-row-${c.call_sid}`}>
                          <td className="px-4 py-3 font-mono text-xs text-slate-700">{(c.call_sid || '').slice(0, 12)}…</td>
                          <td className="px-4 py-3 text-xs">{c.from_number || '—'}</td>
                          <td className="px-4 py-3">
                            <Badge variant="outline">{(c.lang_final || c.lang || '?').toUpperCase()}</Badge>
                          </td>
                          <td className="px-4 py-3 text-xs">{fmtDate(c.started_at)}</td>
                          <td className="px-4 py-3 text-xs flex items-center gap-1">
                            <Clock className="h-3 w-3" /> {fmtDuration(c.duration_seconds)}
                          </td>
                          <td className="px-4 py-3">
                            <Badge className={statusColor(c.status)}>{c.status || 'in_progress'}</Badge>
                          </td>
                          <td className="px-4 py-3">
                            {c.handoff === 'transfer_to_support' ? (
                              <Badge className="bg-amber-100 text-amber-800 border-amber-300 flex items-center gap-1 w-max">
                                <ArrowRightLeft className="h-3 w-3" /> Support
                              </Badge>
                            ) : (
                              <span className="text-xs text-slate-400">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-600 max-w-xs">
                            <div className="truncate">{c.summary || '—'}</div>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setExpanded(isOpen ? null : c.call_sid)}
                              data-testid={`ai-voice-toggle-${c.call_sid}`}
                            >
                              {isOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                            </Button>
                          </td>
                        </tr>
                        {isOpen && (
                          <tr>
                            <td colSpan={9} className="p-0">
                              <TranscriptView callSid={c.call_sid} token={token} />
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
