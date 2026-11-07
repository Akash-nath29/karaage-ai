import { useQuery } from '@tanstack/react-query'
import { ArrowRight } from 'lucide-react'
import { Link, useNavigate } from 'react-router'

import { SimpleForm } from '@/components/simple-form'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import { useProgress } from '@/features/assessments/api'
import { useMe } from '@/features/auth/api'
import { useCourse } from '@/features/courses/api'
import { CourseRow } from '@/features/courses/CourseRow'
import { nextStop, stations, STOP_ACTION, stopPath } from '@/features/courses/journey'
import { depthLabel } from '@/features/lessons/api'
import { useStructure } from '@/features/syllabus/api'
import { useCreateWorkspace, useWorkspace, useWorkspaces, workspaceFields, type WorkspaceInput } from '@/features/workspaces/api'
import { WorkspacesPage } from '@/features/workspaces/WorkspacesPage'
import { api, atLeast } from '@/lib/api'

type TopicRef = { topic_id: string; title: string; course_id: string; course_title: string; last_accuracy: number | null; revise_by: string | null }
type Analytics = {
  courses_enrolled: number
  topics_completed: number
  topics_remaining: number
  lessons_generated: number
  quiz_attempts: number
  average_accuracy: number | null
  weak_topics: TopicRef[]
  revision_due: TopicRef[]
  courses: { course_id: string; title: string; workspace_name: string; topics: number; completed: number; studied: number; revision_required: number; accuracy: number | null }[]
  recent_lessons: { lesson_id: string; topic_title: string; course_title: string; depth: string; visibility: string; updated_at: string }[]
  recent_sessions: { session_id: string; title: string; course_title: string | null; updated_at: string }[]
}

const pct = (x: number | null) => (x === null ? '–' : `${Math.round(x * 100)}%`)

/** Screen 1 and Module I (D38): your courses and the next stop in each, then what to revise and where you left off.
 * A first visit gets the path through the product instead. */
