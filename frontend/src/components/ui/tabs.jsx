import * as React from "react"
import * as TabsPrimitive from "@radix-ui/react-tabs"

import { cn } from "@/lib/utils"

const Tabs = TabsPrimitive.Root

const TabsList = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(
      "inline-flex items-center w-full border-b-2 border-slate-200 dark:border-slate-700",
      className
    )}
    style={{ 
      background: 'transparent',
      padding: 0,
      gap: 0
    }}
    {...props} />
))
TabsList.displayName = TabsPrimitive.List.displayName

const TabsTrigger = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "relative inline-flex items-center justify-center gap-2 px-5 py-3 text-sm transition-all border-b-2 -mb-[2px]",
      "border-transparent",
      "data-[state=active]:border-blue-600 dark:data-[state=active]:border-blue-400",
      "focus-visible:outline-none",
      "disabled:pointer-events-none disabled:opacity-50",
      className
    )}
    style={{ 
      background: 'transparent',
      boxShadow: 'none',
      borderRadius: 0,
      fontWeight: 500,
      color: '#64748b'
    }}
    {...props} />
))
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName

const TabsContent = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      "mt-6 ring-offset-background focus-visible:outline-none",
      className
    )}
    {...props} />
))
TabsContent.displayName = TabsPrimitive.Content.displayName

export { Tabs, TabsList, TabsTrigger, TabsContent }
