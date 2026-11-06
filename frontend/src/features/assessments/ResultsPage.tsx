import { Link, useParams } from 'react-router'

import { JobProgress } from '@/components/job-progress'
import { Markdown } from '@/components/lesson-blocks/markdown'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useRegrade, useResults, type AnswerResult } from '@/features/assessments/api'
import { QuestionHeader } from '@/features/assessments/QuizPage'
import { useJobProgress } from '@/lib/jobs'

/** Evaluation and feedback for one attempt (Screen 6, Workflow 6). */
export function ResultsPage() {
  const { attemptId = '' } = useParams()
  const results = useResults(attemptId)
  const regrade = useRegrade(attemptId)
  const attempt = results.data?.attempt
  const progress = useJobProgress(attempt?.job_id ?? null, attempt?.status === 'grading', ['attempt', attemptId])

  if (results.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (results.error) return <p role="alert" className="text-destructive">{results.error.message}</p>
  const r = results.data
  const a = r.attempt
  const estimated = r.answers.some((x) => x.graded_by === 'ai')

  return (
    <div className="grid gap-8">
      <header className="grid gap-3">
        <Link to={`/quizzes/${r.quiz_id}`} className="text-sm text-muted-foreground hover:underline">
          ← {r.quiz_title}
        </Link>
        <h1 className="text-2xl font-semibold">Results</h1>
        {a.status === 'graded' && (
          <div className="flex flex-wrap items-baseline gap-3">
            <p className="text-4xl font-semibold tabular-nums">
              {a.score} <span className="text-xl text-muted-foreground">/ {a.max_score}</span>
            </p>
            {estimated && <Badge variant="secondary">Estimated</Badge>}
          </div>
        )}
        {estimated && a.status === 'graded' && (
          <p className="max-w-prose text-sm text-muted-foreground">
            Written answers were marked by the AI against each question's rubric. Treat those marks as an estimate of how
            an examiner might grade them, not as an official university grade.
          </p>
        )}
        {a.status === 'grading' && <JobProgress event={progress} label="Marking written answers" />}
        {a.status === 'failed' && (
          <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-destructive">
            <p>Marking failed: {a.error}</p>
            <Button size="sm" variant="outline" disabled={regrade.isPending} onClick={() => regrade.mutate()}>
              Grade again
            </Button>
          </div>
        )}
        <Link to={`/courses/${r.course_id}/progress`} className="text-sm underline-offset-2 hover:underline">
          See your progress
        </Link>
      </header>

      <ol className="grid gap-8">
        {r.answers.map((x) => (
          <AnswerCard key={x.question.id} result={x} />
        ))}
      </ol>
    </div>
  )
}

function AnswerCard({ result: x }: { result: AnswerResult }) {
  const f = x.feedback
  const choice = x.question.type === 'mcq' || x.question.type === 'true_false'
  const given = choice && x.answer !== '' ? x.question.options[Number(x.answer)] : x.answer
  return (
    <li className="grid gap-3 border-b pb-8">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <QuestionHeader question={x.question} />
        <p className="text-sm font-medium tabular-nums">
          {x.score === null ? 'Marking…' : `${x.score} / ${x.max_score}`}
          {x.correct === true && <Badge className="ml-2">Correct</Badge>}
          {x.correct === false && <Badge variant="destructive" className="ml-2">Incorrect</Badge>}
          {x.graded_by === 'ai' && <Badge variant="secondary" className="ml-2">AI estimate</Badge>}
        </p>
      </div>
      <Markdown text={x.question.text} />
      <div className="grid gap-1">
        <h3 className="text-sm font-medium text-muted-foreground">Your answer</h3>
        {given ? <p className="whitespace-pre-wrap">{given}</p> : <p className="text-sm text-muted-foreground italic">No answer</p>}
      </div>

      {f.criteria && (
        <table className="w-full max-w-lg text-sm">
          <caption className="mb-1 text-left text-sm font-medium text-muted-foreground">Rubric</caption>
          <thead className="sr-only">
            <tr>
              <th>Criterion</th>
              <th>Marks</th>
            </tr>
          </thead>
          <tbody>
            {f.criteria.map((c) => (
              <tr key={c.criterion} className="border-t">
                <td className="py-1 pr-4">{c.criterion}</td>
                <td className="py-1 text-right tabular-nums">
                  {c.awarded} / {c.marks}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <FeedbackList title="What you got right" items={f.correct_concepts} />
      <FeedbackList title="Missing" items={f.missing_concepts} />
      <FeedbackList title="Incorrect statements" items={f.incorrect_statements} />
      <FeedbackList title="To improve" items={f.suggestions} />

      {x.reference_answer && (
        <details open={x.correct === false || (x.score !== null && x.score < x.max_score)}>
          <summary className="cursor-pointer text-sm font-medium">Reference answer</summary>
          <div className="mt-2 rounded-xl bg-muted/50 px-4 py-3">
            <Markdown text={x.reference_answer} />
            {x.explanation && <Markdown text={x.explanation} className="mt-2 text-sm text-muted-foreground" />}
          </div>
        </details>
      )}
    </li>
  )
}

function FeedbackList({ title, items }: { title: string; items?: string[] }) {
  if (!items?.length) return null
  return (
    <div className="grid gap-1">
      <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
      <ul className="grid list-disc gap-0.5 pl-5 text-sm">
        {items.map((i) => (
          <li key={i}>{i}</li>
        ))}
      </ul>
    </div>
  )
}
