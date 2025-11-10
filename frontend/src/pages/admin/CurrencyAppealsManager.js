import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { 
  DollarSign, 
  CheckCircle, 
  XCircle, 
  Clock, 
  MapPin, 
  FileText,
  AlertCircle,
  Shield
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CurrencyAppealsManager = () => {
  const { t } = useTranslation();
  const [appeals, setAppeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAppeal, setSelectedAppeal] = useState(null);
  const [adminNotes, setAdminNotes] = useState('');
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    fetchAllAppeals();
  }, []);

  const fetchAllAppeals = async () => {
    try {
      setLoading(true);
      // Fetch all appeals (this would need an admin endpoint)
      // For now, we'll use the user endpoint and assume admin can see all
      const response = await axios.get(`${API}/currency-appeals`);
      setAppeals(response.data.appeals || []);
    } catch (error) {
      console.error('Failed to fetch appeals:', error);
      toast.error('Failed to load currency appeals');
    } finally {
      setLoading(false);
    }
  };

  const handleReviewAppeal = async (appealId, status) => {
    try {
      setProcessing(true);
      await axios.post(`${API}/admin/currency-appeals/${appealId}/review`, {
        status,
        admin_notes: adminNotes
      });
      
      toast.success(`Appeal ${status} successfully!`);
      setSelectedAppeal(null);
      setAdminNotes('');
      fetchAllAppeals();
    } catch (error) {
      console.error('Failed to review appeal:', error);
      toast.error(error.response?.data?.detail || 'Failed to review appeal');
    } finally {
      setProcessing(false);
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      pending: { color: 'bg-yellow-100 text-yellow-800', icon: Clock },
      approved: { color: 'bg-green-100 text-green-800', icon: CheckCircle },
      rejected: { color: 'bg-red-100 text-red-800', icon: XCircle }
    };
    
    const { color, icon: Icon } = styles[status] || styles.pending;
    
    return (
      <Badge className={`${color} flex items-center gap-1`}>
        <Icon className="h-3 w-3" />
        {status.toUpperCase()}
      </Badge>
    );
  };

  const getCurrencyIcon = (currency) => {
    return currency === 'CAD' ? '🇨🇦' : '🇺🇸';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Currency Enforcement Appeals
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Review and manage user requests to change their enforced currency
          </p>
        </CardHeader>
        <CardContent>
          {appeals.length === 0 ? (
            <div className="text-center py-12">
              <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">No currency appeals found</p>
            </div>
          ) : (
            <div className="space-y-4">
              {appeals.map((appeal) => (
                <Card key={appeal.id} className="border-l-4 border-l-primary">
                  <CardContent className="p-6">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      {/* Appeal Details */}
                      <div className="md:col-span-2 space-y-4">
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="flex items-center gap-3 mb-2">
                              <h3 className="font-semibold text-lg">
                                User ID: {appeal.user_id.substring(0, 8)}...
                              </h3>
                              {getStatusBadge(appeal.status)}
                            </div>
                            <div className="flex items-center gap-4 text-sm text-muted-foreground">
                              <span className="flex items-center gap-1">
                                <DollarSign className="h-4 w-4" />
                                Requested: {getCurrencyIcon(appeal.requested_currency)} {appeal.requested_currency}
                              </span>
                              <span className="flex items-center gap-1">
                                <Clock className="h-4 w-4" />
                                {new Date(appeal.submitted_at).toLocaleDateString()}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <div className="flex items-start gap-2">
                            <FileText className="h-4 w-4 text-muted-foreground mt-1" />
                            <div>
                              <p className="font-medium text-sm">Reason:</p>
                              <p className="text-sm text-muted-foreground">{appeal.reason}</p>
                            </div>
                          </div>

                          {appeal.current_location && (
                            <div className="flex items-start gap-2">
                              <MapPin className="h-4 w-4 text-muted-foreground mt-1" />
                              <div>
                                <p className="font-medium text-sm">Current Location:</p>
                                <p className="text-sm text-muted-foreground">{appeal.current_location}</p>
                              </div>
                            </div>
                          )}

                          {appeal.proof_documents && appeal.proof_documents.length > 0 && (
                            <div className="flex items-start gap-2">
                              <FileText className="h-4 w-4 text-muted-foreground mt-1" />
                              <div>
                                <p className="font-medium text-sm">Proof Documents:</p>
                                <ul className="text-sm text-blue-600">
                                  {appeal.proof_documents.map((doc, idx) => (
                                    <li key={idx}>
                                      <a href={doc} target="_blank" rel="noopener noreferrer">
                                        Document {idx + 1}
                                      </a>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            </div>
                          )}

                          {appeal.admin_notes && (
                            <div className="bg-muted p-3 rounded-md">
                              <p className="font-medium text-sm">Admin Notes:</p>
                              <p className="text-sm">{appeal.admin_notes}</p>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="space-y-4">
                        {appeal.status === 'pending' && (
                          <>
                            <div className="space-y-2">
                              <Label htmlFor={`notes-${appeal.id}`}>Admin Notes</Label>
                              <Input
                                id={`notes-${appeal.id}`}
                                placeholder="Add notes about your decision..."
                                value={selectedAppeal === appeal.id ? adminNotes : ''}
                                onChange={(e) => {
                                  setSelectedAppeal(appeal.id);
                                  setAdminNotes(e.target.value);
                                }}
                              />
                            </div>

                            <div className="flex flex-col gap-2">
                              <Button
                                onClick={() => handleReviewAppeal(appeal.id, 'approved')}
                                disabled={processing}
                                className="w-full bg-green-600 hover:bg-green-700"
                              >
                                <CheckCircle className="mr-2 h-4 w-4" />
                                Approve Appeal
                              </Button>
                              <Button
                                onClick={() => handleReviewAppeal(appeal.id, 'rejected')}
                                disabled={processing}
                                variant="destructive"
                                className="w-full"
                              >
                                <XCircle className="mr-2 h-4 w-4" />
                                Reject Appeal
                              </Button>
                            </div>
                          </>
                        )}

                        {appeal.status !== 'pending' && (
                          <div className="text-center py-4">
                            <p className="text-sm text-muted-foreground">
                              Reviewed on {new Date(appeal.reviewed_at).toLocaleDateString()}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Statistics Card */}
      <Card>
        <CardHeader>
          <CardTitle>Appeal Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 bg-yellow-50 rounded-lg">
              <Clock className="h-8 w-8 text-yellow-600 mx-auto mb-2" />
              <p className="text-2xl font-bold">{appeals.filter(a => a.status === 'pending').length}</p>
              <p className="text-sm text-muted-foreground">Pending</p>
            </div>
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <CheckCircle className="h-8 w-8 text-green-600 mx-auto mb-2" />
              <p className="text-2xl font-bold">{appeals.filter(a => a.status === 'approved').length}</p>
              <p className="text-sm text-muted-foreground">Approved</p>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <XCircle className="h-8 w-8 text-red-600 mx-auto mb-2" />
              <p className="text-2xl font-bold">{appeals.filter(a => a.status === 'rejected').length}</p>
              <p className="text-sm text-muted-foreground">Rejected</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default CurrencyAppealsManager;