export function DashboardPage() {
  const me = useMe()
  const workspaces = useWorkspaces()
  const stats = useQuery({ queryKey: ['analytics', 'me'], queryFn: () => api<Analytics>('/users/me/learning-analytics') })
  const s = stats.data
  const firstVisit = workspaces.data?.length === 0
  const name = me.data?.display_name.split(' ')[0]
  const revise = s ? [...new Map([...s.revision_due, ...s.weak_topics].map((t) => [t.topic_id, t])).values()].slice(0, 6) : []

  return (
    <div className="grid gap-12">
      <section className="grid gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          {firstVisit ? 'Welcome to Karaage' : `Welcome back${name ? `, ${name}` : ''}`}
        </h1>
        {stats.error && <p role="alert" className="text-destructive">{stats.error.message}</p>}
        {s && s.courses.length > 0 && (
          <p className="text-sm text-muted-foreground tabular-nums">
            {s.topics_completed} of {s.topics_completed + s.topics_remaining} topics completed across {s.courses_enrolled} course
            {s.courses_enrolled === 1 ? '' : 's'}
            {s.average_accuracy !== null && ` · average check score ${pct(s.average_accuracy)}`}
          </p>
        )}
      </section>

      {firstVisit ? (
        <GettingStarted />
      ) : (
        <>
          {s && s.courses.length > 0 && <Continue analytics={s} />}
          <section aria-labelledby="courses-title" className="grid gap-4">
            <h2 id="courses-title" className="text-lg font-medium">Your courses</h2>
            {s && s.courses.length === 0 && (
              <p className="text-muted-foreground">No courses yet. Open a workspace below and add one, or ask its admin to.</p>
            )}
            {!!s?.courses.length && (
              <ul className="divide-y rounded-xl border">
                {s.courses.map((c) => (
                  <CourseRow key={c.course_id} id={c.course_id} title={c.title} detail={c.workspace_name} />
                ))}
              </ul>
            )}
          </section>

          {revise.length > 0 && (
            <section aria-labelledby="revise-title" className="grid gap-3">
              <h2 id="revise-title" className="text-lg font-medium">Revise next</h2>
              <ul className="grid gap-1.5 text-sm">
                {revise.map((t) => (
                  <li key={t.topic_id}>
                    <Link to={`/topics/${t.topic_id}`} className="font-medium hover:underline">
                      {t.title}
                    </Link>
                    <span className="text-muted-foreground">
                      {' '}
                      · {t.course_title}
                      {t.last_accuracy !== null && ` · last check ${pct(t.last_accuracy)}`}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {s && (s.recent_lessons.length > 0 || s.recent_sessions.length > 0) && (
            <div className="grid gap-10 sm:grid-cols-2">
              {s.recent_lessons.length > 0 && (
                <section aria-labelledby="recent-lessons" className="grid content-start gap-3">
                  <h2 id="recent-lessons" className="text-lg font-medium">Recent lessons</h2>
                  <ul className="grid gap-1.5 text-sm">
                    {s.recent_lessons.map((l) => (
                      <li key={l.lesson_id} className="grid gap-0.5">
                        <Link to={`/lessons/${l.lesson_id}`} className="justify-self-start font-medium hover:underline">
                          {l.topic_title}
                        </Link>
                        <span className="flex flex-wrap items-center gap-x-2 text-muted-foreground">
                          {depthLabel(l.depth)} · {l.course_title}
                          {l.visibility === 'private' && <Badge variant="outline">Private</Badge>}
                        </span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {s.recent_sessions.length > 0 && (
                <section aria-labelledby="recent-tutor" className="grid content-start gap-3">
                  <h2 id="recent-tutor" className="text-lg font-medium">Tutor conversations</h2>
                  <ul className="grid gap-1.5 text-sm">
                    {s.recent_sessions.map((r) => (
                      <li key={r.session_id}>
                        <Link to={`/tutor/${r.session_id}`} className="font-medium hover:underline">
                          {r.title}
                        </Link>
                        {r.course_title && <span className="text-muted-foreground"> · {r.course_title}</span>}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}

          <WorkspacesPage />
        </>
      )}
    </div>
  )
}

const PATH: [string, string][] = [
  ['Create a workspace', 'One per class, semester or study group. You can invite people to it later.'],
  ['Add a course', 'Its title and code as they appear on the syllabus.'],
  ['Upload the syllabus and your notes', 'Karaage reads the units and topics, then writes a lesson for every topic.'],
  ['Study topic by topic', 'Read the lesson, check yourself, see what you missed, then move on to the next stop.'],
]

function GettingStarted() {
  const create = useCreateWorkspace()
  const navigate = useNavigate()
  return (
    <section aria-labelledby="path-title" className="grid gap-10 md:grid-cols-2">
      <div className="grid content-start gap-5">
        <h2 id="path-title" className="text-lg font-medium">How Karaage works</h2>
        <ol className="grid gap-4">
          {PATH.map(([title, detail], i) => (
            <li key={title} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3">
              <span aria-hidden className="flex size-7 items-center justify-center rounded-full border text-sm font-medium tabular-nums">
                {i + 1}
              </span>
              <div className="grid gap-0.5">
                <p className="font-medium">{title}</p>
                <p className="text-sm text-muted-foreground">{detail}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="text-sm text-muted-foreground">Got an invitation link from a classmate? Open it to join their workspace instead.</p>
      </div>
      <div className="grid content-start gap-4 rounded-xl border p-5">
        <h2 className="text-lg font-medium">Start with a workspace</h2>
        <SimpleForm
          fields={workspaceFields}
          submitLabel="Create workspace"
          pending={create.isPending}
          error={create.error}
          onSubmit={async (v) => navigate(`/workspaces/${(await create.mutateAsync(v as WorkspaceInput)).id}`)}
        />
      </div>
    </section>
  )
}

/** The dashboard's one primary step: the next stop in the course you were last in. For a course you're still setting up,
 * finishing its setup instead. */
function Continue({ analytics: a }: { analytics: Analytics }) {
  const recent = a.recent_lessons[0]?.course_title ?? a.recent_sessions.find((r) => r.course_title)?.course_title
  const course = a.courses.find((c) => c.title === recent) ?? a.courses[0]
  const structure = useStructure(course.course_id)
  const progress = useProgress(course.course_id)
  const meta = useCourse(course.course_id)
  const role = useWorkspace(meta.data?.workspace_id).data?.role
  if (!structure.data) return null
  const line = stations(structure.data, progress.data)
  const stop = nextStop(line)
  const panel = (title: string, detail: string, to: string, action: string) => (
    <section aria-labelledby="continue-title" className="grid gap-4 rounded-xl border p-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <div className="grid gap-1">
        <h2 id="continue-title" className="text-lg font-medium text-balance">{title}</h2>
        <p className="text-sm text-muted-foreground">{detail}</p>
      </div>
      <Link to={to} className={buttonVariants({ size: 'lg' })}>
        {action}
        <ArrowRight />
      </Link>
    </section>
  )
  if (!line.length)
    return atLeast(role, 'editor')
      ? panel(`Finish setting up ${course.title}`, 'Upload its syllabus and Karaage writes a lesson for every topic.', `/courses/${course.course_id}`, 'Continue setup')
      : null
  return stop && panel(`Next stop: ${stop.station.title}`, `${course.title} · ${stop.station.unitTitle}`, stopPath(stop), STOP_ACTION[stop.action])
}
