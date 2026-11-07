import { useId } from 'react'
import { Link, useNavigate } from 'react-router'

import { ConfirmDelete } from '@/components/confirm-delete'
import { NativeSelect } from '@/components/native-select'
import { Button, buttonVariants } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  percent,
  TYPE_LABEL,
  useCourseQuizzes,
  useCreateQuiz,
  useDeleteQuiz,
  useProgress,
  useQuestions,
  type Difficulty,
  type QuestionType,
  type QuizRequest,
} from '@/features/assessments/api'
import { useStructure } from '@/features/syllabus/api'
import { StartTutor } from '@/features/tutor/StartTutor'
import { useRole } from '@/features/workspaces/api'
import { atLeast } from '@/lib/api'

/** Course page: quizzes (H4, A21), the question bank, progress and the tutor. */
export function PracticePanel({ courseId, workspaceId }: { courseId: string; workspaceId: string }) {
  const id = useId()
  const structure = useStructure(courseId)
  const quizzes = useCourseQuizzes(courseId)
  const editor = atLeast(useRole(workspaceId), 'editor')
  const drafts = useQuestions(courseId, 'draft', editor)
  const progress = useProgress(courseId)
  const create = useCreateQuiz({ courseId })
  const remove = useDeleteQuiz()
  const navigate = useNavigate()
  const hasTopics = (structure.data?.topic_count ?? 0) > 0
  const p = progress.data

  return (
    <section aria-labelledby="practice-title" className="grid gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="practice-title" className="text-lg font-medium">
          Practice and progress
        </h2>
        <div className="flex flex-wrap gap-2">
          <StartTutor context={{ workspace_id: workspaceId, course_id: courseId }} />
          {editor && (
            <Link to={`/courses/${courseId}/questions`} className={buttonVariants({ variant: 'outline' })}>
              Question bank{drafts.data?.length ? ` (${drafts.data.length} to review)` : ''}
            </Link>
          )}
          <Link to={`/courses/${courseId}/progress`} className={buttonVariants({ variant: 'outline' })}>
            Progress
          </Link>
        </div>
      </div>
      {p && p.topics.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {p.completed} of {p.topics.length} topics completed · {p.studied} studied · {p.revision_required} to revise · quiz
          accuracy {percent(p.accuracy)}
        </p>
      )}

      {hasTopics ? (
        <form
          className="grid gap-3 rounded-xl border px-4 py-4"
          onSubmit={(e) => {
            e.preventDefault()
            const f = new FormData(e.currentTarget)
            const scope = f.get('scope') as string
            const body: QuizRequest = {
              count: Number(f.get('count')),
              difficulty: (f.get('difficulty') as Difficulty) || undefined,
              marks: Number(f.get('marks')) || undefined,
              types: f.getAll('types') as QuestionType[],
              unit_id: scope || undefined,
            }
            create.mutate(body, { onSuccess: (q) => navigate(`/quizzes/${q.id}`) })
          }}
        >
          <h3 className="font-medium">New quiz</h3>
          <div className="flex flex-wrap gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor={`${id}scope`}>Covering</Label>
              <NativeSelect id={`${id}scope`} name="scope" defaultValue="">
                <option value="">The whole course</option>
                {structure.data?.units.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.title}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor={`${id}count`}>Questions</Label>
              <Input id={`${id}count`} name="count" type="number" min={1} max={30} defaultValue={5} className="w-20" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor={`${id}difficulty`}>Difficulty</Label>
              <NativeSelect id={`${id}difficulty`} name="difficulty" defaultValue="">
                <option value="">Any</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </NativeSelect>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor={`${id}marks`}>Marks each</Label>
              <NativeSelect id={`${id}marks`} name="marks" defaultValue="">
                <option value="">Any</option>
                {[1, 2, 5, 10].map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </NativeSelect>
            </div>
          </div>
          <fieldset className="flex flex-wrap gap-x-4 gap-y-1">
            <legend className="mb-1 text-sm font-medium">Question types (none ticked: a mix)</legend>
            {Object.entries(TYPE_LABEL).map(([value, label]) => (
              <label key={value} className="flex items-center gap-1.5 text-sm">
                <input type="checkbox" name="types" value={value} />
                {label}
              </label>
            ))}
          </fieldset>
          {create.error && <p role="alert" className="text-sm text-destructive">{create.error.message}</p>}
          <div>
            <Button type="submit" pending={create.isPending}>
              Create quiz
            </Button>
          </div>
        </form>
      ) : (
        <p className="text-sm text-muted-foreground">Confirm the syllabus to create quizzes on its units and topics.</p>
      )}

      {quizzes.data && quizzes.data.length > 0 && (
        <ul className="grid gap-2" aria-label="Quizzes">
          {quizzes.data.map((q) => {
            const last = q.attempts.find((a) => a.status === 'graded')
            return (
              <li key={q.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border px-4 py-2">
                <div>
                  <Link to={`/quizzes/${q.id}`} className="font-medium hover:underline">
                    {q.title}
                  </Link>
                  <p className="text-sm text-muted-foreground">
                    {new Date(q.created_at).toLocaleDateString()} ·{' '}
                    {q.status === 'generating' ? 'preparing…' : q.status === 'failed' ? 'failed' : last ? `last score ${last.score} / ${last.max_score}` : 'not attempted'}
                  </p>
                </div>
                <ConfirmDelete label="Delete" pending={remove.isPending} onConfirm={() => remove.mutate(q.id)} />
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
