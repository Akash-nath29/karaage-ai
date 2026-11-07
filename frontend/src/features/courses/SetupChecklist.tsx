import { Circle, CircleCheck, CircleDashed, CircleDot, LoaderCircle } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'

import { JobProgress } from '@/components/job-progress'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import type { Course } from '@/features/courses/api'
import { useDocuments } from '@/features/documents/api'
import { UploadForm } from '@/features/documents/DocumentsPanel'
import { useStructure, useSyllabus } from '@/features/syllabus/api'
import { BatchStatus, ChooseDocument, DraftReview, EditStructure } from '@/features/syllabus/SyllabusPanel'
import { useMembers } from '@/features/workspaces/api'
import { atLeast, type Role } from '@/lib/api'
import { useJobProgress } from '@/lib/jobs'
import { cn } from '@/lib/utils'

type StepState = 'done' | 'current' | 'running' | 'waiting' | 'optional'
type Step = { key: string; title: string; state: StepState; optional?: boolean; summary: ReactNode; body?: ReactNode }

const STATE_TEXT: Record<StepState, string> = {
  done: 'Done',
  current: 'To do now',
  running: 'In progress',
  waiting: 'Waits for an earlier step',
  optional: 'Optional',
}

function StepIcon({ state }: { state: StepState }) {
  const cls = 'size-5'
  if (state === 'done') return <CircleCheck aria-hidden className={cls} />
  if (state === 'running') return <LoaderCircle aria-hidden className={cn(cls, 'animate-spin motion-reduce:animate-none')} />
  if (state === 'current') return <CircleDot aria-hidden className={cls} />
  if (state === 'waiting') return <CircleDashed aria-hidden className={cn(cls, 'text-muted-foreground')} />
  return <Circle aria-hidden className={cn(cls, 'text-muted-foreground')} />
}

/** Course setup in the order each step depends on the last (D38): syllabus, topics, materials, lessons, people. Only the
 * step to do now is open; finished ones shrink to a line, and the whole list folds away once the course is ready. */
