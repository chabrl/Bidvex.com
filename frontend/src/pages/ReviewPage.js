import API_BASE from '../config';
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Separator } from '../components/ui/separator';
import { Textarea } from '../components/ui/textarea';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Star, ArrowLeft, Loader2, CheckCircle2, Package, User, MessageSquare, Truck, Send } from 'lucide-react';

const API = API_BASE;

const StarSelector = ({ value, onChange, label, size = 'lg' }) => {
  const [hover, setHover] = useState(0);
  const starSize = size === 'lg' ? 'h-8 w-8' : 'h-6 w-6';

  return (
    <div className="space-y-1">
      {label && <label className="text-sm font-medium text-slate-700 dark:text-slate-300">{label}</label>}
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type="button"
            onMouseEnter={() => setHover(star)}
            onMouseLeave={() => setHover(0)}
            onClick={() => onChange(star)}
            className="transition-transform hover:scale-110 min-w-[44px] min-h-[44px] flex items-center justify-center"
            data-testid={`star-${label?.toLowerCase().replace(/\s/g, '-') || 'rating'}-${star}`}
          >
            <Star
              className={`${starSize} transition-colors ${
                star <= (hover || value)
                  ? 'fill-amber-400 text-amber-400'
                  : 'fill-slate-200 text-slate-200 dark:fill-slate-700 dark:text-slate-700'
              }`}
            />
          </button>
        ))}
      </div>
    </div>
  );
};

