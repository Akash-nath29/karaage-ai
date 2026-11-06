import { useId, useState } from 'react'
import { Link } from 'react-router'

import { NativeSelect } from '@/components/native-select'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import type { Course } from '@/features/courses/api'
import { useDocuments } from '@/features/documents/api'
import { useCancelBatch, useGenerateMissing } from '@/features/lessons/api'
import {
  STATUS_LABEL,
  toStructure,
  useConfirm,
  useLinkSyllabus,
  useReparse,
  useSaveDraft,
  useSaveStructure,
  useStructure,
  useSyllabus,
  type StructureOut,
  type Syllabus,
} from '@/features/syllabus/api'
import { StructureEditor } from '@/features/syllabus/StructureEditor'
import { JobProgress } from '@/components/job-progress'
import { useRole } from '@/features/workspaces/api'
import { atLeast } from '@/lib/api'
import { useJobProgress } from '@/lib/jobs'

const percent = (x: number) => `${Math.round(x * 100)}%`

export function SyllabusPanel({ course }: { course: Course }) {
  const id = useId()
  const syllabus = useSyllabus(course.id)
  const structure = useStructure(course.id)
  const s = syllabus.data
  const parsing = s?.status === 'parsing'
  const progress = useJobProgress(s?.job_id ?? null, parsing, ['syllabus', course.id])
  const [mode, setMode] = useState<'view' | 'edit' | 'choose'>('view')
  const tree = structure.data
  const hasStructure = !!tree?.units.length
  const role = useRole(course.workspace_id)
  const admin = atLeast(role, 'admin') // the syllabus and structure are course management (A11)

  return (
    <section className="grid gap-4" aria-labelledby={`${id}heading`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={`${id}heading`} className="text-lg font-medium">
          Syllabus
        </h2>
        {hasStructure && (
          <p className="text-sm text-muted-foreground">
            {tree.topic_count} topics · {percent(tree.coverage)} have study materials · {tree.lessons_ready} lessons ready
          </p>
        )}
      </div>
      {hasStructure && <BatchStatus courseId={course.id} structure={tree} canRun={atLeast(role, 'editor')} />}
      {(syllabus.error || structure.error) && (
        <p role="alert" className="text-destructive">{(syllabus.error ?? structure.error)?.message}</p>
      )}

      {parsing && <JobProgress event={progress} label="Parsing the syllabus" />}
      {s?.status === 'failed' && (
        <p role="alert" className="text-sm text-destructive">
          {s.error}
        </p>
      )}
      {admin && (!s || s.status === 'failed' || mode === 'choose') && !parsing && (
        <ChooseDocument course={course} syllabus={s ?? null} onDone={() => setMode('view')} />
      )}

      {admin && s?.status === 'draft' && s.draft && <DraftReview course={course} syllabus={s} replacing={hasStructure} />}
      {!admin && !hasStructure && <p className="text-sm text-muted-foreground">No syllabus yet: an admin adds it.</p>}

      {s?.status !== 'draft' && mode === 'edit' && (
        <EditStructure courseId={course.id} structure={tree ?? { units: [], topic_count: 0, coverage: 0, lessons_ready: 0, lessons_pending: 0 }} onDone={() => setMode('view')} />
      )}
      {s?.status !== 'draft' && mode !== 'edit' && hasStructure && (
        <>
          <StructureView structure={tree} />
          {admin && <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setMode('edit')}>
              Edit units and topics
            </Button>
            {s?.document_id && <ReparseButton courseId={course.id} />}
            {s && mode !== 'choose' && (
              <Button variant="ghost" onClick={() => setMode('choose')}>
                Use another document
              </Button>
            )}
          </div>}
        </>
      )}
      {admin && !s && !hasStructure && mode === 'view' && (
        <Button variant="link" className="justify-self-start px-0" onClick={() => setMode('edit')}>
          No syllabus file? Add units and topics by hand
        </Button>
      )}
    </section>
  )
}

