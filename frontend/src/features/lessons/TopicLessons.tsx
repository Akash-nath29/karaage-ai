import { useId } from 'react'
import { Link } from 'react-router'

import { JobProgress } from '@/components/job-progress'
import { NativeSelect } from '@/components/native-select'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useDocuments } from '@/features/documents/api'
import {
  DEPTHS,
  depthLabel,
  isBusy,
  useGenerateLesson,
  usePins,
  usePublish,
  useSetPins,
  useTopicLessons,
  type Lesson,
  type Visibility,
} from '@/features/lessons/api'
import { useRole } from '@/features/workspaces/api'
import { atLeast } from '@/lib/api'
import { useJobProgress } from '@/lib/jobs'

export function TopicLessons({ topicId, workspaceId }: { topicId: string; workspaceId: string }) {
  const id = useId()
  const lessons = useTopicLessons(topicId)
  const generate = useGenerateLesson(topicId)
  const existing = new Set((lessons.data ?? []).map((l) => l.depth))
  const editor = atLeast(useRole(workspaceId), 'editor') // shares lessons; viewers' lessons stay private (D28)

  return (
    <section className="grid gap-4" aria-labelledby={`${id}heading`}>
      <h2 id={`${id}heading`} className="text-lg font-medium">
        Lessons
      </h2>
      {lessons.error && <p role="alert" className="text-destructive">{lessons.error.message}</p>}
      {lessons.data?.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No lesson yet. Generating one uses your materials first and searches the web only for gaps.
        </p>
      )}
      {!!lessons.data?.length && (
        <ul className="divide-y rounded-xl border">
          {lessons.data.map((l) => (
            <LessonRow key={l.id} lesson={l} canShare={editor} />
          ))}
        </ul>
      )}
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault()
          const form = new FormData(e.currentTarget)
          generate.mutate({ depth: form.get('depth') as string, visibility: (form.get('visibility') as Visibility | null) ?? undefined })
        }}
      >
        <div className="grid gap-1.5">
          <label htmlFor={`${id}depth`} className="text-sm font-medium">
            Depth
          </label>
          <NativeSelect id={`${id}depth`} name="depth" defaultValue={DEPTHS.find(([d]) => !existing.has(d))?.[0] ?? 'detailed'}>
            {DEPTHS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </div>
        {editor && (
          <div className="grid gap-1.5">
            <label htmlFor={`${id}visibility`} className="text-sm font-medium">
              Who can read it
            </label>
            <NativeSelect id={`${id}visibility`} name="visibility" defaultValue="workspace">
              <option value="workspace">Everyone in the workspace</option>
              <option value="private">Only me</option>
            </NativeSelect>
          </div>
        )}
        <Button type="submit" pending={generate.isPending}>
          Generate lesson
        </Button>
        {!editor && <p className="w-full text-xs text-muted-foreground">Lessons you generate are private to you.</p>}
        {generate.error && (
          <p role="alert" className="w-full text-sm text-destructive">
            {generate.error.message}
          </p>
        )}
      </form>
      {editor && <Pins topicId={topicId} workspaceId={workspaceId} />}
    </section>
  )
}

const STATUS: Record<Lesson['status'], string> = {
  queued: 'Queued',
  generating: 'Writing…',
  ready: 'Ready',
  failed: 'Failed',
  cancelled: 'Cancelled',
}

function LessonRow({ lesson: l, canShare }: { lesson: Lesson; canShare: boolean }) {
  const busy = isBusy(l)
  const progress = useJobProgress(l.job_id, busy, ['topic-lessons'])
  const publish = usePublish(l.id)
  return (
    <li className="grid gap-2 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid gap-0.5">
          {l.current_version > 0 ? (
            <Link to={`/lessons/${l.id}`} className="font-medium hover:underline">
              {depthLabel(l.depth)}
            </Link>
          ) : (
            <span className="font-medium">{depthLabel(l.depth)}</span>
          )}
          <span className="text-sm text-muted-foreground">
            {l.current_version > 0 ? `Version ${l.current_version}` : 'Not generated yet'}
            {l.outdated_reason && ' · may be out of date'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {l.visibility === 'private' && <Badge variant="outline">Private</Badge>}
          {l.visibility === 'private' && canShare && l.current_version > 0 && (
            <Button size="sm" variant="outline" pending={publish.isPending} onClick={() => publish.mutate()}>
              Share with workspace
            </Button>
          )}
          <Badge variant={l.status === 'failed' ? 'destructive' : l.status === 'ready' ? 'secondary' : 'outline'}>{STATUS[l.status]}</Badge>
        </div>
      </div>
      {publish.error && <p role="alert" className="text-sm text-destructive">{publish.error.message}</p>}
      {busy && <JobProgress event={progress} label={`Writing the ${depthLabel(l.depth)} lesson`} />}
      {l.status === 'failed' && l.error && (
        <p role="alert" className="text-sm text-destructive">
          {l.error}
        </p>
      )}
    </li>
  )
}

function Pins({ topicId, workspaceId }: { topicId: string; workspaceId: string }) {
  const pins = usePins(topicId)
  const documents = useDocuments(workspaceId)
  const save = useSetPins(topicId)
  const pinned = new Set((pins.data ?? []).map((d) => d.id))
  const candidates = (documents.data ?? []).filter((d) => d.kind !== 'syllabus')
  return (
    <details className="text-sm">
      <summary className="cursor-pointer">Pinned documents ({pinned.size})</summary>
      <form
        key={[...pinned].join()} // reset checkboxes after a save
        className="mt-3 grid gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          save.mutate(new FormData(e.currentTarget).getAll('document') as string[])
        }}
      >
        <p className="text-muted-foreground">
          Pinned documents are always used as evidence for this topic's lessons, on top of the passages matched automatically.
        </p>
        {candidates.length === 0 && <p className="text-muted-foreground">Upload notes or textbooks first.</p>}
        {candidates.map((d) => (
          <label key={d.id} className="flex items-center gap-2">
            <input type="checkbox" name="document" value={d.id} defaultChecked={pinned.has(d.id)} />
            {d.filename}
          </label>
        ))}
        {candidates.length > 0 && (
          <Button type="submit" size="sm" variant="outline" className="justify-self-start" pending={save.isPending}>
            Save pins
          </Button>
        )}
        {save.error && <p role="alert" className="text-destructive">{save.error.message}</p>}
      </form>
    </details>
  )
}
