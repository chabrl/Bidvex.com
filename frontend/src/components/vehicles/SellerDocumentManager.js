import API_BASE from '../../config';
/**
 * Seller Document Upload Component
 * Handles document upload for seller verification
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Progress } from '../../components/ui/progress';
import { useTranslation } from 'react-i18next';
import {
  Upload, FileText, CheckCircle, XCircle, Clock, AlertTriangle,
  Image, File, Trash2, Eye, RefreshCw, Shield, Info
} from 'lucide-react';

const API = API_BASE;

// Document type labels
const DOCUMENT_LABELS = {
  identity_front: 'ID Front',
  identity_back: 'ID Back',
  proof_of_address: 'Proof of Address',
  business_registration: 'Business Registration',
  dealer_license: 'Dealer License',
  auctioneer_license: 'Auctioneer License',
  insurance_certificate: 'Insurance Certificate',
  tax_certificate: 'Tax Certificate',
  vehicle_ownership: 'Vehicle Ownership',
  vehicle_title: 'Vehicle Title',
  inspection_report: 'Inspection Report',
  carfax_report: 'Vehicle History Report'
};

// Status badge component
const StatusBadge = ({ status }) => {
  const { t } = useTranslation();
  const config = {
    pending: { color: 'bg-amber-100 text-amber-800', icon: Clock, label: 'Pending Review' },
    approved: { color: 'bg-green-100 text-green-800', icon: CheckCircle, label: 'Approved' },
    rejected: { color: 'bg-red-100 text-red-800', icon: XCircle, label: 'Rejected' },
    expired: { color: 'bg-slate-100 text-slate-800', icon: AlertTriangle, label: 'Expired' }
  };

  const { color, icon: Icon, label } = config[status] || config.pending;

  return (
    <Badge className={color}>
      <Icon className="h-3 w-3 mr-1" />
      {label}
    </Badge>
  );
};

// Single document card
const DocumentCard = ({ document, onReupload }) => {
  const isImage = document.mime_type?.startsWith('image/');
  const FileIcon = isImage ? Image : FileText;

  const formatDate = (date) => {
    return new Date(date).toLocaleDateString('en-CA', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <Card className={`${document.status === 'rejected' ? 'border-red-300' : ''}`}>
      <CardContent className="p-4">
        <div className="flex items-start gap-4">
          <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
            document.status === 'approved' ? 'bg-green-100' :
            document.status === 'rejected' ? 'bg-red-100' :
            'bg-slate-100'
          }`}>
            <FileIcon className={`h-6 w-6 ${
              document.status === 'approved' ? 'text-green-600' :
              document.status === 'rejected' ? 'text-red-600' :
              'text-slate-600'
            }`} />
          </div>
          
          <div className="flex-1">
            <div className="flex items-start justify-between">
              <div>
                <h4 className="font-semibold text-slate-900 dark:text-white">
                  {DOCUMENT_LABELS[document.document_type] || document.document_type}
                </h4>
                <p className="text-sm text-slate-500 mt-0.5">
                  {document.original_filename}
                </p>
              </div>
              <StatusBadge status={document.status} />
            </div>

            <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
              <span>Uploaded: {formatDate(document.uploaded_at)}</span>
              <span>{formatSize(document.file_size)}</span>
            </div>

            {document.status === 'rejected' && document.rejection_reason && (
              <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                <strong>Rejection reason:</strong> {document.rejection_reason}
              </div>
            )}

            {document.status === 'rejected' && (
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={() => onReupload(document.document_type)}
              >
                <RefreshCw className="h-4 w-4 mr-1" />
                Re-upload Document
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Upload dropzone component
const UploadDropzone = ({ documentType, onUpload, isUploading }) => {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const droppedFile = e.dataTransfer?.files?.[0];
    if (droppedFile) {
      validateAndSetFile(droppedFile);
    }
  }, []);

  const handleFileInput = (e) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      validateAndSetFile(selectedFile);
    }
  };

  const validateAndSetFile = (f) => {
    setError(null);
    
    // Validate type
    const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];
    if (!allowedTypes.includes(f.type)) {
      setError('Invalid file type. Allowed: PDF, JPG, PNG, WEBP');
      return;
    }

    // Validate size (10MB)
    if (f.size > 10 * 1024 * 1024) {
      setError('File too large. Maximum size: 10MB');
      return;
    }

    setFile(f);
  };

  const handleUpload = async () => {
    if (!file) return;
    
    setUploading(true);
    setError(null);

    try {
      await onUpload(documentType, file);
      setFile(null);
    } catch (err) {
      setError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div
        className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
          dragActive ? 'border-blue-500 bg-blue-50' : 'border-slate-300 hover:border-slate-400'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        {file ? (
          <div className="space-y-3">
            <div className="flex items-center justify-center gap-2">
              <File className="h-8 w-8 text-blue-600" />
              <div className="text-left">
                <p className="font-medium text-slate-900">{file.name}</p>
                <p className="text-sm text-slate-500">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setFile(null)}
              >
                <Trash2 className="h-4 w-4 text-red-500" />
              </Button>
            </div>
            <Button 
              onClick={handleUpload} 
              disabled={uploading}
              className="w-full"
            >
              {uploading ? 'Uploading...' : 'Upload Document'}
            </Button>
          </div>
        ) : (
          <>
            <Upload className="h-10 w-10 text-slate-400 mx-auto mb-2" />
            <p className="text-sm text-slate-600">
              Drag and drop your file here, or
            </p>
            <label className="cursor-pointer">
              <span className="text-blue-600 hover:underline">browse</span>
              <input
                type="file"
                className="hidden"
                accept=".pdf,.jpg,.jpeg,.png,.webp"
                onChange={handleFileInput}
              />
            </label>
            <p className="text-xs text-slate-500 mt-2">
              PDF, JPG, PNG, WEBP (max 10MB)
            </p>
          </>
        )}
      </div>

      {error && (
        <p className="text-sm text-red-600 flex items-center gap-1">
          <AlertTriangle className="h-4 w-4" />
          {error}
        </p>
      )}
    </div>
  );
};

// Main document manager component
const SellerDocumentManager = ({ onVerificationComplete }) => {
  const { token } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [requiredDocs, setRequiredDocs] = useState([]);
  const [verificationStatus, setVerificationStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploadingType, setUploadingType] = useState(null);

  const fetchDocuments = async () => {
    try {
      const [docsRes, requiredRes] = await Promise.all([
        axios.get(`${API}/vehicle-documents/my`, {
          headers: { Authorization: `Bearer ${token}` }
        }),
        axios.get(`${API}/vehicle-documents/required`, {
          headers: { Authorization: `Bearer ${token}` }
        })
      ]);

      setDocuments(docsRes.data.documents || []);
      setVerificationStatus(docsRes.data.verification_status);
      setRequiredDocs(requiredRes.data.required_documents || []);
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [token]);

  const handleUpload = async (documentType, file) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);

    await axios.post(`${API}/vehicle-documents/upload`, formData, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'multipart/form-data'
      }
    });

    // Refresh documents
    await fetchDocuments();
    setUploadingType(null);

    // Check if verification complete
    if (verificationStatus?.all_verified && onVerificationComplete) {
      onVerificationComplete();
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  // Calculate progress
  const uploadedCount = requiredDocs.filter(d => d.uploaded).length;
  const approvedCount = documents.filter(d => d.status === 'approved').length;
  const progress = requiredDocs.length > 0 
    ? Math.round((approvedCount / requiredDocs.length) * 100) 
    : 0;

  return (
    <div className="space-y-6" data-testid="document-manager">
      {/* Verification Progress */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-blue-600" />
            Document Verification
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600">
                {approvedCount} of {requiredDocs.length} documents approved
              </span>
              <span className="font-medium">{progress}%</span>
            </div>
            <Progress value={progress} className="h-2" />

            {verificationStatus?.all_verified ? (
              <div className="flex items-center gap-2 text-green-600 bg-green-50 p-3 rounded-lg">
                <CheckCircle className="h-5 w-5" />
                <span className="font-medium">All documents verified!</span>
              </div>
            ) : verificationStatus?.missing_documents?.length > 0 && (
              <div className="flex items-start gap-2 text-amber-700 bg-amber-50 p-3 rounded-lg">
                <Info className="h-5 w-5 mt-0.5" />
                <div>
                  <p className="font-medium">Missing documents:</p>
                  <ul className="text-sm mt-1 list-disc list-inside">
                    {verificationStatus.missing_documents.map(doc => (
                      <li key={doc}>{DOCUMENT_LABELS[doc] || doc}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Required Documents */}
      <Card>
        <CardHeader>
          <CardTitle>{t("vehicles.requiredDocuments")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {requiredDocs.map((docReq) => {
            const existingDoc = documents.find(d => d.document_type === docReq.type && d.status !== 'rejected');
            const rejectedDoc = documents.find(d => d.document_type === docReq.type && d.status === 'rejected');
            
            if (existingDoc) {
              return <DocumentCard key={docReq.type} document={existingDoc} onReupload={setUploadingType} />;
            }

            if (rejectedDoc && uploadingType !== docReq.type) {
              return <DocumentCard key={docReq.type} document={rejectedDoc} onReupload={setUploadingType} />;
            }

            return (
              <Card key={docReq.type} className="border-dashed">
                <CardContent className="p-4">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center">
                      <Upload className="h-6 w-6 text-slate-400" />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-semibold text-slate-900">
                        {DOCUMENT_LABELS[docReq.type] || docReq.name}
                      </h4>
                      <p className="text-sm text-slate-500 mt-0.5">
                        {docReq.description}
                      </p>

                      {uploadingType === docReq.type ? (
                        <div className="mt-3">
                          <UploadDropzone
                            documentType={docReq.type}
                            onUpload={handleUpload}
                          />
                          <Button
                            variant="ghost"
                            size="sm"
                            className="mt-2"
                            onClick={() => setUploadingType(null)}
                          >
                            Cancel
                          </Button>
                        </div>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-3"
                          onClick={() => setUploadingType(docReq.type)}
                        >
                          <Upload className="h-4 w-4 mr-1" />
                          Upload
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
};

export default SellerDocumentManager;
