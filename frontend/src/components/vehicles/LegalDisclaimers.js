/**
 * LegalDisclaimers.js
 * Legal and compliance UI components for vehicle auctions
 * As-Is/Where-Is disclaimers, terms acceptance, platform role notices
 */

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Alert, AlertDescription, AlertTitle } from '../ui/alert';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../ui/dialog';
import {
  AlertTriangle, Shield, FileText, CheckCircle, Info,
  Clock, CreditCard, Gavel, Eye, Car, Scale, Users,
  Building2, Phone, HelpCircle
} from 'lucide-react';

// Platform Role Disclaimer
export const PlatformRoleDisclaimer = ({ compact = false }) => {
  if (compact) {
    return (
      <div className="text-xs text-slate-500 flex items-center gap-1" data-testid="platform-disclaimer-compact">
        <Info className="h-3 w-3" />
        <span>BidVex is a marketplace, not the seller. All sales are direct between buyer and seller.</span>
      </div>
    );
  }

  return (
    <Alert className="border-blue-200 bg-blue-50 dark:bg-blue-950/30" data-testid="platform-disclaimer">
      <Building2 className="h-5 w-5 text-blue-600" />
      <AlertTitle className="text-blue-800 dark:text-blue-200">Platform Role</AlertTitle>
      <AlertDescription className="text-blue-700 dark:text-blue-300 text-sm">
        BidVex operates as a marketplace platform connecting buyers and sellers. 
        We are <strong>not</strong> the seller of any vehicle. All transactions occur 
        directly between the buyer and seller. BidVex does not take title, possession, 
        or responsibility for the vehicles listed.
      </AlertDescription>
    </Alert>
  );
};

// As-Is Where-Is Disclaimer
export const AsIsWhereIsDisclaimer = ({ vehicle, prominent = false }) => {
  const baseClasses = prominent 
    ? "border-2 border-amber-300 bg-amber-50 dark:bg-amber-950/30" 
    : "border-amber-200 bg-amber-50/50 dark:bg-amber-950/20";

  return (
    <Alert className={baseClasses} data-testid="as-is-disclaimer">
      <AlertTriangle className="h-5 w-5 text-amber-600" />
      <AlertTitle className="text-amber-800 dark:text-amber-200">As-Is, Where-Is Sale</AlertTitle>
      <AlertDescription className="text-amber-700 dark:text-amber-300 space-y-2">
        <p className="text-sm">
          This vehicle is sold <strong>"As-Is, Where-Is"</strong> without any warranty, 
          express or implied. The seller makes no representations about the vehicle's 
          condition, merchantability, or fitness for any purpose.
        </p>
        <div className="flex flex-wrap gap-2 mt-2">
          <Badge variant="outline" className="text-amber-700 border-amber-300">No Warranty</Badge>
          <Badge variant="outline" className="text-amber-700 border-amber-300">No Returns</Badge>
          <Badge variant="outline" className="text-amber-700 border-amber-300">Buyer Assumes Risk</Badge>
        </div>
        {prominent && (
          <p className="text-xs mt-3 text-amber-600">
            We strongly recommend inspecting the vehicle in person or hiring a professional 
            inspector before bidding.
          </p>
        )}
      </AlertDescription>
    </Alert>
  );
};

// Inspection Reminder
export const InspectionReminder = () => (
  <Card className="border-blue-200 bg-gradient-to-r from-blue-50 to-cyan-50 dark:from-blue-950/30 dark:to-cyan-950/30" data-testid="inspection-reminder">
    <CardContent className="p-4">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
          <Eye className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <h4 className="font-semibold text-blue-800 dark:text-blue-200">Inspect Before You Bid</h4>
          <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
            All vehicles are sold as-is. We recommend:
          </p>
          <ul className="text-sm text-blue-600 dark:text-blue-400 mt-2 space-y-1">
            <li className="flex items-center gap-2">
              <CheckCircle className="h-3 w-3" /> In-person inspection when possible
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="h-3 w-3" /> Third-party mechanic inspection
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="h-3 w-3" /> Review all photos and condition report
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle className="h-3 w-3" /> Contact seller with questions
            </li>
          </ul>
        </div>
      </div>
    </CardContent>
  </Card>
);

