import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import axios from 'axios';
import {
  Building2, Shield, TrendingUp, FileText, Upload,
  CheckCircle, Clock, XCircle, ArrowRight, Briefcase,
  DollarSign, Users, Award, ChevronRight, Loader2
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BecomePartnerPage = () => {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [partnerStatus, setPartnerStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Form state
  const [companyName, setCompanyName] = useState('');
  const [neqNumber, setNeqNumber] = useState('');
  const [neqFile, setNeqFile] = useState(null);
  const [certFiles, setCertFiles] = useState([]);

  useEffect(() => {
    if (user && token) fetchStatus();
    else setLoading(false);
  }, [user, token]);

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API}/partner/status`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setPartnerStatus(res.data);
    } catch { /* user not logged in */ }
    finally { setLoading(false); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!neqFile) { toast.error('NEQ proof document is required.'); return; }
    if (certFiles.length === 0) { toast.error('At least one professional certification is required.'); return; }

    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('company_name', companyName);
      formData.append('neq_number', neqNumber);
      formData.append('neq_document', neqFile);
      certFiles.forEach(f => formData.append('certification_documents', f));

      const res = await axios.post(`${API}/partner/apply`, formData, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' }
      });
      toast.success(res.data.message);
      fetchStatus();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to submit application.');
    } finally { setSubmitting(false); }
  };

  const statusBadge = {
    pending: { icon: Clock, class: 'bg-amber-100 text-amber-800 border-amber-200', label: 'Under Review' },
    verified: { icon: CheckCircle, class: 'bg-emerald-100 text-emerald-800 border-emerald-200', label: 'Verified Partner' },
    rejected: { icon: XCircle, class: 'bg-red-100 text-red-800 border-red-200', label: 'Application Declined' },
  };

  // Value props
  const benefits = [
    { icon: DollarSign, title: 'Only 3% Platform Fee', desc: 'Industry-leading rate. No hidden costs. Compare with 10-15% on BidSpotter or HiBid.' },
    { icon: Shield, title: 'Verified Auction Firm Badge', desc: 'Build buyer trust with a prominent verification badge on all your listings.' },
    { icon: TrendingUp, title: 'Custom Buyer Premiums', desc: 'Set your own buyer premium rate per auction — 10%, 15%, 18%, or any rate you choose.' },
    { icon: Users, title: 'Stripe Connect Payouts', desc: 'Direct payouts to your bank via Stripe Connect. Hammer price + buyer premium, minus the 3% platform fee.' },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950">
      {/* Hero */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(59,130,246,0.15),transparent_70%)]" />
        <div className="max-w-5xl mx-auto px-4 pt-24 pb-16 relative z-10">
          <div className="text-center space-y-4">
            <Badge className="bg-blue-600/20 text-blue-400 border border-blue-500/30 px-4 py-1.5 text-sm font-medium" data-testid="partner-hero-badge">
              <Building2 className="w-4 h-4 mr-2 inline" /> Partner Program
            </Badge>
            <h1 className="text-4xl sm:text-5xl font-bold text-white tracking-tight" data-testid="partner-hero-title">
              Run Your Auctions on BidVex
            </h1>
            <p className="text-lg text-slate-400 max-w-2xl mx-auto">
              A professional-grade platform for licensed auction firms, bankruptcy trustees, and liquidators. 
              Pay only <span className="text-blue-400 font-semibold">3% — the lowest rate in the industry</span>.
            </p>
          </div>
        </div>
      </div>

      {/* Benefits Grid */}
      <div className="max-w-5xl mx-auto px-4 pb-16">
        <div className="grid sm:grid-cols-2 gap-4">
          {benefits.map((b, i) => (
            <Card key={i} className="bg-white/5 border-white/10 backdrop-blur-sm hover:bg-white/[0.07] transition-colors" data-testid={`partner-benefit-${i}`}>
              <CardContent className="p-5 flex gap-4">
                <div className="w-10 h-10 rounded-lg bg-blue-600/20 flex items-center justify-center flex-shrink-0">
                  <b.icon className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-white text-sm">{b.title}</h3>
                  <p className="text-slate-400 text-xs mt-1 leading-relaxed">{b.desc}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Fee Comparison */}
      <div className="max-w-5xl mx-auto px-4 pb-16">
        <Card className="bg-white/5 border-white/10 overflow-hidden">
          <CardHeader className="pb-3">
            <CardTitle className="text-white text-lg flex items-center gap-2">
              <Briefcase className="w-5 h-5 text-blue-400" /> Fee Comparison
            </CardTitle>
          </CardHeader>
          <CardContent className="px-6 pb-6">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="fee-comparison-table">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="text-left text-slate-400 py-2 font-medium">Platform</th>
                    <th className="text-right text-slate-400 py-2 font-medium">Commission</th>
                    <th className="text-right text-slate-400 py-2 font-medium">On $10,000 Sale</th>
                  </tr>
                </thead>
                <tbody className="text-slate-300">
                  <tr className="border-b border-white/5">
                    <td className="py-2.5 font-semibold text-blue-400">BidVex Partner</td>
                    <td className="text-right">3%</td>
                    <td className="text-right font-semibold text-emerald-400">$300</td>
                  </tr>
                  <tr className="border-b border-white/5">
                    <td className="py-2.5">BidSpotter</td>
                    <td className="text-right">8-12%</td>
                    <td className="text-right text-red-400">$800 - $1,200</td>
                  </tr>
                  <tr className="border-b border-white/5">
                    <td className="py-2.5">HiBid</td>
                    <td className="text-right">5-10%</td>
                    <td className="text-right text-red-400">$500 - $1,000</td>
                  </tr>
                  <tr>
                    <td className="py-2.5">Proxibid</td>
                    <td className="text-right">7-10%</td>
                    <td className="text-right text-red-400">$700 - $1,000</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Application Section */}
      <div className="max-w-3xl mx-auto px-4 pb-24">
        <Card className="bg-white/5 border-white/10" data-testid="partner-application-section">
          <CardHeader>
            <CardTitle className="text-white text-lg flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-400" /> Apply for Partner Status
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Status Display */}
            {partnerStatus && partnerStatus.verification_status !== 'unverified' && (
              <div className={`flex items-center gap-3 p-4 rounded-lg border ${statusBadge[partnerStatus.verification_status]?.class || 'bg-slate-800 border-slate-700 text-slate-300'}`} data-testid="partner-status-banner">
                {(() => { const Icon = statusBadge[partnerStatus.verification_status]?.icon || Clock; return <Icon className="w-5 h-5" />; })()}
                <div>
                  <span className="font-semibold text-sm">{statusBadge[partnerStatus.verification_status]?.label || partnerStatus.verification_status}</span>
                  {partnerStatus.company_name && <span className="text-xs ml-2 opacity-75">{partnerStatus.company_name}</span>}
                  {partnerStatus.rejection_reason && <p className="text-xs mt-1">{partnerStatus.rejection_reason}</p>}
                </div>
              </div>
            )}

            {/* Show form only if not logged in, or status is unverified/rejected */}
            {!user ? (
              <div className="text-center py-8 space-y-4">
                <p className="text-slate-400">Sign in to submit your partner application.</p>
                <Button onClick={() => navigate('/auth')} className="bg-blue-600 hover:bg-blue-700" data-testid="partner-login-cta">
                  Sign In <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            ) : partnerStatus?.verification_status === 'verified' ? (
              <div className="text-center py-6 space-y-3">
                <Award className="w-12 h-12 text-emerald-400 mx-auto" />
                <p className="text-emerald-400 font-semibold">You are a Verified Partner!</p>
                <p className="text-slate-400 text-sm">Your listings display the Verified Auction Firm badge.</p>
              </div>
            ) : partnerStatus?.verification_status === 'pending' ? (
              <div className="text-center py-6 space-y-3">
                <Clock className="w-12 h-12 text-amber-400 mx-auto animate-pulse" />
                <p className="text-amber-400 font-semibold">Application Under Review</p>
                <p className="text-slate-400 text-sm">Our team is reviewing your documents. We'll contact you at <span className="text-white">partners@bidvex.ca</span>.</p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-2">
                  <Label className="text-slate-300 text-sm">Company / Firm Name *</Label>
                  <Input
                    value={companyName}
                    onChange={e => setCompanyName(e.target.value)}
                    placeholder="e.g., ABC Auctions Inc."
                    required
                    className="bg-white/5 border-white/10 text-white placeholder:text-slate-500"
                    data-testid="partner-company-name"
                  />
                </div>

                <div className="space-y-2">
                  <Label className="text-slate-300 text-sm">NEQ (Quebec Enterprise Number) *</Label>
                  <Input
                    value={neqNumber}
                    onChange={e => setNeqNumber(e.target.value)}
                    placeholder="e.g., 1234567890"
                    required
                    className="bg-white/5 border-white/10 text-white placeholder:text-slate-500"
                    data-testid="partner-neq-number"
                  />
                </div>

                <div className="space-y-2">
                  <Label className="text-slate-300 text-sm">NEQ Proof Document * <span className="text-slate-500">(PDF, JPG, PNG)</span></Label>
                  <div className="relative">
                    <input
                      type="file"
                      accept=".pdf,.jpg,.jpeg,.png,.webp"
                      onChange={e => setNeqFile(e.target.files[0])}
                      required
                      className="hidden"
                      id="neq-upload"
                      data-testid="partner-neq-upload"
                    />
                    <label htmlFor="neq-upload" className="flex items-center gap-2 px-4 py-2.5 rounded-md border border-dashed border-white/20 bg-white/5 text-slate-400 hover:border-blue-500/50 hover:text-blue-400 cursor-pointer transition-colors text-sm">
                      <Upload className="w-4 h-4" />
                      {neqFile ? <span className="text-white">{neqFile.name}</span> : 'Upload NEQ proof'}
                    </label>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label className="text-slate-300 text-sm">Professional Certifications * <span className="text-slate-500">(Auctioneer license, Trustee credentials)</span></Label>
                  <div className="relative">
                    <input
                      type="file"
                      accept=".pdf,.jpg,.jpeg,.png,.webp"
                      multiple
                      onChange={e => setCertFiles(Array.from(e.target.files))}
                      required
                      className="hidden"
                      id="cert-upload"
                      data-testid="partner-cert-upload"
                    />
                    <label htmlFor="cert-upload" className="flex items-center gap-2 px-4 py-2.5 rounded-md border border-dashed border-white/20 bg-white/5 text-slate-400 hover:border-blue-500/50 hover:text-blue-400 cursor-pointer transition-colors text-sm">
                      <Upload className="w-4 h-4" />
                      {certFiles.length > 0 ? <span className="text-white">{certFiles.length} file(s) selected</span> : 'Upload certifications'}
                    </label>
                  </div>
                </div>

                <div className="bg-white/5 rounded-lg p-4 border border-white/10 text-xs text-slate-400 space-y-1">
                  <p>By applying, you confirm that all submitted documents are authentic and verifiable.</p>
                  <p>Our team will review your application and may contact you at <span className="text-white">partners@bidvex.ca</span> for additional details.</p>
                </div>

                <Button
                  type="submit"
                  disabled={submitting || !companyName || !neqNumber || !neqFile || certFiles.length === 0}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
                  data-testid="partner-submit-btn"
                >
                  {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ChevronRight className="w-4 h-4 mr-2" />}
                  {submitting ? 'Submitting...' : 'Submit Partner Application'}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default BecomePartnerPage;
