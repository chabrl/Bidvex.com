import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import axios from 'axios';
import {
  Building2, Shield, TrendingUp, FileText, Upload,
  CheckCircle, Clock, XCircle, ArrowRight,
  DollarSign, Users, Award, ChevronRight, Loader2, Zap
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BecomePartnerPage = () => {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [partnerStatus, setPartnerStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
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
    } catch { /* not logged in */ }
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

  const benefits = [
    {
      icon: DollarSign,
      title: 'Fixed 3% Platform Fee',
      desc: 'The lowest rate in the industry. No tiered pricing, no hidden charges, no surprises.',
      accent: 'from-emerald-500/20 to-emerald-600/5 border-emerald-500/20',
      iconColor: 'text-emerald-400',
    },
    {
      icon: TrendingUp,
      title: 'Set Your Own Buyer Premium',
      desc: 'Full control over your margin. Configure custom buyer premium rates per auction — 10%, 15%, 18%, or any rate.',
      accent: 'from-blue-500/20 to-blue-600/5 border-blue-500/20',
      iconColor: 'text-blue-400',
    },
    {
      icon: Shield,
      title: 'Verified Auction Firm Badge',
      desc: 'Stand out with a trust badge on every listing. Show buyers they are dealing with a licensed professional.',
      accent: 'from-violet-500/20 to-violet-600/5 border-violet-500/20',
      iconColor: 'text-violet-400',
    },
    {
      icon: Zap,
      title: 'Direct Stripe Connect Payouts',
      desc: 'Hammer price and buyer premium are transferred directly to your bank. No waiting, no intermediaries.',
      accent: 'from-amber-500/20 to-amber-600/5 border-amber-500/20',
      iconColor: 'text-amber-400',
    },
  ];

  const StatusBanner = () => {
    if (!partnerStatus || partnerStatus.verification_status === 'unverified') return null;
    const config = {
      pending: { icon: Clock, bg: 'bg-amber-950/50 border-amber-700/40', text: 'text-amber-300', label: 'Application Under Review', sub: 'Our team is reviewing your documents. Expected turnaround: 24-48 hours.' },
      verified: { icon: Award, bg: 'bg-emerald-950/50 border-emerald-700/40', text: 'text-emerald-300', label: 'Verified Partner', sub: 'Your listings carry the Verified Auction Firm badge.' },
      rejected: { icon: XCircle, bg: 'bg-red-950/50 border-red-700/40', text: 'text-red-300', label: 'Application Declined', sub: partnerStatus.rejection_reason || 'Please contact partners@bidvex.ca for details.' },
    }[partnerStatus.verification_status];
    if (!config) return null;
    const Icon = config.icon;
    return (
      <div className={`flex items-start gap-3 p-4 rounded-xl border ${config.bg}`} data-testid="partner-status-banner">
        <Icon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${config.text}`} />
        <div>
          <p className={`font-semibold text-sm ${config.text}`}>{config.label}</p>
          <p className="text-xs text-slate-400 mt-0.5">{config.sub}</p>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 dark:bg-slate-950 text-white">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(59,130,246,0.12),transparent_60%)]" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,rgba(16,185,129,0.08),transparent_60%)]" />
        </div>
        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 pt-20 sm:pt-28 pb-12 sm:pb-16">
          <div className="space-y-5">
            <Badge className="bg-white/[0.08] text-slate-300 border border-white/10 px-3 py-1 text-xs font-medium tracking-wide backdrop-blur-sm" data-testid="partner-hero-badge">
              <Building2 className="w-3.5 h-3.5 mr-1.5 inline" /> PARTNER PROGRAM
            </Badge>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight leading-[1.1]" data-testid="partner-hero-title">
              Professional Auction
              <br />
              <span className="bg-gradient-to-r from-blue-400 via-emerald-400 to-blue-400 bg-clip-text text-transparent">
                Infrastructure
              </span>
            </h1>
            <p className="text-base sm:text-lg text-slate-400 max-w-xl leading-relaxed">
              BidVex provides licensed auctioneers, bankruptcy trustees, and liquidators with a 
              modern platform to run their sales — at a flat <span className="text-white font-medium">3% platform fee</span>.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              {!user ? (
                <Button onClick={() => navigate('/auth')} size="lg" className="bg-blue-600 hover:bg-blue-700 h-11 px-6 text-sm font-medium" data-testid="partner-cta-signin">
                  Sign In to Apply <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              ) : (
                <Button onClick={() => document.getElementById('apply-section')?.scrollIntoView({ behavior: 'smooth' })} size="lg" className="bg-blue-600 hover:bg-blue-700 h-11 px-6 text-sm font-medium" data-testid="partner-cta-apply">
                  Apply Now <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              )}
              <Button variant="outline" size="lg" className="border-white/10 text-slate-300 hover:bg-white/5 h-11 px-6 text-sm" onClick={() => window.location.href = 'mailto:partners@bidvex.ca'} data-testid="partner-cta-contact">
                Contact Us
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 pb-16 sm:pb-20">
        <div className="grid sm:grid-cols-2 gap-3 sm:gap-4">
          {benefits.map((b, i) => (
            <div
              key={i}
              className={`group relative rounded-xl border bg-gradient-to-br p-5 transition-all duration-300 hover:scale-[1.01] ${b.accent}`}
              data-testid={`partner-benefit-${i}`}
            >
              <div className={`w-9 h-9 rounded-lg bg-white/[0.06] flex items-center justify-center mb-3`}>
                <b.icon className={`w-4.5 h-4.5 ${b.iconColor}`} />
              </div>
              <h3 className="font-semibold text-white text-sm mb-1">{b.title}</h3>
              <p className="text-slate-400 text-xs leading-relaxed">{b.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ROI Highlight */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 pb-16 sm:pb-20">
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-6 sm:p-8 backdrop-blur-sm">
          <div className="flex flex-col sm:flex-row gap-6 sm:gap-10 items-start">
            <div className="flex-1 space-y-2">
              <h2 className="text-lg font-semibold text-white">The Math Is Simple</h2>
              <p className="text-sm text-slate-400 leading-relaxed">
                On a <span className="text-white font-medium">$50,000 liquidation sale</span>, you pay BidVex 
                <span className="text-emerald-400 font-semibold"> $1,500</span>. 
                On other platforms, that same sale costs $4,000 — $7,500.
              </p>
              <p className="text-xs text-slate-500 pt-1">
                You keep your buyer premium. We only charge 3% of hammer price.
                All payment processing fees are transparently passed to the buyer.
              </p>
            </div>
            <div className="flex-shrink-0 text-center px-4 py-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 min-w-[140px]">
              <div className="text-2xl sm:text-3xl font-bold text-emerald-400" data-testid="partner-savings-highlight">3%</div>
              <div className="text-xs text-emerald-400/70 font-medium">Platform Fee</div>
              <div className="text-[10px] text-slate-500 mt-1">vs. 8-15% industry avg.</div>
            </div>
          </div>
        </div>
      </section>

      {/* Application Form */}
      <section id="apply-section" className="max-w-3xl mx-auto px-4 sm:px-6 pb-20 sm:pb-28">
        <div className="rounded-xl border border-white/10 bg-white/[0.02] overflow-hidden">
          <div className="px-6 pt-6 pb-3 border-b border-white/5">
            <h2 className="font-semibold text-white text-base flex items-center gap-2">
              <FileText className="w-4 h-4 text-blue-400" /> Apply for Partner Status
            </h2>
            <p className="text-xs text-slate-500 mt-1">Submit your credentials for review. All fields are mandatory.</p>
          </div>
          <div className="p-6 space-y-5">
            <StatusBanner />

            {!user ? (
              <div className="text-center py-10 space-y-4">
                <Users className="w-10 h-10 text-slate-600 mx-auto" />
                <p className="text-slate-400 text-sm">Sign in to your BidVex account to submit an application.</p>
                <Button onClick={() => navigate('/auth')} className="bg-blue-600 hover:bg-blue-700" data-testid="partner-login-cta">
                  Sign In <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            ) : partnerStatus?.verification_status === 'verified' ? (
              <div className="text-center py-10 space-y-3">
                <Award className="w-12 h-12 text-emerald-400 mx-auto" />
                <p className="text-emerald-400 font-semibold">You are a Verified Partner</p>
                <p className="text-slate-500 text-sm">All your listings carry the Verified Auction Firm badge.</p>
              </div>
            ) : partnerStatus?.verification_status === 'pending' ? null : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-slate-400 text-xs">Company / Firm Name</Label>
                    <Input
                      value={companyName} onChange={e => setCompanyName(e.target.value)}
                      placeholder="e.g., ABC Auctions Inc." required
                      className="bg-white/5 border-white/10 text-white placeholder:text-slate-600 h-9 text-sm"
                      data-testid="partner-company-name"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-slate-400 text-xs">NEQ (Quebec Enterprise Number)</Label>
                    <Input
                      value={neqNumber} onChange={e => setNeqNumber(e.target.value)}
                      placeholder="e.g., 1234567890" required
                      className="bg-white/5 border-white/10 text-white placeholder:text-slate-600 h-9 text-sm"
                      data-testid="partner-neq-number"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-slate-400 text-xs">NEQ Proof Document <span className="text-slate-600">(PDF, JPG, PNG — max 10 MB)</span></Label>
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" onChange={e => setNeqFile(e.target.files[0])} required className="hidden" id="neq-upload" data-testid="partner-neq-upload" />
                  <label htmlFor="neq-upload" className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-dashed border-white/15 bg-white/[0.03] text-slate-500 hover:border-blue-500/40 hover:text-blue-400 cursor-pointer transition-colors text-sm">
                    <Upload className="w-4 h-4 flex-shrink-0" />
                    {neqFile ? <span className="text-white truncate">{neqFile.name}</span> : 'Upload NEQ proof document'}
                  </label>
                </div>

                <div className="space-y-1.5">
                  <Label className="text-slate-400 text-xs">Professional Certifications <span className="text-slate-600">(Auctioneer license, Trustee credentials — max 10 MB each)</span></Label>
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" multiple onChange={e => setCertFiles(Array.from(e.target.files))} required className="hidden" id="cert-upload" data-testid="partner-cert-upload" />
                  <label htmlFor="cert-upload" className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-dashed border-white/15 bg-white/[0.03] text-slate-500 hover:border-blue-500/40 hover:text-blue-400 cursor-pointer transition-colors text-sm">
                    <Upload className="w-4 h-4 flex-shrink-0" />
                    {certFiles.length > 0 ? <span className="text-white">{certFiles.length} file(s) selected</span> : 'Upload professional certifications'}
                  </label>
                </div>

                <div className="rounded-lg bg-white/[0.03] border border-white/5 p-3 text-[11px] text-slate-500 leading-relaxed space-y-1">
                  <p>By submitting, you confirm all documents are authentic and verifiable.</p>
                  <p>Our team will review your application within 24-48 hours and contact you at <span className="text-slate-300">partners@bidvex.ca</span>.</p>
                </div>

                <Button
                  type="submit"
                  disabled={submitting || !companyName || !neqNumber || !neqFile || certFiles.length === 0}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-40 h-10 text-sm font-medium"
                  data-testid="partner-submit-btn"
                >
                  {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ChevronRight className="w-4 h-4 mr-2" />}
                  {submitting ? 'Submitting...' : 'Submit Partner Application'}
                </Button>
              </form>
            )}
          </div>
        </div>
      </section>
    </div>
  );
};

export default BecomePartnerPage;