function BatchStatus({ courseId, structure, canRun }: { courseId: string; structure: StructureOut; canRun: boolean }) {
  const cancel = useCancelBatch(courseId)
  const missing = useGenerateMissing(courseId)
  const outstanding = structure.topic_count - structure.lessons_ready - structure.lessons_pending
  if (!structure.lessons_pending && outstanding <= 0) return null
  return (
    <div role="status" className="flex flex-wrap items-center gap-3 rounded-xl border px-4 py-3 text-sm">
      {structure.lessons_pending > 0 ? (
        <>
          <span>
            Writing lessons: {structure.lessons_ready} of {structure.topic_count} ready, {structure.lessons_pending} in progress or queued.
          </span>
          {canRun && (
            <Button size="sm" variant="outline" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
              Cancel queued lessons
            </Button>
          )}
        </>
      ) : (
        <>
          <span>{outstanding} topics don't have a lesson yet.</span>
          {canRun && (
            <Button size="sm" variant="outline" disabled={missing.isPending} onClick={() => missing.mutate()}>
              Generate missing lessons
            </Button>
          )}
        </>
      )}
      {(cancel.error ?? missing.error) && <span className="text-destructive">{(cancel.error ?? missing.error)?.message}</span>}
    </div>
  )
}

function ChooseDocument({ course, syllabus, onDone }: { course: Course; syllabus: Syllabus | null; onDone: () => void }) {
  const id = useId()
  const documents = useDocuments(course.workspace_id)
  const link = useLinkSyllabus(course.id)
  // Syllabus-type uploads first, then this course's, then everything else in the workspace.
  const options = [...(documents.data ?? [])].sort(
    (a, b) => Number(b.kind === 'syllabus') - Number(a.kind === 'syllabus') || Number(b.course_id === course.id) - Number(a.course_id === course.id),
  )
  if (!documents.data) return null
  if (!options.length)
    return (
      <p className="text-sm text-muted-foreground">
        Upload your syllabus under <strong>Study materials</strong> (type: Syllabus), then parse it here. A single PDF of
        the whole programme works too: the course is found by its title and code.
      </p>
    )
  return (
    <form
      className="flex flex-wrap items-end gap-3"
      onSubmit={(e) => {
        e.preventDefault()
        link.mutate(new FormData(e.currentTarget).get('document') as string, { onSuccess: onDone })
      }}
    >
      <div className="grid gap-1.5">
        <Label htmlFor={`${id}doc`}>Syllabus document</Label>
        <NativeSelect id={`${id}doc`} name="document" defaultValue={syllabus?.document_id ?? options[0].id} className="max-w-sm">
          {options.map((d) => (
            <option key={d.id} value={d.id}>
              {d.filename}
              {d.kind === 'syllabus' ? ' (syllabus)' : ''}
            </option>
          ))}
        </NativeSelect>
      </div>
      <Button type="submit" disabled={link.isPending}>
        Parse syllabus
      </Button>
      {link.error && (
        <p role="alert" className="w-full text-sm text-destructive">
          {link.error.message}
        </p>
      )}
    </form>
  )
}