// Payment Terms Display
export const PaymentTermsDisplay = ({ deadline, penaltyRate = 2 }) => (
  <Card className="border-slate-200" data-testid="payment-terms">
    <CardHeader className="pb-2">
      <CardTitle className="text-base flex items-center gap-2">
        <CreditCard className="h-5 w-5 text-slate-600" />
        Payment Terms
      </CardTitle>
    </CardHeader>
    <CardContent className="space-y-3">
      <div className="flex items-start gap-3">
        <Clock className="h-5 w-5 text-slate-400 mt-0.5" />
        <div>
          <p className="font-medium">Payment Deadline</p>
          <p className="text-sm text-slate-500">
            {deadline ? (
              <>Due by {new Date(deadline).toLocaleDateString('en-CA', { 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
              })}</>
            ) : (
              <>Within 14 days of auction end</>
            )}
          </p>
        </div>
      </div>
      
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-amber-500 mt-0.5" />
        <div>
          <p className="font-medium">Late Payment Penalty</p>
          <p className="text-sm text-slate-500">
            {penaltyRate}% per month on overdue balance
          </p>
        </div>
      </div>
      
      <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-3 text-sm">
        <p className="text-slate-600 dark:text-slate-400">
          <strong>Accepted Payment Methods:</strong> Bank transfer, certified cheque, 
          credit card (subject to processing fee)
        </p>
      </div>
    </CardContent>
  </Card>
);

// Binding Bid Notice
export const BindingBidNotice = ({ compact = false }) => {
  if (compact) {
    return (
      <div className="flex items-center gap-2 text-xs text-slate-500 bg-slate-50 dark:bg-slate-800/50 rounded px-2 py-1">
        <Gavel className="h-3 w-3" />
        <span>All bids are legally binding contracts</span>
      </div>
    );
  }

  return (
    <Alert className="border-slate-300 bg-slate-50 dark:bg-slate-900" data-testid="binding-bid-notice">
      <Gavel className="h-5 w-5 text-slate-600" />
      <AlertTitle className="text-slate-800 dark:text-slate-200">Legally Binding Bids</AlertTitle>
      <AlertDescription className="text-slate-600 dark:text-slate-400 text-sm">
        By placing a bid, you enter into a legally binding contract to purchase the vehicle 
        if you are the winning bidder. Bid retractions are only permitted in exceptional 
        circumstances and at the platform's discretion.
      </AlertDescription>
    </Alert>
  );
};

