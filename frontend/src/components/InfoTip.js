import React, { useState } from 'react';
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
 * Bilingual tooltip with mobile-first tap-to-toggle behaviour.
 * Desktop: hover or focus opens the tooltip.
 * Mobile: tap toggles visibility (no hover on touch devices).
 */
const InfoTip = ({ en, fr, side = 'top', className = '', inline = false }) => {
  const { i18n } = useTranslation();
  const isFrench = i18n.language?.startsWith('fr');
  const text = isFrench ? (fr || en) : en;
  const [open, setOpen] = useState(false);

  if (!text) return null;

  if (inline) {
    return (
      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-relaxed" data-testid="infotip-inline">
        {text}
      </p>
    );
  }

  // Detect coarse pointer (touch-first device) → use controlled tap-to-toggle
  // On hover-capable devices, Radix's default open-on-hover still works.
  return (
    <TooltipProvider delayDuration={0}>
      <Tooltip open={open} onOpenChange={setOpen}>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setOpen((v) => !v);
            }}
            onMouseEnter={() => setOpen(true)}
            onMouseLeave={() => setOpen(false)}
            onBlur={() => setOpen(false)}
            className={`inline-flex items-center justify-center h-6 w-6 rounded-full text-slate-400 hover:text-blue-600 dark:hover:text-cyan-400 transition-colors active:scale-95 touch-manipulation ${className}`}
            aria-label="Info"
            aria-expanded={open}
            data-testid="infotip-trigger"
          >
            <Info className="h-4 w-4" />
          </button>
        </TooltipTrigger>
        <TooltipContent
          side={side}
          className="max-w-[280px] text-xs leading-relaxed bidvex-tooltip-content"
          onPointerDownOutside={() => setOpen(false)}
          data-testid="infotip-content"
        >
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default InfoTip;
