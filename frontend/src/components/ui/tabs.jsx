import * as React from "react"
import * as TabsPrimitive from "@radix-ui/react-tabs"

import { cn } from "@/lib/utils"

const Tabs = TabsPrimitive.Root

const TabsList = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(
      "inline-flex items-center w-full border-b-2 border-slate-200 dark:border-slate-700",
      "bg-transparent",
      className
    )}
    style={{ 
      background: 'transparent',
      backgroundColor: 'transparent',
      padding: 0,
      gap: 0,
      WebkitAppearance: 'none',
      MozAppearance: 'none',
      appearance: 'none'
    }}
    {...props} />
))
TabsList.displayName = TabsPrimitive.List.displayName

const TabsTrigger = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "relative inline-flex items-center justify-center gap-2 px-5 py-3 text-sm transition-colors border-b-2 -mb-[2px]",
      "border-transparent bg-transparent",
      "text-slate-500 dark:text-slate-400",
      "hover:text-slate-900 dark:hover:text-slate-100",
      "data-[state=active]:border-blue-600 dark:data-[state=active]:border-blue-400",
      "data-[state=active]:text-blue-600 dark:data-[state=active]:text-blue-400",
      "data-[state=active]:font-semibold",
      "focus-visible:outline-none focus-visible:ring-0",
      "disabled:pointer-events-none disabled:opacity-50",
      className
    )}
    style={{ 
      background: 'transparent',
      backgroundColor: 'transparent',
      boxShadow: 'none',
      borderRadius: 0,
      WebkitAppearance: 'none',
      MozAppearance: 'none',
      appearance: 'none',
      '--tw-gradient-stops': 'transparent',
      '--tw-bg-opacity': '0'
    }}
    {...props} />
))
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName

const TabsContent = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      "mt-6 ring-offset-background focus-visible:outline-none bg-transparent",
      className
    )}
    style={{ background: 'transparent', backgroundColor: 'transparent' }}
    {...props} />
))
TabsContent.displayName = TabsPrimitive.Content.displayName

export { Tabs, TabsList, TabsTrigger, TabsContent }
