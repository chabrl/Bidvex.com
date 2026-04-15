import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../components/ui/tooltip';
import { Info } from 'lucide-react';

/**
 * <InfoTip en="..." fr="..." />
 * Unified bilingual tooltip. Desktop: hover. Mobile: tap.
 * Max 2 lines. No paragraphs. No technical language.
 */
const InfoTip = ({ en, fr, side = 'top', className = '' }) => {
  const { i18n } = useTranslation();
  const isFrench = i18n.language?.startsWith('fr');
  const text = isFrench ? (fr || en) : en;

  if (!text) return null;

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className={`inline-flex items-center justify-center h-4 w-4 rounded-full text-slate-400 hover:text-primary transition-colors focus:outline-none ${className}`}
            aria-label="Info"
            tabIndex={0}
          >
            <Info className="h-3.5 w-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent side={side} className="max-w-[280px] text-xs leading-relaxed">
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default InfoTip;
