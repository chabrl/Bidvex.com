/**
 * iter375 — Template picker modal.
 *
 * Shown when admin clicks "+ New page" on the Landing Pages list.
 * Selection navigates to `/admin/landing-pages/new?template={id}` — the
 * editor reads that query param and pre-fills the form.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../../components/ui/dialog';
import { Button } from '../../components/ui/button';
import {
  FileText, Store, ShoppingCart, Handshake, Car, Warehouse, ArrowRight,
} from 'lucide-react';
import { LANDING_PAGE_TEMPLATES } from './landingPageTemplates';

const ICON_MAP = {
  FileText, Store, ShoppingCart, Handshake, Car, Warehouse,
};

export default function LandingPageTemplatePicker({ open, onOpenChange }) {
  const navigate = useNavigate();

  const choose = (id) => {
    onOpenChange(false);
    navigate(`/admin/landing-pages/new?template=${id}`);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-4xl"
        data-testid="lp-template-picker"
      >
        <DialogHeader>
          <DialogTitle>Choose a starter template</DialogTitle>
          <DialogDescription>
            Every template is fully editable after creation. Pick the one closest to your goal — you can always start blank.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 mt-2">
          {LANDING_PAGE_TEMPLATES.map((tpl) => {
            const Icon = ICON_MAP[tpl.icon] || FileText;
            const isBlank = tpl.id === 'blank';
            return (
              <button
                key={tpl.id}
                type="button"
                onClick={() => choose(tpl.id)}
                data-testid={`lp-template-${tpl.id}`}
                className={`group relative text-left rounded-xl border-2 p-4 transition-all
                  ${isBlank
                    ? 'border-dashed border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-white'
                    : 'border-slate-200 bg-white hover:border-cyan-400 hover:shadow-lg hover:-translate-y-0.5'}
                `}
              >
                <div className={`w-11 h-11 rounded-lg flex items-center justify-center mb-3
                  ${isBlank
                    ? 'bg-slate-200 text-slate-600'
                    : 'bg-gradient-to-br from-[#2B8FD0] to-[#3FB4CB] text-white shadow-md shadow-cyan-500/25'
                  }`}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                  {tpl.name_en}
                  <ArrowRight className="h-3.5 w-3.5 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-cyan-600" />
                </div>
                <div className="text-xs text-slate-500 mt-1 leading-snug">
                  {tpl.description_en}
                </div>
                <div className="text-[11px] text-slate-400 mt-2 italic">
                  {tpl.name_fr}
                </div>
              </button>
            );
          })}
        </div>

        <div className="flex justify-end pt-3 border-t mt-2">
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            data-testid="lp-template-cancel"
          >
            Cancel
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
