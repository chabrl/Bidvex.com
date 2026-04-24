import React from 'react';
import { Button } from './button';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';

/**
 * AsyncButton — wraps shadcn <Button> with:
 *  - loading spinner while action is in flight
 *  - automatic error toast on throw
 *  - disabled-while-processing guard (no double-clicks)
 *  - optional success toast
 *
 * Props:
 *  - onAction: async function (required) — throws on error
 *  - successMessage: string shown in a toast on success (optional)
 *  - errorMessage: string override for the error toast; if omitted, uses error.message
 *  - confirmBefore: string — if set, confirm() dialog before running (quick guard; use ConfirmDialog for modal)
 *  - ...rest: any <Button> props (variant, size, className, children, data-testid, etc.)
 */
export const AsyncButton = React.forwardRef(function AsyncButton(
  {
    onAction,
    successMessage,
    errorMessage,
    confirmBefore,
    children,
    disabled,
    loadingText,
    ...rest
  },
  ref,
) {
  const [busy, setBusy] = React.useState(false);

  const handleClick = async (e) => {
    if (busy) return;
    if (confirmBefore && !window.confirm(confirmBefore)) return;
    setBusy(true);
    try {
      await onAction(e);
      if (successMessage) toast.success(successMessage);
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.error ||
        err?.message ||
        'Something went wrong. Please try again.';
      const msg = typeof detail === 'string' ? detail : JSON.stringify(detail);
      toast.error(errorMessage || msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button ref={ref} onClick={handleClick} disabled={disabled || busy} {...rest}>
      {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
      {busy && loadingText ? loadingText : children}
    </Button>
  );
});
