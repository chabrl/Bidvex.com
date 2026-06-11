import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Star, ArrowLeft, Loader2, CheckCircle2, Package, Send } from 'lucide-react';

const API = API_BASE;

const StarPicker = ({ value, onChange }) => {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-1 justify-center" data-testid="review-star-picker">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onMouseEnter={() => setHover(star)}
          onMouseLeave={() => setHover(0)}
          onClick={() => onChange(star)}
          className="transition-transform hover:scale-110 min-w-[44px] min-h-[44px] flex items-center justify-center"
          data-testid={`review-star-${star}`}
        >
          <Star
            className={`h-9 w-9 transition-colors ${
              star <= (hover || value)
                ? 'fill-amber-400 text-amber-400'
                : 'fill-slate-200 text-slate-200 dark:fill-slate-700 dark:text-slate-700'
            }`}
          />
        </button>
      ))}
    </div>
  );
};

export default function ReviewSubmitPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const listingId = params.get('listing_id');
  const role = params.get('role') === 'seller' ? 'seller' : 'buyer';

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState(null);
  const [ctx, setCtx] = useState(null);
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/auth?redirect=' + encodeURIComponent(window.location.pathname + window.location.search));
      return;
    }
    if (!listingId) {
      setError(t('reviewSubmit.missingListing'));
      setLoading(false);
      return;
    }
    axios.get(`${API}/reviews/submit-context`, {
      params: { listing_id: listingId, role },
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        setCtx(res.data);
        if (res.data.existing_review) setSubmitted(true);
      })
      .catch((err) => {
        const d = err.response?.data?.detail;
        setError(typeof d === 'string' ? d : t('reviewSubmit.cannotLoad'));
      })
      .finally(() => setLoading(false));
  }, [listingId, role]); // eslint-disable-line

  const handleSubmit = async () => {
    if (rating === 0) {
      toast.error(t('reviewSubmit.selectRating'));
      return;
    }
    setSubmitting(true);
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${API}/reviews/submit`,
        { listing_id: listingId, role, rating, comment: comment.trim() || null },
        { headers: { Authorization: `Bearer ${token}` } });
      setSubmitted(true);
      toast.success(t('reviewSubmit.submittedToast'));
    } catch (err) {
      const d = err.response?.data?.detail;
      if (err.response?.status === 409) {
        setSubmitted(true);
      } else {
        toast.error(typeof d === 'string' ? d : t('reviewSubmit.submitFailed'));
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900">
        <Loader2 className="h-8 w-8 animate-spin text-cyan-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 dark:bg-slate-900 px-4">
        <Alert className="max-w-md" data-testid="review-submit-error">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button variant="outline" className="mt-4" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4 mr-2" /> {t('reviewSubmit.goBack')}
        </Button>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 dark:bg-slate-900 px-4">
        <Card className="max-w-md w-full text-center border-0 shadow-lg" data-testid="review-submit-confirmation">
          <CardContent className="py-10">
            <CheckCircle2 className="h-14 w-14 text-emerald-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-2">
              {t('reviewSubmit.submittedTitle')}
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
              {t('reviewSubmit.submittedBody')}
            </p>
            <Button onClick={() => navigate('/marketplace')} data-testid="review-submit-done-btn">
              {t('reviewSubmit.backToMarketplace')}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 py-10 px-4" data-testid="review-submit-page">
      <div className="max-w-lg mx-auto">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)} className="mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" /> {t('reviewSubmit.goBack')}
        </Button>
        <Card className="border-0 shadow-lg">
          <CardHeader>
            <CardTitle data-testid="review-submit-title">
              {role === 'buyer' ? t('reviewSubmit.rateSeller') : t('reviewSubmit.rateBuyer')}
            </CardTitle>
            <CardDescription>
              {role === 'buyer'
                ? t('reviewSubmit.rateSellerDesc', { name: ctx?.counterparty_name || '' })
                : t('reviewSubmit.rateBuyerDesc', { name: ctx?.counterparty_name || '' })}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-100 dark:bg-slate-800">
              {ctx?.item_image ? (
                <img src={ctx.item_image} alt={ctx.item_title} className="h-14 w-14 rounded object-cover" />
              ) : (
                <div className="h-14 w-14 rounded bg-slate-200 dark:bg-slate-700 flex items-center justify-center">
                  <Package className="h-6 w-6 text-slate-400" />
                </div>
              )}
              <div className="min-w-0">
                <p className="font-medium text-sm text-slate-900 dark:text-white line-clamp-1" data-testid="review-item-title">
                  {ctx?.item_title}
                </p>
                <p className="text-xs text-slate-500">{ctx?.counterparty_name}</p>
              </div>
            </div>

            <StarPicker value={rating} onChange={setRating} />

            <div>
              <Textarea
                value={comment}
                onChange={(e) => setComment(e.target.value.slice(0, 500))}
                placeholder={t('reviewSubmit.commentPlaceholder')}
                rows={4}
                maxLength={500}
                data-testid="review-comment-input"
              />
              <p className="text-xs text-slate-400 mt-1 text-right">{comment.length} / 500</p>
            </div>

            <Button
              className="w-full"
              onClick={handleSubmit}
              disabled={submitting || rating === 0}
              data-testid="review-submit-btn"
            >
              {submitting ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> {t('reviewSubmit.submitting')}</>
              ) : (
                <><Send className="h-4 w-4 mr-2" /> {t('reviewSubmit.submit')}</>
              )}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
