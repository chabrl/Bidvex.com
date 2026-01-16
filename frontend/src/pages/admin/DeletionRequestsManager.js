import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { AlertTriangle, CheckCircle, XCircle, Eye, Trash2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DeletionRequestsManager = () => {
  const navigate = useNavigate();
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [confirmModal, setConfirmModal] = useState({ open: false, request: null, action: null });

  useEffect(() => {
    fetchRequests();
  }, []);

  const fetchRequests = async () => {
    try {
      const response = await axios.get(`${API}/admin/deletion-requests`);
      setRequests(response.data || []);
    } catch (error) {
      console.error('Failed to fetch deletion requests:', error);
      toast.error('Failed to load deletion requests');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (requestId) => {
    try {
      await axios.post(`${API}/admin/deletion-requests/${requestId}/approve`);
      toast.success('Deletion request approved. Listing deleted.');
      fetchRequests();
      setConfirmModal({ open: false, request: null, action: null });
    } catch (error) {
      toast.error('Failed to approve deletion');
    }
  };

  const handleReject = async (requestId) => {
    try {
      await axios.post(`${API}/admin/deletion-requests/${requestId}/reject`);
      toast.success('Deletion request rejected. Listing remains active.');
      fetchRequests();
      setConfirmModal({ open: false, request: null, action: null });
    } catch (error) {
      toast.error('Failed to reject deletion');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Trash2 className="h-6 w-6 text-red-600" />
          Deletion Requests
        </h2>
        <p className="text-muted-foreground">Review and manage seller deletion requests</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-6">
            <p className="text-2xl font-bold text-orange-600">{requests.length}</p>
            <p className="text-sm text-muted-foreground">Pending Requests</p>
          </CardContent>
        </Card>
      </div>

      {/* Requests List */}
      <Card>
        <CardHeader>
          <CardTitle>Pending Deletion Requests ({requests.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {requests.length > 0 ? (
            <div className="space-y-4">
              {requests.map((req) => (
                <div
                  key={req.id}
                  className="p-4 border-2 border-red-200 dark:border-red-900/50 rounded-lg bg-red-50/50 dark:bg-red-900/10"
                >
                  <div className="flex flex-col md:flex-row justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className="h-5 w-5 text-red-600" />
                        <h3 className="font-semibold text-slate-900 dark:text-slate-100">
                          {req.listing_title}
                        </h3>
                        <Badge variant={req.listing_type === 'multi' ? 'default' : 'secondary'}>
                          {req.listing_type === 'multi' ? `Multi (${req.total_lots} lots)` : 'Single'}
                        </Badge>
                      </div>
                      
                      <div className="space-y-2 text-sm">
                        <p className="text-muted-foreground">
                          <strong>Seller:</strong> {req.seller_name} ({req.seller_email})
                        </p>
                        <p className="text-muted-foreground">
                          <strong>Requested:</strong> {new Date(req.requested_at).toLocaleString()}
                        </p>
                        <div className="p-3 bg-white dark:bg-slate-800 rounded border">
                          <p className="text-xs text-muted-foreground mb-1"><strong>Reason for Deletion:</strong></p>
                          <p className="text-slate-900 dark:text-slate-100">{req.reason}</p>
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 md:w-48">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => navigate(req.listing_type === 'multi' ? `/lots/${req.listing_id}` : `/listing/${req.listing_id}`)}
                      >
                        <Eye className="h-4 w-4 mr-1" />
                        View Listing
                      </Button>
                      <Button
                        size="sm"
                        className="bg-red-600 hover:bg-red-700 text-white"
                        onClick={() => setConfirmModal({ open: true, request: req, action: 'approve' })}
                      >
                        <CheckCircle className="h-4 w-4 mr-1" />
                        Approve & Delete
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setConfirmModal({ open: true, request: req, action: 'reject' })}
                      >
                        <XCircle className="h-4 w-4 mr-1" />
                        Reject Request
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">No pending deletion requests</p>
          )}
        </CardContent>
      </Card>

      {/* Admin Confirmation Modal */}
      {confirmModal.open && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg border-2 border-red-600">
            <CardHeader className="bg-red-50 dark:bg-red-900/20">
              <CardTitle className="text-red-600 flex items-center gap-2">
                <AlertTriangle className="h-6 w-6" />
                {confirmModal.action === 'approve' ? '⚠️ WARNING: Irreversible Action' : 'Reject Deletion Request'}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              {confirmModal.action === 'approve' ? (
                <>
                  <div className="space-y-2">
                    <p className="font-semibold text-slate-900 dark:text-slate-100">
                      English:
                    </p>
                    <p className="text-sm text-slate-700 dark:text-slate-300">
                      You are about to delete a live auction. This action is <strong>permanent and cannot be undone</strong>. 
                      Deleting an active listing may result in loss of bidder trust and potential legal disputes. 
                      Are you sure you wish to proceed?
                    </p>
                  </div>
                  <div className="space-y-2">
                    <p className="font-semibold text-slate-900 dark:text-slate-100">
                      Français:
                    </p>
                    <p className="text-sm text-slate-700 dark:text-slate-300">
                      Vous êtes sur le point de supprimer une enchère en cours. Cette action est <strong>permanente et irréversible</strong>. 
                      La suppression d'une annonce active peut entraîner une perte de confiance des enchérisseurs et des litiges juridiques potentiels. 
                      Êtes-vous sûr de vouloir continuer ?
                    </p>
                  </div>
                  <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded border border-red-300 dark:border-red-700">
                    <p className="text-sm font-semibold text-red-900 dark:text-red-300">
                      Deleting: {confirmModal.request?.listing_title}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Seller: {confirmModal.request?.seller_name}
                    </p>
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-900 dark:text-slate-100">
                  Are you sure you want to reject this deletion request? The listing will remain active.
                </p>
              )}

              <div className="flex gap-2 justify-end pt-4 border-t">
                <Button
                  variant="outline"
                  onClick={() => setConfirmModal({ open: false, request: null, action: null })}
                >
                  Cancel
                </Button>
                {confirmModal.action === 'approve' ? (
                  <Button
                    variant="destructive"
                    onClick={() => handleApprove(confirmModal.request.id)}
                  >
                    Confirm Deletion
                  </Button>
                ) : (
                  <Button
                    variant="default"
                    onClick={() => handleReject(confirmModal.request.id)}
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

export default DeletionRequestsManager;
