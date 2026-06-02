/**
 * iter266 Mission 3A — NotificationDetailModal
 *
 * Centered pop-up showing the full content of any notification + an
 * optional attachment upload section when `requires_attachment` is set.
 *
 * Replaces the legacy "click notification → navigate to /settings"
 * UX flow. The original navigation logic is preserved behind an
 * optional "View Details" CTA button when the notification carries
 * an `action_url` / `cta_url`.
 */
import React, { useEffect, useRef, useState, useCallback } from 'react';
import axios from 'axios';
import API_BASE from '../config';
import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from './ui/dialog';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { toast } from 'sonner';
import {
  Bell,
  X,
  Paperclip,
  Upload,
  CheckCircle2,
  ExternalLink,
  Loader2,
  AlertTriangle,
} from 'lucide-react';

const API = API_BASE;

const COLOR_BORDER = {
  info:            'border-t-[4px] border-t-blue-500',
  warning:         'border-t-[4px] border-t-amber-400',
  action_required: 'border-t-[4px] border-t-rose-400',
  success:         'border-t-[4px] border-t-emerald-400',
};

export default function NotificationDetailModal({
  notification,
  open,
  onClose,
  onMarkedRead,
  onNavigate,
}) {
  const { token, user } = useAuth();
  const { i18n } = useTranslation();
  const isFrench = i18n?.language?.startsWith('fr') || user?.preferred_language === 'fr';

  const [file, setFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [localSubmitted, setLocalSubmitted] = useState(false);
  const fileInputRef = useRef(null);
  const markedRef = useRef(false);

  const colorKey = notification?.color_type || (notification?.requires_attachment ? 'action_required' : 'info');
  const borderCls = COLOR_BORDER[colorKey] || COLOR_BORDER.info;

  // i18n field selection.
  const title =
    (isFrench && (notification?.title_fr || notification?.titleFr)) ||
    notification?.title ||
    (isFrench ? 'Notification' : 'Notification');
  const body =
    (isFrench && (notification?.body_fr || notification?.bodyFr || notification?.message_fr)) ||
    notification?.body ||
    notification?.message ||
    '';
  const attachmentLabel =
    (isFrench && notification?.attachment_request_label_fr) ||
    notification?.attachment_request_label ||
    (isFrench ? 'Téléversez le document demandé' : 'Upload the requested document');

  const senderName = notification?.sender_name || (isFrench ? 'Système BidVex' : 'BidVex System');
  const ctaUrl = notification?.cta_url || notification?.action_url || notification?.route_url;
  const ctaLabel = notification?.cta_label || (isFrench ? 'Ouvrir' : 'View Details');

  const requiresAttachment = !!notification?.requires_attachment;
  const alreadySubmitted = !!notification?.attachment_submitted || localSubmitted;
  const maxMb = Number(notification?.attachment_max_mb || 1);
  const types = notification?.attachment_types || 'PDF, JPG, PNG';

  // Mark as read on open (idempotent).
  const markAsRead = useCallback(async () => {
    if (!notification?.id || notification?.read || notification?.is_read || markedRef.current) return;
    markedRef.current = true;
    try {
      await axios.post(`${API}/notifications/${notification.id}/read`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      onMarkedRead && onMarkedRead(notification.id);
    } catch (e) {
      // Silent — non-blocking.
    }
  }, [notification, token, onMarkedRead]);

  useEffect(() => {
    if (open) markAsRead();
    if (!open) {
      setFile(null);
      setLocalSubmitted(false);
      markedRef.current = false;
    }
  }, [open, markAsRead]);

  const handleFilePick = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > maxMb * 1024 * 1024) {
      toast.error(
        isFrench
          ? `Fichier trop volumineux (max ${maxMb} Mo).`
          : `File too large (max ${maxMb} MB).`,
      );
      return;
    }
    setFile(f);
  };

  const handleSubmitAttachment = async () => {
    if (!file) {
      toast.error(isFrench ? 'Veuillez choisir un fichier.' : 'Please choose a file.');
      return;
    }
    try {
      setSubmitting(true);
      const fd = new FormData();
      fd.append('file', file);
      await axios.post(
        `${API}/notifications/${notification.id}/submit-attachment`,
        fd,
        { headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' } },
      );
      toast.success(isFrench ? 'Document envoyé.' : 'Attachment sent.');
      setLocalSubmitted(true);
      setFile(null);
    } catch (e) {
      toast.error(e.response?.data?.detail || (isFrench ? 'Échec du téléversement' : 'Upload failed'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCta = () => {
    if (onNavigate && notification) onNavigate(notification);
    onClose && onClose();
  };

  if (!notification) return null;

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose && onClose(); }}>
      <DialogContent
        className={`sm:max-w-[560px] max-h-[80vh] overflow-y-auto bg-white dark:bg-slate-900 ${borderCls}`}
        data-testid="notification-detail-modal"
      >
        {/* Header */}
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 mt-1">
            <span className="text-3xl" role="img" aria-label="icon">
              {notification?.notification_icon || '📬'}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <DialogTitle className="text-lg font-bold leading-tight" data-testid="notif-modal-title">
              {title}
            </DialogTitle>
            <DialogDescription className="text-xs text-slate-500 mt-1">
              {isFrench ? 'De' : 'From'}: <span className="font-semibold">{senderName}</span>
              {notification?.created_at && (
                <>
                  {' · '}
                  {new Date(notification.created_at).toLocaleString(isFrench ? 'fr-CA' : 'en-CA')}
                </>
              )}
            </DialogDescription>
          </div>
          {colorKey === 'action_required' && (
            <Badge className="bg-rose-100 text-rose-800 border border-rose-300">
              <AlertTriangle className="h-3 w-3 mr-1" />
              {isFrench ? 'Action requise' : 'Action Required'}
            </Badge>
          )}
        </div>

        {/* Body */}
        <div className="mt-4 text-sm leading-relaxed text-slate-700 dark:text-slate-200 whitespace-pre-line" data-testid="notif-modal-body">
          {body}
        </div>

        {/* Attachment block */}
        {requiresAttachment && (
          <div className="mt-5 rounded-lg border border-rose-200 bg-rose-50/60 dark:bg-rose-950/30 p-4" data-testid="notif-attachment-block">
            <div className="flex items-start gap-2 mb-3">
              <Paperclip className="h-5 w-5 text-rose-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-rose-900 dark:text-rose-200">
                  {isFrench
                    ? `L'administrateur demande un document :`
                    : `Admin is requesting a document from you:`}
                </p>
                <p className="text-sm text-rose-800 dark:text-rose-300 mt-1">"{attachmentLabel}"</p>
                <p className="text-xs text-slate-500 mt-2">
                  {isFrench ? 'Acceptés' : 'Accepted'}: {types} · {isFrench ? 'Taille max' : 'Max'}: {maxMb} MB
                </p>
              </div>
            </div>

            {alreadySubmitted ? (
              <div className="flex items-center gap-2 text-emerald-700 bg-emerald-50 dark:bg-emerald-950/30 rounded p-3" data-testid="notif-attachment-submitted">
                <CheckCircle2 className="h-5 w-5" />
                <span className="text-sm font-medium">
                  {isFrench ? 'Document envoyé à l\'administrateur.' : 'Attachment sent to admin.'}
                </span>
              </div>
            ) : (
              <div className="space-y-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={types.toLowerCase().split(/[ ,]+/).filter(Boolean).map(t => `.${t.replace('.','')}`).join(',')}
                  onChange={handleFilePick}
                  className="hidden"
                  data-testid="notif-file-input"
                />
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={submitting}
                    data-testid="notif-select-file-btn"
                  >
                    📁 {file ? file.name.slice(0, 28) : (isFrench ? 'Choisir un fichier' : 'Select File')}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    onClick={handleSubmitAttachment}
                    disabled={!file || submitting}
                    className="bg-rose-600 hover:bg-rose-700 text-white"
                    data-testid="notif-submit-attachment-btn"
                  >
                    {submitting ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Upload className="h-3 w-3 mr-1" />}
                    {isFrench ? 'Envoyer à l\'admin' : 'Send to Admin'}
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* CTA + footer */}
        <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-2">
            {ctaUrl && (
              <Button
                type="button"
                size="sm"
                onClick={handleCta}
                className="bg-indigo-600 hover:bg-indigo-700 text-white"
                data-testid="notif-cta-btn"
              >
                {ctaLabel}
                <ExternalLink className="h-3 w-3 ml-1" />
              </Button>
            )}
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onClose}
            data-testid="notif-close-btn"
          >
            <X className="h-3 w-3 mr-1" />
            {isFrench ? 'Fermer' : 'Close'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
