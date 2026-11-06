import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useMe } from '@/features/auth/api'
import { depthLabel } from '@/features/lessons/api'
import { WorkspacesPage } from '@/features/workspaces/WorkspacesPage'
import { api } from '@/lib/api'

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

/** Screen 1 and Module I: your study progress across every workspace, then your workspaces. */
export function DashboardPage() {
  const me = useMe()
  const stats = useQuery({ queryKey: ['analytics', 'me'], queryFn: () => api<Analytics>('/users/me/learning-analytics') })
  const s = stats.data
  const tiles: [string, string | number][] = s
    ? [
        ['Courses', s.courses_enrolled],
        ['Topics completed', s.topics_completed],
        ['Topics remaining', s.topics_remaining],
        ['Lessons available', s.lessons_generated],
        ['Quiz attempts', s.quiz_attempts],
        ['Average quiz score', pct(s.average_accuracy)],
      ]
    : []

  return (
    <div className="grid gap-10">
      <section className="grid gap-4">
        <h1 className="text-2xl font-semibold">Welcome back{me.data ? `, ${me.data.display_name.split(' ')[0]}` : ''}</h1>
        {stats.error && <p role="alert" className="text-destructive">{stats.error.message}</p>}
        {s && (
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {tiles.map(([label, value]) => (
              <div key={label} className="rounded-xl border px-4 py-3">
                <dt className="text-sm text-muted-foreground">{label}</dt>
                <dd className="text-2xl font-semibold tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      {s && (s.recent_sessions.length > 0 || s.revision_due.length > 0 || s.weak_topics.length > 0) && (
        <section className="grid gap-4 sm:grid-cols-2" aria-label="Continue learning">
          {s.recent_sessions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Continue learning</CardTitle>
                <CardDescription>Your recent tutor conversations</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="grid gap-1.5 text-sm">
                  {s.recent_sessions.map((r) => (
                    <li key={r.session_id}>
                      <Link to={`/tutor/${r.session_id}`} className="hover:underline">{r.title}</Link>
                      {r.course_title && <span className="text-muted-foreground"> · {r.course_title}</span>}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          {(s.revision_due.length > 0 || s.weak_topics.length > 0) && (
            <Card>
              <CardHeader>
                <CardTitle>Revise next</CardTitle>
                <CardDescription>Weak topics and revision due (A14)</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="grid gap-1.5 text-sm">
                  {[...new Map([...s.weak_topics, ...s.revision_due].map((t) => [t.topic_id, t])).values()].slice(0, 8).map((t) => (
                    <li key={t.topic_id}>
                      <Link to={`/topics/${t.topic_id}`} className="hover:underline">{t.title}</Link>
                      <span className="text-muted-foreground">
                        {' '}· {t.course_title}{t.last_accuracy !== null && ` · last quiz ${pct(t.last_accuracy)}`}
                      </span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </section>
      )}

      {s && s.courses.length > 0 && (
        <section className="grid gap-3" aria-labelledby="study-progress">
          <h2 id="study-progress" className="text-lg font-medium">Study progress</h2>
          <ul className="grid gap-2">
            {s.courses.map((c) => (
              <li key={c.course_id} className="grid gap-1.5 rounded-xl border px-4 py-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <Link to={`/courses/${c.course_id}/progress`} className="font-medium hover:underline">{c.title}</Link>
                  <span className="text-sm text-muted-foreground">
                    {c.completed}/{c.topics} topics completed · {c.studied} studied
                    {c.revision_required > 0 && ` · ${c.revision_required} to revise`} · {c.workspace_name}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label={`${c.title} completion`}
                     aria-valuemin={0} aria-valuemax={c.topics || 1} aria-valuenow={c.completed}>
                  <div className="h-full bg-primary" style={{ width: `${c.topics ? (100 * c.completed) / c.topics : 0}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {s && s.recent_lessons.length > 0 && (
        <section className="grid gap-3" aria-labelledby="recent-lessons">
          <h2 id="recent-lessons" className="text-lg font-medium">Recent lessons</h2>
          <ul className="grid gap-1.5 text-sm">
            {s.recent_lessons.map((l) => (
              <li key={l.lesson_id} className="flex flex-wrap items-center gap-2">
                <Link to={`/lessons/${l.lesson_id}`} className="font-medium hover:underline">{l.topic_title}</Link>
                <span className="text-muted-foreground">{depthLabel(l.depth)} · {l.course_title}</span>
                {l.visibility === 'private' && <Badge variant="outline">Private</Badge>}
              </li>
            ))}
          </ul>
        </section>
      )}

      <WorkspacesPage />
    </div>
  )
}