// Terms Acceptance Dialog
export const TermsAcceptanceDialog = ({ 
  open, 
  onOpenChange, 
  onAccept, 
  vehicleTitle,
  loading = false 
}) => {
  const [checksCompleted, setChecksCompleted] = useState({
    asIs: false,
    binding: false,
    inspect: false,
    payment: false,
    platform: false
  });

  const allChecked = Object.values(checksCompleted).every(Boolean);

  const handleAccept = () => {
    if (allChecked) {
      onAccept();
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Scale className="h-6 w-6 text-blue-600" />
            Bidding Terms & Conditions
          </DialogTitle>
          <DialogDescription>
            Please read and accept the following terms before placing your bid on{' '}
            <strong>{vehicleTitle}</strong>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 my-4">
          {/* As-Is Disclaimer */}
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Checkbox
                id="check-as-is"
                checked={checksCompleted.asIs}
                onCheckedChange={(checked) => setChecksCompleted(prev => ({ ...prev, asIs: checked }))}
              />
              <div className="space-y-1">
                <label htmlFor="check-as-is" className="font-semibold text-amber-800 cursor-pointer">
                  As-Is, Where-Is Sale
                </label>
                <p className="text-sm text-amber-700">
                  I understand this vehicle is sold "As-Is, Where-Is" without warranty. 
                  The seller makes no guarantees about condition, and I accept all risk.
                </p>
              </div>
            </div>
          </div>

          {/* Binding Bid */}
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Checkbox
                id="check-binding"
                checked={checksCompleted.binding}
                onCheckedChange={(checked) => setChecksCompleted(prev => ({ ...prev, binding: checked }))}
              />
              <div className="space-y-1">
                <label htmlFor="check-binding" className="font-semibold text-slate-800 cursor-pointer">
                  Legally Binding Bid
                </label>
                <p className="text-sm text-slate-600">
                  I understand my bid is a legally binding contract. If I win, I am 
                  obligated to complete the purchase.
                </p>
              </div>
            </div>
          </div>

          {/* Inspection Responsibility */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Checkbox
                id="check-inspect"
                checked={checksCompleted.inspect}
                onCheckedChange={(checked) => setChecksCompleted(prev => ({ ...prev, inspect: checked }))}
              />
              <div className="space-y-1">
                <label htmlFor="check-inspect" className="font-semibold text-blue-800 cursor-pointer">
                  Inspection Responsibility
                </label>
                <p className="text-sm text-blue-700">
                  I am responsible for inspecting the vehicle or arranging inspection 
                  before bidding. I have reviewed the photos and condition report.
                </p>
              </div>
            </div>
          </div>

          {/* Payment Terms */}
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Checkbox
                id="check-payment"
                checked={checksCompleted.payment}
                onCheckedChange={(checked) => setChecksCompleted(prev => ({ ...prev, payment: checked }))}
              />
              <div className="space-y-1">
                <label htmlFor="check-payment" className="font-semibold text-green-800 cursor-pointer">
                  Payment Terms
                </label>
                <p className="text-sm text-green-700">
                  I understand payment is due within 14 days of auction end, and late 
                  payments are subject to a 2% monthly penalty.
                </p>
              </div>
            </div>
          </div>

          {/* Platform Role */}
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Checkbox
                id="check-platform"
                checked={checksCompleted.platform}
                onCheckedChange={(checked) => setChecksCompleted(prev => ({ ...prev, platform: checked }))}
              />
              <div className="space-y-1">
                <label htmlFor="check-platform" className="font-semibold text-purple-800 cursor-pointer">
                  Platform Role Understanding
                </label>
                <p className="text-sm text-purple-700">
                  I understand BidVex is a marketplace platform, not the seller. 
                  BidVex does not handle title transfer, delivery, or guarantee vehicle condition.
                </p>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter className="flex-col sm:flex-row gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button 
            onClick={handleAccept} 
            disabled={!allChecked || loading}
            className="bg-blue-600 hover:bg-blue-700"
          >
            {loading ? 'Processing...' : 'Accept Terms & Continue'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// Deposit Notice
export const DepositNotice = ({ amount, isPaid = false }) => (
  <Alert 
    className={isPaid 
      ? "border-green-200 bg-green-50 dark:bg-green-950/30" 
      : "border-blue-200 bg-blue-50 dark:bg-blue-950/30"
    }
    data-testid="deposit-notice"
  >
    <CreditCard className={`h-5 w-5 ${isPaid ? 'text-green-600' : 'text-blue-600'}`} />
    <AlertTitle className={isPaid ? "text-green-800 dark:text-green-200" : "text-blue-800 dark:text-blue-200"}>
      {isPaid ? 'Deposit Confirmed' : 'Refundable Deposit Required'}
    </AlertTitle>
    <AlertDescription className={isPaid ? "text-green-700 dark:text-green-300" : "text-blue-700 dark:text-blue-300"}>
      {isPaid ? (
        <span>Your deposit of <strong>${amount}</strong> has been confirmed. You may now place bids.</span>
      ) : (
        <span>
          A refundable deposit of <strong>${amount}</strong> is required before bidding. 
          Deposits are returned to non-winning bidders within 5 business days.
        </span>
      )}
    </AlertDescription>
  </Alert>
);

// Help Contact Card
export const HelpContactCard = () => (
  <Card className="border-slate-200" data-testid="help-contact">
    <CardContent className="p-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-slate-100 rounded-full flex items-center justify-center">
          <HelpCircle className="h-5 w-5 text-slate-600" />
        </div>
        <div className="flex-1">
          <h4 className="font-medium">Need Help?</h4>
          <p className="text-sm text-slate-500">Questions about this listing?</p>
        </div>
        <Button variant="outline" size="sm" className="gap-1">
          <Phone className="h-4 w-4" />
          Contact Support
        </Button>
      </div>
    </CardContent>
  </Card>
);

// Combined Legal Footer
export const LegalFooter = () => (
  <div className="space-y-3 pt-4 border-t border-slate-200 dark:border-slate-800" data-testid="legal-footer">
    <PlatformRoleDisclaimer compact />
    <BindingBidNotice compact />
    <p className="text-xs text-slate-400 text-center">
      By using BidVex, you agree to our{' '}
      <a href="/terms" className="underline hover:text-slate-600">Terms of Service</a>
      {' '}and{' '}
      <a href="/privacy" className="underline hover:text-slate-600">Privacy Policy</a>
    </p>
  </div>
);

export default {
  PlatformRoleDisclaimer,
  AsIsWhereIsDisclaimer,
  InspectionReminder,
  PaymentTermsDisplay,
  BindingBidNotice,
  TermsAcceptanceDialog,
  DepositNotice,
  HelpContactCard,
  LegalFooter
};
