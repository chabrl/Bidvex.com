import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { CheckCircle2, Loader2, AlertCircle } from 'lucide-react';
import confetti from 'canvas-confetti';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PaymentSuccessPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('processing');
  const [paymentInfo, setPaymentInfo] = useState(null);
  const sessionId = searchParams.get('session_id');

  useEffect(() => {
    if (sessionId) {
      checkPaymentStatus();
    } else {
      setStatus('error');
    }
  }, [sessionId]);

  const checkPaymentStatus = async () => {
    let attempts = 0;
    const maxAttempts = 5;
    const pollInterval = 2000;

    const poll = async () => {
      if (attempts >= maxAttempts) {
        setStatus('timeout');
        return;
      }

      try {
        const response = await axios.get(`${API}/payments/status/${sessionId}`);
        const data = response.data;
        setPaymentInfo(data);

        if (data.payment_status === 'paid') {
          setStatus('success');
          confetti({
            particleCount: 150,
            spread: 100,
            origin: { y: 0.6 },
            colors: ['#F05A4F', '#30C7B5', '#FFD700']
          });
          return;
        } else if (data.status === 'expired') {
          setStatus('expired');
          return;
        }

        attempts++;
        setTimeout(poll, pollInterval);
      } catch (error) {
        console.error('Error checking payment status:', error);
        setStatus('error');
      }
    };

    poll();
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12" data-testid="payment-success-page">
      <Card className="w-full max-w-md glassmorphism">
        <CardContent className="p-8 text-center space-y-6">
          {status === 'processing' && (
            <>
              <Loader2 className="h-16 w-16 mx-auto text-primary animate-spin" />
              <h2 className="text-2xl font-bold">Processing Payment</h2>
              <p className="text-muted-foreground">
                Please wait while we confirm your payment...
              </p>
            </>
          )}

          {status === 'success' && (
            <>
              <CheckCircle2 className="h-16 w-16 mx-auto text-green-500" data-testid="success-icon" />
              <h2 className="text-2xl font-bold">Payment Successful!</h2>
              <p className="text-muted-foreground">
                Congratulations on your purchase! The seller will be notified and will contact you shortly.
              </p>
              {paymentInfo && (
                <div className="bg-accent/20 rounded-lg p-4 text-sm space-y-1">
                  <p><span className="font-medium">Amount:</span> ${(paymentInfo.amount_total / 100).toFixed(2)}</p>
                  <p><span className="font-medium">Status:</span> {paymentInfo.payment_status}</p>
                </div>
              )}
              <div className="flex flex-col sm:flex-row gap-3">
                <Button
                  onClick={() => navigate('/buyer/dashboard')}
                  className="gradient-button text-white border-0 flex-1"
                  data-testid="view-dashboard-btn"
                >
                  View My Purchases
                </Button>
                <Button
                  variant="outline"
                  onClick={() => navigate('/marketplace')}
                  className="flex-1"
                >
                  Continue Shopping
                </Button>
              </div>
            </>
          )}

          {status === 'error' && (
            <>
              <AlertCircle className="h-16 w-16 mx-auto text-red-500" />
              <h2 className="text-2xl font-bold">Payment Error</h2>
              <p className="text-muted-foreground">
                There was an error processing your payment. Please try again or contact support.
              </p>
              <Button
                onClick={() => navigate('/marketplace')}
                className="gradient-button text-white border-0 w-full"
              >
                Return to Marketplace
              </Button>
            </>
          )}

          {status === 'timeout' && (
            <>
              <AlertCircle className="h-16 w-16 mx-auto text-orange-500" />
              <h2 className="text-2xl font-bold">Payment Verification Timeout</h2>
              <p className="text-muted-foreground">
                We're still confirming your payment. Please check your email for confirmation or contact support.
              </p>
              <Button
                onClick={() => navigate('/buyer/dashboard')}
                className="gradient-button text-white border-0 w-full"
              >
                Go to Dashboard
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default PaymentSuccessPage;
