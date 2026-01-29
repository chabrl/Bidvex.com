import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';
import { Shield, CheckCircle, XCircle, Eye, RefreshCw, AlertTriangle } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TaxVerificationQueue = () => {
  const [pendingUsers, setPendingUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionModal, setActionModal] = useState({ open: false, action: null, user: null });
  const [rejectionReason, setRejectionReason] = useState('');

  useEffect(() => {
    fetchPendingVerifications();
  }, []);

  const fetchPendingVerifications = async () => {
    try {
      const response = await axios.get(`${API}/admin/tax/pending`);
      setPendingUsers(response.data || []);
    } catch (error) {
      toast.error('Failed to load tax verifications');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (userId) => {
    try {
      await axios.post(`${API}/admin/tax/${userId}/approve`, {
        notes: 'Tax information verified and approved'
      });
      toast.success('Tax information approved! User can now receive payouts.');
      setActionModal({ open: false, action: null, user: null });
      fetchPendingVerifications();
    } catch (error) {
      toast.error('Failed to approve');
    }
  };

  const handleReject = async (userId) => {
    if (!rejectionReason || rejectionReason.length < 10) {
      toast.error('Please provide a detailed rejection reason (minimum 10 characters)');
      return;
    }

    try {
      await axios.post(`${API}/admin/tax/${userId}/reject`, {
        reason: rejectionReason,
        notes: 'Admin rejected - user must resubmit'
      });
      toast.success('Tax information rejected. User has been notified.');
      setActionModal({ open: false, action: null, user: null });
      setRejectionReason('');
      fetchPendingVerifications();
    } catch (error) {
      toast.error('Failed to reject');
    }
  };

  const handleReset = async (userId) => {
    try {
      await axios.post(`${API}/admin/tax/${userId}/reset`);
      toast.success('Tax status reset. User can resubmit information.');
      fetchPendingVerifications();
    } catch (error) {
      toast.error('Failed to reset status');
    }
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Shield className="h-6 w-6 text-blue-600" />
          Tax Verification Queue
        </h2>
        <p className="text-muted-foreground">Review and verify seller tax information (CRA Part XX Compliance)</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-6">
            <p className="text-2xl font-bold text-orange-600">{pendingUsers.length}</p>
            <p className="text-sm text-muted-foreground">Pending Review</p>
          </CardContent>
        </Card>
      </div>

      {/* Pending Verifications List */}
      <Card>
        <CardHeader>
          <CardTitle>Pending Tax Verifications ({pendingUsers.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {pendingUsers.length > 0 ? (
            <div className="space-y-4">
              {pendingUsers.map((user) => (
                <div
                  key={user.id}
                  className="p-4 border-2 border-orange-200 dark:border-orange-900/50 rounded-lg bg-orange-50/50 dark:bg-orange-900/10"
                >
                  <div className="flex flex-col md:flex-row justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-semibold text-slate-900 dark:text-slate-100">
                          {user.name}
                        </h3>
                        <Badge variant={user.seller_type === 'business' ? 'default' : 'secondary'}>
                          {user.seller_type === 'business' ? 'Business' : 'Individual'}
                        </Badge>
                        <Badge variant="outline" className="bg-orange-100 text-orange-800 border-orange-300">
                          {user.tax_verification_status}
                        </Badge>
                      </div>
                      
                      <div className="space-y-1 text-sm">
                        <p className="text-muted-foreground">
                          <strong>Email:</strong> {user.email}
                        </p>
                        {user.seller_type === 'business' && (
                          <>
                            <p className="text-muted-foreground">
                              <strong>Business:</strong> {user.legal_business_name || 'N/A'}
                            </p>
                            <p className="text-muted-foreground">
                              <strong>Province:</strong> {user.business_province || 'N/A'}
                            </p>
                            <p className="text-muted-foreground">
                              <strong>Tax ID (Masked):</strong> {user.tax_id_masked || 'N/A'}
                            </p>
                            {user.business_province === 'QC' && (
                              <>
                                <p className="text-muted-foreground">
                                  <strong>NEQ:</strong> {user.neq_number || 'Not provided'}
                                </p>
                                <p className="text-muted-foreground">
                                  <strong>QST:</strong> {user.qst_number ? user.qst_number.substring(0, 5) + '****' : 'Not provided'}
                                </p>
                              </>
                            )}
                            <p className="text-muted-foreground">
                              <strong>GST/HST:</strong> {user.gst_number ? user.gst_number.substring(0, 5) + '****' : 'Not provided'}
                            </p>
                          </>
                        )}
                        {user.seller_type === 'individual' && (
                          <>
                            <p className="text-muted-foreground">
                              <strong>DOB:</strong> {user.date_of_birth || 'N/A'}
                            </p>
                            <p className="text-muted-foreground">
                              <strong>Tax ID (Masked):</strong> {user.tax_id_masked || 'N/A'}
                            </p>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 md:w-48">
                      <Button
                        size="sm"
                        className="bg-green-600 hover:bg-green-700 text-white"
                        onClick={() => setActionModal({ open: true, action: 'approve', user })}
                      >
                        <CheckCircle className="h-4 w-4 mr-1" />
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => setActionModal({ open: true, action: 'reject', user })}
                      >
                        <XCircle className="h-4 w-4 mr-1" />
                        Reject
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleReset(user.id)}
                      >
                        <RefreshCw className="h-4 w-4 mr-1" />
                        Reset
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">No pending tax verifications</p>
          )}
        </CardContent>
      </Card>

      {/* Confirmation Modal */}
      {actionModal.open && actionModal.user && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg border-2 border-blue-600">
            <CardHeader className={actionModal.action === 'approve' ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'}>
              <CardTitle className={actionModal.action === 'approve' ? 'text-green-600' : 'text-red-600'}>
                {actionModal.action === 'approve' ? '✅ Approve Tax Information' : '❌ Reject Tax Information'}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="p-3 bg-gray-100 dark:bg-gray-800 rounded">
                <p className="font-semibold text-slate-900 dark:text-slate-100">
                  {actionModal.user.name} ({actionModal.user.email})
                </p>
                <p className="text-sm text-muted-foreground">
                  {actionModal.user.seller_type === 'business' ? `Business - ${actionModal.user.business_province || 'N/A'}` : 'Individual Seller'}
                </p>
              </div>

              {actionModal.action === 'approve' ? (
                <p className="text-sm text-slate-900 dark:text-slate-100">
                  By approving, this user will:
                  <ul className="list-disc ml-6 mt-2 space-y-1">
                    <li>Have their status changed to "Verified" 🟢</li>
                    <li>Be able to receive payouts immediately</li>
                    <li>Receive email confirmation</li>
                  </ul>
                </p>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-slate-900 dark:text-slate-100">
                    Provide a reason for rejection (user will see this):
                  </p>
                  <textarea
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                    placeholder="e.g., Invalid Business Number format, Missing required documents, etc."
                    className="w-full px-3 py-2 border rounded-md min-h-[100px] text-slate-900 dark:text-slate-100 bg-white dark:bg-slate-800"
                  />
                  <p className="text-xs text-muted-foreground">
                    {rejectionReason.length}/10 characters minimum
                  </p>
                </div>
              )}

              <div className="flex gap-2 justify-end pt-4 border-t">
                <Button
                  variant="outline"
                  onClick={() => {
                    setActionModal({ open: false, action: null, user: null });
                    setRejectionReason('');
                  }}
                >
                  Cancel
                </Button>
                {actionModal.action === 'approve' ? (
                  <Button
                    className="bg-green-600 hover:bg-green-700 text-white"
                    onClick={() => handleApprove(actionModal.user.id)}
                  >
                    Confirm Approval
                  </Button>
                ) : (
                  <Button
                    variant="destructive"
                    onClick={() => handleReject(actionModal.user.id)}
                    disabled={rejectionReason.length < 10}
                  >
                    Confirm Rejection
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};

export default TaxVerificationQueue;
