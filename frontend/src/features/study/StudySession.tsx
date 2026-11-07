import { ArrowRight, Check, MessageCircle, X } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link, Navigate, Route, Routes, useNavigate, useParams, useSearchParams } from 'react-router'

import { RouteTabs } from '@/components/route-tabs'
import { UnitLine } from '@/components/station-line'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import {
  PROGRESS_LABEL,
  useCourseQuizzes,
  useCreateQuiz,
  useMarkStudied,
  useProgress,
  type AttemptSummary,
  type ProgressStatus,
  type Quiz,
} from '@/features/assessments/api'
import { QuizView } from '@/features/assessments/QuizPage'
import { ResultsView } from '@/features/assessments/ResultsPage'
import { nextStop, stations, stopPath, type NextStop } from '@/features/courses/journey'
import { PassageCard } from '@/features/documents/PassageCard'
import { depthLabel, useTopicLessons, type Lesson } from '@/features/lessons/api'
import { LessonView } from '@/features/lessons/LessonPage'
import { TopicLessons } from '@/features/lessons/TopicLessons'
import { ResearchPanel } from '@/features/research/ResearchPanel'
import { useStructure, useTopic, type TopicDetail } from '@/features/syllabus/api'
import { useCreateSession, useSessions } from '@/features/tutor/api'
import { TutorChat } from '@/features/tutor/TutorChat'
import { useMediaQuery } from '@/lib/use-media-query'

/** Everything the three stages share: the topic, where it sits on the course's line, and this learner's checks. */
type Session = {
  topic: TopicDetail
  status: ProgressStatus | undefined
  stop: NextStop | null // the course's one next stop (journey.nextStop): the same one the course home names
  after: NextStop | null // where to go once this topic is done: the next stop with this topic left out
  checks: Quiz[] // this topic's quizzes, newest first
  latest: AttemptSummary | undefined // the newest marked or marking attempt
}

const PROGRESS_BADGE: Record<ProgressStatus, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  completed: 'default',
  studied: 'secondary',
  revision_required: 'destructive',
  not_started: 'outline',
}

