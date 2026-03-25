import API_BASE from '../config';
import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Loader2, Download, DollarSign, TrendingUp, Shield, BarChart3, FileSpreadsheet, AlertTriangle, Banknote } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { formatCurrency } from '../utils/currencyFormatter';
import { toast } from 'sonner';

const API = `${API_BASE}/api`;

const PERIOD_OPTIONS = [
  { value: 'current', label: 'Current Quarter' },
  { value: 'last', label: 'Last Quarter' },
  { value: 'all', label: 'All Time' },
  { value: 'custom', label: 'Custom Range' },
];

const CHART_COLORS = ['#2563eb', '#059669', '#d97706', '#dc2626', '#7c3aed', '#0891b2', '#be185d', '#4f46e5'];

const AdminTaxDashboard = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [period, setPeriod] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [exporting, setExporting] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (period === 'custom' && startDate && endDate) {
        params.append('start_date', startDate);
        params.append('end_date', endDate);
      } else if (period !== 'custom') {
        params.append('period', period);
      }

      const res = await axios.get(`${API}/admin/tax-dashboard/summary?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data);
    } catch (err) {
      toast.error('Failed to load tax dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (period !== 'custom') fetchData();
  }, [period]);

  const handleCustomSearch = () => {
    if (!startDate || !endDate) {
      toast.error('Please select both start and end dates');
      return;
    }
    fetchData();
  };

  const handleExportCSV = async () => {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (period === 'custom' && startDate && endDate) {
        params.append('start_date', startDate);
        params.append('end_date', endDate);
      } else if (period !== 'custom') {
        params.append('period', period);
      }

      const res = await axios.get(`${API}/admin/tax-dashboard/export-csv?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `bidvex_tax_report_${period}_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('CSV exported successfully');
    } catch {
      toast.error('Failed to export CSV');
    } finally {
      setExporting(false);
    }
  };

  const totals = data?.totals || {};
  const reserve = data?.reserve || {};
  const regional = data?.regional_breakdown || [];

  // Prepare chart data
  const chartData = useMemo(() =>
    regional.map(r => ({
      region: r.region,
      GST: parseFloat(r.gst?.toFixed(2)) || 0,
      QST: parseFloat(r.qst?.toFixed(2)) || 0,
      HST: parseFloat(r.hst?.toFixed(2)) || 0,
    })),
    [regional]
  );

  const pieData = useMemo(() => {
    const items = [];
    if (totals.gst_collected > 0) items.push({ name: 'GST (5%)', value: totals.gst_collected });
    if (totals.qst_collected > 0) items.push({ name: 'QST (9.975%)', value: totals.qst_collected });
    if (totals.hst_collected > 0) items.push({ name: 'HST', value: totals.hst_collected });
    return items;
  }, [totals]);

  const reservePercent = reserve.total_revenue > 0
    ? ((reserve.tax_liability / reserve.total_revenue) * 100).toFixed(1)
    : '0.0';

  return (
    <div className="space-y-6" data-testid="admin-tax-dashboard">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2" data-testid="tax-dashboard-title">
            <Shield className="h-6 w-6 text-blue-600" />
            Tax Collection Dashboard
          </h2>
          <p className="text-muted-foreground text-sm mt-1">
            GST/QST/HST collected from auction commissions and buyer's premiums
          </p>
        </div>
        <Button
          variant="outline"
          onClick={handleExportCSV}
          disabled={exporting || loading}
          className="min-h-[48px] gap-2"
          data-testid="export-csv-btn"
        >
          {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          <FileSpreadsheet className="h-4 w-4" />
          Export CSV
        </Button>
      </div>

      {/* Period Filter */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex flex-col sm:flex-row items-end gap-4">
            <div className="space-y-2 w-full sm:w-48">
              <Label>Period</Label>
              <Select value={period} onValueChange={setPeriod}>
                <SelectTrigger data-testid="period-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PERIOD_OPTIONS.map(o => (
                    <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {period === 'custom' && (
              <>
                <div className="space-y-2 w-full sm:w-40">
                  <Label>{t("admin.startDate")}</Label>
                  <Input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} data-testid="start-date-input" />
                </div>
                <div className="space-y-2 w-full sm:w-40">
                  <Label>{t("admin.endDate")}</Label>
                  <Input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} data-testid="end-date-input" />
                </div>
                <Button onClick={handleCustomSearch} className="min-h-[48px]" data-testid="apply-filter-btn">
                  Apply
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      ) : (
        <>
          {/* Hero Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="border-l-4 border-l-blue-600" data-testid="gst-card">
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground font-medium">GST Collected</p>
                    <p className="text-2xl font-bold text-blue-600" data-testid="gst-total">
                      {formatCurrency(totals.gst_collected || 0)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Remit to CRA (5%)</p>
                  </div>
                  <DollarSign className="h-8 w-8 text-blue-200" />
                </div>
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-emerald-600" data-testid="qst-card">
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground font-medium">QST Collected</p>
                    <p className="text-2xl font-bold text-emerald-600" data-testid="qst-total">
                      {formatCurrency(totals.qst_collected || 0)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Remit to Revenu Qu&eacute;bec (9.975%)</p>
                  </div>
                  <Banknote className="h-8 w-8 text-emerald-200" />
                </div>
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-amber-600" data-testid="hst-card">
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground font-medium">HST Collected</p>
                    <p className="text-2xl font-bold text-amber-600" data-testid="hst-total">
                      {formatCurrency(totals.hst_collected || 0)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">ON, NB, NL, NS, PE</p>
                  </div>
                  <TrendingUp className="h-8 w-8 text-amber-200" />
                </div>
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-purple-600" data-testid="total-tax-card">
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground font-medium">Total Tax Liability</p>
                    <p className="text-2xl font-bold text-purple-600" data-testid="total-tax">
                      {formatCurrency(totals.total_tax_collected || 0)}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">{totals.transaction_count || 0} transactions</p>
                  </div>
                  <Shield className="h-8 w-8 text-purple-200" />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Cash vs Reserve + Pie Chart */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Net Cash vs Tax Reserve */}
            <Card data-testid="reserve-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-amber-500" />
                  Net Cash vs Tax Reserve
                </CardTitle>
                <CardDescription>
                  How much of your revenue is operating cash vs tax liability
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Total Taxable Revenue</span>
                    <span className="font-semibold" data-testid="total-revenue">{formatCurrency(reserve.total_revenue || 0)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-red-600">Tax Liability (to remit)</span>
                    <span className="font-semibold text-red-600" data-testid="tax-liability">-{formatCurrency(reserve.tax_liability || 0)}</span>
                  </div>
                  <div className="border-t pt-3">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">Net Operating Cash</span>
                      <span className="text-xl font-bold text-green-600" data-testid="net-cash">{formatCurrency(reserve.net_operating_cash || 0)}</span>
                    </div>
                  </div>
                  {/* Visual bar */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Operating ({(100 - parseFloat(reservePercent)).toFixed(1)}%)</span>
                      <span>Tax Reserve ({reservePercent}%)</span>
                    </div>
                    <div className="w-full h-4 bg-green-100 rounded-full overflow-hidden flex">
                      <div
                        className="h-full bg-green-500 transition-all"
                        style={{ width: `${100 - parseFloat(reservePercent)}%` }}
                      />
                      <div
                        className="h-full bg-red-400 transition-all"
                        style={{ width: `${reservePercent}%` }}
                      />
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Tax Type Distribution Pie */}
            <Card data-testid="pie-chart-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-blue-500" />
                  Tax Type Distribution
                </CardTitle>
              </CardHeader>
              <CardContent>
                {pieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        outerRadius={80}
                        label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                        dataKey="value"
                      >
                        {pieData.map((_, index) => (
                          <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(val) => formatCurrency(val)} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex flex-col items-center justify-center h-[250px] text-muted-foreground">
                    <BarChart3 className="h-12 w-12 mb-2 opacity-30" />
                    <p>No tax data for this period</p>
                    <p className="text-xs">Complete some transactions to see the breakdown</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Regional Bar Chart */}
          <Card data-testid="regional-chart-card">
            <CardHeader>
              <CardTitle>Tax Revenue by Province/State</CardTitle>
              <CardDescription>GST, QST, and HST collected per region</CardDescription>
            </CardHeader>
            <CardContent>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={350}>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="region" />
                    <YAxis tickFormatter={(val) => formatCurrency(val)} />
                    <Tooltip formatter={(val) => formatCurrency(val)} />
                    <Legend />
                    <Bar dataKey="GST" fill="#2563eb" />
                    <Bar dataKey="QST" fill="#059669" />
                    <Bar dataKey="HST" fill="#d97706" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex flex-col items-center justify-center h-[350px] text-muted-foreground">
                  <BarChart3 className="h-16 w-16 mb-3 opacity-30" />
                  <p className="text-lg font-medium">No regional data available</p>
                  <p className="text-sm">Tax data will appear here once transactions are processed</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Regional Table */}
          {regional.length > 0 && (
            <Card data-testid="regional-table-card">
              <CardHeader>
                <CardTitle>{t("admin.detailedBreakdown")}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left">
                        <th className="pb-3 font-medium">Region</th>
                        <th className="pb-3 font-medium text-right">Transactions</th>
                        <th className="pb-3 font-medium text-right">Taxable Amount</th>
                        <th className="pb-3 font-medium text-right">GST</th>
                        <th className="pb-3 font-medium text-right">QST</th>
                        <th className="pb-3 font-medium text-right">HST</th>
                        <th className="pb-3 font-medium text-right">Total Tax</th>
                      </tr>
                    </thead>
                    <tbody>
                      {regional.map(r => (
                        <tr key={r.region} className="border-b last:border-0">
                          <td className="py-3">
                            <Badge variant="outline">{r.region}</Badge>
                          </td>
                          <td className="py-3 text-right">{r.transactions}</td>
                          <td className="py-3 text-right">{formatCurrency(r.taxable_amount)}</td>
                          <td className="py-3 text-right text-blue-600">{formatCurrency(r.gst)}</td>
                          <td className="py-3 text-right text-emerald-600">{formatCurrency(r.qst)}</td>
                          <td className="py-3 text-right text-amber-600">{formatCurrency(r.hst)}</td>
                          <td className="py-3 text-right font-semibold">{formatCurrency(r.total_tax)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Auction Volume Summary */}
          <Card>
            <CardContent className="pt-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
                <div>
                  <p className="text-xs text-muted-foreground">Hammer Volume</p>
                  <p className="text-lg font-bold">{formatCurrency(totals.total_hammer_volume || 0)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Taxable Revenue</p>
                  <p className="text-lg font-bold">{formatCurrency(totals.total_taxable_revenue || 0)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Total Transactions</p>
                  <p className="text-lg font-bold">{totals.transaction_count || 0}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Effective Tax Rate</p>
                  <p className="text-lg font-bold">
                    {totals.total_taxable_revenue > 0
                      ? ((totals.total_tax_collected / totals.total_taxable_revenue) * 100).toFixed(1)
                      : '0.0'}%
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
};

export default AdminTaxDashboard;
