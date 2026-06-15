/**
 * EmailToFriendModal — iter304
 *
 * Lightweight modal used on vehicle listing detail pages to share a
 * listing with a friend via a branded BidVex email. Rate limited
 * server-side to 5 sends per user per day.
 */
import API_BASE from '../config';
import React, { useState } from 'react';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Mail, X, Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Button } from './ui/button';
import { Label } from './ui/label';

const API = API_BASE;

const EmailToFriendModal = ({ open, onClose, vehicleId, listingTitle }) => {
  const { i18n } = useTranslation();
  const fr = (i18n.language || 'en').toLowerCase().startsWith('fr');
  const [recipient, setRecipient] = useState('');
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);

  const reset = () => { setRecipient(''); setMessage(''); setSending(false); };

  const handleSend = async () => {
    if (!recipient.trim()) {
      toast.error(fr ? "Adresse courriel requise" : 'Recipient email required');
      return;
    }
    setSending(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(
        `${API}/vehicles/${vehicleId}/email-to-friend`,
        { recipient_email: recipient.trim(), message: message.trim() || null },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      toast.success(fr ? 'Courriel envoyé !' : 'Email sent!');
      reset();
      onClose?.();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = (typeof detail === 'object' ? (fr ? detail.message_fr : detail.message_en) : detail)
        || (fr ? "Échec de l'envoi" : 'Failed to send email');
      toast.error(msg);
      setSending(false);
    }
  };

  return (
    <Dialog open={!!open} onOpenChange={(v) => { if (!v) { onClose?.(); reset(); } }}>
      <DialogContent className="max-w-md" data-testid="email-to-friend-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-blue-600" />
            {fr ? 'Envoyer à un ami' : 'Email to a Friend'}
          </DialogTitle>
          <DialogDescription className="text-xs">
            {listingTitle && <span className="block font-medium text-slate-700 dark:text-slate-200">{listingTitle}</span>}
            {fr
              ? "Limite : 5 envois par jour pour éviter les abus."
              : 'Daily limit: 5 sends per user to prevent spam.'}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label htmlFor="etf-recipient" className="text-xs">{fr ? "Courriel du destinataire *" : "Recipient's email *"}</Label>
            <Input
              id="etf-recipient"
              data-testid="email-to-friend-recipient-input"
              type="email"
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              placeholder="friend@example.com"
              disabled={sending}
            />
          </div>
          <div>
            <Label htmlFor="etf-message" className="text-xs">{fr ? 'Message personnel (facultatif)' : 'Personal message (optional)'}</Label>
            <Textarea
              id="etf-message"
              data-testid="email-to-friend-message-input"
              rows={3}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={fr ? 'Salut, regarde ce véhicule...' : "Hey — thought you'd like this one..."}
              maxLength={500}
              disabled={sending}
            />
            <p className="text-[10px] text-slate-400 mt-1 text-right">{message.length}/500</p>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-3">
          <Button variant="ghost" onClick={() => { onClose?.(); reset(); }} disabled={sending} data-testid="email-to-friend-cancel-btn">
            <X className="h-4 w-4 mr-1" /> {fr ? 'Annuler' : 'Cancel'}
          </Button>
          <Button onClick={handleSend} disabled={sending || !recipient.trim()} data-testid="email-to-friend-send-btn">
            {sending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Mail className="h-4 w-4 mr-1" />}
            {fr ? 'Envoyer' : 'Send'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default EmailToFriendModal;
