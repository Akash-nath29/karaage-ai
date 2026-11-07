import type { ReactNode } from 'react'
import { NavLink } from 'react-router'

import { cn } from '@/lib/utils'

/** Tabs that are links: each one has a URL, so back, reload and sharing land on the same tab. */
export function RouteTabs({ label, tabs, className }: { label: string; tabs: { to: string; label: ReactNode; end?: boolean }[]; className?: string }) {
  return (
    <nav aria-label={label} className={cn('border-b', className)}>
      <ul className="flex flex-wrap gap-x-1">
        {tabs.map((t) => (
          <li key={t.to}>
            <NavLink
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                cn(
                  '-mb-px flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
                  isActive ? 'border-foreground text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground',
                )
              }
            >
              {t.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
