import { ArrowRight } from 'lucide-react'
import { Link, Navigate, Route, Routes, useNavigate, useParams } from 'react-router'

import { ConfirmDelete } from '@/components/confirm-delete'
import { RouteTabs } from '@/components/route-tabs'
import { SimpleForm } from '@/components/simple-form'
import { UnitStations } from '@/components/station-line'
import { buttonVariants } from '@/components/ui/button'
import { useProgress } from '@/features/assessments/api'
import { PracticePanel } from '@/features/assessments/PracticePanel'
import { courseFields, useCourse, useDeleteCourse, useUpdateCourse, type Course } from '@/features/courses/api'
import { nextStop, stations, STOP_ACTION, stopPath, type NextStop, type Station } from '@/features/courses/journey'
import { SetupChecklist } from '@/features/courses/SetupChecklist'
import { DocumentsPanel } from '@/features/documents/DocumentsPanel'
import { SearchPanel } from '@/features/documents/SearchPanel'
import { useStructure } from '@/features/syllabus/api'
import { SyllabusPanel } from '@/features/syllabus/SyllabusPanel'
import { useWorkspace } from '@/features/workspaces/api'
import { atLeast } from '@/lib/api'

/** Screen 3, the course home (D38): organisers get the setup checklist until the course is ready; everyone gets one
 * next stop and the syllabus as lines of topics. Practice, materials and settings sit in tabs beside the topics. */
export function CoursePage() {
  const { courseId = '' } = useParams()
  const course = useCourse(courseId)
  const workspace = useWorkspace(course.data?.workspace_id)

  if (course.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (course.error) return <p role="alert" className="text-destructive">{course.error.message}</p>
  const c = course.data
  const role = workspace.data?.role
  const admin = atLeast(role, 'admin')
  const base = `/courses/${c.id}`

  return (
    <div className="grid gap-8">
      <header className="grid gap-2">
        <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
          <Link to={`/workspaces/${c.workspace_id}`} className="hover:text-foreground hover:underline">
            {workspace.data?.name ?? 'Workspace'}
          </Link>
        </nav>
        <h1 className="text-2xl font-semibold tracking-tight text-balance">{c.title}</h1>
        {(c.code || c.term) && <p className="text-sm text-muted-foreground">{[c.code, c.term].filter(Boolean).join(' · ')}</p>}
        {c.description && <p className="mt-1 max-w-prose">{c.description}</p>}
      </header>

      <SetupChecklist course={c} role={role} />

      <div className="grid gap-8">
        <RouteTabs
          label="Course"
          tabs={[
            { to: base, end: true, label: 'Topics' },
            { to: `${base}/practice`, label: 'Practice' },
            { to: `${base}/materials`, label: 'Materials' },
            ...(admin ? [{ to: `${base}/settings`, label: 'Settings' }] : []),
          ]}
        />
        <Routes>
          <Route index element={<CourseTopics course={c} />} />
          <Route path="practice" element={<PracticePanel courseId={c.id} workspaceId={c.workspace_id} />} />
          <Route
            path="materials"
            element={
              <div className="grid gap-12">
                <DocumentsPanel workspaceId={c.workspace_id} courseId={c.id} />
                <SearchPanel workspaceId={c.workspace_id} courseId={c.id} />
              </div>
            }
          />
          <Route
            path="settings"
            element={role === undefined ? <p className="text-muted-foreground">Loading…</p> : admin ? <CourseSettings course={c} /> : <Navigate to={base} replace />}
          />
          <Route path="*" element={<Navigate to={base} replace />} />
        </Routes>
      </div>
    </div>
  )
}

function CourseTopics({ course: c }: { course: Course }) {
  const structure = useStructure(c.id)
  const progress = useProgress(c.id)
  if (structure.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (structure.error) return <p role="alert" className="text-destructive">{structure.error.message}</p>
  if (!structure.data.units.length) return <p className="text-muted-foreground">Topics appear here once the course has its units and topics.</p>
  const line = stations(structure.data, progress.data)
  const stop = nextStop(line)
  return (
    <div className="grid gap-10">
      <NextStopPanel stop={stop} line={line} courseId={c.id} />
      {structure.data.units.map((u, i) => (
        <UnitStations key={u.id} index={i} title={u.title} stations={line.filter((s) => s.unitId === u.id)} nextId={stop?.station.id} />
      ))}
    </div>
  )
}

const REASON: Record<NextStop['action'], string> = {
  check: "You've read it: five questions show what stuck.",
  revise: 'Your last check came in under the bar: worth another pass.',
  learn: 'Next in the syllabus.',
}

function NextStopPanel({ stop, line, courseId }: { stop: NextStop | null; line: Station[]; courseId: string }) {
  const done = line.filter((s) => s.state === 'done').length
  if (!stop)
    return (
      <section aria-labelledby="next-stop" className="grid gap-3 rounded-xl border p-5">
        <h2 id="next-stop" className="text-lg font-medium">Every topic is completed</h2>
        <p className="text-sm text-muted-foreground">Keep it fresh before the exam with a mixed quiz or past papers.</p>
        <div>
          <Link to={`/courses/${courseId}/practice`} className={buttonVariants()}>
            Practise
          </Link>
        </div>
      </section>
    )
  const s = stop.station
  return (
    <section aria-labelledby="next-stop" className="grid gap-4 rounded-xl border p-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <div className="grid gap-1">
        <h2 id="next-stop" className="text-lg font-medium text-balance">Next stop: {s.title}</h2>
        <p className="text-sm text-muted-foreground">
          {s.unitTitle} · {stop.action === 'learn' && !s.lessonReady ? 'Its lesson is still being written.' : REASON[stop.action]}
        </p>
        <p className="text-sm text-muted-foreground tabular-nums">
          {done} of {line.length} topics completed
        </p>
      </div>
      <Link to={stopPath(stop)} className={buttonVariants({ size: 'lg' })}>
        {STOP_ACTION[stop.action]}
        <ArrowRight />
      </Link>
    </section>
  )
}

function CourseSettings({ course: c }: { course: Course }) {
  const update = useUpdateCourse(c.id)
  const remove = useDeleteCourse(c.id)
  const navigate = useNavigate()
  return (
    <div className="grid gap-12">
      <section aria-labelledby="details-title" className="grid max-w-md gap-4">
        <h2 id="details-title" className="text-lg font-medium">Course details</h2>
        <SimpleForm fields={courseFields} initial={c} submitLabel="Save" pending={update.isPending} error={update.error}
                    onSubmit={(v) => update.mutateAsync(v)} />
        {update.isSuccess && <p role="status" className="text-sm text-muted-foreground">Saved.</p>}
      </section>
      <SyllabusPanel course={c} />
      <section aria-labelledby="delete-title" className="grid gap-3 border-t pt-8">
        <h2 id="delete-title" className="text-lg font-medium">Delete this course</h2>
        <p className="text-sm text-muted-foreground">Removes the course for everyone in the workspace.</p>
        <div>
          <ConfirmDelete label="Delete course" pending={remove.isPending}
                         onConfirm={() => remove.mutate(undefined, { onSuccess: () => navigate(`/workspaces/${c.workspace_id}`) })} />
        </div>
      </section>
    </div>
  )
}
