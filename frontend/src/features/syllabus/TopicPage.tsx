import { Link, useParams } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { TopicPractice } from '@/features/assessments/PracticePanel'
import { PassageCard } from '@/features/documents/PassageCard'
import { TopicLessons } from '@/features/lessons/TopicLessons'
import { ResearchPanel } from '@/features/research/ResearchPanel'
import { STATUS_LABEL, useTopic } from '@/features/syllabus/api'

export function TopicPage() {
  const { topicId = '' } = useParams()
  const topic = useTopic(topicId)
  if (topic.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (topic.error) return <p role="alert" className="text-destructive">{topic.error.message}</p>
  const t = topic.data

  return (
    <div className="grid gap-10">
      <section className="grid gap-3">
        <Link to={`/courses/${t.course_id}`} className="text-sm text-muted-foreground hover:underline">
          ← {t.course_title}
        </Link>
        <p className="text-sm text-muted-foreground">{t.unit_title}</p>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{t.title}</h1>
          <Badge variant={t.status === 'not_started' ? 'outline' : 'secondary'}>{STATUS_LABEL[t.status]}</Badge>
        </div>
        {t.subtopics.length > 0 && (
          <ul className="flex flex-wrap gap-1.5" aria-label="Subtopics">
            {t.subtopics.map((s) => (
              <li key={s.id}>
                <Badge variant="outline">{s.title}</Badge>
              </li>
            ))}
          </ul>
        )}
      </section>

      <TopicLessons topicId={t.id} workspaceId={t.workspace_id} />
      <TopicPractice topicId={t.id} courseId={t.course_id} workspaceId={t.workspace_id} />

      <section className="grid gap-3">
        <h2 className="text-lg font-medium">From your materials</h2>
        {t.materials.length ? (
          <ol className="grid gap-3">
            {t.materials.map((p) => (
              <PassageCard key={p.chunk_id} passage={p} />
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted-foreground">
            None of this course's materials match this topic yet. Upload notes or textbook chapters to the course and
            they'll be matched to topics automatically.
          </p>
        )}
      </section>

      <ResearchPanel topicId={t.id} />
    </div>
  )
}
