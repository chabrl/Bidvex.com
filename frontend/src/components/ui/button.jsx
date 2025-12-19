import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-[#2563EB] text-white shadow-md hover:bg-[#1D4ED8] hover:shadow-lg hover:-translate-y-0.5 disabled:bg-[#9CA3AF] disabled:text-white disabled:shadow-none disabled:translate-y-0",
        destructive:
          "bg-[#DC2626] text-white shadow-sm hover:bg-[#B91C1C] hover:shadow-md",
        outline:
          "border-2 border-[#94A3B8] bg-white text-[#1F2937] shadow-sm hover:bg-[#F1F5F9] hover:border-[#64748B]",
        secondary:
          "bg-[#1E3A5F] text-white shadow-sm hover:bg-[#0F2942] hover:shadow-md",
        ghost: "text-[#374151] hover:bg-[#F1F5F9] hover:text-[#1F2937]",
        link: "text-[#2563EB] underline-offset-4 hover:underline font-medium",
      },
      size: {
        default: "h-10 px-5 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-11 rounded-md px-8 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const Button = React.forwardRef(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props} />
  );
})
Button.displayName = "Button"

export { Button, buttonVariants }