export function SetupChecklist({ course: c, role }: { course: Course; role: Role | undefined }) {
  const editor = atLeast(role, 'editor')
  const admin = atLeast(role, 'admin') // the syllabus and structure are course management (A11)
  const syllabus = useSyllabus(c.id)
  const structure = useStructure(c.id)
  const documents = useDocuments(c.workspace_id)
  const members = useMembers(c.workspace_id)
  const s = syllabus.data
  const parsing = s?.status === 'parsing'
  const progress = useJobProgress(s?.job_id ?? null, parsing, ['syllabus', c.id])
  const [open, setOpen] = useState<string | null>(null)
  const [byHand, setByHand] = useState(false)
  const [showAll, setShowAll] = useState(false)

  if (syllabus.isPending || structure.isPending || documents.isPending) return null
  const tree = structure.data
  const hasTopics = !!tree?.units.length
  if (!editor)
    return hasTopics ? null : (
      <p role="status" className="rounded-xl border px-4 py-3 text-sm text-muted-foreground">
        This course is still being set up. Its topics and lessons appear here as soon as they're ready.
      </p>
    )

  const docs = documents.data ?? [] // every file in the workspace: any of them can be this course's syllabus
  const mine = docs.filter((d) => d.course_id === c.id)
  const reading = mine.some((d) => d.status !== 'ready' && d.status !== 'failed')
  const ready = tree?.lessons_ready ?? 0
  const total = tree?.topic_count ?? 0
  const people = members.data?.length ?? 0

  // Neither of the first two steps waits on the other: materials are optional, and topics can come from any file
  // already in the workspace (whichever course it was uploaded to) or be typed in.
  const steps: Step[] = [
    {
      key: 'materials',
      title: 'Add your study materials',
      optional: true,
      state: mine.length ? 'done' : 'optional',
      summary: mine.length
        ? `${mine.length} file${mine.length === 1 ? '' : 's'} in this course${reading ? ', some still being read' : ''}`
        : 'Whatever you have: the syllabus, notes, textbooks or past question papers. Lessons draw on them first.',
      body: editor && (
        <UploadForm workspaceId={c.workspace_id} courseId={c.id} defaultKind={docs.some((d) => d.kind === 'syllabus') || hasTopics ? 'notes' : 'syllabus'}
                    className="border-0 p-0" />
      ),
    },
    {
      key: 'topics',
      title: 'Units and topics',
      state: parsing ? 'running' : hasTopics && s?.status !== 'draft' ? 'done' : 'current',
      summary: parsing
        ? 'Reading the syllabus…'
        : s?.status === 'draft'
          ? 'Check the draft, fix anything the parser got wrong, then confirm.'
          : hasTopics
            ? `${tree!.units.length} units · ${total} topics`
            : s?.status === 'failed'
              ? s.error
              : docs.length
                ? 'Read them from a syllabus already in this workspace, or type them in.'
                : 'Type them in, or add the syllabus as a study material and Karaage reads them out of it.',
      body: !admin ? (
        <p className="text-sm text-muted-foreground">An admin of this workspace sets the units and topics.</p>
      ) : parsing ? (
        <JobProgress event={progress} label="Parsing the syllabus" />
      ) : s?.status === 'draft' && s.draft ? (
        <DraftReview course={c} syllabus={s} replacing={hasTopics} />
      ) : hasTopics ? (
        <Link to={`/courses/${c.id}/settings`} className={buttonVariants({ variant: 'outline', size: 'sm' })}>
          Edit units and topics
        </Link>
      ) : byHand ? (
        <EditStructure
          courseId={c.id}
          structure={tree ?? { units: [], topic_count: 0, coverage: 0, lessons_ready: 0, lessons_pending: 0 }}
          onDone={() => setByHand(false)}
        />
      ) : (
        <div className="grid gap-4">
          {docs.length > 0 && <ChooseDocument course={c} syllabus={s ?? null} onDone={() => setOpen(null)} />}
          <Button variant={docs.length ? 'link' : 'outline'} className={cn('justify-self-start', docs.length > 0 && 'px-0')} onClick={() => setByHand(true)}>
            {docs.length ? 'No syllabus? Type the units and topics in' : 'Type the units and topics in'}
          </Button>
        </div>
      ),
    },
    {
      key: 'lessons',
      title: 'Lessons for every topic',
      state: !hasTopics ? 'waiting' : tree!.lessons_pending ? 'running' : ready >= total ? 'done' : 'current',
      summary: !hasTopics
        ? 'Written automatically once the topics are confirmed.'
        : ready >= total
          ? `All ${total} ready`
          : `${ready} of ${total} ready${tree!.lessons_pending ? `, ${tree!.lessons_pending} being written` : ''}`,
      body: hasTopics && <BatchStatus courseId={c.id} structure={tree!} canRun={editor} />,
    },
    ...(admin
      ? [
          {
            key: 'people',
            title: 'Invite classmates',
            optional: true,
            state: (people > 1 ? 'done' : 'optional') as StepState,
            summary: people > 1 ? `${people} people in this workspace` : 'Everyone you invite to the workspace can study this course.',
            body: (
              <Link to={`/workspaces/${c.workspace_id}/members`} className={buttonVariants({ variant: 'outline', size: 'sm' })}>
                Invite people
              </Link>
            ),
          },
        ]
      : []),
  ]

  const core = steps.filter((x) => !x.optional)
  const doneCount = core.filter((x) => x.state === 'done').length
  if (doneCount === core.length && !showAll && !open)
    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border px-4 py-3 text-sm">
        <CircleCheck aria-hidden className="size-4" />
        <span>
          Set up: {total} topics, {ready} lessons ready.
        </span>
        <Button variant="link" size="sm" className="h-auto px-0" onClick={() => setShowAll(true)}>
          Show setup
        </Button>
      </div>
    )

  // Nothing in the workspace yet: start by adding materials. Otherwise open the first step that needs doing, so an
  // upload leads straight into picking the syllabus out of it.
  const active = open ?? (!docs.length && !hasTopics ? 'materials' : steps.find((x) => x.state === 'current' || x.state === 'running')?.key)
  return (
    <section aria-labelledby="setup-title" className="grid gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="setup-title" className="text-lg font-medium">Set up this course</h2>
        <span className="text-sm text-muted-foreground tabular-nums">
          {doneCount} of {core.length} required steps done
        </span>
      </div>
      <ol className="divide-y border-y">
        {steps.map((step) => {
          const expanded = step.key === active && !!step.body
          return (
            <li key={step.key} className="grid grid-cols-[1.75rem_minmax(0,1fr)] gap-x-3 py-4">
              <span className="pt-0.5">
                <StepIcon state={step.state} />
              </span>
              <div className="grid min-w-0 gap-1.5">
                <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-2">
                  <h3 className={cn('flex flex-wrap items-center gap-x-2 gap-y-1 font-medium', step.state === 'waiting' && 'text-muted-foreground')}>
                    {step.title}
                    {step.optional && <Badge variant="outline">Optional</Badge>}
                  </h3>
                  {step.body && !expanded && step.state !== 'waiting' && (
                    <Button size="sm" variant="ghost" onClick={() => setOpen(step.key)}>
                      {step.state === 'done' ? 'Change' : 'Open'}
                    </Button>
                  )}
                </div>
                <p className="max-w-prose text-sm text-muted-foreground">
                  <span className="sr-only">{STATE_TEXT[step.state]}: </span>
                  {step.summary}
                </p>
                {expanded && <div className="pt-2">{step.body}</div>}
              </div>
            </li>
          )
        })}
      </ol>
    </section>
  )
}
