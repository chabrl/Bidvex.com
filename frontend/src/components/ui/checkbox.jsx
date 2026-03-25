import * as React from "react"
import * as CheckboxPrimitive from "@radix-ui/react-checkbox"
import { Check } from "lucide-react"

import { cn } from "../../lib/utils"

/**
 * BidVex Unified Checkbox Component
 * 
 * Design: Native, clean, modern checkbox appearance
 * - Square shape with subtle rounded corners
 * - Clear checkmark icon
 * - No gradients, circles, or custom designs
 * - Theme-compatible (light/dark mode)
 * - WCAG-compliant accessibility
 */
const Checkbox = React.forwardRef(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      // Base styles - Clean square checkbox with subtle rounding
      "peer relative h-[18px] w-[18px] shrink-0 rounded-[4px]",
      // Border - Clean, visible border
      "border-2 border-slate-400 dark:border-slate-500",
      // Background - Transparent unchecked (no white background)
      "bg-transparent",
      // Ring offset for focus
      "ring-offset-background",
      // Hover state - Subtle border color change
      "hover:border-blue-500 dark:hover:border-blue-400",
      // Focus state - Accessible focus ring
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2",
      // Checked state - Solid blue background, no gradient
      "data-[state=checked]:border-blue-600 data-[state=checked]:bg-blue-600",
      "data-[state=checked]:hover:bg-blue-700 data-[state=checked]:hover:border-blue-700",
      // Dark mode checked
      "dark:data-[state=checked]:border-blue-500 dark:data-[state=checked]:bg-blue-500",
      "dark:data-[state=checked]:hover:bg-blue-600 dark:data-[state=checked]:hover:border-blue-600",
      // Indeterminate state
      "data-[state=indeterminate]:border-blue-600 data-[state=indeterminate]:bg-blue-600",
      "dark:data-[state=indeterminate]:border-blue-500 dark:data-[state=indeterminate]:bg-blue-500",
      // Disabled state
      "disabled:cursor-not-allowed disabled:opacity-50",
      "disabled:hover:border-slate-400 dark:disabled:hover:border-slate-500",
      // Smooth transition
      "transition-colors duration-150 ease-in-out",
      className
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator 
      className={cn(
        "flex items-center justify-center text-white"
      )}
    >
      <Check className="h-3.5 w-3.5 stroke-[2.5]" />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
))
Checkbox.displayName = CheckboxPrimitive.Root.displayName

/**
 * DEPRECATED: Use Checkbox instead
 * Kept for backward compatibility - redirects to main Checkbox
 */
const CheckboxCircle = Checkbox
CheckboxCircle.displayName = "CheckboxCircle"

/**
 * DEPRECATED: Use Checkbox instead  
 * Kept for backward compatibility - redirects to main Checkbox
 */
const CheckboxSmall = Checkbox
CheckboxSmall.displayName = "CheckboxSmall"

export { Checkbox, CheckboxCircle, CheckboxSmall }
