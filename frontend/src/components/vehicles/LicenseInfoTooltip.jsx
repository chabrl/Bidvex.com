/**
 * iter438 — LicenseInfoTooltip
 *
 * Reusable ⓘ icon that, when clicked, opens a Shadcn Dialog explaining
 * a specific licence / permit / tax credential. Copy comes from
 * `locales/{en,fr}.json` under `licenseInfo.credentials.{credentialKey}`.
 *
 * Usage:
 *   <Label>
 *     OPC Permit Number
 *     <LicenseInfoTooltip credentialKey="opc" />
 *   </Label>
 *
 * Supported credentialKey values match the keys under
 * `licenseInfo.credentials` — see i18n files. Adding a new credential
 * only requires appending an entry there; no code change needed.
 */

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Info, ExternalLink } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../ui/dialog';
import { Button } from '../ui/button';

const SECTIONS = [
  { key: 'what',     titleKey: 'licenseInfo.sectionWhat' },
  { key: 'why',      titleKey: 'licenseInfo.sectionWhy' },
  { key: 'issuer',   titleKey: 'licenseInfo.sectionIssuer' },
  { key: 'howToGet', titleKey: 'licenseInfo.sectionHowToGet' },
  { key: 'verification', titleKey: 'licenseInfo.sectionVerification' },
];

const LicenseInfoTooltip = ({ credentialKey, className = '' }) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const base = `licenseInfo.credentials.${credentialKey}`;
  const name = t(`${base}.name`, { defaultValue: credentialKey });
  const websiteUrl = t(`${base}.websiteUrl`, { defaultValue: '' });
  const websiteLabel = t(`${base}.websiteLabel`, { defaultValue: '' });

  return (
    <>
      <button
        type="button"
        aria-label={t('licenseInfo.iconAria')}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen(true);
        }}
        className={`inline-flex items-center justify-center h-5 w-5 rounded-full text-slate-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/40 transition-colors ${className}`}
        data-testid={`license-info-trigger-${credentialKey}`}
      >
        <Info className="h-4 w-4" />
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          className="max-w-lg max-h-[85vh] overflow-y-auto"
          data-testid={`license-info-modal-${credentialKey}`}
        >
          <DialogHeader>
            <DialogTitle
              className="pr-6 text-left"
              data-testid={`license-info-title-${credentialKey}`}
            >
              {name}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 text-sm">
            {SECTIONS.map(({ key, titleKey }) => {
              const body = t(`${base}.${key}`, { defaultValue: '' });
              if (!body) return null;
              return (
                <section
                  key={key}
                  data-testid={`license-info-section-${credentialKey}-${key}`}
                >
                  <h4 className="font-semibold text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1">
                    {t(titleKey)}
                  </h4>
                  <p className="text-slate-700 dark:text-slate-200 leading-relaxed">
                    {body}
                  </p>
                </section>
              );
            })}

            {websiteUrl && (
              <section
                className="pt-2 border-t border-slate-100 dark:border-slate-800"
                data-testid={`license-info-website-${credentialKey}`}
              >
                <h4 className="font-semibold text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-1">
                  {t('licenseInfo.sectionWebsite')}
                </h4>
                <a
                  href={websiteUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-700 hover:underline break-all"
                  data-testid={`license-info-website-link-${credentialKey}`}
                >
                  {websiteLabel || websiteUrl}
                  <ExternalLink className="h-3.5 w-3.5 flex-shrink-0" />
                </a>
              </section>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setOpen(false)}
              data-testid={`license-info-close-${credentialKey}`}
            >
              {t('licenseInfo.close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default LicenseInfoTooltip;
