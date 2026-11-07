import { useId, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ConfirmDelete } from '@/components/confirm-delete'
import { JobProgress } from '@/components/job-progress'
import { Markdown } from '@/components/lesson-blocks/markdown'
import { NativeSelect } from '@/components/native-select'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  OBJECTIVE,
  TYPE_LABEL,
  useCreateQuestion,
  useDeleteQuestion,
  useExtract,
  usePapers,
  useQuestions,
  useUpdateQuestion,
  type Paper,
  type Question,
  type QuestionInput,
  type QuestionType,
} from '@/features/assessments/api'
import { useCourse } from '@/features/courses/api'
import { useStructure } from '@/features/syllabus/api'
import { useRole } from '@/features/workspaces/api'
import { atLeast } from '@/lib/api'
import { useJobProgress } from '@/lib/jobs'

/** The course's question bank: extracted papers to review (H3), plus hand-written and generated questions. */
export function QuestionBankPage() {
  const { courseId = '' } = useParams()
  const [status, setStatus] = useState('')
  const role = useRole(useCourse(courseId).data?.workspace_id)
  const editor = atLeast(role, 'editor')
  const papers = usePapers(courseId)
  const questions = useQuestions(courseId, status || undefined, editor)
  const [adding, setAdding] = useState(false)
  const create = useCreateQuestion(courseId)

  return (
    <div className="grid gap-10">
      <header className="grid gap-2">
        <Link to={`/courses/${courseId}`} className="text-sm text-muted-foreground hover:underline">
          ← Back to course
        </Link>
        <h1 className="text-2xl font-semibold">Question bank</h1>
        {role && !editor && (
          <p role="alert" className="text-destructive">
            The question bank holds answer keys, so only editors and above can open it. Practise with a quiz instead.
          </p>
        )}
        <p className="max-w-prose text-sm text-muted-foreground">
          Questions from your papers arrive as drafts: check the wording, marks and topic, add the answer key, then approve
          them. Quizzes use approved questions first and write the rest.
        </p>
      </header>

      <section aria-labelledby="papers-title" className="grid gap-3">
        <h2 id="papers-title" className="text-lg font-medium">
          Question papers
        </h2>
        {papers.data?.length ? (
          <ul className="grid gap-3">
            {papers.data.map((p) => (
              <PaperRow key={p.document_id} paper={p} courseId={courseId} />
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            Upload previous-year or suggestion papers to this course with the type “Question paper”: their questions are
            extracted automatically.
          </p>
        )}
      </section>

      <section aria-labelledby="questions-title" className="grid gap-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 id="questions-title" className="text-lg font-medium">
            Questions
          </h2>
          <div className="flex items-end gap-2">
            <div className="grid gap-1.5">
              <Label htmlFor="bank-status">Show</Label>
              <NativeSelect id="bank-status" value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">All</option>
                <option value="draft">Drafts to review</option>
                <option value="approved">Approved</option>
              </NativeSelect>
            </div>
            <Button variant="outline" onClick={() => setAdding(true)} disabled={adding}>
              Add a question
            </Button>
          </div>
        </div>
        {adding && (
          <QuestionForm
            courseId={courseId}
            submitLabel="Add question"
            pending={create.isPending}
            error={create.error}
            onCancel={() => setAdding(false)}
            onSubmit={(q) => create.mutate(q, { onSuccess: () => setAdding(false) })}
          />
        )}
        {questions.isPending ? (
          <p className="text-muted-foreground">Loading…</p>
        ) : questions.data?.length ? (
          <ol className="grid gap-4">
            {questions.data.map((q) => (
              <QuestionCard key={q.id} question={q} />
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted-foreground">No questions here yet.</p>
        )}
      </section>
    </div>
  )
}

function PaperRow({ paper: p, courseId }: { paper: Paper; courseId: string }) {
  const extract = useExtract()
  const busy = p.status === 'queued' || p.status === 'running'
  const progress = useJobProgress(p.job_id, busy, ['papers', courseId], ['questions', courseId])
  return (
    <li className="grid gap-2 rounded-xl border px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-medium">{p.filename}</p>
          <p className="text-sm text-muted-foreground">
            {p.status === 'none' ? 'Not read yet' : p.status === 'failed' ? 'Extraction failed' : `${p.questions} questions`}
            {p.drafts > 0 && ` · ${p.drafts} to review`}
          </p>
        </div>
        <Button size="sm" variant="outline" disabled={busy || extract.isPending || p.document_status !== 'ready'}
                pending={extract.isPending && extract.variables === p.document_id} onClick={() => extract.mutate(p.document_id)}>
          {p.status === 'none' ? 'Extract questions' : 'Extract again'}
        </Button>
      </div>
      {busy && <JobProgress event={progress} label={`Reading ${p.filename}`} />}
      {p.status === 'failed' && p.error && <p role="alert" className="text-sm text-destructive">{p.error}</p>}
      {extract.error && <p role="alert" className="text-sm text-destructive">{extract.error.message}</p>}
      {p.status !== 'none' && p.drafts > 0 && (
        <p className="text-xs text-muted-foreground">Extracting again replaces drafts you haven't approved.</p>
      )}
    </li>
  )
}

function QuestionCard({ question: q }: { question: Question }) {
  const [editing, setEditing] = useState(false)
  const update = useUpdateQuestion()
  const remove = useDeleteQuestion()
  const source = [q.filename, q.source_label && `Q${q.source_label.replace(/^q/i, '')}`, q.source_page && `p. ${q.source_page}`]
    .filter(Boolean)
    .join(', ')

  if (editing)
    return (
      <li>
        <QuestionForm
          courseId={q.course_id}
          initial={q}
          submitLabel="Save"
          pending={update.isPending}
          error={update.error}
          onCancel={() => setEditing(false)}
          onSubmit={(input) => update.mutate({ id: q.id, ...input }, { onSuccess: () => setEditing(false) })}
        />
      </li>
    )
  return (
    <li className="grid gap-2 rounded-xl border px-4 py-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant={q.status === 'draft' ? 'outline' : 'secondary'}>{q.status === 'draft' ? 'Draft' : 'Approved'}</Badge>
        <span>
          {TYPE_LABEL[q.type]} · {q.marks} mark{q.marks === 1 ? '' : 's'} · {q.difficulty}
        </span>
        <span>· {q.topic_title ? `${q.unit_title} › ${q.topic_title}` : 'No topic'}</span>
        <span>· {q.source_kind === 'extracted' ? source : q.source_kind === 'generated' ? 'AI-written' : 'Added by you'}</span>
      </div>
      <Markdown text={q.text} />
      {q.options.length > 0 && (
        <ol className="grid list-[lower-alpha] gap-0.5 pl-6 text-sm">
          {q.options.map((o, i) => (
            <li key={i} className={q.answer === String(i) ? 'font-medium' : undefined}>
              <Markdown text={o} inline />
              {q.answer === String(i) && ' ✓'}
            </li>
          ))}
        </ol>
      )}
      <p className="text-sm text-muted-foreground">
        {q.answer === null
          ? 'No answer key yet.'
          : !q.options.length && (
              <>
                Answer key: <span className="text-foreground">{q.answer.length > 160 ? `${q.answer.slice(0, 160)}…` : q.answer}</span>
              </>
            )}
      </p>
      {(update.error || remove.error) && (
        <p role="alert" className="text-sm text-destructive">
          {(update.error ?? remove.error)?.message}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {q.status === 'draft' && (
          <Button size="sm" disabled={update.isPending} pending={update.isPending && update.variables?.id === q.id} onClick={() => update.mutate({ id: q.id, status: 'approved' })}>
            Approve
          </Button>
        )}
        <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
          Edit
        </Button>
        <ConfirmDelete label="Delete" pending={remove.isPending} onConfirm={() => remove.mutate(q.id)} />
      </div>
    </li>
  )
}

const parseRubric = (text: string) =>
  text
    .split('\n')
    .map((line) => line.match(/^(.+?)[:–-]\s*(\d+)\s*$/))
    .filter((m): m is RegExpMatchArray => !!m)
    .map((m) => ({ criterion: m[1].trim(), marks: Number(m[2]) }))

function QuestionForm({
  courseId,
  initial,
  submitLabel,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  courseId: string
  initial?: Question
  submitLabel: string
  pending: boolean
  error: Error | null
  onSubmit: (q: QuestionInput) => void
  onCancel: () => void
}) {
  const id = useId()
  const structure = useStructure(courseId)
  const [type, setType] = useState<QuestionType>(initial?.type ?? 'short')
  const [options, setOptions] = useState((initial?.options ?? []).join('\n'))
  const choices = type === 'true_false' ? ['True', 'False'] : options.split('\n').map((o) => o.trim()).filter(Boolean)
  const written = !OBJECTIVE.has(type)

  return (
    <form
      className="grid gap-4 rounded-xl border px-4 py-4"
      onSubmit={(e) => {
        e.preventDefault()
        const f = new FormData(e.currentTarget)
        const get = (k: string) => ((f.get(k) as string | null) ?? '').trim()
        onSubmit({
          text: get('text'),
          type,
          marks: Number(get('marks')),
          difficulty: get('difficulty') as QuestionInput['difficulty'],
          topic_id: get('topic') || null,
          options: type === 'mcq' ? choices : [],
          answer: get('answer') || null,
          rubric: written ? parseRubric(get('rubric')) : [],
          explanation: get('explanation'),
        })
      }}
    >
      <div className="grid gap-1.5">
        <Label htmlFor={`${id}text`}>Question</Label>
        <Textarea id={`${id}text`} name="text" required minLength={5} defaultValue={initial?.text} rows={3} />
      </div>
      <div className="flex flex-wrap gap-4">
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}type`}>Type</Label>
          <NativeSelect id={`${id}type`} value={type} onChange={(e) => setType(e.target.value as QuestionType)}>
            {Object.entries(TYPE_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}marks`}>Marks</Label>
          <Input id={`${id}marks`} name="marks" type="number" min={1} max={100} required defaultValue={initial?.marks ?? 2} className="w-20" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}difficulty`}>Difficulty</Label>
          <NativeSelect id={`${id}difficulty`} name="difficulty" defaultValue={initial?.difficulty ?? 'medium'}>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </NativeSelect>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}topic`}>Topic</Label>
          <NativeSelect id={`${id}topic`} name="topic" defaultValue={initial?.topic_id ?? ''}>
            <option value="">No topic</option>
            {structure.data?.units.map((u) => (
              <optgroup key={u.id} label={u.title}>
                {u.topics.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title}
                  </option>
                ))}
              </optgroup>
            ))}
          </NativeSelect>
        </div>
      </div>

      {type === 'mcq' && (
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}options`}>Options, one per line</Label>
          <Textarea id={`${id}options`} value={options} onChange={(e) => setOptions(e.target.value)} rows={4} required />
        </div>
      )}
      <div className="grid gap-1.5">
        <Label htmlFor={`${id}answer`}>{written ? 'Model answer (optional: used as the reference when marking)' : 'Correct answer'}</Label>
        {type === 'mcq' || type === 'true_false' ? (
          <NativeSelect id={`${id}answer`} name="answer" defaultValue={initial?.answer ?? ''} className="max-w-md">
            <option value="">Not set</option>
            {choices.map((c, i) => (
              <option key={i} value={String(i)}>
                {c}
              </option>
            ))}
          </NativeSelect>
        ) : written ? (
          <Textarea id={`${id}answer`} name="answer" defaultValue={initial?.answer ?? ''} rows={4} />
        ) : (
          <>
            <Input id={`${id}answer`} name="answer" defaultValue={initial?.answer ?? ''} className="max-w-md" aria-describedby={`${id}answerhint`} />
            <p id={`${id}answerhint`} className="text-xs text-muted-foreground">
              {type === 'numerical' ? 'The final number; answers within 1% count as correct.' : 'Accepted answers separated by | (e.g. primary key|PK).'}
            </p>
          </>
        )}
      </div>
      {written && (
        <div className="grid gap-1.5">
          <Label htmlFor={`${id}rubric`}>Marking rubric, one criterion per line as “criterion: marks”</Label>
          <Textarea
            id={`${id}rubric`}
            name="rubric"
            rows={3}
            defaultValue={initial?.rubric.map((c) => `${c.criterion}: ${c.marks}`).join('\n')}
            aria-describedby={`${id}rubrichint`}
          />
          <p id={`${id}rubrichint`} className="text-xs text-muted-foreground">
            If the marks don't add up to the question's marks, the standard split is used (accuracy, explanation, example,
            presentation).
          </p>
        </div>
      )}
      <div className="grid gap-1.5">
        <Label htmlFor={`${id}explanation`}>Explanation (shown with the results)</Label>
        <Textarea id={`${id}explanation`} name="explanation" defaultValue={initial?.explanation} rows={2} />
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error.message}</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={pending}>
          {submitLabel}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
