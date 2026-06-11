import API_BASE from '../config';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { toast } from 'sonner';
import axios from 'axios';
import { Send, Loader2 } from 'lucide-react';

const API = API_BASE;

const MessageSellerModal = ({ isOpen, onClose, sellerId, listingId, listingTitle }) => {
  const { t, i18n } = useTranslation();
  const isFr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [subject, setSubject] = useState(`${t('messageSeller.inquiryPrefix')}: ${listingTitle || t('messageSeller.auction')}`);
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);

  const handleSend = async () => {
    if (!message.trim()) {
      toast.error(t('messageSeller.enterMessage'));
      return;
    }

    setSending(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(
        `${API}/messages`,
        {
          receiver_id: sellerId,
          listing_id: listingId,
          content: `Subject: ${subject}\n\n${message}`
        },
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );

      toast.success(t('messageSeller.sentSuccess'));
      setMessage('');
      setSubject(`${t('messageSeller.inquiryPrefix')}: ${listingTitle || t('messageSeller.auction')}`);
      onClose();
    } catch (error) {
      console.error('Failed to send message:', error);
      // iter196 — backend gate returns detail = { code, message_en, message_fr }
      const detail = error?.response?.data?.detail;
      let msg;
      if (detail && typeof detail === 'object') {
        msg = isFr
          ? (detail.message_fr || detail.message_en || detail.code)
          : (detail.message_en || detail.message_fr || detail.code);
      } else if (typeof detail === 'string') {
        msg = detail;
      } else {
        msg = t('messageSeller.sendFailed');
      }
      toast.error(msg, { duration: 6000 });
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>📨 {t('messageSeller.title')}</DialogTitle>
          <DialogDescription>
            {t('messageSeller.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="subject">{t('messageSeller.subject')}</Label>
            <Input
              id="subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder={t('messageSeller.subjectPlaceholder')}
              data-testid="message-seller-subject"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="message">{t('messageSeller.message')}</Label>
            <Textarea
              id="message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={t('messageSeller.messagePlaceholder')}
              rows={6}
              required
              data-testid="message-seller-content"
            />
            <p className="text-xs text-muted-foreground">
              {message.length} / 1000 {t('messageSeller.characters')}
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={sending}
            data-testid="message-seller-cancel"
          >
            {t('messageSeller.cancel')}
          </Button>
          <Button
            onClick={handleSend}
            disabled={sending || !message.trim()}
            className="gradient-button text-white"
            data-testid="message-seller-send"
          >
            {sending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t('messageSeller.sending')}
              </>
            ) : (
              <>
                <Send className="mr-2 h-4 w-4" />
                {t('messageSeller.send')}
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default MessageSellerModal;
