/**
 * Checkbox Demo Page - Shows all checkbox variants
 */

import React, { useState } from 'react';
import { Checkbox, CheckboxCircle, CheckboxSmall } from '../components/ui/checkbox';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Label } from '../components/ui/label';

const CheckboxDemo = () => {
  const [checks, setChecks] = useState({
    default1: false,
    default2: true,
    circle1: false,
    circle2: true,
    small1: false,
    small2: true,
    native1: false,
    native2: true,
  });

  const handleChange = (key) => {
    setChecks(prev => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="min-h-screen bg-slate-100 dark:bg-slate-950 py-12">
      <div className="max-w-4xl mx-auto px-4">
        <h1 className="text-3xl font-bold text-center mb-8 text-slate-900 dark:text-white">
          Modern Checkbox Design Demo
        </h1>
        
        <div className="grid md:grid-cols-2 gap-6">
          {/* Default Checkbox */}
          <Card>
            <CardHeader>
              <CardTitle>Default Rounded Checkbox</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-3">
                <Checkbox 
                  id="default1" 
                  checked={checks.default1}
                  onCheckedChange={() => handleChange('default1')}
                />
                <Label htmlFor="default1" className="cursor-pointer">
                  Unchecked state (click me!)
                </Label>
              </div>
              <div className="flex items-center space-x-3">
                <Checkbox 
                  id="default2" 
                  checked={checks.default2}
                  onCheckedChange={() => handleChange('default2')}
                />
                <Label htmlFor="default2" className="cursor-pointer">
                  Checked state with gradient
                </Label>
              </div>
              <div className="flex items-center space-x-3">
                <Checkbox id="disabled" disabled />
                <Label htmlFor="disabled" className="text-slate-400">
                  Disabled state
                </Label>
              </div>
            </CardContent>
          </Card>

          {/* Circular Checkbox */}
          <Card>
            <CardHeader>
              <CardTitle>Circular Checkbox Variant</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-3">
                <CheckboxCircle 
                  id="circle1" 
                  checked={checks.circle1}
                  onCheckedChange={() => handleChange('circle1')}
                />
                <Label htmlFor="circle1" className="cursor-pointer">
                  Unchecked circle
                </Label>
              </div>
              <div className="flex items-center space-x-3">
                <CheckboxCircle 
                  id="circle2" 
                  checked={checks.circle2}
                  onCheckedChange={() => handleChange('circle2')}
                />
                <Label htmlFor="circle2" className="cursor-pointer">
                  Checked with emerald color
                </Label>
              </div>
            </CardContent>
          </Card>

          {/* Small Checkbox */}
          <Card>
            <CardHeader>
              <CardTitle>Small Compact Checkbox</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-3">
                <CheckboxSmall 
                  id="small1" 
                  checked={checks.small1}
                  onCheckedChange={() => handleChange('small1')}
                />
                <Label htmlFor="small1" className="cursor-pointer text-sm">
                  Small unchecked
                </Label>
              </div>
              <div className="flex items-center space-x-3">
                <CheckboxSmall 
                  id="small2" 
                  checked={checks.small2}
                  onCheckedChange={() => handleChange('small2')}
                />
                <Label htmlFor="small2" className="cursor-pointer text-sm">
                  Small checked
                </Label>
              </div>
            </CardContent>
          </Card>

          {/* Native HTML Checkbox */}
          <Card>
            <CardHeader>
              <CardTitle>Native HTML Checkbox (Styled)</CardTitle>
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
            </CardContent>
          </Card>
        </div>

        {/* Form Example */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Real Form Example</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-start space-x-3">
                <Checkbox id="terms" className="mt-1" />
                <div>
                  <Label htmlFor="terms" className="cursor-pointer font-medium">
                    Accept Terms & Conditions
                  </Label>
                  <p className="text-sm text-slate-500 mt-1">
                    By checking this box, you agree to our Terms of Service and Privacy Policy.
                  </p>
                </div>
              </div>
              
              <div className="flex items-start space-x-3">
                <Checkbox id="newsletter" className="mt-1" />
                <div>
                  <Label htmlFor="newsletter" className="cursor-pointer font-medium">
                    Subscribe to Newsletter
                  </Label>
                  <p className="text-sm text-slate-500 mt-1">
                    Receive updates about new features and auction opportunities.
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <Checkbox id="seller" className="mt-1" defaultChecked />
                <div>
                  <Label htmlFor="seller" className="cursor-pointer font-medium">
                    I am a licensed dealer
                  </Label>
                  <p className="text-sm text-slate-500 mt-1">
                    Check this if you hold a valid dealer license in your province.
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default CheckboxDemo;
