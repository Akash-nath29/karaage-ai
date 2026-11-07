import { Link, useParams } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { percent, PROGRESS_LABEL, useMarkStudied, useProgress, type ProgressStatus } from '@/features/assessments/api'
import { useCourse } from '@/features/courses/api'

const BADGE: Record<ProgressStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  completed: 'default',
  studied: 'secondary',
  revision_required: 'destructive',
  not_started: 'outline',
}

/** Screen 7: topic and unit completion, quiz accuracy, weak areas, what to revise (H6, A14). */
export function ProgressPage() {
  const { courseId = '' } = useParams()
  const course = useCourse(courseId)
  const progress = useProgress(courseId)
  const mark = useMarkStudied()

  if (progress.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (progress.error) return <p role="alert" className="text-destructive">{progress.error.message}</p>
  const p = progress.data
  const titles = new Map(p.topics.map((t) => [t.topic_id, t.title]))
  const revise = p.topics.filter((t) => t.status === 'revision_required')

  return (
    <div className="grid gap-10">
      <header className="grid gap-2">
        <Link to={`/courses/${courseId}`} className="text-sm text-muted-foreground hover:underline">
          ← {course.data?.title ?? 'Back to course'}
        </Link>
        <h1 className="text-2xl font-semibold">Progress</h1>
        <p className="max-w-prose text-sm text-muted-foreground">
          A topic is completed when you've marked it studied and scored at least 70% on its latest quiz. It needs revision
          when the latest quiz is under 50%, or after 14 days without activity.
        </p>
      </header>

      {p.topics.length === 0 ? (
        <p className="text-sm text-muted-foreground">Confirm the course's syllabus to track progress by topic.</p>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              ['Topics completed', `${p.completed} / ${p.topics.length}`],
              ['Studied', String(p.studied)],
              ['To revise', String(p.revision_required)],
              ['Quiz accuracy', `${percent(p.accuracy)}${p.questions_attempted ? ` of ${p.questions_attempted}` : ''}`],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border px-4 py-3">
                <dt className="text-sm text-muted-foreground">{label}</dt>
                <dd className="text-2xl font-semibold tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>

          {(revise.length > 0 || p.weak_topics.length > 0 || p.strong_topics.length > 0) && (
            <section aria-labelledby="focus-title" className="grid gap-2">
              <h2 id="focus-title" className="text-lg font-medium">
                Where to focus
              </h2>
              {revise.length > 0 && (
                <p className="text-sm">
                  <span className="font-medium">Revise now: </span>
                  {revise.map((t, i) => (
                    <span key={t.topic_id}>
                      {i > 0 && ', '}
                      <Link to={`/topics/${t.topic_id}`} className="underline-offset-2 hover:underline">
                        {t.title}
                      </Link>
                    </span>
                  ))}
                </p>
              )}
              {p.weak_topics.length > 0 && (
                <p className="text-sm">
                  <span className="font-medium">Weak areas (latest quiz under 50%): </span>
                  {p.weak_topics.map((id) => titles.get(id)).join(', ')}
                </p>
              )}
              {p.strong_topics.length > 0 && (
                <p className="text-sm">
                  <span className="font-medium">Strong (80% or more): </span>
                  {p.strong_topics.map((id) => titles.get(id)).join(', ')}
                </p>
              )}
            </section>
          )}

          <section aria-labelledby="units-title" className="grid gap-3">
            <h2 id="units-title" className="text-lg font-medium">
              Units
            </h2>
            <ul className="grid gap-3">
              {p.units.map((u) => (
                <li key={u.unit_id} className="grid gap-1">
                  <div className="flex justify-between gap-3 text-sm">
                    <span>{u.title}</span>
                    <span className="text-muted-foreground tabular-nums">
                      {u.completed} / {u.topics} completed · {u.studied} studied
                    </span>
                  </div>
                  <progress className="h-1.5 w-full accent-primary" max={u.topics || 1} value={u.completed} aria-label={`${u.title}: completed topics`} />
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="topics-title" className="grid gap-3">
            <h2 id="topics-title" className="text-lg font-medium">
              Topics
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3 font-medium">Topic</th>
                    <th className="py-2 pr-3 font-medium">Status</th>
                    <th className="py-2 pr-3 font-medium">Latest quiz</th>
                    <th className="py-2 pr-3 font-medium">All answers</th>
                    <th className="py-2 pr-3 font-medium">Revise by</th>
                    <th className="py-2 font-medium">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {p.topics.map((t) => (
                    <tr key={t.topic_id} className="border-t">
                      <td className="py-2 pr-3">
                        <Link to={`/topics/${t.topic_id}`} className="hover:underline">
                          {t.title}
                        </Link>
                      </td>
                      <td className="py-2 pr-3">
                        <Badge variant={BADGE[t.status]}>{PROGRESS_LABEL[t.status]}</Badge>
                      </td>
                      <td className="py-2 pr-3 tabular-nums">{percent(t.last_accuracy)}</td>
                      <td className="py-2 pr-3 tabular-nums">
                        {t.questions_attempted ? `${t.questions_correct} / ${t.questions_attempted} right` : '–'}
                      </td>
                      <td className="py-2 pr-3">{t.revise_by ? new Date(t.revise_by).toLocaleDateString() : '–'}</td>
                      <td className="py-2 text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          aria-pressed={!!t.studied_at}
                          aria-label={`${t.studied_at ? 'Unmark' : 'Mark'} ${t.title} as studied`}
                          disabled={mark.isPending}
                          pending={mark.isPending && mark.variables?.topicId === t.topic_id}
                          onClick={() => mark.mutate({ topicId: t.topic_id, studied: !t.studied_at })}
                        >
                          {t.studied_at ? 'Studied ✓' : 'Mark studied'}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}
