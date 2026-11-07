import { useEffect, useRef } from 'react'
import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import type { Station, StationState } from '@/features/courses/journey'
import { cn } from '@/lib/utils'

const STATION_LABEL: Record<StationState, string> = {
  done: 'Completed',
  studied: 'Read, not checked yet',
  revise: 'Revise',
  todo: 'To learn',
}

const pct = (x: number) => `${Math.round(x * 100)}%`

/** One topic on its unit's line (D38): filled when completed, half-filled when read but not checked, amber when it
 * needs revision, hollow to learn. `ring` marks the course's one next stop; fills and the ring ease in, so finishing a
 * check visibly moves the ring on to the following station. */
export function StationDot({ state, ring = false }: { state: StationState; ring?: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        'relative z-10 block size-3.5 shrink-0 rounded-full border-2 transition-[background-color,border-color,box-shadow] duration-300 ease-out motion-reduce:transition-none',
        state === 'done' && 'border-foreground bg-foreground',
        state === 'studied' && 'border-foreground bg-[linear-gradient(90deg,var(--color-foreground)_50%,var(--color-background)_50%)]',
        state === 'revise' && 'border-amber-600 bg-amber-100 dark:bg-amber-950',
        state === 'todo' && 'border-muted-foreground/60 bg-background',
        ring && 'ring-2 ring-foreground ring-offset-2 ring-offset-background',
      )}
    />
  )
}

/** A unit's topics across a study session, sharing the column: where you are, what's done, and the course's next stop
 * (the same one the course home names, so there is only ever one). */
export function UnitLine({ stations, currentId, nextId }: { stations: Station[]; currentId: string; nextId?: string }) {
  const current = useRef<HTMLAnchorElement>(null)
  useEffect(() => {
    // A statement, not an expression: newer browsers return a promise from scrollIntoView, and an effect may only
    // return a cleanup function.
    current.current?.scrollIntoView({ block: 'nearest', inline: 'center' })
  }, [currentId])
  return (
    <nav aria-label={`Topics in ${stations[0]?.unitTitle ?? 'this unit'}`} className="-mx-2 overflow-x-auto px-2 pb-1">
      <ol className="flex">
        {stations.map((s, i) => {
          const here = s.id === currentId
          const next = s.id === nextId
          return (
            <li key={s.id} className="relative grid min-w-28 flex-1 basis-0 content-start justify-items-center gap-1.5 text-center">
              {i < stations.length - 1 && <span aria-hidden className="absolute top-[11px] left-1/2 h-0.5 w-full bg-border" />}
              <Link
                ref={here ? current : undefined}
                to={`/topics/${s.id}`}
                aria-current={here ? 'page' : undefined}
                className="group grid justify-items-center gap-1.5 rounded-md px-2 pt-1 outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <StationDot state={s.state} ring={next} />
                <span className={cn('line-clamp-2 text-xs leading-snug', here ? 'font-semibold text-foreground' : 'text-muted-foreground group-hover:text-foreground')}>
                  {s.title}
                </span>
                <span className="sr-only">
                  {STATION_LABEL[s.state]}
                  {next ? ', next stop' : ''}
                </span>
              </Link>
              {(here || next) && (
                <span className="grid text-[11px] leading-tight font-medium text-foreground">
                  {next && <span>Next stop</span>}
                  {here && <span className={cn(next && 'font-normal text-muted-foreground')}>You're here</span>}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

/** A unit on the course home: its topics as stations down one line, each a way into its study session. */
export function UnitStations({ index, title, stations, nextId }: { index: number; title: string; stations: Station[]; nextId?: string }) {
  const done = stations.filter((s) => s.state === 'done').length
  const headingId = `unit-${index}`
  return (
    <section aria-labelledby={headingId} className="grid gap-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id={headingId} className="font-medium">
          Unit {index + 1}: {title}
        </h3>
        <span className="text-sm text-muted-foreground tabular-nums">
          {done} of {stations.length} completed
        </span>
      </div>
      <ol>
        {stations.map((s, i) => (
          <li key={s.id} className="relative grid grid-cols-[1.75rem_minmax(0,1fr)]">
            <span
              aria-hidden
              className={cn('absolute left-[13px] w-0.5 bg-border', i === 0 ? 'top-1/2' : 'top-0', i === stations.length - 1 ? 'h-1/2' : 'bottom-0')}
            />
            <span className="flex items-center justify-center">
              <StationDot state={s.state} ring={s.id === nextId} />
            </span>
            <Link
              to={`/topics/${s.id}`}
              className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-lg px-3 py-2.5 outline-none transition-colors hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <span className={cn('min-w-0', s.id === nextId && 'font-medium')}>{s.title}</span>
              <span className="flex items-center gap-2 text-sm text-muted-foreground">
                {s.id === nextId && <Badge>Next stop</Badge>}
                <StationMeta station={s} />
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  )
}

function StationMeta({ station: s }: { station: Station }) {
  const score = s.lastAccuracy !== null ? ` · last check ${pct(s.lastAccuracy)}` : ''
  if (s.state === 'todo') return s.lessonReady ? null : <span>Lesson being written</span>
  if (s.state === 'revise') return <span className="text-amber-700 dark:text-amber-400">Revise{score}</span>
  return (
    <span>
      {STATION_LABEL[s.state]}
      {score}
    </span>
  )
}