function DraftReview({ course, syllabus, replacing }: { course: Course; syllabus: Syllabus; replacing: boolean }) {
  const draft = syllabus.draft!
  const save = useSaveDraft(course.id)
  const confirm = useConfirm(course.id)
  const where = syllabus.page_start ? `pages ${syllabus.page_start}–${syllabus.page_end}` : 'the document'
  return (
    <div className="grid gap-4 rounded-xl border border-dashed p-4">
      <div className="grid gap-1">
        <p className="font-medium">
          Draft from {where}
          {draft.subject_name && `: ${draft.subject_name}`}
          {draft.subject_code && ` (${draft.subject_code})`}
        </p>
        <p className="text-sm text-muted-foreground">
          Check the units and topics, fix anything the parser got wrong, then confirm.
          {replacing && ' Confirming replaces the current structure; topics with the same names keep their materials.'}
        </p>
        {syllabus.generation_estimate && (
          <p className="text-sm">
            Confirming starts writing {syllabus.generation_estimate.lessons} lessons in the background: about{' '}
            {syllabus.generation_estimate.ai_calls} AI calls and ~{Math.round(syllabus.generation_estimate.tokens / 1000)}k tokens,
            plus up to {syllabus.generation_estimate.web_searches_max} web searches where your materials fall short. You can
            cancel it.
          </p>
        )}
      </div>
      {draft.references.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer">Textbooks and references ({draft.references.length})</summary>
          <ul className="mt-2 list-disc pl-5">
            {draft.references.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </details>
      )}
      {draft.exam_structure && <p className="text-sm whitespace-pre-line">Exam: {draft.exam_structure}</p>}
      <StructureEditor
        key={syllabus.job_id} // a new parse resets the editor
        initial={draft}
        actions={[
          { action: 'confirm', label: 'Confirm structure' },
          { action: 'save', label: 'Save draft', variant: 'outline' },
        ]}
        pending={save.isPending || confirm.isPending}
        error={save.error ?? confirm.error}
        onSave={async (tree, action) => {
          await save.mutateAsync({ ...draft, ...tree })
          if (action === 'confirm') await confirm.mutateAsync()
        }}
      />
    </div>
  )
}

function EditStructure({ courseId, structure, onDone }: { courseId: string; structure: StructureOut; onDone: () => void }) {
  const save = useSaveStructure(courseId)
  const initial = structure.units.length ? toStructure(structure) : { units: [{ title: '', hours: null, topics: [] }] }
  return (
    <StructureEditor
      initial={initial}
      actions={[{ action: 'save', label: 'Save structure' }]}
      pending={save.isPending}
      error={save.error}
      onSave={async (tree) => {
        await save.mutateAsync(tree)
        onDone()
      }}
    >
      <Button type="button" variant="ghost" onClick={onDone}>
        Cancel
      </Button>
    </StructureEditor>
  )
}

function ReparseButton({ courseId }: { courseId: string }) {
  const reparse = useReparse(courseId)
  return (
    <Button variant="ghost" onClick={() => reparse.mutate()} disabled={reparse.isPending} title={reparse.error?.message}>
      Re-parse syllabus
    </Button>
  )
}

function StructureView({ structure }: { structure: StructureOut }) {
  return (
    <ol className="grid gap-5">
      {structure.units.map((u, i) => (
        <li key={u.id} className="grid gap-2">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="font-medium">
              Unit {i + 1}: {u.title}
            </h3>
            <span className="text-sm text-muted-foreground">
              {u.hours ? `${u.hours} h · ` : ''}
              {percent(u.coverage)} covered
            </span>
          </div>
          <ul className="divide-y rounded-xl border">
            {u.topics.map((t) => (
              <li key={t.id} className="flex items-start justify-between gap-3 p-3">
                <div className="grid min-w-0 gap-0.5">
                  <Link to={t.lesson_id ? `/lessons/${t.lesson_id}` : `/topics/${t.id}`} className="font-medium hover:underline">
                    {t.title}
                  </Link>
                  {t.subtopics.length > 0 && (
                    <p className="text-sm text-muted-foreground">{t.subtopics.map((st) => st.title).join(' · ')}</p>
                  )}
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <Badge variant={t.status === 'lesson_available' ? 'default' : t.status === 'not_started' ? 'outline' : 'secondary'}>
                    {STATUS_LABEL[t.status]}
                  </Badge>
                  <Link to={`/topics/${t.id}`} className="text-xs text-muted-foreground hover:underline">
                    {t.material_count > 0 ? `${t.material_count} passages · ` : ''}topic details
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ol>
  )
}
