import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { depthLabel, useWorkspaceLessons } from '@/features/lessons/api'
import { useWorkspaceUsage } from '@/features/workspaces/api'

/** Shared learning resources (Phase 6): every lesson you can read in this workspace, newest first. */
export function SharedLessons({ workspaceId }: { workspaceId: string }) {
  const lessons = useWorkspaceLessons(workspaceId)
  if (!lessons.data?.length) return null
  return (
    <section className="grid gap-3" aria-labelledby="shared-lessons">
      <h2 id="shared-lessons" className="text-lg font-medium">Lessons</h2>
      <ul className="divide-y rounded-xl border">
        {lessons.data.slice(0, 12).map((l) => (
          <li key={l.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5 text-sm">
            <Link to={`/lessons/${l.id}`} className="font-medium hover:underline">{l.topic_title}</Link>
            <span className="text-muted-foreground">{depthLabel(l.depth)} · {l.course_title}</span>
            {l.visibility === 'private' && <Badge variant="outline">Private</Badge>}
          </li>
        ))}
      </ul>
      {lessons.data.length > 12 && (
        <p className="text-sm text-muted-foreground">And {lessons.data.length - 12} more on the course pages.</p>
      )}
    </section>
  )
}

const OPERATION: Record<string, string> = {
  lesson_generate: 'Lessons', lesson_enrich: 'Lesson additions', lesson_math_fix: 'Formula fixes', tutor_answer: 'Tutor',
  syllabus_extract: 'Syllabus parsing', syllabus_locate: 'Syllabus parsing', research_plan: 'Research', research_verify: 'Research',
  question_extract: 'Question extraction', quiz_generate: 'Quizzes', answer_grade: 'Marking', web_search: 'Web searches',
}

/** This month's AI usage against the workspace budget (A18, §12); per member for admins (D30). */
export function UsagePanel({ workspaceId }: { workspaceId: string }) {
  const usage = useWorkspaceUsage(workspaceId)
  const u = usage.data
  if (!u) return null
  const share = u.token_budget ? Math.min(1, u.tokens / u.token_budget) : 0
  const chat = u.by_operation.filter((o) => !o.operation.startsWith('embed') && o.operation !== 'web_search')
  return (
    <section className="grid gap-3" aria-labelledby="usage-heading">
      <h2 id="usage-heading" className="text-lg font-medium">AI usage this month</h2>
      <p className="text-sm">
        {u.tokens.toLocaleString()}{u.token_budget ? ` of ${u.token_budget.toLocaleString()}` : ''} tokens ·{' '}
        {u.searches}{u.search_budget ? ` of ${u.search_budget}` : ''} web searches
      </p>
      {u.token_budget > 0 && (
        <div className="h-1.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label="Workspace budget used"
             aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(share * 100)}>
          <div className={share > 0.9 ? 'h-full bg-destructive' : 'h-full bg-primary'} style={{ width: `${share * 100}%` }} />
        </div>
      )}
      <details className="text-sm">
        <summary className="cursor-pointer text-muted-foreground">Details</summary>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          <ul className="grid gap-0.5">
            {chat.map((o) => (
              <li key={o.operation}>
                {OPERATION[o.operation] ?? o.operation}: {o.tokens.toLocaleString()} tokens ({o.calls} calls)
              </li>
            ))}
            <li className="text-muted-foreground">Indexing documents: {u.embedding_tokens.toLocaleString()} tokens (not budgeted)</li>
          </ul>
          {u.by_member && (
            <ul className="grid gap-0.5">
              {u.by_member.map((m) => (
                <li key={m.user_id ?? 'system'}>
                  {m.name}: {m.tokens.toLocaleString()} tokens{m.searches ? `, ${m.searches} searches` : ''}
                </li>
              ))}
            </ul>
          )}
        </div>
      </details>
    </section>
  )
}
