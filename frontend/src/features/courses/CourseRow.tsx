import { Link } from 'react-router'

import { useProgress } from '@/features/assessments/api'
import { useCourse } from '@/features/courses/api'
import { nextStop, stations, stopPath } from '@/features/courses/journey'
import { useStructure } from '@/features/syllabus/api'
import { useWorkspace } from '@/features/workspaces/api'
import { atLeast } from '@/lib/api'

/** A course in a list (dashboard, workspace): how far along you are, and the way into your next stop. */
export function CourseRow({ id, title, detail }: { id: string; title: string; detail?: string }) {
  const structure = useStructure(id)
  const progress = useProgress(id)
  const line = structure.data ? stations(structure.data, progress.data) : []
  const stop = nextStop(line)
  const done = line.filter((s) => s.state === 'done').length
  const organiser = atLeast(useWorkspace(useCourse(id).data?.workspace_id).data?.role, 'editor')

  return (
    <li className="grid gap-x-8 gap-y-3 px-4 py-4 sm:grid-cols-[minmax(0,1fr)_13rem] sm:items-center">
      <div className="grid min-w-0 gap-0.5">
        <Link to={`/courses/${id}`} className="font-medium hover:underline">
          {title}
        </Link>
        {detail && <p className="text-sm text-muted-foreground">{detail}</p>}
        {structure.data &&
          (stop ? (
            <Link to={stopPath(stop)} className="mt-1 text-sm underline-offset-2 hover:underline">
              Next stop: <span className="font-medium">{stop.station.title}</span>
            </Link>
          ) : (
            line.length || !organiser ? (
              <p className="mt-1 text-sm text-muted-foreground">{line.length ? 'Every topic completed' : 'Being set up'}</p>
            ) : (
              <Link to={`/courses/${id}`} className="mt-1 text-sm font-medium underline-offset-2 hover:underline">
                Finish setting it up
              </Link>
            )
          ))}
      </div>
      {line.length > 0 && (
        <div className="grid gap-1.5">
          <div className="h-1.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label={`${title}: topics completed`}
               aria-valuemin={0} aria-valuemax={line.length} aria-valuenow={done}>
            <div className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out motion-reduce:transition-none"
                 style={{ width: `${(100 * done) / line.length}%` }} />
          </div>
          <span className="text-xs text-muted-foreground tabular-nums">
            {done} of {line.length} topics completed
          </span>
        </div>
      )}
    </li>
  )
}
