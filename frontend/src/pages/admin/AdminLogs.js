import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { FileText, Download } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AdminLogs = ({ searchQuery = '' }) => {
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLogs();
  }, [filter]);
  
  // Filter logs based on search query from parent
  const filteredLogs = searchQuery 
    ? logs.filter(log => {
        const detailsStr = typeof log.details === 'object' 
          ? JSON.stringify(log.details) 
          : (log.details || '');
        return log.admin_email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          log.action?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          log.target_type?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          detailsStr.toLowerCase().includes(searchQuery.toLowerCase());
      })
    : logs;

  const fetchLogs = async () => {
    try {
      const endpoint = filter ? `/admin/logs?action_type=${filter}` : '/admin/logs';
      const response = await axios.get(`${API}${endpoint}`);
      setLogs(response.data);
    } catch (error) {
      toast.error('Failed to load logs');
    } finally {
      setLoading(false);
    }
  };

  const exportLogs = () => {
    const csv = [
      ['Date', 'Admin', 'Action', 'Target Type', 'Target ID', 'Details'],
      ...logs.map(log => [
        new Date(log.created_at).toLocaleString(),
        log.admin_email,
        log.action,
        log.target_type,
        log.target_id,
        typeof log.details === 'object' ? JSON.stringify(log.details) : (log.details || '')
      ])
    ].map(row => row.join(',')).join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `admin-logs-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    toast.success('Logs exported');
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2"><FileText className="h-6 w-6" />Admin Action Logs</h2>
          <p className="text-muted-foreground">Audit trail of all admin actions</p>
        </div>
        <Button onClick={exportLogs} variant="outline"><Download className="h-4 w-4 mr-2" />Export Logs</Button>
      </div>

      <div className="flex gap-2">
        <Button variant={!filter ? 'default' : 'outline'} onClick={() => setFilter('')} className={!filter ? 'gradient-button text-white border-0' : ''}>All Actions</Button>
        <Button variant={filter === 'user_update' ? 'default' : 'outline'} onClick={() => setFilter('user_update')}>User Updates</Button>
        <Button variant={filter === 'listing_moderate' ? 'default' : 'outline'} onClick={() => setFilter('listing_moderate')}>Moderation</Button>
        <Button variant={filter === 'promotion_create' ? 'default' : 'outline'} onClick={() => setFilter('promotion_create')}>Promotions</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Action History ({filteredLogs.length})</span>
            {searchQuery && (
              <Badge variant="secondary" className="font-normal">
                Showing results for "{searchQuery}"
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {filteredLogs.length > 0 ? (
            <div className="space-y-2">
              {filteredLogs.map(log => (
                <div key={log.id} className="flex justify-between items-start p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge>{log.action}</Badge>
                      <span className="text-xs text-muted-foreground">{log.admin_email}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{log.target_type}: {log.target_id}</p>
                    {log.details && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {typeof log.details === 'object' 
                          ? JSON.stringify(log.details, null, 2) 
                          : log.details}
                      </p>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">{new Date(log.created_at).toLocaleString()}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">
              {searchQuery ? `No logs matching "${searchQuery}"` : 'No logs yet'}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default AdminLogs;