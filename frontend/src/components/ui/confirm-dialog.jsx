import React from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from './alert-dialog';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';

/**
 * ConfirmDialog — modal confirmation for destructive or consequential admin
 * actions (delete, ban, capture deposit, etc.).
 *
 * Usage:
 *   const [confirm, setConfirm] = useState(null);
 *   ...
 *   <AsyncButton onAction={() => setConfirm({
 *       title: 'Capture $500 deposit?',
 *       description: 'This will charge the buyer…',
 *       onConfirm: async () => await api.captureDeposit(id),
 *       variant: 'destructive',
 *       successMessage: 'Deposit captured',
 *   })}>Capture</AsyncButton>
 *   <ConfirmDialog state={confirm} onClose={() => setConfirm(null)} />
 */
export function ConfirmDialog({ state, onClose }) {
  const [busy, setBusy] = React.useState(false);

  const run = async () => {
    if (!state?.onConfirm) return;
    setBusy(true);
    try {
      await state.onConfirm();
      if (state.successMessage) toast.success(state.successMessage);
      onClose();
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        'Action failed';
      toast.error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AlertDialog open={!!state} onOpenChange={(open) => !open && !busy && onClose()}>
      <AlertDialogContent data-testid="confirm-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle data-testid="confirm-title">
            {state?.title || 'Are you sure?'}
          </AlertDialogTitle>
          <AlertDialogDescription className="whitespace-pre-line" data-testid="confirm-description">
            {state?.description || 'This action cannot be undone.'}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={busy} data-testid="confirm-cancel">
            {state?.cancelText || 'Cancel'}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={(e) => { e.preventDefault(); run(); }}
            disabled={busy}
            data-testid="confirm-action"
            className={
              state?.variant === 'destructive'
                ? 'bg-red-600 hover:bg-red-700 text-white'
                : ''
            }
          >
            {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {state?.confirmText || 'Confirm'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
