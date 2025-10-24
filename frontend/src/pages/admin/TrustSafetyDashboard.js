import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { toast } from 'sonner';
import { Shield, AlertTriangle, TrendingUp, Users, MessageSquare, Eye, Loader2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TrustSafetyDashboard = () => {
  const [trustScores, setTrustScores] = useState([]);
  const [fraudFlags, setFraudFlags] = useState([]);
  const [collusionPatterns, setCollusionPatterns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanningListing, setScanningListing] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [scoresRes, flagsRes, collusionRes] = await Promise.all([
        axios.get(`${API}/admin/trust-safety/scores`),
        axios.get(`${API}/admin/trust-safety/fraud-flags`),
        axios.get(`${API}/admin/trust-safety/collusion-patterns`)
      ]);
      setTrustScores(scoresRes.data);
      setFraudFlags(flagsRes.data);
      setCollusionPatterns(collusionRes.data);
    } catch (error) {
      toast.error('Failed to load trust & safety data');
    } finally {
      setLoading(false);
    }
  };

  const handleScanListing = async (listingId) => {
    setScanningListing(listingId);
    try {
      const response = await axios.post(`${API}/admin/trust-safety/scan-listing?listing_id=${listingId}`);
      toast.success('Listing scanned successfully');
      console.log('Scan result:', response.data);
      fetchData();
    } catch (error) {
      toast.error('Failed to scan listing');
    } finally {
      setScanningListing(null);
    }
  };

  const handleAutoAction = async (userId, action) => {
    if (window.confirm(`Execute auto-action: ${action}?`)) {
      try {
        await axios.post(`${API}/admin/trust-safety/auto-action`, {
          user_id: userId,
          action: action,
          reason: 'Automated safety action based on risk assessment'
        });
        toast.success(`Action ${action} executed`);
        fetchData();
      } catch (error) {
        toast.error('Failed to execute action');
      }
    }
  };

  if (loading) {
    return <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-4 border-primary border-t-transparent"></div></div>;
  }

  const highRiskUsers = trustScores.filter(u => u.risk_level === 'high');
  const mediumRiskUsers = trustScores.filter(u => u.risk_level === 'medium');

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold flex items-center gap-2"><Shield className="h-6 w-6 text-blue-600" />Trust & Safety Dashboard</h2>
        <p className="text-muted-foreground">AI-powered fraud detection and risk management</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="border-2 border-red-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <AlertTriangle className="h-8 w-8 text-red-600" />
              <div>
                <p className="text-3xl font-bold text-red-600">{highRiskUsers.length}</p>
                <p className="text-sm text-muted-foreground">High Risk Users</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card className="border-2 border-yellow-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <Users className="h-8 w-8 text-yellow-600" />
              <div>
                <p className="text-3xl font-bold text-yellow-600">{mediumRiskUsers.length}</p>
                <p className="text-sm text-muted-foreground">Medium Risk Users</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-2 border-orange-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <AlertTriangle className="h-8 w-8 text-orange-600" />
              <div>
                <p className="text-3xl font-bold text-orange-600">{fraudFlags.length}</p>
                <p className="text-sm text-muted-foreground">Fraud Flags</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-2 border-purple-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <MessageSquare className="h-8 w-8 text-purple-600" />
              <div>
                <p className="text-3xl font-bold text-purple-600">{collusionPatterns.length}</p>
                <p className="text-sm text-muted-foreground">Collusion Patterns</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="scores" className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="scores">Trust Scores</TabsTrigger>
          <TabsTrigger value="flags">Fraud Flags</TabsTrigger>
          <TabsTrigger value="collusion">Collusion</TabsTrigger>
          <TabsTrigger value="ai">AI Scanner</TabsTrigger>
        </TabsList>

        {/* Trust Scores Tab */}
        <TabsContent value="scores">
          <Card>
            <CardHeader><CardTitle>User Trust Scores</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2">
                {trustScores.slice(0, 20).map(user => (
                  <div key={user.user_id} className="flex justify-between items-center p-4 border rounded-lg">
                    <div className="flex-1">
                      <p className="font-semibold">{user.name}</p>
                      <p className="text-sm text-muted-foreground">{user.email}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <p className="text-2xl font-bold gradient-text">{user.trust_score}</p>
                        <p className="text-xs text-muted-foreground">Trust Score</p>
                      </div>
                      <Badge className={user.risk_level === 'high' ? 'bg-red-600 text-white' : user.risk_level === 'medium' ? 'bg-yellow-600 text-white' : 'bg-green-600 text-white'}>
                        {user.risk_level.toUpperCase()}
                      </Badge>
                      {user.risk_level === 'high' && (
                        <Button size="sm" variant="destructive" onClick={() => handleAutoAction(user.user_id, 'suspend_messaging')}>Auto-Suspend</Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Fraud Flags Tab */}
        <TabsContent value="flags">
          <Card>
            <CardHeader><CardTitle>Fraud Detection Flags</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-3">
                {fraudFlags.map((flag, idx) => (
                  <div key={idx} className="p-4 border rounded-lg bg-red-50 dark:bg-red-950">
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Badge variant="destructive">{flag.type.replace('_', ' ').toUpperCase()}</Badge>
                          <Badge className={flag.severity === 'high' ? 'bg-red-600 text-white' : 'bg-yellow-600 text-white'}>{flag.severity}</Badge>
                        </div>
                        <p className="font-semibold">{flag.title || flag.user_name || 'N/A'}</p>
                        <p className="text-sm text-muted-foreground">{flag.description}</p>
                        {flag.listing_id && (
                          <Button size="sm" variant="outline" className="mt-2" onClick={() => handleScanListing(flag.listing_id)} disabled={scanningListing === flag.listing_id}>
                            {scanningListing === flag.listing_id ? <><Loader2 className="h-4 w-4 mr-1 animate-spin" />Scanning...</> : <><Eye className="h-4 w-4 mr-1" />AI Scan</>}
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                {fraudFlags.length === 0 && <p className="text-center text-muted-foreground py-8">No fraud flags detected</p>}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Collusion Patterns Tab */}
        <TabsContent value="collusion">
          <Card>
            <CardHeader><CardTitle>Buyer-Seller Collusion Detection</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-3">
                {collusionPatterns.map((pattern, idx) => (
                  <div key={idx} className="p-4 border rounded-lg bg-purple-50 dark:bg-purple-950">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant="destructive">COLLUSION ALERT</Badge>
                      <Badge className="bg-purple-600 text-white">{pattern.severity.toUpperCase()}</Badge>
                    </div>
                    <p className="font-semibold mb-1">{pattern.seller_name} ↔ {pattern.buyer_name}</p>
                    <p className="text-sm text-muted-foreground">{pattern.description}</p>
                    <div className="flex gap-2 mt-2">
                      <Button size="sm" variant="outline" onClick={() => handleAutoAction(pattern.seller_id, 'require_verification')}>Require Seller Verification</Button>
                      <Button size="sm" variant="outline" onClick={() => handleAutoAction(pattern.buyer_id, 'require_verification')}>Require Buyer Verification</Button>
                    </div>
                  </div>
                ))}
                {collusionPatterns.length === 0 && <p className="text-center text-muted-foreground py-8">No collusion patterns detected</p>}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* AI Scanner Tab */}
        <TabsContent value="ai">
          <Card>
            <CardHeader>
              <CardTitle>AI-Powered Content Scanner</CardTitle>
              <p className="text-sm text-muted-foreground">Scan listings and messages for scams using GPT-4</p>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8">
                <Shield className="h-16 w-16 mx-auto mb-4 text-blue-600" />
                <h3 className="text-lg font-semibold mb-2">AI Scanner Active</h3>
                <p className="text-sm text-muted-foreground mb-4">Use the "AI Scan" button on flagged listings to analyze content</p>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="p-4 border rounded-lg">
                    <TrendingUp className="h-6 w-6 mx-auto mb-2 text-green-600" />
                    <p className="text-sm font-semibold">GPT-4 Text Analysis</p>
                    <p className="text-xs text-muted-foreground">Scam keyword detection</p>
                  </div>
                  <div className="p-4 border rounded-lg">
                    <Eye className="h-6 w-6 mx-auto mb-2 text-blue-600" />
                    <p className="text-sm font-semibold">Vision API</p>
                    <p className="text-xs text-muted-foreground">Image duplicate detection</p>
                  </div>
                  <div className="p-4 border rounded-lg">
                    <MessageSquare className="h-6 w-6 mx-auto mb-2 text-purple-600" />
                    <p className="text-sm font-semibold">Message Scanning</p>
                    <p className="text-xs text-muted-foreground">Off-platform attempts</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default TrustSafetyDashboard;