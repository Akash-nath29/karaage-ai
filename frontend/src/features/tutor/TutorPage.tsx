import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { ConfirmDelete } from '@/components/confirm-delete'
import { Button } from '@/components/ui/button'
import {
  useCreateSession,
  useDeleteSession,
  useSession,
  useSessions,
  type SessionContext,
  type TutorSession,
} from '@/features/tutor/api'
import { TutorChat } from '@/features/tutor/TutorChat'
import { cn } from '@/lib/utils'

const contextOf = (s: TutorSession): SessionContext => ({
  workspace_id: s.workspace_id,
  course_id: s.course_id ?? undefined,
  topic_id: s.topic_id ?? undefined,
  lesson_id: s.lesson_id ?? undefined,
  mode: s.mode,
})

/** Screen 5: one conversation, with the others in this course (or workspace) to continue. */
export function TutorPage() {
  const { sessionId = '' } = useParams()
  const session = useSession(sessionId)
  const s = session.data
  const others = useSessions(s?.workspace_id, s?.course_id ? { course_id: s.course_id } : {})
  const create = useCreateSession()
  const remove = useDeleteSession()
  const navigate = useNavigate()

  if (session.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (session.error) return <p role="alert" className="text-destructive">{session.error.message}</p>
  const back = s!.topic_id ? `/topics/${s!.topic_id}` : s!.course_id ? `/courses/${s!.course_id}` : `/workspaces/${s!.workspace_id}`

  return (
    <div className="grid gap-6">
      <header className="grid gap-2">
        <Link to={back} className="text-sm text-muted-foreground hover:underline">
          ← {s!.topic_title ?? s!.course_title ?? 'Back to workspace'}
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="grid gap-1">
            <h1 className="text-2xl font-semibold">AI tutor</h1>
            <p className="text-sm text-muted-foreground">
              {[s!.course_title, s!.topic_title].filter(Boolean).join(' › ') || 'General questions'}
              {s!.lesson_id && ' · reading the lesson'}
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              disabled={create.isPending}
              onClick={() => create.mutate(contextOf(s!), { onSuccess: (n) => navigate(`/tutor/${n.id}`) })}
            >
              New conversation
            </Button>
            <ConfirmDelete
              label="Delete conversation"
              pending={remove.isPending}
              onConfirm={() => remove.mutate(s!.id, { onSuccess: () => navigate(back) })}
            />
          </div>
        </div>
      </header>

      <div className="grid gap-6 md:grid-cols-[13rem_1fr]">
        <nav aria-label="Conversations" className="grid content-start gap-1">
          <h2 className="mb-1 text-sm font-medium text-muted-foreground">Conversations</h2>
          {(others.data ?? []).map((o) => (
            <Link
              key={o.id}
              to={`/tutor/${o.id}`}
              aria-current={o.id === s!.id ? 'page' : undefined}
              className={cn('truncate rounded-lg px-2 py-1 text-sm hover:bg-muted', o.id === s!.id && 'bg-muted font-medium')}
              title={o.title}
            >
              {o.title}
            </Link>
          ))}
        </nav>
        <TutorChat key={s!.id} sessionId={s!.id} initialMode={s!.mode} />
      </div>
      <p className="text-xs text-muted-foreground">
        The tutor can make mistakes. Check important facts against the cited sources.
      </p>
    </div>
  )
}

/** The tutor beside a lesson: the conversation starts with the first question. */
export function TutorPanel({ context }: { context: SessionContext }) {
  const create = useCreateSession()
  const [sessionId, setSessionId] = useState<string | null>(null)
  return (
    <section aria-labelledby="tutor-panel-title" className="grid gap-3 border-t pt-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="tutor-panel-title" className="text-lg font-medium">
          Ask the tutor about this lesson
        </h2>
        {sessionId && (
          <Link to={`/tutor/${sessionId}`} className="text-sm text-muted-foreground hover:underline">
            Open as a full conversation
          </Link>
        )}
      </div>
      <TutorChat
        sessionId={null}
        ensureSession={async () => (await create.mutateAsync(context)).id}
        onSession={setSessionId}
      />
    </section>
  )
}
