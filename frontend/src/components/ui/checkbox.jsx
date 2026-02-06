import * as React from "react"
import * as CheckboxPrimitive from "@radix-ui/react-checkbox"
import { Check } from "lucide-react"

import { cn } from "@/lib/utils"

const Checkbox = React.forwardRef(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      // Base styles - Modern rounded checkbox
      "peer relative h-5 w-5 shrink-0 rounded-md",
      // Border and background - Soft, minimal unchecked state
      "border-2 border-slate-300 dark:border-slate-600",
      "bg-transparent",
      // Hover state - Subtle highlight
      "hover:border-blue-400 dark:hover:border-blue-500",
      "hover:bg-blue-50/50 dark:hover:bg-blue-950/30",
      // Focus state - Accessible ring
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-950",
      // Checked state - Brand color with smooth transition
      "data-[state=checked]:border-blue-600 data-[state=checked]:bg-gradient-to-br data-[state=checked]:from-blue-500 data-[state=checked]:to-blue-600",
      "data-[state=checked]:hover:from-blue-600 data-[state=checked]:hover:to-blue-700",
      "dark:data-[state=checked]:from-blue-600 dark:data-[state=checked]:to-blue-700",
      // Indeterminate state
      "data-[state=indeterminate]:border-blue-600 data-[state=indeterminate]:bg-gradient-to-br data-[state=indeterminate]:from-blue-500 data-[state=indeterminate]:to-blue-600",
      // Disabled state
      "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-slate-300 disabled:hover:bg-transparent",
      // Smooth transitions
      "transition-all duration-200 ease-out",
      // Shadow for depth
      "shadow-sm data-[state=checked]:shadow-md data-[state=checked]:shadow-blue-500/25",
      className
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator 
      className={cn(
        "flex items-center justify-center text-white",
        // Checkmark animation
        "animate-in zoom-in-50 duration-200"
      )}
    >
      <Check className="h-3.5 w-3.5 stroke-[3]" />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
))
Checkbox.displayName = CheckboxPrimitive.Root.displayName

// Circular variant for special use cases
const CheckboxCircle = React.forwardRef(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      // Base styles - Circular checkbox
      "peer relative h-5 w-5 shrink-0 rounded-full",
      // Border and background
      "border-2 border-slate-300 dark:border-slate-600",
      "bg-transparent",
      // Hover state
      "hover:border-emerald-400 dark:hover:border-emerald-500",
      "hover:bg-emerald-50/50 dark:hover:bg-emerald-950/30",
      // Focus state
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-slate-950",
      // Checked state
      "data-[state=checked]:border-emerald-500 data-[state=checked]:bg-gradient-to-br data-[state=checked]:from-emerald-400 data-[state=checked]:to-emerald-600",
      "data-[state=checked]:hover:from-emerald-500 data-[state=checked]:hover:to-emerald-700",
      // Disabled state
      "disabled:cursor-not-allowed disabled:opacity-50",
      // Transitions
      "transition-all duration-200 ease-out",
      // Shadow
      "shadow-sm data-[state=checked]:shadow-md data-[state=checked]:shadow-emerald-500/25",
      className
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator 
      className={cn(
        "flex items-center justify-center text-white",
        "animate-in zoom-in-50 duration-200"
      )}
    >
      <Check className="h-3 w-3 stroke-[3]" />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
))
CheckboxCircle.displayName = "CheckboxCircle"

// Small variant for compact spaces
const CheckboxSmall = React.forwardRef(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      // Smaller size
      "peer relative h-4 w-4 shrink-0 rounded",
      // Border and background
      "border-[1.5px] border-slate-300 dark:border-slate-600",
      "bg-transparent",
      // Hover state
      "hover:border-blue-400 dark:hover:border-blue-500",
      "hover:bg-blue-50/50 dark:hover:bg-blue-950/30",
      // Focus state
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 focus-visible:ring-offset-1",
      // Checked state
      "data-[state=checked]:border-blue-600 data-[state=checked]:bg-blue-600",
      "data-[state=checked]:hover:bg-blue-700",
      // Disabled state
      "disabled:cursor-not-allowed disabled:opacity-50",
      // Transitions
      "transition-all duration-150 ease-out",
      className
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator 
      className={cn(
        "flex items-center justify-center text-white",
        "animate-in zoom-in-50 duration-150"
      )}
    >
      <Check className="h-3 w-3 stroke-[3]" />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
))
CheckboxSmall.displayName = "CheckboxSmall"

export { Checkbox, CheckboxCircle, CheckboxSmall }