/** A topic as one sitting (D38): Learn, Check, Review, then on to the next stop, with the tutor alongside. */
export function StudySession() {
  const { topicId = '' } = useParams()
  const topic = useTopic(topicId)
  if (topic.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (topic.error) return <p role="alert" className="text-destructive">{topic.error.message}</p>
  return <SessionLayout key={topicId} topic={topic.data} />
}

function SessionLayout({ topic: t }: { topic: TopicDetail }) {
  const structure = useStructure(t.course_id)
  const progress = useProgress(t.course_id)
  const quizzes = useCourseQuizzes(t.course_id)
  const line = structure.data ? stations(structure.data, progress.data) : []
  const stop = nextStop(line)
  const checks = (quizzes.data ?? [])
    .filter((q) => q.settings.topic_ids.length === 1 && q.settings.topic_ids[0] === t.id)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
  const s: Session = {
    topic: t,
    status: progress.data?.topics.find((x) => x.topic_id === t.id)?.status,
    stop,
    after: stop?.station.id === t.id ? nextStop(line.filter((x) => x.id !== t.id)) : stop,
    checks,
    latest: checks
      .flatMap((q) => q.attempts)
      .filter((a) => a.status !== 'failed')
      .sort((a, b) => b.created_at.localeCompare(a.created_at))[0],
  }
  const unit = line.filter((x) => x.unitId === t.unit_id)
  const base = `/topics/${t.id}`

  return (
    <div className="grid items-start gap-10 pb-16 lg:grid-cols-[minmax(0,1fr)_22rem] lg:pb-0">
      <div className="grid min-w-0 gap-6">
      <header className="grid gap-2">
        <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
          <Link to={`/courses/${t.course_id}`} className="hover:text-foreground hover:underline">
            {t.course_title}
          </Link>{' '}
          › {t.unit_title}
        </nav>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-balance">{t.title}</h1>
          {s.status && <Badge variant={PROGRESS_BADGE[s.status]}>{PROGRESS_LABEL[s.status]}</Badge>}
        </div>
        {t.subtopics.length > 0 && <p className="max-w-prose text-sm text-muted-foreground">{t.subtopics.map((x) => x.title).join(' · ')}</p>}
      </header>

      {unit.length > 1 && <UnitLine stations={unit} currentId={t.id} nextId={stop?.station.unitId === t.unit_id ? stop.station.id : undefined} />}

        <div className="grid min-w-0 gap-8">
          <RouteTabs
            label="Study stages"
            className="sticky top-0 z-20 bg-background"
            tabs={[
              { to: base, end: true, label: <>Learn{s.status && s.status !== 'not_started' && <Check aria-label="done" className="size-3.5" />}</> },
              { to: `${base}/check`, label: <>Check{s.latest && <Check aria-label="done" className="size-3.5" />}</> },
              {
                to: `${base}/review`,
                label: (
                  <>
                    Review
                    {s.latest?.status === 'graded' && (
                      <span className="text-muted-foreground tabular-nums">
                        {s.latest.score}/{s.latest.max_score}
                      </span>
                    )}
                  </>
                ),
              },
            ]}
          />
          <Routes>
            <Route index element={<LearnStage s={s} />} />
            <Route path="check" element={<CheckStage s={s} />} />
            <Route path="review" element={<ReviewStage s={s} />} />
            <Route path="*" element={<Navigate to={base} replace />} />
          </Routes>
        </div>
      </div>
      <TutorDock topic={t} />
    </div>
  )
}

/** Shared lessons first, the detailed depth first: the version most of the class reads. */
const pickLesson = (list: Lesson[]) =>
  [...list].sort((a, b) => Number(a.visibility !== 'workspace') - Number(b.visibility !== 'workspace') || Number(a.depth !== 'detailed') - Number(b.depth !== 'detailed'))[0]

function LearnStage({ s }: { s: Session }) {
  const t = s.topic
  const lessons = useTopicLessons(t.id)
  const [params, setParams] = useSearchParams()
  const readable = (lessons.data ?? []).filter((l) => l.current_version > 0)
  const chosen = readable.find((l) => l.id === params.get('lesson')) ?? pickLesson(readable)
  const version = Number(params.get('version')) || undefined

  if (lessons.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (lessons.error) return <p role="alert" className="text-destructive">{lessons.error.message}</p>
  return (
    <div className="grid gap-12">
      {chosen ? (
        <>
          {readable.length > 1 && (
            <div role="group" aria-label="Lesson version" className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground">Read it as</span>
              {readable.map((l) => (
                <Button key={l.id} size="sm" variant={l.id === chosen.id ? 'default' : 'outline'} aria-pressed={l.id === chosen.id}
                        onClick={() => setParams({ lesson: l.id })}>
                  {depthLabel(l.depth)}
                  {l.visibility === 'private' && ' · only you'}
                </Button>
              ))}
            </div>
          )}
          <LessonView key={chosen.id} lessonId={chosen.id} version={version}
                      onVersion={(v) => setParams(v ? { lesson: chosen.id, version: String(v) } : { lesson: chosen.id })}>
            <DoneReading s={s} />
          </LessonView>
        </>
      ) : (
        <section aria-labelledby="no-lesson" className="grid gap-4">
          <h2 id="no-lesson" className="text-lg font-medium">No lesson to read yet</h2>
          <p className="max-w-prose text-sm text-muted-foreground">
            If it's being written you'll see its progress below, and it opens here when it's ready. You can also write one
            now: it uses your course materials first and searches the web only for gaps.
          </p>
          <TopicLessons topicId={t.id} workspaceId={t.workspace_id} />
        </section>
      )}
      <MoreOnTopic topic={t} showLessons={!!chosen} />
    </div>
  )
}

/** The hand-off from reading to checking: marks the topic read (so a good score can complete it), then opens the check. */
function DoneReading({ s }: { s: Session }) {
  const mark = useMarkStudied()
  const navigate = useNavigate()
  const read = s.status !== undefined && s.status !== 'not_started'
  const check = `/topics/${s.topic.id}/check`
  return (
    <section aria-labelledby="done-reading" className="grid gap-3 rounded-xl border bg-muted/40 p-5">
      <h2 id="done-reading" className="text-lg font-medium">Done reading?</h2>
      <p className="max-w-prose text-sm text-muted-foreground">
        Five questions on this topic show what stuck. Objective answers are marked at once; written ones by the AI against a
        rubric.
      </p>
      <div>
        <Button size="lg" pending={mark.isPending}
                onClick={() => (read ? navigate(check) : mark.mutate({ topicId: s.topic.id, studied: true }, { onSuccess: () => navigate(check) }))}>
          Check yourself
          <ArrowRight />
        </Button>
      </div>
      {mark.error && <p role="alert" className="text-sm text-destructive">{mark.error.message}</p>}
    </section>
  )
}

function MoreOnTopic({ topic: t, showLessons }: { topic: TopicDetail; showLessons: boolean }) {
  return (
    <section aria-labelledby="more-on-topic" className="grid gap-4 border-t pt-8">
      <h2 id="more-on-topic" className="text-lg font-medium">More on this topic</h2>
      <details className="group grid gap-3">
        <summary className="cursor-pointer font-medium">From your materials ({t.materials.length})</summary>
        <div className="mt-3">
          {t.materials.length ? (
            <ol className="grid gap-3">
              {t.materials.map((p) => (
                <PassageCard key={p.chunk_id} passage={p} />
              ))}
            </ol>
          ) : (
            <p className="text-sm text-muted-foreground">
              None of the course's materials match this topic yet. Notes and textbook chapters added to the course are
              matched to topics automatically.
            </p>
          )}
        </div>
      </details>
      <details>
        <summary className="cursor-pointer font-medium">Web research</summary>
        <div className="mt-3">
          <ResearchPanel topicId={t.id} />
        </div>
      </details>
      {showLessons && (
        <details id="more-lessons">
          <summary className="cursor-pointer font-medium">Other versions and depths</summary>
          <div className="mt-3">
            <TopicLessons topicId={t.id} workspaceId={t.workspace_id} />
          </div>
        </details>
      )}
    </section>
  )
}

function CheckStage({ s }: { s: Session }) {
  const t = s.topic
  const navigate = useNavigate()
  const create = useCreateQuiz({ topicId: t.id })
  const open = s.checks.find((q) => q.status !== 'failed' && q.attempts.length === 0)

  if (open)
    return (
      <section aria-labelledby="check-title" className="grid gap-6">
        <h2 id="check-title" className="text-lg font-medium">Check yourself</h2>
        <QuizView key={open.id} quizId={open.id} onSubmitted={(a) => navigate(`/topics/${t.id}/review?attempt=${a.id}`)} />
      </section>
    )
  return (
    <section aria-labelledby="check-title" className="grid max-w-prose gap-4">
      <h2 id="check-title" className="text-lg font-medium">Check yourself on {t.title}</h2>
      <p className="text-sm text-muted-foreground">
        Five questions from this topic, a mix of quick and written ones. You'll see each answer marked, what you missed and a
        reference answer.
      </p>
      {s.latest?.status === 'graded' && (
        <p className="text-sm">
          Last time you scored{' '}
          <span className="font-medium tabular-nums">
            {s.latest.score} / {s.latest.max_score}
          </span>
          .{' '}
          <Link to={`/topics/${t.id}/review`} className="underline underline-offset-2">
            See that review
          </Link>
        </p>
      )}
      <div>
        <Button size="lg" pending={create.isPending} onClick={() => create.mutate({ count: 5 })}>
          {s.latest ? 'Take a new check' : 'Start the check'}
        </Button>
      </div>
      {create.error && <p role="alert" className="text-sm text-destructive">{create.error.message}</p>}
    </section>
  )
}

function ReviewStage({ s }: { s: Session }) {
  const [params] = useSearchParams()
  const attemptId = params.get('attempt') ?? s.latest?.id
  if (!attemptId)
    return (
      <section aria-labelledby="review-title" className="grid max-w-prose gap-3">
        <h2 id="review-title" className="text-lg font-medium">Nothing to review yet</h2>
        <p className="text-sm text-muted-foreground">Take the check and your marked answers, what you missed and the reference answers appear here.</p>
        <div>
          <Link to={`/topics/${s.topic.id}/check`} className={buttonVariants()}>
            Go to the check
          </Link>
        </div>
      </section>
    )
  return (
    <div className="grid gap-8">
      <WhatNext s={s} />
      <section aria-label="Your answers">
        <ResultsView key={attemptId} attemptId={attemptId} />
      </section>
      <StopLink stop={s.after} courseId={s.topic.course_id} />
    </div>
  )
}

/** After a check, in one of four states: still marking; this topic needs another pass (revise); it's close (another
 * check completes it); or it's done, so on to the course's next stop. */
function WhatNext({ s }: { s: Session }) {
  const t = s.topic
  const navigate = useNavigate()
  const retake = useCreateQuiz({ topicId: t.id })
  const newCheck = (variant: 'default' | 'ghost') => (
    <Button variant={variant} pending={retake.isPending}
            onClick={() => retake.mutate({ count: 5 }, { onSuccess: () => navigate(`/topics/${t.id}/check`) })}>
      Take a new check
    </Button>
  )
  const moveOn = s.after && (
    <Link to={stopPath(s.after)} className={buttonVariants({ variant: 'ghost' })}>
      Move on to {s.after.station.title}
    </Link>
  )
  const error = retake.error && <p role="alert" className="text-sm text-destructive">{retake.error.message}</p>

  if (s.latest?.status === 'grading')
    return (
      <section role="status" aria-labelledby="what-next" className="grid gap-1 rounded-xl border p-5">
        <h2 id="what-next" className="text-lg font-medium">Marking your written answers</h2>
        <p className="text-sm text-muted-foreground">Your score and where to go next appear here as soon as the marking is done.</p>
      </section>
    )
  const stillHere = s.stop?.station.id === t.id // this topic is still the course's next stop
  if (stillHere && s.stop!.action === 'revise')
    return (
      <section role="status" aria-labelledby="what-next" className="grid gap-3 rounded-xl border border-amber-600/40 bg-amber-50 p-5 dark:bg-amber-950/40">
        <h2 id="what-next" className="text-lg font-medium">Worth another pass</h2>
        <p className="max-w-prose text-sm">
          This check came in under the bar. Re-read what's marked missing below, ask the tutor about it, then take a new check.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link to={`/topics/${t.id}`} className={buttonVariants()}>
            Back to the lesson
          </Link>
          {newCheck('ghost')}
          {moveOn}
        </div>
        {error}
      </section>
    )
  if (stillHere)
    return (
      <section aria-labelledby="what-next" className="grid gap-3 rounded-xl border p-5">
        <h2 id="what-next" className="text-lg font-medium">Nearly there</h2>
        <p className="max-w-prose text-sm text-muted-foreground">A stronger score on one more check completes this topic.</p>
        <div className="flex flex-wrap gap-2">
          {newCheck('default')}
          {moveOn}
        </div>
        {error}
      </section>
    )
  return (
    <section aria-labelledby="what-next" className="grid gap-4 rounded-xl border p-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <div className="grid gap-1">
        <h2 id="what-next" className="text-lg font-medium">{s.status === 'completed' ? 'Topic completed' : 'Checked'}</h2>
        <p className="text-sm text-muted-foreground">
          {s.after
            ? `Next stop: ${s.after.station.title}${s.after.station.unitId !== t.unit_id ? `, in ${s.after.station.unitTitle}` : ''}.`
            : 'Every topic in the course is done.'}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {newCheck('ghost')}
        <StopLink stop={s.after} courseId={t.course_id} size="lg" />
      </div>
      {error}
    </section>
  )
}

function StopLink({ stop, courseId, size }: { stop: NextStop | null; courseId: string; size?: 'lg' }) {
  return stop ? (
    <Link to={stopPath(stop)} className={buttonVariants({ size })}>
      Next stop
      <ArrowRight />
    </Link>
  ) : (
    <Link to={`/courses/${courseId}`} className={buttonVariants({ size, variant: 'outline' })}>
      Back to the course
    </Link>
  )
}

/** The tutor beside every stage: a rail on wide screens, a sheet from a button on phones. One conversation per visit,
 * created with the first question; earlier ones about this topic stay a click away. */
function TutorDock({ topic: t }: { topic: TopicDetail }) {
  const wide = useMediaQuery('(min-width: 64rem)')
  const create = useCreateSession()
  const sessions = useSessions(t.workspace_id, { topic_id: t.id })
  const [sessionId, setSessionId] = useState<string | null>(null)
  const sheet = useRef<HTMLDialogElement>(null)
  const earlier = (sessions.data ?? []).filter((x) => x.id !== sessionId).slice(0, 4)

  const body = (fill: boolean) => (
    <>
      <TutorChat
        className={fill ? 'flex min-h-0 flex-1 flex-col [&>div:first-child]:max-h-none [&>div:first-child]:flex-1' : undefined}
        sessionId={null}
        ensureSession={async () => (await create.mutateAsync({ workspace_id: t.workspace_id, topic_id: t.id })).id}
        onSession={setSessionId}
      />
      {sessionId && (
        <Link to={`/tutor/${sessionId}`} className="text-sm text-muted-foreground hover:text-foreground hover:underline">
          Open as a full conversation
        </Link>
      )}
      {earlier.length > 0 && (
        <div className="grid gap-1 text-sm">
          <h3 className="text-muted-foreground">Earlier about this topic</h3>
          <ul className="grid gap-0.5">
            {earlier.map((x) => (
              <li key={x.id} className="truncate">
                <Link to={`/tutor/${x.id}`} className="hover:underline" title={x.title}>
                  {x.title}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )

  if (wide)
    return (
      <aside aria-labelledby="tutor-title" className="sticky top-4 grid max-h-[calc(100dvh-2rem)] content-start gap-3 overflow-y-auto">
        <div className="grid gap-0.5">
          <h2 id="tutor-title" className="font-medium">Ask the tutor</h2>
          <p className="text-sm text-muted-foreground">It knows this topic and your course materials.</p>
        </div>
        {body(false)}
      </aside>
    )
  return (
    <>
      <Button size="lg" className="fixed right-4 bottom-4 z-30 shadow-lg" onClick={() => sheet.current?.showModal()}>
        <MessageCircle />
        Ask the tutor
      </Button>
      <dialog
        ref={sheet}
        aria-labelledby="tutor-title"
        className="mx-0 mt-auto mb-0 h-[85dvh] max-h-none w-full max-w-none rounded-t-2xl border-t bg-background p-4 text-foreground backdrop:bg-black/40"
      >
        <div className="flex h-full flex-col gap-3">
          <div className="flex items-center justify-between gap-3">
            <h2 id="tutor-title" className="font-medium">Ask the tutor about {t.title}</h2>
            <Button variant="ghost" size="icon" aria-label="Close the tutor" onClick={() => sheet.current?.close()}>
              <X />
            </Button>
          </div>
          {body(true)}
        </div>
      </dialog>
    </>
  )
}
