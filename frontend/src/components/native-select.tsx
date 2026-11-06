import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

// Native <select>: keyboard and screen-reader behaviour for free, styled like <Input>.
export function NativeSelect({ className, ...props }: ComponentProps<'select'>) {
  return (
    <select
      className={cn(
        'h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30',
        className,
      )}
      {...props}
    />
  )
}
