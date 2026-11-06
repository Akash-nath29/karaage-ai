import { useId } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { JobProgress } from '@/components/job-progress'
import { Markdown } from '@/components/lesson-blocks/markdown'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { TYPE_LABEL, useQuiz, useSubmitAttempt, type QuizQuestion } from '@/features/assessments/api'
import { useJobProgress } from '@/lib/jobs'

/** Screen 6: answer a quiz. Objective answers are marked at once; written ones by the AI (an estimate). */
export function QuizPage() {
  const { quizId = '' } = useParams()
  const quiz = useQuiz(quizId)
  const submit = useSubmitAttempt(quizId)
  const navigate = useNavigate()
  const progress = useJobProgress(quiz.data?.job_id ?? null, quiz.data?.status === 'generating', ['quiz', quizId])

  if (quiz.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (quiz.error) return <p role="alert" className="text-destructive">{quiz.error.message}</p>
  const q = quiz.data
  const total = q.questions.reduce((sum, x) => sum + x.marks, 0)
  const written = q.questions.some((x) => !['mcq', 'true_false', 'fill_blank', 'numerical'].includes(x.type))

  return (
    <div className="grid gap-8">
      <header className="grid gap-2">
        <Link to={`/courses/${q.course_id}`} className="text-sm text-muted-foreground hover:underline">
          ← Back to course
        </Link>
        <h1 className="text-2xl font-semibold">{q.title}</h1>
        {q.status === 'ready' && (
          <p className="text-sm text-muted-foreground">
            {q.questions.length} questions · {total} marks
            {written && ' · written answers are marked by the AI against a rubric: the score is an estimate'}
          </p>
        )}
        {q.status === 'generating' && <JobProgress event={progress} label="Preparing the quiz" />}
        {q.status === 'failed' && (
          <p role="alert" className="text-sm text-destructive">
            This quiz couldn't be prepared: {q.error}
          </p>
        )}
      </header>

      {q.attempts.length > 0 && (
        <section aria-labelledby="attempts-title" className="grid gap-2">
          <h2 id="attempts-title" className="font-medium">
            Your attempts
          </h2>
          <ul className="grid gap-1 text-sm">
            {q.attempts.map((a) => (
              <li key={a.id}>
                <Link to={`/attempts/${a.id}`} className="hover:underline">
                  {new Date(a.created_at).toLocaleString()}:{' '}
                  {a.status === 'graded' ? `${a.score} / ${a.max_score}` : a.status === 'grading' ? 'marking…' : 'marking failed'}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {q.status === 'ready' && (
        <form
          className="grid gap-8"
          onSubmit={(e) => {
            e.preventDefault()
            const data = new FormData(e.currentTarget)
            const answers = q.questions.map((x) => ({ question_id: x.id, answer: ((data.get(x.id) as string | null) ?? '').trim() }))
            submit.mutate(answers, { onSuccess: (a) => navigate(`/attempts/${a.id}`) })
          }}
        >
          <ol className="grid gap-8">
            {q.questions.map((x) => (
              <QuestionField key={x.id} question={x} />
            ))}
          </ol>
          {submit.error && <p role="alert" className="text-sm text-destructive">{submit.error.message}</p>}
          <div>
            <Button type="submit" disabled={submit.isPending}>
              {submit.isPending ? 'Submitting…' : 'Submit answers'}
            </Button>
          </div>
        </form>
      )}
    </div>
  )
}

export function QuestionHeader({ question: x }: { question: QuizQuestion }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <span className="font-medium text-foreground">Question {x.position}</span>
      <Badge variant="outline">
        {x.marks} mark{x.marks === 1 ? '' : 's'}
      </Badge>
      <Badge variant="outline">{x.difficulty}</Badge>
      <span>{TYPE_LABEL[x.type]}</span>
      {x.topic_title && <span>· {x.topic_title}</span>}
    </div>
  )
}

function QuestionField({ question: x }: { question: QuizQuestion }) {
  const id = useId()
  const choice = x.type === 'mcq' || x.type === 'true_false'
  return (
    <li className="grid gap-3">
      <QuestionHeader question={x} />
      {choice ? (
        <fieldset className="grid gap-2">
          <legend className="mb-2">
            <Markdown text={x.text} />
          </legend>
          {x.options.map((o, i) => (
            <label key={i} className="flex items-start gap-2 rounded-lg border px-3 py-2 has-checked:border-primary">
              <input type="radio" name={x.id} value={String(i)} className="mt-1" />
              <Markdown text={o} inline />
            </label>
          ))}
        </fieldset>
      ) : (
        <div className="grid gap-2">
          <div id={`${id}q`}>
            <Markdown text={x.text} />
          </div>
          <Label htmlFor={`${id}a`} className="text-sm text-muted-foreground">
            {x.type === 'numerical' ? 'Final answer (a number)' : x.type === 'fill_blank' ? 'The missing word or phrase' : 'Your answer'}
          </Label>
          {x.type === 'numerical' || x.type === 'fill_blank' ? (
            <Input id={`${id}a`} name={x.id} aria-describedby={`${id}q`} inputMode={x.type === 'numerical' ? 'decimal' : undefined} className="max-w-sm" />
          ) : (
            <Textarea id={`${id}a`} name={x.id} aria-describedby={`${id}q`} rows={x.marks >= 5 ? 10 : 4} maxLength={20000} />
          )}
        </div>
      )}
    </li>
  )
}
