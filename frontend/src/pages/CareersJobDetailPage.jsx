/**
 * iter318 — BidVex Careers job detail + multi-step application form.
 *
 * Route: /careers/:job_id
 * Public — no auth required.
 *
 * Adapts dynamically to the job's `required_inputs`:
 *   • Step 2 (Questions) is HIDDEN when no custom_text_fields and no
 *     custom_date_fields exist.
 *   • Step 3 (Documents) is HIDDEN when every `requires_*` is false.
 *
 * Submits to POST /api/careers/jobs/:job_id/apply as multipart/form-data.
 */
import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  Loader2, MapPin, DollarSign, Briefcase, FileUp, ArrowLeft, ArrowRight,
  CheckCircle2, AlertTriangle,
} from 'lucide-react';

import API_BASE from '../config';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';

const PROVINCES = [
  'AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT',
];

const CV_MAX = 5 * 1024 * 1024;
const COVER_MAX = 5 * 1024 * 1024;
const PHOTO_MAX = 3 * 1024 * 1024;
const CERT_MAX = 5 * 1024 * 1024;
const MAX_PHOTOS = 5;
const MAX_CERTS = 3;

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const ACCEPT_DOC = '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document';
const ACCEPT_IMG = '.jpg,.jpeg,.png,image/jpeg,image/png';
const ACCEPT_PDF = '.pdf,application/pdf';

