import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Upload, FileSpreadsheet, Download, CheckCircle2, AlertTriangle,
  ArrowLeft, Loader2, X
} from 'lucide-react';
import { toast } from 'sonner';
import SEO from '../components/SEO';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BulkImportPage = () => {
  const navigate = useNavigate();
  const { token } = useAuth();
  const fileRef = useRef(null);

  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);

  const headers = { Authorization: `Bearer ${token}` };

  const downloadTemplate = async () => {
    try {
      const resp = await axios.get(`${API}/partner-pro/bulk-import/template`, {
        headers,
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(resp.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'bidvex_bulk_import_template.csv';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error('Failed to download template');
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const { data } = await axios.post(`${API}/partner-pro/bulk-import`, form, {
        headers: { ...headers, 'Content-Type': 'multipart/form-data' },
      });
      setResult(data);
      if (data.imported > 0) toast.success(`${data.imported} listings imported`);
      if (data.errors > 0) toast.warning(`${data.errors} rows had errors`);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Import failed';
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer?.files?.[0];
    if (f && f.name.endsWith('.csv')) setFile(f);
    else toast.error('Only CSV files are accepted');
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900" data-testid="bulk-import-page">
      <SEO title="Bulk Import — BidVex" />

      {/* Header */}
      <div className="bg-gradient-to-r from-blue-900 via-slate-900 to-cyan-900">
        <div className="max-w-4xl mx-auto px-4 py-8">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" onClick={() => navigate(-1)} className="text-white hover:bg-white/10" data-testid="bulk-back-btn">
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div className="p-2.5 bg-cyan-500/20 backdrop-blur rounded-xl border border-cyan-400/30">
              <FileSpreadsheet className="h-7 w-7 text-cyan-300" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Bulk Listing Import</h1>
              <p className="text-blue-200/80 text-sm">Upload a CSV to create multiple listings at once</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        {/* Step 1: Template */}
        <Card className="border-0 shadow-md dark:bg-slate-800/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Badge className="bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-300 text-xs">1</Badge>
              Download Template
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
              Start with our template. Required columns: <code className="text-xs bg-slate-100 dark:bg-slate-700 px-1 rounded">title</code>, <code className="text-xs bg-slate-100 dark:bg-slate-700 px-1 rounded">starting_price</code>, <code className="text-xs bg-slate-100 dark:bg-slate-700 px-1 rounded">category</code>.
            </p>
            <Button variant="outline" onClick={downloadTemplate} className="border-cyan-500 text-cyan-600 hover:bg-cyan-50 dark:hover:bg-cyan-900/20" data-testid="download-template-btn">
              <Download className="h-4 w-4 mr-2" /> Download CSV Template
            </Button>
          </CardContent>
        </Card>

        {/* Step 2: Upload */}
        <Card className="border-0 shadow-md dark:bg-slate-800/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Badge className="bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-300 text-xs">2</Badge>
              Upload CSV
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
                file ? 'border-cyan-400 bg-cyan-50/50 dark:bg-cyan-900/10' : 'border-slate-300 dark:border-slate-600 hover:border-cyan-400'
              }`}
              onClick={() => fileRef.current?.click()}
              onDragOver={e => e.preventDefault()}
              onDrop={onDrop}
              data-testid="csv-dropzone"
            >
              <input
                ref={fileRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={e => setFile(e.target.files?.[0] || null)}
                data-testid="csv-file-input"
              />
              {file ? (
                <div className="flex items-center justify-center gap-3">
                  <FileSpreadsheet className="h-8 w-8 text-cyan-500" />
                  <div className="text-left">
                    <p className="font-medium text-slate-900 dark:text-white">{file.name}</p>
                    <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB</p>
                  </div>
                  <button onClick={e => { e.stopPropagation(); setFile(null); }} className="text-slate-400 hover:text-red-500">
                    <X className="h-5 w-5" />
                  </button>
                </div>
              ) : (
                <>
                  <Upload className="h-10 w-10 mx-auto text-slate-400 mb-3" />
                  <p className="font-medium text-slate-700 dark:text-slate-300">Drop CSV here or click to browse</p>
                  <p className="text-xs text-slate-500 mt-1">Max 5 MB</p>
                </>
              )}
            </div>

            <div className="mt-4 flex justify-end">
              <Button
                onClick={handleUpload}
                disabled={!file || uploading}
                className="bg-cyan-600 hover:bg-cyan-700 text-white"
                data-testid="upload-csv-btn"
              >
                {uploading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Upload className="h-4 w-4 mr-2" />}
                {uploading ? 'Importing...' : 'Import Listings'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Result */}
        {result && (
          <Card className="border-0 shadow-md dark:bg-slate-800/50" data-testid="import-result">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                {result.imported > 0 ? <CheckCircle2 className="h-5 w-5 text-green-500" /> : <AlertTriangle className="h-5 w-5 text-amber-500" />}
                Import Results
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-4 text-center">
                  <p className="text-2xl font-bold text-green-600 dark:text-green-400">{result.imported}</p>
                  <p className="text-xs text-green-700 dark:text-green-300">Imported</p>
                </div>
                <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4 text-center">
                  <p className="text-2xl font-bold text-red-600 dark:text-red-400">{result.errors}</p>
                  <p className="text-xs text-red-700 dark:text-red-300">Errors</p>
                </div>
              </div>

              {result.error_details?.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs font-medium text-slate-500 mb-2">Error details:</p>
                  <div className="max-h-40 overflow-y-auto space-y-1">
                    {result.error_details.map((e, i) => (
                      <div key={i} className="flex gap-2 text-xs">
                        <Badge variant="outline" className="text-red-600 shrink-0">Row {e.row}</Badge>
                        <span className="text-slate-600 dark:text-slate-400">{e.error}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default BulkImportPage;
