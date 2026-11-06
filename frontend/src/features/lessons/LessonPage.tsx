import { useId, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'

import { JobProgress } from '@/components/job-progress'
import { CitationLink, LessonBlock } from '@/components/lesson-blocks/blocks'
import { NativeSelect } from '@/components/native-select'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  depthLabel,
  isBusy,
  useEnrich,
  useFeedback,
  useLesson,
  usePublish,
  useRegenerate,
  useVersions,
  type Citation,
  type LessonDetail,
} from '@/features/lessons/api'
import { TutorPanel } from '@/features/tutor/TutorPage'
import { useRole } from '@/features/workspaces/api'
import { atLeast } from '@/lib/api'
import { useJobProgress } from '@/lib/jobs'

export function LessonPage() {
  const { lessonId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const version = Number(params.get('version')) || undefined
  const detail = useLesson(lessonId, version)
  const lesson = detail.data?.lesson
  const progress = useJobProgress(lesson?.job_id ?? null, !!lesson && isBusy(lesson), ['lesson', lessonId])
  const role = useRole(detail.data?.workspace_id)

  if (detail.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (detail.error) return <p role="alert" className="text-destructive">{detail.error.message}</p>
  const d = detail.data
  const doc = d.document
  const citations = new Map(d.citations.map((c) => [c.label, c]))
  const latest = d.version.version === d.lesson.current_version
  const shared = d.lesson.visibility === 'workspace'
  // Shared lessons change only by editors and above; a private one only by its owner, the only one who sees it (D28).
  const canChange = !shared || atLeast(role, 'editor')

  return (
    <article className="grid gap-10">
      <header className="grid gap-4">
        <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
          <Link to={`/courses/${d.course_id}`} className="hover:underline">
            {d.course_title}
          </Link>{' '}
          › {d.unit_title} ›{' '}
          <Link to={`/topics/${d.lesson.topic_id}`} className="hover:underline">
            {d.topic_title}
          </Link>
        </nav>
        <div className="grid gap-1">
          <h1 className="text-3xl font-semibold tracking-tight">{doc.title}</h1>
          <p className="text-sm text-muted-foreground">
            {depthLabel(doc.depth)} · about {doc.estimated_minutes} min · version {d.version.version}
            {!latest && ` of ${d.lesson.current_version}`}
            {!shared && ' · private: only you can see it'}
          </p>
          {!shared && atLeast(role, 'editor') && <ShareButton lessonId={d.lesson.id} />}
        </div>
        {!latest && (
          <p className="rounded-xl border border-dashed px-4 py-2 text-sm">
            You're reading an older version.{' '}
            <button type="button" className="font-medium underline" onClick={() => setParams({})}>
              Go to the latest
            </button>
          </p>
        )}
        {d.lesson.outdated_reason && latest && (
          <OutdatedNotice lessonId={lessonId} reason={d.lesson.outdated_reason} busy={isBusy(d.lesson)} canChange={canChange} />
        )}
        {isBusy(d.lesson) && <JobProgress event={progress} label="Writing a new version" />}
        {d.lesson.status === 'failed' && d.lesson.error && (
          <p role="alert" className="text-sm text-destructive">
            The last generation failed: {d.lesson.error}
          </p>
        )}
        {doc.learning_objectives.length > 0 && (
          <div className="grid gap-1.5">
            <h2 className="font-medium">You'll be able to</h2>
            <ul className="grid list-disc gap-1 pl-6">
              {doc.learning_objectives.map((o) => (
                <li key={o}>{o}</li>
              ))}
            </ul>
          </div>
        )}
        {doc.prerequisites.length > 0 && (
          <p className="text-sm">
            <span className="font-medium">Before you start:</span> {doc.prerequisites.join(' · ')}
          </p>
        )}
        <nav aria-label="Sections in this lesson">
          <ol className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {doc.sections.map((s, i) => (
              <li key={s.id}>
                <a href={`#${s.id}`} className="text-muted-foreground hover:text-foreground hover:underline">
                  {i + 1}. {s.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>
      </header>

      {doc.sections.map((s) => (
        <section key={s.id} id={s.id} aria-labelledby={`${s.id}-title`} className="grid scroll-mt-6 gap-5">
          <h2 id={`${s.id}-title`} className="text-xl font-semibold">
            {s.title}
          </h2>
          {s.blocks.map((b, i) => (
            <LessonBlock key={i} block={b} citations={citations} />
          ))}
        </section>
      ))}

      <Sources citations={d.citations} />
      <TutorPanel context={{ lesson_id: d.lesson.id }} />
      <LessonActions detail={d} canChange={canChange}
                     onVersion={(v) => setParams(v === d.lesson.current_version ? {} : { version: String(v) })} />
    </article>
  )
}

function ShareButton({ lessonId }: { lessonId: string }) {
  const publish = usePublish(lessonId)
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button size="sm" variant="outline" className="justify-self-start" disabled={publish.isPending} onClick={() => publish.mutate()}>
        Share with workspace
      </Button>
      {publish.error && <p role="alert" className="text-sm text-destructive">{publish.error.message}</p>}
    </div>
  )
}

function OutdatedNotice({ lessonId, reason, busy, canChange }: { lessonId: string; reason: string; busy: boolean; canChange: boolean }) {
  const regenerate = useRegenerate(lessonId)
  return (
    <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border-l-4 border-amber-600/50 bg-amber-50 px-4 py-3 text-sm dark:bg-amber-950/40">
      <p>This lesson may be out of date. {reason}</p>
      {canChange && (
        <Button size="sm" variant="outline" disabled={busy || regenerate.isPending} onClick={() => regenerate.mutate()}>
          Regenerate
        </Button>
      )}
    </div>
  )
}

function Sources({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null
  const groups: [string, Citation[]][] = [
    ['Your materials', citations.filter((c) => c.kind === 'material')],
    ['Web sources', citations.filter((c) => c.kind === 'web')],
  ]
  return (
    <section aria-labelledby="sources-title" className="grid gap-4 border-t pt-6">
      <h2 id="sources-title" className="text-lg font-medium">
        Sources
      </h2>
      {groups.map(
        ([title, list]) =>
          list.length > 0 && (
            <div key={title} className="grid gap-2">
              <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
              <ul className="grid gap-2">
                {list.map((c) => (
                  <li key={c.label} className="text-sm">
                    <CitationLink citation={c} />
                    {c.kind === 'web' && c.title && <span className="text-muted-foreground"> · {c.title}</span>}
                    <details>
                      <summary className="cursor-pointer text-xs text-muted-foreground">What the lesson used</summary>
                      <blockquote className="mt-1 border-l-2 pl-3 text-muted-foreground whitespace-pre-line">{c.quote}</blockquote>
                    </details>
                  </li>
                ))}
              </ul>
            </div>
          ),
      )}
    </section>
  )
}

function LessonActions({ detail: d, canChange, onVersion }: { detail: LessonDetail; canChange: boolean; onVersion: (version: number) => void }) {
  const id = useId()
  const versions = useVersions(d.lesson.id)
  const regenerate = useRegenerate(d.lesson.id)
  const enrich = useEnrich(d.lesson.id)
  const busy = isBusy(d.lesson) || regenerate.isPending || enrich.isPending
  return (
    <section aria-label="Lesson actions" className="grid gap-6 border-t pt-6">
      {!canChange && (
        <p className="text-sm text-muted-foreground">
          This lesson is shared by your workspace. Want it another way?{' '}
          <Link to={`/topics/${d.lesson.topic_id}`} className="underline">Generate your own private version</Link>, or ask
          the tutor above.
        </p>
      )}
      {canChange && <form
        className="grid gap-1.5"
        onSubmit={(e) => {
          e.preventDefault()
          const form = e.currentTarget
          const request = (new FormData(form).get('request') as string).trim()
          if (request) enrich.mutate(request, { onSuccess: () => form.reset() })
        }}
      >
        <Label htmlFor={`${id}ask`}>Need more? Ask for an extra explanation, example or practice</Label>
        <div className="flex gap-2">
          <Input id={`${id}ask`} name="request" minLength={3} maxLength={500} required placeholder="e.g. another worked example with numbers" />
          <Button type="submit" disabled={busy}>
            Add to lesson
          </Button>
        </div>
        {enrich.error && <p role="alert" className="text-sm text-destructive">{enrich.error.message}</p>}
      </form>}

      <div className="flex flex-wrap items-end gap-4">
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}version`}>Version</Label>
          <NativeSelect id={`${id}version`} value={d.version.version} onChange={(e) => onVersion(Number(e.target.value))}>
            {(versions.data ?? [d.version]).map((v) => (
              <option key={v.version} value={v.version}>
                {v.version}: {v.kind === 'enriched' ? 'extended' : 'generated'} {new Date(v.created_at).toLocaleDateString()}
              </option>
            ))}
          </NativeSelect>
        </div>
        {canChange && (
          <Button variant="outline" disabled={busy} onClick={() => regenerate.mutate()}>
            Regenerate as a new version
          </Button>
        )}
        {regenerate.error && <p role="alert" className="text-sm text-destructive">{regenerate.error.message}</p>}
      </div>

      <Feedback lessonId={d.lesson.id} />

      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">About this version</summary>
        <p className="mt-2">
          Written by {d.version.model} (prompt {d.version.prompt_version}) ·{' '}
          {(d.version.input_tokens + d.version.output_tokens).toLocaleString()} tokens
        </p>
        {d.version.warnings.length > 0 && (
          <ul className="mt-1 list-disc pl-5">
            {d.version.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        )}
      </details>
    </section>
  )
}

function Feedback({ lessonId }: { lessonId: string }) {
  const id = useId()
  const feedback = useFeedback(lessonId)
  const [rating, setRating] = useState<1 | -1 | null>(null)
  if (feedback.isSuccess) return <p className="text-sm text-muted-foreground">Thanks for the feedback.</p>
  return (
    <form
      className="grid gap-2"
      onSubmit={(e) => {
        e.preventDefault()
        if (rating) feedback.mutate({ rating, comment: (new FormData(e.currentTarget).get('comment') as string).trim() })
      }}
    >
      <fieldset className="flex flex-wrap items-center gap-2">
        <legend className="mb-1.5 text-sm font-medium">Was this lesson helpful?</legend>
        <Button type="button" size="sm" variant={rating === 1 ? 'default' : 'outline'} aria-pressed={rating === 1} onClick={() => setRating(1)}>
          Helpful
        </Button>
        <Button type="button" size="sm" variant={rating === -1 ? 'default' : 'outline'} aria-pressed={rating === -1} onClick={() => setRating(-1)}>
          Not helpful
        </Button>
      </fieldset>
      {rating && (
        <div className="flex gap-2">
          <Input name="comment" aria-label="What could be better? (optional)" placeholder="What could be better? (optional)" maxLength={2000} id={`${id}c`} />
          <Button type="submit" size="sm" disabled={feedback.isPending}>
            Send
          </Button>
        </div>
      )}
      {feedback.error && <p role="alert" className="text-sm text-destructive">{feedback.error.message}</p>}
    </form>
  )
}
