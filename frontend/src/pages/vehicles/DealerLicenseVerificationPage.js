import { extractErrorMessage } from '../../utils/errorHandler';
/**
 * DealerLicenseVerificationPage — iter194
 * Buyer-facing form to submit dealer license proof for "licensed_only" auction access.
 * Routes via App.js: /vehicle-auctions/dealer-license
 */
import API_BASE from '../../config';
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import {
  ShieldCheck, Clock, CheckCircle2, XCircle, FileText, Upload, Loader2, ArrowLeft,
} from 'lucide-react';
import { toast } from 'sonner';

const API = API_BASE;

const DealerLicenseVerificationPage = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [record, setRecord] = useState(null); // existing license record
  const [form, setForm] = useState({
    license_number: '',
    jurisdiction: '',
    expiry_date: '',
    document_url: '',
  });

  useEffect(() => {
    if (!token) {
      navigate('/auth');
      return;
    }
    (async () => {
      try {
        const res = await axios.get(`${API}/dealer-licenses/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setRecord(res.data);
        if (res.data?.license) {
          setForm({
            license_number: res.data.license.license_number || '',
            jurisdiction: res.data.license.jurisdiction || '',
            expiry_date: res.data.license.expiry_date
              ? new Date(res.data.license.expiry_date).toISOString().split('T')[0]
              : '',
            document_url: res.data.license.document_url || '',
          });
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [token, navigate]);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await axios.post(`${API}/uploads/document`, fd, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
      });
      setForm((prev) => ({ ...prev, document_url: res.data.url }));
      toast.success(t('storage.facilityRegister.fileUploaded'));
    } catch (err) {
      toast.error(extractErrorMessage(err) || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async () => {
    if (!form.license_number || !form.jurisdiction || !form.expiry_date || !form.document_url) {
      toast.error(t('storage.facilityRegister.fieldRequired'));
      return;
    }
    const expiry = new Date(form.expiry_date);
    if (expiry <= new Date()) {
      toast.error(t('vehicleDealer.expiryInPast'));
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(
        `${API}/dealer-licenses`,
        { ...form, expiry_date: new Date(form.expiry_date).toISOString() },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      const res = await axios.get(`${API}/dealer-licenses/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setRecord(res.data);
      toast.success(t('vehicleDealer.alreadySubmitted'));
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'object'
        ? (detail.message_en || JSON.stringify(detail))
        : (detail || t('vehicleDealer.submissionError'));
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  const status = record?.status || 'none';
  const isApproved = status === 'approved';
  const isPending = status === 'pending';
  const isRejected = status === 'rejected';
  const isExpired = status === 'expired';

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-10" data-testid="dealer-license-verification-page">
      <div className="max-w-2xl mx-auto px-4">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center text-sm text-blue-600 hover:underline mb-3"
          data-testid="dealer-license-back-btn"
        >
          <ArrowLeft className="h-3.5 w-3.5 mr-1" /> Back
        </button>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-2xl">
              <ShieldCheck className="h-6 w-6 text-blue-600" />
              {t('vehicleDealer.verifyTitle')}
            </CardTitle>
            <p className="text-sm text-muted-foreground mt-1">{t('vehicleDealer.verifySubtitle')}</p>
          </CardHeader>
          <CardContent className="space-y-5">
            {/* STATUS DISPLAY */}
            {isApproved && (
              <div className="p-4 rounded-md bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-300" data-testid="dealer-license-approved-badge">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                  <span className="font-semibold text-emerald-800 dark:text-emerald-200">{t('vehicleDealer.approved')}</span>
                  <Badge variant="outline" className="ml-2 border-emerald-500 text-emerald-700">{t('vehicleDealer.approved')}</Badge>
                </div>
                <p className="text-sm text-emerald-700 dark:text-emerald-300 mt-2">{t('vehicleDealer.approvedDesc')}</p>
              </div>
            )}
            {isPending && (
              <div className="p-4 rounded-md bg-amber-50 dark:bg-amber-950/30 border border-amber-300" data-testid="dealer-license-pending-badge">
                <div className="flex items-center gap-2">
                  <Clock className="h-5 w-5 text-amber-600" />
                  <span className="font-semibold text-amber-800 dark:text-amber-200">{t('vehicleDealer.underReview')}</span>
                </div>
                <p className="text-sm text-amber-700 dark:text-amber-300 mt-2">{t('vehicleDealer.underReviewDesc')}</p>
              </div>
            )}
            {isRejected && (
              <div className="p-4 rounded-md bg-red-50 dark:bg-red-950/30 border border-red-300" data-testid="dealer-license-rejected-badge">
                <div className="flex items-center gap-2">
                  <XCircle className="h-5 w-5 text-red-600" />
                  <span className="font-semibold text-red-800 dark:text-red-200">{t('vehicleDealer.rejected')}</span>
                </div>
                <p className="text-sm text-red-700 dark:text-red-300 mt-2">
                  {t('vehicleDealer.rejectedDesc', { reason: record?.license?.rejection_reason || '—' })}
                </p>
              </div>
            )}
            {isExpired && (
              <div className="p-4 rounded-md bg-orange-50 dark:bg-orange-950/30 border border-orange-300">
                <div className="flex items-center gap-2">
                  <Clock className="h-5 w-5 text-orange-600" />
                  <span className="font-semibold text-orange-800 dark:text-orange-200">{t('vehicleDealer.expiredStatus')}</span>
                </div>
                <p className="text-sm text-orange-700 dark:text-orange-300 mt-2">{t('vehicleDealer.expiredStatusDesc')}</p>
              </div>
            )}

            {/* SUBMIT FORM (shown if no submission OR rejected/expired) */}
            {(!isApproved && !isPending) && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="license_number">{t('vehicleDealer.licenseNumber')}</Label>
                  <Input
                    id="license_number"
                    value={form.license_number}
                    onChange={(e) => setForm({ ...form, license_number: e.target.value })}
                    placeholder={t('vehicleDealer.licenseNumberPh')}
                    data-testid="dealer-license-number-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="jurisdiction">{t('vehicleDealer.jurisdiction')}</Label>
                  <Input
                    id="jurisdiction"
                    value={form.jurisdiction}
                    onChange={(e) => setForm({ ...form, jurisdiction: e.target.value.toUpperCase() })}
                    placeholder={t('vehicleDealer.jurisdictionPh')}
                    maxLength={4}
                    data-testid="dealer-license-jurisdiction-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="expiry_date">{t('vehicleDealer.expiryDate')}</Label>
                  <Input
                    id="expiry_date"
                    type="date"
                    value={form.expiry_date}
                    onChange={(e) => setForm({ ...form, expiry_date: e.target.value })}
                    min={new Date().toISOString().split('T')[0]}
                    data-testid="dealer-license-expiry-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="document_upload">{t('vehicleDealer.documentUpload')}</Label>
                  <p className="text-xs text-muted-foreground">{t('vehicleDealer.documentUploadDesc')}</p>
                  <div className="flex items-center gap-3">
                    <input
                      type="file"
                      id="document_upload"
                      accept=".pdf,.jpg,.jpeg,.png"
                      onChange={handleFileUpload}
                      className="hidden"
                      data-testid="dealer-license-file-input"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => document.getElementById('document_upload').click()}
                      disabled={uploading}
                      data-testid="dealer-license-upload-btn"
                    >
                      {uploading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Upload className="h-4 w-4 mr-2" />}
                      {t('storage.facilityRegister.uploadFile')}
                    </Button>
                    {form.document_url && (
                      <span className="inline-flex items-center gap-1 text-sm text-emerald-600">
                        <FileText className="h-4 w-4" />
                        {t('storage.facilityRegister.fileUploaded')}
                      </span>
                    )}
                  </div>
                </div>

                <Button
                  onClick={handleSubmit}
                  disabled={submitting || !form.license_number || !form.jurisdiction || !form.expiry_date || !form.document_url}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white"
                  data-testid="dealer-license-submit-btn"
                >
                  {submitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                  {submitting ? t('vehicleDealer.submitting') : (isRejected || isExpired ? t('vehicleDealer.resubmit') : t('vehicleDealer.submitForReview'))}
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default DealerLicenseVerificationPage;
