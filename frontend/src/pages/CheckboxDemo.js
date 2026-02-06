/**
 * Checkbox Demo Page - Shows unified BidVex checkbox style
 * 
 * This demonstrates the single, standardized checkbox design
 * used across the entire BidVex platform.
 */

import React, { useState } from 'react';
import { Checkbox } from '../components/ui/checkbox';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Label } from '../components/ui/label';
import { Check, AlertCircle } from 'lucide-react';

const CheckboxDemo = () => {
  const [checks, setChecks] = useState({
    demo1: false,
    demo2: true,
    demo3: false,
    native1: false,
    native2: true,
    terms: false,
    newsletter: false,
    dealer: true,
    notifications: false,
  });

  const handleChange = (key) => {
    setChecks(prev => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-slate-950 py-12">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold mb-3 text-slate-900 dark:text-white">
            BidVex Unified Checkbox Design
          </h1>
          <p className="text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
            Clean, modern, native checkbox appearance. One consistent style across the entire platform.
          </p>
        </div>
        
        <div className="grid md:grid-cols-2 gap-6">
          {/* Radix UI Checkbox (Component) */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Check className="w-5 h-5 text-blue-600" />
                Component Checkbox
              </CardTitle>
              <CardDescription>
                Using the Radix UI Checkbox component
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-3">
                <Checkbox 
                  id="demo1" 
                  checked={checks.demo1}
                  onCheckedChange={() => handleChange('demo1')}
                />
                <Label htmlFor="demo1" className="cursor-pointer">
                  Unchecked state (click me!)
                </Label>
              </div>
              <div className="flex items-center space-x-3">
                <Checkbox 
                  id="demo2" 
                  checked={checks.demo2}
                  onCheckedChange={() => handleChange('demo2')}
                />
                <Label htmlFor="demo2" className="cursor-pointer">
                  Checked state
                </Label>
              </div>
              <div className="flex items-center space-x-3">
                <Checkbox id="disabled" disabled />
                <Label htmlFor="disabled" className="text-slate-400 cursor-not-allowed">
                  Disabled state
                </Label>
              </div>
            </CardContent>
          </Card>

          {/* Native HTML Checkbox */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Check className="w-5 h-5 text-blue-600" />
                Native HTML Checkbox
              </CardTitle>
              <CardDescription>
                Standard HTML input with global CSS styling
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-3">
                <input 
                  type="checkbox" 
                  id="native1"
                  checked={checks.native1}
                  onChange={() => handleChange('native1')}
                />
                <label htmlFor="native1" className="cursor-pointer">
                  Native unchecked
                </label>
              </div>
              <div className="flex items-center space-x-3">
                <input 
                  type="checkbox" 
                  id="native2"
                  checked={checks.native2}
                  onChange={() => handleChange('native2')}
                />
                <label htmlFor="native2" className="cursor-pointer">
                  Native checked
                </label>
              </div>
              <div className="flex items-center space-x-3">
                <input 
                  type="checkbox" 
                  id="nativeDisabled"
                  disabled
                />
                <label htmlFor="nativeDisabled" className="text-slate-400 cursor-not-allowed">
                  Disabled state
                </label>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* States Demo */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>All Checkbox States</CardTitle>
            <CardDescription>
              Consistent behavior across unchecked, checked, hover, focus, and disabled states
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div className="text-center">
                <div className="flex justify-center mb-2">
                  <Checkbox checked={false} />
                </div>
                <span className="text-sm text-slate-600 dark:text-slate-400">Unchecked</span>
              </div>
              <div className="text-center">
                <div className="flex justify-center mb-2">
                  <Checkbox checked={true} />
                </div>
                <span className="text-sm text-slate-600 dark:text-slate-400">Checked</span>
              </div>
              <div className="text-center">
                <div className="flex justify-center mb-2">
                  <Checkbox disabled />
                </div>
                <span className="text-sm text-slate-600 dark:text-slate-400">Disabled</span>
              </div>
              <div className="text-center">
                <div className="flex justify-center mb-2">
                  <Checkbox checked={true} disabled />
                </div>
                <span className="text-sm text-slate-600 dark:text-slate-400">Checked + Disabled</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Form Example */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Real Form Example</CardTitle>
            <CardDescription>
              How checkboxes appear in actual BidVex forms
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-5">
              <div className="flex items-start space-x-3">
                <Checkbox 
                  id="terms" 
                  className="mt-0.5"
                  checked={checks.terms}
                  onCheckedChange={() => handleChange('terms')}
                />
                <div>
                  <Label htmlFor="terms" className="cursor-pointer font-medium">
                    Accept Terms & Conditions
                  </Label>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    By checking this box, you agree to our Terms of Service and Privacy Policy.
                  </p>
                </div>
              </div>
              
              <div className="flex items-start space-x-3">
                <Checkbox 
                  id="newsletter" 
                  className="mt-0.5"
                  checked={checks.newsletter}
                  onCheckedChange={() => handleChange('newsletter')}
                />
                <div>
                  <Label htmlFor="newsletter" className="cursor-pointer font-medium">
                    Subscribe to Newsletter
                  </Label>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Receive updates about new features and auction opportunities.
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <Checkbox 
                  id="dealer" 
                  className="mt-0.5"
                  checked={checks.dealer}
                  onCheckedChange={() => handleChange('dealer')}
                />
                <div>
                  <Label htmlFor="dealer" className="cursor-pointer font-medium">
                    I am a licensed dealer
                  </Label>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Check this if you hold a valid dealer license in your province.
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <input 
                  type="checkbox" 
                  id="notifications"
                  className="mt-0.5"
                  checked={checks.notifications}
                  onChange={() => handleChange('notifications')}
                />
                <div>
                  <label htmlFor="notifications" className="cursor-pointer font-medium block">
                    Enable push notifications
                  </label>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Get instant alerts for bids and auction updates.
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Design Specs */}
        <Card className="mt-6 border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-blue-700 dark:text-blue-300">
              <AlertCircle className="w-5 h-5" />
              Design Specifications
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm text-slate-700 dark:text-slate-300">
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-green-600" />
                Square shape with 4px border radius
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-green-600" />
                18x18px size for optimal touch targets
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-green-600" />
                2px border in slate-400 (unchecked)
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-green-600" />
                Blue-600 fill when checked
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-green-600" />
                No gradients, shadows, or custom icons
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-green-600" />
                Transparent background (adapts to theme)
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-green-600" />
                WCAG 2.1 AA compliant contrast
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default CheckboxDemo;
