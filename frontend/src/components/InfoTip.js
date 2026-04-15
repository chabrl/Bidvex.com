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
 * Unified bilingual tooltip. Desktop: hover. Mobile: focus/tap.
 * Visibility enforced via .bidvex-tooltip-content in index.css.
 */
const InfoTip = ({ en, fr, side = 'top', className = '', inline = false }) => {
  const { i18n } = useTranslation();
  const isFrench = i18n.language?.startsWith('fr');
  const text = isFrench ? (fr || en) : en;

  if (!text) return null;

  if (inline) {
    return (
      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-relaxed" data-testid="infotip-inline">
        {text}
      </p>
    );
  }

  return (
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            role="button"
            tabIndex={0}
            className={`inline-flex items-center justify-center h-5 w-5 rounded-full text-slate-400 hover:text-blue-600 dark:hover:text-cyan-400 transition-colors cursor-help ${className}`}
            aria-label="Info"
            data-testid="infotip-trigger"
          >
            <Info className="h-4 w-4" />
          </span>
        </TooltipTrigger>
        <TooltipContent side={side} className="max-w-[280px] text-xs leading-relaxed">
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default InfoTip;
