import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Star } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const RateSellerModal = ({ 
  isOpen, 
  onClose, 
  auctionId, 
  auctionType = 'single',
  sellerId, 
  sellerName 
}) => {
  const { token } = useAuth();
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (rating === 0) {
      toast.error('Please select a rating');
      return;
    }

    try {
      setSubmitting(true);
      
      const ratingData = {
        auction_id: auctionId,
        auction_type: auctionType || 'single',
        target_user_id: sellerId,
        rating: rating,
        comment: comment.trim() || null
      };

      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      await axios.post(`${API}/ratings`, ratingData, { headers });
      
      toast.success('Rating submitted successfully!');
      handleClose();
    } catch (error) {
      const detail = error.response?.data?.detail;
      let message = 'Failed to submit rating';
      if (typeof detail === 'string') {
        // User-friendly messages for known errors
        if (detail.includes('must participate') || detail.includes('must win')) {
          message = 'You must win at least one item from this seller to leave a rating!';
        } else {
          message = detail;
        }
      } else if (Array.isArray(detail)) {
        message = detail.map(e => (typeof e === 'string' ? e : e?.msg || '')).filter(Boolean).join(', ') || message;
      } else if (detail && typeof detail === 'object') {
        message = detail.msg || JSON.stringify(detail);
      }
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setRating(0);
    setHoverRating(0);
    setComment('');
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md" data-testid="rate-seller-modal">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold">Rate Seller</DialogTitle>
          <DialogDescription>
            Share your experience{sellerName ? <> with <span className="font-semibold">{sellerName}</span></> : ''}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-3">
          {/* Star Rating */}
          <div className="flex flex-col items-center space-y-2.5">
            <p className="text-sm text-muted-foreground">How would you rate this seller?</p>
            <div className="flex gap-1.5">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  className="focus:outline-none transition-transform hover:scale-110"
                  onMouseEnter={() => setHoverRating(star)}
                  onMouseLeave={() => setHoverRating(0)}
                  onClick={() => setRating(star)}
                  data-testid={`rate-star-${star}`}
                >
                  <Star
                    className={`h-9 w-9 transition-colors ${
                      star <= (hoverRating || rating)
                        ? 'fill-amber-400 text-amber-400'
                        : 'text-gray-300 dark:text-gray-600'
                    }`}
                  />
                </button>
              ))}
            </div>
            {rating > 0 && (
              <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
                {['', 'Poor', 'Fair', 'Good', 'Very Good', 'Excellent'][rating]}
              </p>
            )}
          </div>

          {/* Optional Comment */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Comment (Optional)</label>
            <Textarea
              placeholder="Share your experience with this seller..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              maxLength={500}
              className="resize-none text-sm"
              data-testid="rate-comment"
            />
            <p className="text-xs text-muted-foreground text-right">
              {comment.length}/500
            </p>
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" size="sm" onClick={handleClose} disabled={submitting}>
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={submitting || rating === 0}
            className="bg-blue-600 hover:bg-blue-700 text-white"
            data-testid="rate-submit-btn"
          >
            {submitting ? 'Submitting...' : 'Submit Rating'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default RateSellerModal;
