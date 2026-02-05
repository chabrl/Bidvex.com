/**
 * Vehicle Invoices Page
 * Shows all invoices for the current user (as buyer or seller)
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { InvoiceView } from '../../components/vehicles/PricingBreakdown';
import {
  Receipt, DollarSign, Clock, CheckCircle, AlertTriangle,
  ChevronLeft, Download, CreditCard, Building2, User,
  TrendingUp, Calendar, FileText
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const formatPrice = (amount) => {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD',
    minimumFractionDigits: 2,
  }).format(amount || 0);
};

const formatDate = (date) => {
  return new Date(date).toLocaleDateString('en-CA', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
};

// Invoice list item component
const InvoiceListItem = ({ invoice, onClick }) => {
  const statusColors = {
    pending: 'bg-amber-100 text-amber-800',
    paid: 'bg-green-100 text-green-800',
    overdue: 'bg-red-100 text-red-800',
    cancelled: 'bg-slate-100 text-slate-800'
  };

  const statusIcons = {
    pending: Clock,
    paid: CheckCircle,
    overdue: AlertTriangle,
    cancelled: FileText
  };

  const StatusIcon = statusIcons[invoice.payment_status] || Clock;

  return (
    <Card 
      className="cursor-pointer hover:shadow-lg transition-shadow"
      onClick={onClick}
      data-testid={`invoice-item-${invoice.id}`}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <Receipt className="h-4 w-4 text-slate-400" />
              <span className="font-mono text-sm text-slate-600">
                {invoice.invoice_number}
              </span>
              <Badge className={statusColors[invoice.payment_status]}>
                <StatusIcon className="h-3 w-3 mr-1" />
                {invoice.payment_status?.charAt(0).toUpperCase() + invoice.payment_status?.slice(1)}
              </Badge>
            </div>
            
            <h3 className="font-semibold text-slate-900 dark:text-white">
              {invoice.vehicle_title}
            </h3>
            
            <p className="text-sm text-slate-500 mt-1">
              VIN: {invoice.vehicle_vin}
            </p>
            
            <div className="flex items-center gap-4 mt-2 text-sm text-slate-500">
              <span className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                {formatDate(invoice.created_at)}
              </span>
              {invoice.invoice_type === 'buyer' && (
                <span className="flex items-center gap-1">
                  <User className="h-4 w-4" />
                  Buyer Invoice
                </span>
              )}
              {invoice.invoice_type === 'seller_settlement' && (
                <span className="flex items-center gap-1">
                  <Building2 className="h-4 w-4" />
                  Seller Settlement
                </span>
              )}
            </div>
          </div>
          
          <div className="text-right">
            <p className="text-2xl font-bold text-blue-600">
              {invoice.invoice_type === 'seller_settlement' 
                ? formatPrice(invoice.net_payout)
                : formatPrice(invoice.total_amount)
              }
            </p>
            <p className="text-xs text-slate-500">
              {invoice.invoice_type === 'seller_settlement' ? 'Net Payout' : 'Total Due'}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Invoice detail view
const InvoiceDetail = ({ invoiceId, onBack }) => {
  const { token } = useAuth();
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [paying, setPaying] = useState(false);

  useEffect(() => {
    const fetchInvoice = async () => {
      try {
        const response = await axios.get(`${API}/vehicle-invoices/${invoiceId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setInvoice(response.data);
      } catch (error) {
        console.error('Failed to fetch invoice:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchInvoice();
  }, [invoiceId, token]);

  const handlePay = async () => {
    setPaying(true);
    try {
      await axios.post(
        `${API}/vehicle-invoices/${invoiceId}/pay`,
        null,
        {
          params: { payment_method: 'card' },
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      // Refresh invoice
      const response = await axios.get(`${API}/vehicle-invoices/${invoiceId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setInvoice(response.data);
    } catch (error) {
      console.error('Payment failed:', error);
    } finally {
      setPaying(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={onBack}>
        <ChevronLeft className="h-4 w-4 mr-1" /> Back to Invoices
      </Button>

      {invoice && <InvoiceView invoice={invoice} />}

      {/* Actions */}
      {invoice && invoice.payment_status !== 'paid' && invoice.invoice_type === 'buyer' && (
        <div className="flex gap-4">
          <Button 
            className="flex-1" 
            size="lg"
            onClick={handlePay}
            disabled={paying}
          >
            <CreditCard className="h-5 w-5 mr-2" />
            {paying ? 'Processing...' : 'Pay Invoice'}
          </Button>
          <Button variant="outline" size="lg">
            <Download className="h-5 w-5 mr-2" />
            Download PDF
          </Button>
        </div>
      )}
    </div>
  );
};

