import type { JobEvent } from '@/lib/jobs'

export function JobProgress({ event, label }: { event: JobEvent | null; label: string }) {
  return (
    <div className="grid gap-1" aria-live="polite">
      <progress className="h-1.5 w-full accent-primary" max={100} value={event?.progress ?? 0} aria-label={label} />
      <p className="text-sm text-muted-foreground">{event?.message ?? 'Waiting for a worker…'}</p>
    </div>
  )
}
