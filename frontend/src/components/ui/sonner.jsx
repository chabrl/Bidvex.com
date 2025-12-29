import { useTheme } from "next-themes"
import { Toaster as Sonner, toast } from "sonner"

/**
 * BidVex Enhanced Toast System
 * - Auto-dismiss after 3.5 seconds
 * - Swipe to dismiss
 * - Brand colors: Cyan (#06B6D4) for success, Blue (#1E3A8A) for info, Red for errors
 * - Top-right position for non-intrusive feedback
 */

const Toaster = ({
  ...props
}) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme}
      className="toaster group"
      position="top-right"
      expand={false}
      richColors={true}
      closeButton={true}
      duration={3500}
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-xl group-[.toaster]:rounded-xl",
          description: "group-[.toast]:text-muted-foreground",
          actionButton:
            "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton:
            "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
          success: "group-[.toaster]:bg-[#06B6D4]/10 group-[.toaster]:border-[#06B6D4]/30 group-[.toaster]:text-[#06B6D4] dark:group-[.toaster]:bg-[#06B6D4]/20",
          error: "group-[.toaster]:bg-red-50 group-[.toaster]:border-red-200 group-[.toaster]:text-red-600 dark:group-[.toaster]:bg-red-900/20 dark:group-[.toaster]:border-red-800",
          warning: "group-[.toaster]:bg-amber-50 group-[.toaster]:border-amber-200 group-[.toaster]:text-amber-600 dark:group-[.toaster]:bg-amber-900/20 dark:group-[.toaster]:border-amber-800",
          info: "group-[.toaster]:bg-[#1E3A8A]/10 group-[.toaster]:border-[#1E3A8A]/30 group-[.toaster]:text-[#1E3A8A] dark:group-[.toaster]:bg-[#1E3A8A]/20",
        },
      }}
      {...props} />
  );
}

export { Toaster, toast }