// Main invoices page
const VehicleInvoicesPage = () => {
  const navigate = useNavigate();
  const { invoiceId } = useParams();
  const { user, token } = useAuth();
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedInvoice, setSelectedInvoice] = useState(invoiceId || null);
  const [activeTab, setActiveTab] = useState('all');

  useEffect(() => {
    if (!user) {
      navigate('/auth');
      return;
    }

    const fetchInvoices = async () => {
      try {
        const response = await axios.get(`${API}/vehicle-invoices/my`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setInvoices(response.data.invoices || []);
      } catch (error) {
        console.error('Failed to fetch invoices:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchInvoices();
  }, [user, token, navigate]);

  if (selectedInvoice) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 py-8">
        <div className="max-w-3xl mx-auto px-4">
          <InvoiceDetail 
            invoiceId={selectedInvoice} 
            onBack={() => setSelectedInvoice(null)}
          />
        </div>
      </div>
    );
  }

  const buyerInvoices = invoices.filter(inv => inv.invoice_type === 'buyer');
  const sellerInvoices = invoices.filter(inv => inv.invoice_type === 'seller_settlement');
  const pendingInvoices = invoices.filter(inv => 
    inv.payment_status === 'pending' || inv.payment_status === 'overdue'
  );

  const filteredInvoices = activeTab === 'buyer' ? buyerInvoices :
                          activeTab === 'seller' ? sellerInvoices :
                          activeTab === 'pending' ? pendingInvoices :
                          invoices;

  // Stats
  const totalPending = pendingInvoices
    .filter(inv => inv.invoice_type === 'buyer')
    .reduce((sum, inv) => sum + (inv.total_amount || 0), 0);
  
  const totalEarnings = sellerInvoices
    .filter(inv => inv.settlement_status === 'completed')
    .reduce((sum, inv) => sum + (inv.net_payout || 0), 0);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950" data-testid="vehicle-invoices-page">
      {/* Header */}
      <div className="bg-white dark:bg-slate-900 border-b">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <Button 
            variant="ghost" 
            onClick={() => navigate('/vehicle-auctions')}
            className="mb-4"
          >
            <ChevronLeft className="h-4 w-4 mr-1" /> Back to Vehicle Auctions
          </Button>
          
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
            <Receipt className="h-8 w-8 text-blue-600" />
            My Vehicle Invoices
          </h1>
          <p className="text-slate-500 mt-1">
            View and manage your vehicle auction invoices and settlements
          </p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-amber-100 rounded-lg flex items-center justify-center">
                  <Clock className="h-6 w-6 text-amber-600" />
                </div>
                <div>
                  <p className="text-sm text-slate-500">Pending Payments</p>
                  <p className="text-2xl font-bold text-amber-600">{formatPrice(totalPending)}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
                  <TrendingUp className="h-6 w-6 text-green-600" />
                </div>
                <div>
                  <p className="text-sm text-slate-500">Total Earnings</p>
                  <p className="text-2xl font-bold text-green-600">{formatPrice(totalEarnings)}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                  <FileText className="h-6 w-6 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm text-slate-500">Total Invoices</p>
                  <p className="text-2xl font-bold text-blue-600">{invoices.length}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-6">
            <TabsTrigger value="all">All ({invoices.length})</TabsTrigger>
            <TabsTrigger value="buyer">Purchases ({buyerInvoices.length})</TabsTrigger>
            <TabsTrigger value="seller">Sales ({sellerInvoices.length})</TabsTrigger>
            <TabsTrigger value="pending">
              Pending ({pendingInvoices.length})
              {pendingInvoices.length > 0 && (
                <span className="ml-1 w-2 h-2 bg-amber-500 rounded-full inline-block" />
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value={activeTab}>
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
              </div>
            ) : filteredInvoices.length === 0 ? (
              <Card className="text-center py-12">
                <Receipt className="h-16 w-16 text-slate-300 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-slate-600">No Invoices Found</h3>
                <p className="text-slate-500 mt-1">
                  You don&apos;t have any invoices in this category yet.
                </p>
              </Card>
            ) : (
              <div className="space-y-4">
                {filteredInvoices.map((invoice) => (
                  <InvoiceListItem
                    key={invoice.id}
                    invoice={invoice}
                    onClick={() => setSelectedInvoice(invoice.id)}
                  />
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default VehicleInvoicesPage;
