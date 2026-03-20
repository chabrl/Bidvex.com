import React, { useState, useMemo, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Switch } from '../components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '../components/ui/popover';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '../components/ui/command';
import { Check, ChevronsUpDown, MapPin, AlertCircle } from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from '../components/ui/button';
import locationData from '../data/locations.json';

const POSTAL_CODE_PATTERNS = {
  CA: {
    regex: /^[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d$/,
    label: 'Postal Code',
    placeholder: 'J1J 1J1',
    format: (v) => {
      const clean = v.replace(/\s/g, '').toUpperCase();
      if (clean.length > 3) return clean.slice(0, 3) + ' ' + clean.slice(3, 6);
      return clean.toUpperCase();
    },
  },
  US: {
    regex: /^\d{5}(-\d{4})?$/,
    label: 'ZIP Code',
    placeholder: '90210',
    format: (v) => v.replace(/[^\d-]/g, ''),
  },
};

const LocationSelector = ({ value, onChange, errors: externalErrors }) => {
  const { t } = useTranslation();
  const [manualCity, setManualCity] = useState(false);
  const [regionOpen, setRegionOpen] = useState(false);
  const [cityOpen, setCityOpen] = useState(false);
  const [postalTouched, setPostalTouched] = useState(false);

  const country = value?.country || 'CA';
  const region = value?.region || '';
  const city = value?.city || '';
  const postalCode = value?.postalCode || '';

  // Get country data
  const countryData = locationData[country];
  const regions = countryData?.regions || {};

  // Build sorted region list
  const regionList = useMemo(() =>
    Object.entries(regions)
      .map(([code, data]) => ({ code, name: data.name }))
      .sort((a, b) => a.name.localeCompare(b.name)),
    [regions]
  );

  // Build city list for selected region
  const cityList = useMemo(() => {
    if (!region || !regions[region]) return [];
    return [...regions[region].cities].sort();
  }, [region, regions]);

  // Postal code config
  const postalConfig = POSTAL_CODE_PATTERNS[country] || POSTAL_CODE_PATTERNS.CA;

  // Validation
  const postalValid = !postalCode || postalConfig.regex.test(postalCode);

  // Detect if the current city was manually entered (not in list)
  useEffect(() => {
    if (city && region && regions[region]) {
      const inList = regions[region].cities.some(
        (c) => c.toLowerCase() === city.toLowerCase()
      );
      if (!inList) setManualCity(true);
    }
  }, []);

  const update = (field, val) => {
    const next = { country, region, city, postalCode, ...{ [field]: val } };
    // Reset dependent fields on cascade
    if (field === 'country') {
      next.region = '';
      next.city = '';
      next.postalCode = '';
    }
    if (field === 'region') {
      next.city = '';
    }
    onChange(next);
  };

  const handlePostalChange = (e) => {
    const formatted = postalConfig.format(e.target.value);
    if (country === 'CA' && formatted.replace(/\s/g, '').length > 6) return;
    if (country === 'US' && formatted.replace(/-/g, '').length > 9) return;
    update('postalCode', formatted);
  };

  return (
    <div className="space-y-4" data-testid="location-selector">
      {/* Row 1: Country + Province/State */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Country */}
        <div className="space-y-2">
          <Label className="flex items-center gap-2">
            <MapPin className="h-4 w-4" />
            {t('locationSelector.country', 'Country')} *
          </Label>
          <Select
            value={country}
            onValueChange={(v) => update('country', v)}
            data-testid="location-country-select"
          >
            <SelectTrigger data-testid="location-country-trigger">
              <SelectValue placeholder={t('locationSelector.selectCountry', 'Select country')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="CA">Canada</SelectItem>
              <SelectItem value="US">United States</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Province/State - Searchable */}
        <div className="space-y-2">
          <Label>
            {country === 'CA'
              ? t('locationSelector.province', 'Province')
              : t('locationSelector.state', 'State')} *
          </Label>
          <Popover open={regionOpen} onOpenChange={setRegionOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                role="combobox"
                aria-expanded={regionOpen}
                className="w-full justify-between font-normal"
                data-testid="location-region-trigger"
              >
                {region
                  ? regionList.find((r) => r.code === region)?.name || region
                  : t('locationSelector.selectRegion', 'Select...')}
                <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
              <Command>
                <CommandInput
                  placeholder={t('locationSelector.searchRegion', 'Search...')}
                  data-testid="location-region-search"
                />
                <CommandList>
                  <CommandEmpty>{t('locationSelector.noRegionFound', 'No results found.')}</CommandEmpty>
                  <CommandGroup>
                    {regionList.map((r) => (
                      <CommandItem
                        key={r.code}
                        value={r.name}
                        onSelect={() => {
                          update('region', r.code);
                          setRegionOpen(false);
                        }}
                        data-testid={`location-region-option-${r.code}`}
                      >
                        <Check className={cn('mr-2 h-4 w-4', region === r.code ? 'opacity-100' : 'opacity-0')} />
                        {r.name} ({r.code})
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
          {externalErrors?.region && (
            <p className="text-xs text-red-500 flex items-center gap-1">
              <AlertCircle className="h-3 w-3" /> {externalErrors.region}
            </p>
          )}
        </div>
      </div>

      {/* Row 2: City + Postal Code */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* City - Searchable or Manual */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>{t('locationSelector.city', 'City')} *</Label>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                {t('locationSelector.enterManually', 'Enter manually')}
              </span>
              <Switch
                checked={manualCity}
                onCheckedChange={(checked) => {
                  setManualCity(checked);
                  if (!checked) update('city', '');
                }}
                data-testid="location-manual-city-toggle"
              />
            </div>
          </div>

          {manualCity ? (
            <Input
              value={city}
              onChange={(e) => update('city', e.target.value)}
              placeholder={t('locationSelector.enterCityName', 'Enter city name...')}
              data-testid="location-city-manual-input"
            />
          ) : (
            <Popover open={cityOpen} onOpenChange={setCityOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  role="combobox"
                  aria-expanded={cityOpen}
                  className="w-full justify-between font-normal"
                  disabled={!region}
                  data-testid="location-city-trigger"
                >
                  {city || t('locationSelector.selectCity', 'Select city...')}
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                <Command>
                  <CommandInput
                    placeholder={t('locationSelector.searchCity', 'Search city...')}
                    data-testid="location-city-search"
                  />
                  <CommandList>
                    <CommandEmpty>
                      <div className="py-2 text-center text-sm">
                        <p>{t('locationSelector.cityNotFound', 'City not found.')}</p>
                        <button
                          className="mt-1 text-blue-600 hover:underline text-xs"
                          onClick={() => {
                            setManualCity(true);
                            setCityOpen(false);
                          }}
                          data-testid="location-city-not-found-manual"
                        >
                          {t('locationSelector.enterManuallyLink', 'Enter manually instead')}
                        </button>
                      </div>
                    </CommandEmpty>
                    <CommandGroup>
                      {cityList.map((c) => (
                        <CommandItem
                          key={c}
                          value={c}
                          onSelect={() => {
                            update('city', c);
                            setCityOpen(false);
                          }}
                          data-testid={`location-city-option-${c.replace(/\s/g, '-')}`}
                        >
                          <Check className={cn('mr-2 h-4 w-4', city === c ? 'opacity-100' : 'opacity-0')} />
                          {c}
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          )}
          {externalErrors?.city && (
            <p className="text-xs text-red-500 flex items-center gap-1">
              <AlertCircle className="h-3 w-3" /> {externalErrors.city}
            </p>
          )}
        </div>

        {/* Postal / ZIP Code */}
        <div className="space-y-2">
          <Label>{postalConfig.label} *</Label>
          <Input
            value={postalCode}
            onChange={handlePostalChange}
            onBlur={() => setPostalTouched(true)}
            placeholder={postalConfig.placeholder}
            className={cn(
              postalTouched && postalCode && !postalValid && 'border-red-500 focus-visible:ring-red-500'
            )}
            data-testid="location-postal-code-input"
          />
          {postalTouched && postalCode && !postalValid && (
            <p className="text-xs text-red-500 flex items-center gap-1">
              <AlertCircle className="h-3 w-3" />
              {country === 'CA'
                ? t('locationSelector.invalidPostal', 'Format: A1A 1A1')
                : t('locationSelector.invalidZip', 'Format: 12345 or 12345-6789')}
            </p>
          )}
          {externalErrors?.postalCode && (
            <p className="text-xs text-red-500 flex items-center gap-1">
              <AlertCircle className="h-3 w-3" /> {externalErrors.postalCode}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default LocationSelector;