export default function CareersJobDetailPage() {
  const { job_id: jobId } = useParams();
  const navigate = useNavigate();

  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    first_name: '', last_name: '', email: '', phone: '',
    province: '', preferred_language: 'en',
  });
  const [customResponses, setCustomResponses] = useState({});
  const [files, setFiles] = useState({
    cv: null, cover_letter: null, photos: [], certifications: [],
  });
  const [fieldErrors, setFieldErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(null);
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API_BASE}/careers/jobs/${jobId}`);
        if (!cancelled) {
          setJob(r.data);
          setForm((s) => ({ ...s, preferred_language: s.preferred_language || 'en' }));
        }
      } catch (e) {
        if (!cancelled) setLoadError(e?.response?.data?.detail || 'Job not found');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [jobId]);

  const req = job?.required_inputs || {};
  const hasCustomFields = useMemo(
    () => (req.custom_text_fields || []).length > 0 || (req.custom_date_fields || []).length > 0,
    [req],
  );
  const hasFileFields = useMemo(
    () => req.requires_cv || req.requires_cover_letter
        || req.requires_photos || req.requires_certifications,
    [req],
  );
  const totalSteps = 1 + (hasCustomFields ? 1 : 0) + (hasFileFields ? 1 : 0);
  const stepLabel = (idx) => {
    if (idx === 1) return 'Your Information / Vos informations';
    if (idx === 2 && hasCustomFields) return 'Questions';
    return 'Documents';
  };

  // ─── Step 1 validation ──
  const validateStep1 = () => {
    const errs = {};
    if (!form.first_name.trim()) errs.first_name = 'Required / Obligatoire';
    if (!form.last_name.trim())  errs.last_name = 'Required / Obligatoire';
    if (!EMAIL_RE.test(form.email.trim())) errs.email = 'Invalid email / Courriel invalide';
    if (!form.phone.trim()) errs.phone = 'Required / Obligatoire';
    if (!form.province) errs.province = 'Required / Obligatoire';
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  // ─── Step 2 (custom questions) validation ──
  const validateStep2 = () => {
    const errs = {};
    (req.custom_text_fields || []).forEach((label) => {
      if (!customResponses[label] || !String(customResponses[label]).trim()) {
        errs[`custom_${label}`] = 'Required / Obligatoire';
      }
    });
    (req.custom_date_fields || []).forEach((label) => {
      if (!customResponses[label]) {
        errs[`custom_${label}`] = 'Required / Obligatoire';
      }
    });
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  // ─── Step 3 (files) validation ──
  const validateStep3 = () => {
    const errs = {};
    if (req.requires_cv && !files.cv) errs.cv = 'CV required / CV obligatoire';
    if (req.requires_cover_letter && !files.cover_letter) {
      errs.cover_letter = 'Cover letter required / Lettre obligatoire';
    }
    if (req.requires_photos && (!files.photos || files.photos.length === 0)) {
      errs.photos = 'At least one photo / Au moins une photo';
    }
    if (req.requires_certifications && (!files.certifications || files.certifications.length === 0)) {
      errs.certifications = 'At least one certification / Au moins une certification';
    }
    // Size checks (clientside)
    if (files.cv && files.cv.size > CV_MAX) errs.cv = 'Max 5 MB';
    if (files.cover_letter && files.cover_letter.size > COVER_MAX) errs.cover_letter = 'Max 5 MB';
    if (files.photos) {
      files.photos.forEach((p) => { if (p.size > PHOTO_MAX) errs.photos = 'Each photo max 3 MB'; });
      if (files.photos.length > MAX_PHOTOS) errs.photos = `Max ${MAX_PHOTOS} photos`;
    }
    if (files.certifications) {
      files.certifications.forEach((c) => { if (c.size > CERT_MAX) errs.certifications = 'Each cert max 5 MB'; });
      if (files.certifications.length > MAX_CERTS) errs.certifications = `Max ${MAX_CERTS} certifications`;
    }
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleNext = () => {
    if (step === 1 && !validateStep1()) return;
    if (step === 2 && hasCustomFields && !validateStep2()) return;
    setStep((s) => s + 1);
  };

  const handleSubmit = async () => {
    if (hasFileFields && !validateStep3()) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => fd.append(k, v));
      fd.append('custom_responses', JSON.stringify(customResponses));
      if (files.cv) fd.append('cv', files.cv);
      if (files.cover_letter) fd.append('cover_letter', files.cover_letter);
      (files.photos || []).forEach((p) => fd.append('photos', p));
      (files.certifications || []).forEach((c) => fd.append('certifications', c));

      const r = await axios.post(`${API_BASE}/careers/jobs/${jobId}/apply`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setSuccess(r.data);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      if (detail && typeof detail === 'object') {
        setSubmitError(
          form.preferred_language === 'fr'
            ? detail.message_fr || detail.message_en || 'Erreur'
            : detail.message_en || 'Submission failed',
        );
      } else {
        setSubmitError(typeof detail === 'string' ? detail : e?.message || 'Submission failed');
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20" data-testid="job-detail-loading">
        <Loader2 className="h-8 w-8 animate-spin text-sky-600" />
      </div>
    );
  }

  if (loadError || !job) {
    return (
      <div className="container mx-auto max-w-2xl py-12 px-4" data-testid="job-detail-404">
        <Card className="border-2 border-rose-200 bg-rose-50">
          <CardContent className="p-6 flex items-center gap-3">
            <AlertTriangle className="h-6 w-6 text-rose-600" />
            <p className="text-rose-900">
              This job is no longer available. / Ce poste n&apos;est plus disponible.
            </p>
          </CardContent>
        </Card>
        <div className="mt-4">
          <Link to="/careers">
            <Button variant="outline" data-testid="back-to-careers-btn">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Careers / Retour aux carrières
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="container mx-auto max-w-2xl py-16 px-4" data-testid="application-success">
        <Card className="border-2 border-emerald-300 bg-emerald-50">
          <CardContent className="p-8 text-center">
            <CheckCircle2 className="h-14 w-14 mx-auto text-emerald-600 mb-4" />
            <h1 className="text-2xl font-bold text-emerald-900 mb-2">
              Application Submitted!
            </h1>
            <h2 className="text-lg font-semibold text-emerald-800 mb-6">
              Candidature soumise !
            </h2>
            <p className="text-emerald-900">
              Thank you {form.first_name}. We&apos;ll review your application and
              contact you within 5–7 business days.
            </p>
            <p className="text-emerald-800 italic mt-2">
              Merci {form.first_name}. Nous examinerons votre candidature et vous
              contacterons dans les 5 à 7 jours ouvrables.
            </p>
          </CardContent>
        </Card>
        <div className="mt-6 text-center">
          <Button variant="outline" onClick={() => navigate('/careers')} data-testid="back-to-careers-success-btn">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Careers / Retour aux carrières
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-4xl py-10 px-4" data-testid="job-detail-page">
      <Link to="/careers" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-sky-600 mb-4">
        <ArrowLeft className="h-4 w-4" /> Back to Careers / Retour
      </Link>

      <header className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900" data-testid="detail-title">{job.title}</h1>
        {job.title_fr && (
          <h2 className="text-xl text-slate-600 italic" data-testid="detail-title-fr">{job.title_fr}</h2>
        )}
        <div className="flex flex-wrap items-center gap-3 mt-4 text-sm text-slate-600">
          <Badge className="bg-sky-100 text-sky-800 hover:bg-sky-100">
            <Briefcase className="h-3 w-3 mr-1 inline" /> {job.department}
          </Badge>
          <span className="flex items-center gap-1"><MapPin className="h-4 w-4" /> {job.location}</span>
          {job.commission_range && (
            <span className="flex items-center gap-1 text-emerald-700 font-semibold">
              <DollarSign className="h-4 w-4" /> {job.commission_range}
            </span>
          )}
        </div>
      </header>

      <Card className="mb-8" data-testid="description-card">
        <CardContent className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="text-sm font-bold uppercase text-slate-500 mb-2">English</h3>
            <div className="whitespace-pre-line text-sm leading-relaxed text-slate-800" data-testid="description-en">
              {job.description_en}
            </div>
          </div>
          <div>
            <h3 className="text-sm font-bold uppercase text-slate-500 mb-2">Français</h3>
            <div className="whitespace-pre-line text-sm leading-relaxed text-slate-800" data-testid="description-fr">
              {job.description_fr}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── Multi-step form ── */}
      <Card data-testid="apply-form-card">
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold">Apply Now / Postuler maintenant</h2>
            <Badge variant="outline" data-testid="step-indicator">
              Step {step} of {totalSteps} — {stepLabel(step)}
            </Badge>
          </div>

          {/* Step 1 */}
          {step === 1 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="step-1">
              <div>
                <Label>First Name / Prénom *</Label>
                <Input
                  data-testid="input-first-name"
                  value={form.first_name}
                  onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                  className={fieldErrors.first_name ? 'border-rose-400' : ''}
                />
                {fieldErrors.first_name && <p className="text-xs text-rose-600 mt-1">{fieldErrors.first_name}</p>}
              </div>
              <div>
                <Label>Last Name / Nom *</Label>
                <Input
                  data-testid="input-last-name"
                  value={form.last_name}
                  onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                  className={fieldErrors.last_name ? 'border-rose-400' : ''}
                />
                {fieldErrors.last_name && <p className="text-xs text-rose-600 mt-1">{fieldErrors.last_name}</p>}
              </div>
              <div>
                <Label>Email *</Label>
                <Input
                  data-testid="input-email"
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className={fieldErrors.email ? 'border-rose-400' : ''}
                />
                {fieldErrors.email && <p className="text-xs text-rose-600 mt-1">{fieldErrors.email}</p>}
              </div>
              <div>
                <Label>Phone / Téléphone *</Label>
                <Input
                  data-testid="input-phone"
                  type="tel"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  className={fieldErrors.phone ? 'border-rose-400' : ''}
                />
                {fieldErrors.phone && <p className="text-xs text-rose-600 mt-1">{fieldErrors.phone}</p>}
              </div>
              <div>
                <Label>Province *</Label>
                <select
                  data-testid="input-province"
                  value={form.province}
                  onChange={(e) => setForm({ ...form, province: e.target.value })}
                  className={`mt-1 block w-full rounded border px-3 py-2 text-sm bg-white ${fieldErrors.province ? 'border-rose-400' : 'border-slate-300'}`}
                >
                  <option value="">— Select / Sélectionnez —</option>
                  {PROVINCES.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
                {fieldErrors.province && <p className="text-xs text-rose-600 mt-1">{fieldErrors.province}</p>}
              </div>
              <div>
                <Label>Preferred Language / Langue préférée</Label>
                <div className="mt-2 flex items-center gap-4">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="radio" name="lang" value="en"
                      data-testid="radio-lang-en"
                      checked={form.preferred_language === 'en'}
                      onChange={() => setForm({ ...form, preferred_language: 'en' })}
                    />
                    English
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="radio" name="lang" value="fr"
                      data-testid="radio-lang-fr"
                      checked={form.preferred_language === 'fr'}
                      onChange={() => setForm({ ...form, preferred_language: 'fr' })}
                    />
                    Français
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* Step 2 (Questions) */}
          {step === 2 && hasCustomFields && (
            <div className="space-y-4" data-testid="step-2">
              {(req.custom_text_fields || []).map((label) => (
                <div key={label}>
                  <Label>{label} *</Label>
                  <Textarea
                    data-testid={`input-text-${label}`}
                    value={customResponses[label] || ''}
                    onChange={(e) => setCustomResponses({ ...customResponses, [label]: e.target.value })}
                    rows={3}
                    className={fieldErrors[`custom_${label}`] ? 'border-rose-400' : ''}
                  />
                  {fieldErrors[`custom_${label}`] && (
                    <p className="text-xs text-rose-600 mt-1">{fieldErrors[`custom_${label}`]}</p>
                  )}
                </div>
              ))}
              {(req.custom_date_fields || []).map((label) => (
                <div key={label}>
                  <Label>{label} *</Label>
                  <Input
                    data-testid={`input-date-${label}`}
                    type="date"
                    value={customResponses[label] || ''}
                    onChange={(e) => setCustomResponses({ ...customResponses, [label]: e.target.value })}
                    className={fieldErrors[`custom_${label}`] ? 'border-rose-400' : ''}
                  />
                  {fieldErrors[`custom_${label}`] && (
                    <p className="text-xs text-rose-600 mt-1">{fieldErrors[`custom_${label}`]}</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Step 3 (Documents) — only when any requires_* is true */}
          {(step === 3 || (step === 2 && !hasCustomFields)) && hasFileFields && (
            <div className="space-y-4" data-testid="step-3">
              {req.requires_cv && (
                <FileField
                  testid="upload-cv"
                  icon="📄"
                  label="Upload CV / Téléverser CV (PDF or DOCX, max 5 MB)"
                  accept={ACCEPT_DOC}
                  multiple={false}
                  onChange={(f) => setFiles({ ...files, cv: f[0] || null })}
                  files={files.cv ? [files.cv] : []}
                  error={fieldErrors.cv}
                />
              )}
              {req.requires_cover_letter && (
                <FileField
                  testid="upload-cover-letter"
                  icon="📄"
                  label="Cover Letter / Lettre de motivation (PDF or DOCX, max 5 MB)"
                  accept={ACCEPT_DOC}
                  multiple={false}
                  onChange={(f) => setFiles({ ...files, cover_letter: f[0] || null })}
                  files={files.cover_letter ? [files.cover_letter] : []}
                  error={fieldErrors.cover_letter}
                />
              )}
              {req.requires_photos && (
                <FileField
                  testid="upload-photos"
                  icon="📸"
                  label="Portfolio Photos (JPG/PNG, max 3 MB each, up to 5 files)"
                  accept={ACCEPT_IMG}
                  multiple
                  onChange={(f) => setFiles({ ...files, photos: f.slice(0, MAX_PHOTOS) })}
                  files={files.photos || []}
                  error={fieldErrors.photos}
                />
              )}
              {req.requires_certifications && (
                <FileField
                  testid="upload-certifications"
                  icon="🏆"
                  label="Certifications (PDF, max 5 MB each, up to 3 files)"
                  accept={ACCEPT_PDF}
                  multiple
                  onChange={(f) => setFiles({ ...files, certifications: f.slice(0, MAX_CERTS) })}
                  files={files.certifications || []}
                  error={fieldErrors.certifications}
                />
              )}
            </div>
          )}

          {submitError && (
            <div className="mt-4 rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" data-testid="submit-error">
              {submitError}
            </div>
          )}

          {/* Footer nav */}
          <div className="mt-6 flex items-center justify-between">
            <Button
              variant="outline"
              onClick={() => setStep((s) => Math.max(1, s - 1))}
              disabled={step === 1 || submitting}
              data-testid="step-back-btn"
            >
              <ArrowLeft className="h-4 w-4 mr-2" /> Back / Retour
            </Button>
            {step < totalSteps ? (
              <Button
                onClick={handleNext}
                className="bg-sky-600 hover:bg-sky-700"
                data-testid="step-next-btn"
              >
                Next / Suivant <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            ) : (
              <Button
                onClick={handleSubmit}
                disabled={submitting}
                className="bg-emerald-600 hover:bg-emerald-700"
                data-testid="submit-application-btn"
              >
                {submitting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <FileUp className="h-4 w-4 mr-2" />}
                Submit Application / Soumettre
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}


function FileField({ testid, icon, label, accept, multiple, onChange, files, error }) {
  const id = `file-${testid}`;
  return (
    <div>
      <label
        htmlFor={id}
        className={`block rounded border-2 border-dashed p-4 text-center cursor-pointer transition-colors ${error ? 'border-rose-400 bg-rose-50' : 'border-slate-300 hover:bg-slate-50'}`}
        data-testid={testid}
      >
        <div className="text-2xl mb-1">{icon}</div>
        <div className="text-sm font-semibold">{label}</div>
        <input
          id={id}
          type="file"
          accept={accept}
          multiple={multiple}
          className="hidden"
          onChange={(e) => onChange(Array.from(e.target.files || []))}
        />
        {files.length > 0 && (
          <ul className="mt-2 text-xs text-slate-600 list-none" data-testid={`${testid}-list`}>
            {files.map((f, i) => (
              <li key={i}>
                {f.name} ({(f.size / 1024).toFixed(0)} KB)
              </li>
            ))}
          </ul>
        )}
      </label>
      {error && <p className="text-xs text-rose-600 mt-1">{error}</p>}
    </div>
  );
}
