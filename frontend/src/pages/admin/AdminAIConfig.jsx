/**
 * iter497 — Admin BidVex Gemini System-Instruction Editor
 * =======================================================
 *
 * Backed by:
 *   GET  /api/admin/ai-config/system-instruction
 *   PUT  /api/admin/ai-config/system-instruction
 *
 * The system instruction drives every Gemini call in the platform
 * (Watchdog, streaming chat, listing assistants). Persisting to
 * MongoDB (`db.ai_config`) lets Ops edit AI behavior without a code
 * deployment, and the backend snapshots the previous version into
 * `db.ai_config_history` for CRA-style traceability.
 *
 * UI conventions match the other admin pages:
 *   • Uses shadcn/ui primitives from `../../components/ui/*`.
 *   • Reads the auth token from AuthContext (bearer JWT).
 *   • Every interactive element carries a data-testid for E2E tests.
 *   • Bilingual copy uses fallbacks so untranslated keys still read cleanly.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { useAuth } from '../../contexts/AuthContext';
import API_BASE from '../../config';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '../../components/ui/alert';
import { toast } from 'sonner';
import { AlertTriangle, Loader2, RefreshCcw, Save, Undo2 } from 'lucide-react';

const API = API_BASE;

const formatDate = (iso, locale) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(locale, {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  } catch (_e) {
    return iso;
  }
};

const AdminAIConfig = () => {
  const { t, i18n } = useTranslation();
  const { token, user } = useAuth();
  const locale = i18n.language?.startsWith('fr') ? 'fr-CA' : 'en-CA';

  const [loading, setLoading]   = useState(true);
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState(null);
  const [current, setCurrent]   = useState(null);   // full response from GET
  const [draft, setDraft]       = useState('');
  const [showDiff, setShowDiff] = useState(false);

  const authHeaders = useMemo(() => (
    token ? { Authorization: `Bearer ${token}` } : {}
  ), [token]);

  const roleOK = useMemo(() => {
    const r = (user?.role || '').toLowerCase();
    return r === 'admin' || r === 'super_admin';
  }, [user]);

  const dirty = current && draft !== current.value;

  const fetchCurrent = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(
        `${API}/admin/ai-config/system-instruction`,
        { headers: authHeaders },
      );
      setCurrent(res.data);
      setDraft(res.data?.value || '');
    } catch (e) {
      const status = e?.response?.status;
      if (status === 401 || status === 403) {
        setError(t('adminAIConfig.loadErrorAuth', 'You do not have permission to view the AI config.'));
      } else {
        setError(t('adminAIConfig.loadError', 'Could not load the current system instruction. Please retry.'));
      }
    } finally {
      setLoading(false);
    }
  }, [authHeaders, t]);

  useEffect(() => {
    if (roleOK) fetchCurrent();
    else setLoading(false);
  }, [fetchCurrent, roleOK]);

  const handleSave = async () => {
    if (!draft || !draft.trim()) {
      toast.error(t('adminAIConfig.emptyValueError', 'System instruction cannot be empty.'));
      return;
    }
    if (draft.length > 200000) {
      toast.error(t('adminAIConfig.tooLargeError', 'System instruction exceeds the 200,000 character ceiling.'));
      return;
    }
    setSaving(true);
    try {
      const res = await axios.put(
        `${API}/admin/ai-config/system-instruction`,
        { value: draft },
        { headers: { ...authHeaders, 'Content-Type': 'application/json' } },
      );
      setCurrent(res.data);
      setDraft(res.data?.value || '');
      toast.success(t('adminAIConfig.saveSuccess', 'System instruction updated. Live Gemini calls now use the new prompt.'));
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : (detail?.message_en || detail?.[0]?.msg || 'Save failed.');
      toast.error(t('adminAIConfig.saveError', 'Save failed: {{msg}}', { msg }));
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (!current) return;
    setDraft(current.value || '');
    toast.info(t('adminAIConfig.resetDraft', 'Draft reverted to the currently saved value.'));
  };

  if (!roleOK) {
    return (
      <div className="max-w-3xl mx-auto p-8" data-testid="ai-config-forbidden">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>{t('adminAIConfig.forbiddenTitle', 'Admins only')}</AlertTitle>
          <AlertDescription>
            {t('adminAIConfig.forbiddenBody', 'This tool edits the BidVex AI system instruction. Only administrators can access it.')}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8" data-testid="admin-ai-config-page">
      <div className="flex flex-col gap-2 mb-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900" data-testid="ai-config-heading">
              {t('adminAIConfig.title', 'BidVex Gemini — System Instruction')}
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              {t('adminAIConfig.subtitle', 'Live-edit the prompt that governs every Gemini 2.5 Flash call across the platform. Changes are persisted to db.ai_config and take effect within seconds.')}
            </p>
          </div>
          <Button
            variant="outline"
            onClick={fetchCurrent}
            disabled={loading}
            data-testid="ai-config-refresh-btn"
          >
            {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCcw className="h-4 w-4 mr-2" />}
            {t('adminAIConfig.refresh', 'Refresh')}
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6" data-testid="ai-config-error">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>{t('adminAIConfig.errorTitle', 'Something went wrong')}</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className="mb-6" data-testid="ai-config-metadata-card">
        <CardHeader>
          <CardTitle className="text-base font-semibold">
            {t('adminAIConfig.metadataTitle', 'Currently active')}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-slate-500 mb-1">{t('adminAIConfig.charCount', 'Characters')}</div>
            <div className="font-mono text-slate-900" data-testid="ai-config-char-count">
              {current?.char_count?.toLocaleString(locale) ?? '—'}
            </div>
          </div>
          <div>
            <div className="text-slate-500 mb-1">{t('adminAIConfig.source', 'Source')}</div>
            <div data-testid="ai-config-source">
              <Badge className={current?.source === 'admin_edit'
                ? 'bg-emerald-100 text-emerald-900'
                : 'bg-slate-100 text-slate-700'}>
                {current?.source || '—'}
              </Badge>
            </div>
          </div>
          <div>
            <div className="text-slate-500 mb-1">{t('adminAIConfig.updatedAt', 'Updated at')}</div>
            <div className="text-slate-900" data-testid="ai-config-updated-at">
              {formatDate(current?.updated_at, locale)}
            </div>
          </div>
          {current?.updated_by_user_id ? (
            <div className="sm:col-span-3">
              <div className="text-slate-500 mb-1">{t('adminAIConfig.updatedBy', 'Updated by (user id)')}</div>
              <div className="font-mono text-xs text-slate-700 break-all" data-testid="ai-config-updated-by">
                {current.updated_by_user_id}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            {t('adminAIConfig.editorTitle', 'Prompt editor')}
            {dirty && (
              <Badge className="bg-amber-100 text-amber-900" data-testid="ai-config-dirty-badge">
                {t('adminAIConfig.unsaved', 'Unsaved changes')}
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="font-mono text-xs min-h-[520px] leading-relaxed"
            placeholder={t('adminAIConfig.placeholder', 'System instruction text…')}
            data-testid="ai-config-editor"
            disabled={loading || saving}
          />
          <div className="mt-2 text-xs text-slate-500 flex items-center gap-4 flex-wrap">
            <span data-testid="ai-config-draft-count">
              {t('adminAIConfig.draftCount', '{{n}} characters', { n: (draft?.length || 0).toLocaleString(locale) })}
            </span>
            <span>
              {t('adminAIConfig.ceilingNote', 'Max 200,000 characters — larger payloads are rejected.')}
            </span>
          </div>

          <div className="mt-6 flex items-center gap-3 flex-wrap">
            <Button
              onClick={handleSave}
              disabled={loading || saving || !dirty}
              data-testid="ai-config-save-btn"
              className="bg-slate-900 hover:bg-slate-800 text-white"
            >
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
              {t('adminAIConfig.save', 'Save & apply live')}
            </Button>
            <Button
              variant="outline"
              onClick={handleReset}
              disabled={loading || saving || !dirty}
              data-testid="ai-config-reset-btn"
            >
              <Undo2 className="h-4 w-4 mr-2" />
              {t('adminAIConfig.reset', 'Revert to saved')}
            </Button>
            <Button
              variant="ghost"
              onClick={() => setShowDiff((s) => !s)}
              disabled={!dirty}
              data-testid="ai-config-toggle-diff-btn"
            >
              {showDiff ? t('adminAIConfig.hideDiff', 'Hide diff') : t('adminAIConfig.showDiff', 'Show diff preview')}
            </Button>
          </div>

          {showDiff && dirty && (
            <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="ai-config-diff-preview">
              <div>
                <div className="text-xs font-semibold text-slate-500 mb-1">
                  {t('adminAIConfig.diffCurrent', 'Currently saved')}
                </div>
                <pre className="bg-slate-50 border border-slate-200 rounded-md p-3 text-[11px] leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
{current?.value || ''}
                </pre>
              </div>
              <div>
                <div className="text-xs font-semibold text-slate-500 mb-1">
                  {t('adminAIConfig.diffDraft', 'Your draft')}
                </div>
                <pre className="bg-emerald-50 border border-emerald-200 rounded-md p-3 text-[11px] leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
{draft}
                </pre>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Alert className="border-slate-200 bg-slate-50" data-testid="ai-config-guardrail-note">
        <AlertTriangle className="h-4 w-4 text-amber-600" />
        <AlertTitle>{t('adminAIConfig.guardrailsTitle', 'Guardrails')}</AlertTitle>
        <AlertDescription className="text-slate-600">
          {t('adminAIConfig.guardrailsBody', 'Every save writes a snapshot of the previous value to db.ai_config_history for audit. The Gemini in-memory cache is invalidated immediately so live traffic uses the new prompt within seconds.')}
        </AlertDescription>
      </Alert>
    </div>
  );
};

export default AdminAIConfig;