const ReviewPage = () => {
  const { transactionId } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState(null);
  const [details, setDetails] = useState(null);

  const [rating, setRating] = useState(0);
  const [itemAccuracy, setItemAccuracy] = useState(0);
  const [communication, setCommunication] = useState(0);
  const [shippingSpeed, setShippingSpeed] = useState(0);
  const [comment, setComment] = useState('');

  useEffect(() => {
    fetchDetails();
  }, [transactionId]); // eslint-disable-line

  const fetchDetails = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      if (!token) {
        navigate('/auth?redirect=' + encodeURIComponent(window.location.pathname));
        return;
      }
      const res = await axios.get(`${API}/reviews/details/${transactionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setDetails(res.data);
      if (res.data.existing_review) {
        setSubmitted(true);
      }
    } catch (err) {
      setError(err.response?.data?.detail || t('reviewPage.cannotLoad'));
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (rating === 0) {
      toast.error(t('reviewPage.selectStarRating'));
      return;
    }
    if (comment && comment.trim().length > 0 && comment.trim().length < 20) {
      toast.error(t('reviewPage.commentMinError'));
      return;
    }

    setSubmitting(true);
    try {
      const token = localStorage.getItem('token');
      const payload = { transaction_id: transactionId, rating };
      if (itemAccuracy > 0) payload.item_accuracy = itemAccuracy;
      if (communication > 0) payload.communication = communication;
      if (shippingSpeed > 0) payload.shipping_speed = shippingSpeed;
      if (comment.trim().length >= 20) payload.comment = comment.trim();

      await axios.post(`${API}/reviews/create`, payload, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setSubmitted(true);
      toast.success(t('reviewPage.reviewSubmitted'));
    } catch (err) {
      toast.error(err.response?.data?.detail || t('reviewPage.cannotLoad'));
    } finally {
      setSubmitting(false);
    }
  };

  const ratingLabels = {
    5: t('reviewPage.excellent'),
    4: t('reviewPage.great'),
    3: t('reviewPage.good'),
    2: t('reviewPage.fair'),
    1: t('reviewPage.poor'),
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 py-12">
        <div className="container max-w-lg mx-auto px-4">
          <Card>
            <CardContent className="p-8 text-center">
              <Package className="h-12 w-12 text-red-400 mx-auto mb-4" />
              <h2 className="text-xl font-bold mb-2">{t('reviewPage.cannotLoad')}</h2>
              <p className="text-slate-500 mb-4">{error}</p>
              <Button variant="outline" onClick={() => navigate(-1)}>
                <ArrowLeft className="h-4 w-4 mr-2" /> {t('reviewPage.goBack')}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (submitted) {
    const existing = details?.existing_review;
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 py-12">
        <div className="container max-w-lg mx-auto px-4">
          <Card className="border-green-200 dark:border-green-800" data-testid="review-success">
            <CardContent className="p-8 text-center">
              <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="h-8 w-8 text-green-600" />
              </div>
              <h2 className="text-2xl font-bold text-green-700 dark:text-green-400 mb-2">
                {existing ? t('reviewPage.alreadySubmitted') : t('reviewPage.thankYou')}
              </h2>
              <p className="text-slate-600 dark:text-slate-400 mb-2">
                {existing ? t('reviewPage.alreadyReviewedDesc') : t('reviewPage.successDesc')}
              </p>
              {existing && (
                <div className="flex justify-center gap-0.5 my-4">
                  {[1, 2, 3, 4, 5].map((s) => (
                    <Star key={s} className={`h-6 w-6 ${s <= existing.rating ? 'fill-amber-400 text-amber-400' : 'fill-slate-200 text-slate-200'}`} />
                  ))}
                </div>
              )}
              <div className="flex gap-3 justify-center mt-6">
                <Button variant="outline" onClick={() => navigate('/marketplace')}>
                  {t('reviewPage.continueBrowsing')}
                </Button>
                {details?.seller_id && (
                  <Button onClick={() => navigate(`/store/${details.seller_id}`)}>
                    {t('reviewPage.viewSeller')}
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 py-8">
      <div className="container max-w-2xl mx-auto px-4">
        <Button variant="ghost" onClick={() => navigate(-1)} className="mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" /> {t('reviewPage.back')}
        </Button>

        <Card data-testid="review-form">
          <CardHeader>
            <CardTitle className="text-2xl">{t('reviewPage.howWasPurchase')}</CardTitle>
            <CardDescription>{t('reviewPage.helpOthers')}</CardDescription>
          </CardHeader>

          <CardContent className="space-y-6">
            <div className="flex gap-4 items-center bg-slate-50 dark:bg-slate-800 rounded-lg p-4">
              {details.item_image ? (
                <img src={details.item_image} alt="" className="w-16 h-16 rounded-lg object-cover flex-shrink-0" />
              ) : (
                <div className="w-16 h-16 rounded-lg bg-slate-200 dark:bg-slate-700 flex items-center justify-center flex-shrink-0">
                  <Package className="h-6 w-6 text-slate-400" />
                </div>
              )}
              <div className="min-w-0">
                <h3 className="font-semibold truncate">{details.item_title}</h3>
                <p className="text-sm text-slate-500">{t('reviewPage.soldBy', { name: details.seller_name })}</p>
              </div>
            </div>

            <Separator />

            <div className="space-y-2 text-center" data-testid="overall-rating-section">
              <h3 className="text-lg font-semibold">{t('reviewPage.overallRating')}</h3>
              <p className="text-sm text-slate-500">{t('reviewPage.howWouldYouRate')}</p>
              <div className="flex justify-center">
                <StarSelector value={rating} onChange={setRating} size="lg" />
              </div>
              {rating > 0 && (
                <p className="text-sm text-amber-600 font-medium">{ratingLabels[rating]}</p>
              )}
            </div>

            <Separator />

            <div className="space-y-4" data-testid="category-ratings-section">
              <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">
                {t('reviewPage.detailedRatings')}
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3 text-center">
                  <Package className="h-5 w-5 text-blue-500 mx-auto mb-1" />
                  <StarSelector value={itemAccuracy} onChange={setItemAccuracy} label={t('reviewPage.itemAccuracy')} size="sm" />
                </div>
                <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3 text-center">
                  <MessageSquare className="h-5 w-5 text-green-500 mx-auto mb-1" />
                  <StarSelector value={communication} onChange={setCommunication} label={t('reviewPage.communication')} size="sm" />
                </div>
                <div className="bg-slate-50 dark:bg-slate-800 rounded-lg p-3 text-center">
                  <Truck className="h-5 w-5 text-purple-500 mx-auto mb-1" />
                  <StarSelector value={shippingSpeed} onChange={setShippingSpeed} label={t('reviewPage.shippingSpeed')} size="sm" />
                </div>
              </div>
            </div>

            <Separator />

            <div className="space-y-2" data-testid="comment-section">
              <label className="text-sm font-medium">{t('reviewPage.writtenReview')}</label>
              <Textarea
                placeholder={t('reviewPage.sharePlaceholder')}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                maxLength={500}
                rows={4}
                className="resize-none"
                data-testid="review-comment-input"
              />
              <p className="text-xs text-slate-400 text-right">{comment.length}/500</p>
            </div>

            {comment.length > 0 && comment.length < 20 && (
              <Alert className="bg-amber-50 dark:bg-amber-950 border-amber-200">
                <AlertDescription className="text-amber-700 text-sm">
                  {t('reviewPage.commentMinChars', { count: 20 - comment.length })}
                </AlertDescription>
              </Alert>
            )}
          </CardContent>

          <CardFooter className="flex flex-col gap-3">
            <Button
              className="w-full h-12 text-lg"
              onClick={handleSubmit}
              disabled={rating === 0 || submitting}
              data-testid="submit-review-btn"
            >
              {submitting ? (
                <><Loader2 className="h-5 w-5 mr-2 animate-spin" /> {t('reviewPage.submittingReview')}</>
              ) : (
                <><Send className="h-5 w-5 mr-2" /> {t('reviewPage.submitReview')}</>
              )}
            </Button>
            <p className="text-xs text-slate-400 text-center">
              {t('reviewPage.privacyNote', { name: details?.seller_name ? details.seller_name.split(' ')[0] : 'You' })}
            </p>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
};

export default ReviewPage;
