import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, send } from '@/lib/api'

export type QuestionType = 'mcq' | 'true_false' | 'fill_blank' | 'numerical' | 'short' | 'long' | 'descriptive'
export type Difficulty = 'easy' | 'medium' | 'hard'

export const TYPE_LABEL: Record<QuestionType, string> = {
  mcq: 'Multiple choice',
  true_false: 'True/false',
  fill_blank: 'Fill in the blank',
  numerical: 'Numerical',
  short: 'Short answer',
  long: 'Long answer',
  descriptive: 'Descriptive',
}
export const OBJECTIVE = new Set<string>(['mcq', 'true_false', 'fill_blank', 'numerical'])

export type Criterion = { criterion: string; marks: number }

export type Question = {
  id: string
  course_id: string
  topic_id: string | null
  text: string
  type: QuestionType
  marks: number
  difficulty: Difficulty
  options: string[]
  answer: string | null
  rubric: Criterion[]
  explanation: string
  source_kind: 'extracted' | 'generated' | 'manual'
  document_id: string | null
  source_page: number | null
  source_label: string
  status: 'draft' | 'approved'
  created_at: string
  topic_title: string | null
  unit_title: string | null
  filename: string | null
}

export type QuestionInput = {
  topic_id: string | null
  text: string
  type: QuestionType
  marks: number
  difficulty: Difficulty
  options: string[]
  answer: string | null
  rubric: Criterion[]
  explanation: string
  status?: 'draft' | 'approved'
}

export type Paper = {
  document_id: string
  filename: string
  document_status: string
  job_id: string | null
  status: 'none' | 'queued' | 'running' | 'succeeded' | 'failed'
  error: string | null
  questions: number
  drafts: number
}

export type QuizQuestion = {
  id: string
  position: number
  text: string
  type: QuestionType
  marks: number
  difficulty: Difficulty
  options: string[]
  topic_title: string | null
}

export type AttemptSummary = {
  id: string
  status: 'grading' | 'graded' | 'failed'
  score: number
  max_score: number
  job_id: string | null
  error: string | null
  created_at: string
  graded_at: string | null
}

export type Quiz = {
  id: string
  course_id: string
  title: string
  settings: { count: number; difficulty: Difficulty | null; marks: number | null; types: QuestionType[]; unit_id: string | null; topic_ids: string[] }
  status: 'generating' | 'ready' | 'failed'
  job_id: string | null
  error: string | null
  created_at: string
  questions: QuizQuestion[]
  attempts: AttemptSummary[]
}

export type QuizRequest = { count: number; difficulty?: Difficulty; marks?: number; types?: QuestionType[]; unit_id?: string; topic_ids?: string[] }

export type AiFeedback = {
  criteria?: (Criterion & { awarded: number })[]
  correct_concepts?: string[]
  missing_concepts?: string[]
  incorrect_statements?: string[]
  suggestions?: string[]
  note?: string
}

export type AnswerResult = {
  question: QuizQuestion
  answer: string
  score: number | null
  max_score: number
  graded_by: 'auto' | 'ai' | null
  correct: boolean | null
  feedback: AiFeedback
  reference_answer: string | null
  explanation: string
}

export type AttemptResults = { attempt: AttemptSummary; quiz_id: string; quiz_title: string; course_id: string; answers: AnswerResult[] }

// --- Question bank ------------------------------------------------------------------------------------------------

export const usePapers = (courseId: string) =>
  useQuery({ queryKey: ['papers', courseId], queryFn: () => api<Paper[]>(`/courses/${courseId}/question-papers`) })

/** Editors and above only: the bank holds answer keys (D32). */
export const useQuestions = (courseId: string, status?: string, enabled = true) =>
  useQuery({
    queryKey: ['questions', courseId, status ?? 'all'],
    queryFn: () => api<Question[]>(`/courses/${courseId}/questions${status ? `?status=${status}` : ''}`),
    enabled,
  })

function useBankMutation<In, Out>(fn: (input: In) => Promise<Out>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: async () => {
      await Promise.all(['questions', 'papers'].map((k) => qc.invalidateQueries({ queryKey: [k] })))
    },
  })
}

export const useExtract = () => useBankMutation((documentId: string) => api(`/documents/${documentId}/questions/extract`, send('POST')))
export const useCreateQuestion = (courseId: string) =>
  useBankMutation((q: QuestionInput) => api<Question>(`/courses/${courseId}/questions`, send('POST', q)))
export const useUpdateQuestion = () =>
  useBankMutation(({ id, ...patch }: Partial<QuestionInput> & { id: string }) => api<Question>(`/questions/${id}`, send('PATCH', patch)))
export const useDeleteQuestion = () => useBankMutation((id: string) => api<void>(`/questions/${id}`, send('DELETE')))

// --- Quizzes and attempts -----------------------------------------------------------------------------------------

export const useQuiz = (quizId: string) => useQuery({ queryKey: ['quiz', quizId], queryFn: () => api<Quiz>(`/quizzes/${quizId}`) })

export const useCourseQuizzes = (courseId: string) =>
  useQuery({ queryKey: ['quizzes', courseId], queryFn: () => api<Quiz[]>(`/courses/${courseId}/quizzes`) })

export const useCreateQuiz = (scope: { courseId?: string; topicId?: string }) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: QuizRequest) =>
      api<Quiz>(scope.topicId ? `/topics/${scope.topicId}/quizzes` : `/courses/${scope.courseId}/quizzes`, send('POST', body)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quizzes'] }),
  })
}

export const useDeleteQuiz = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (quizId: string) => api<void>(`/quizzes/${quizId}`, send('DELETE')),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['quizzes'] }),
  })
}

export const useSubmitAttempt = (quizId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (answers: { question_id: string; answer: string }[]) =>
      api<AttemptSummary>(`/quizzes/${quizId}/attempts`, send('POST', { answers })),
    onSuccess: () => Promise.all(['quiz', 'quizzes', 'progress'].map((k) => qc.invalidateQueries({ queryKey: [k] }))),
  })
}

export const useResults = (attemptId: string) =>
  useQuery({ queryKey: ['attempt', attemptId], queryFn: () => api<AttemptResults>(`/attempts/${attemptId}/results`) })

export const useRegrade = (attemptId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api<AttemptSummary>(`/attempts/${attemptId}/grade`, send('POST')),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['attempt', attemptId] }),
  })
}

// --- Progress (A14) -----------------------------------------------------------------------------------------------

export type ProgressStatus = 'not_started' | 'studied' | 'revision_required' | 'completed'
export const PROGRESS_LABEL: Record<ProgressStatus, string> = {
  not_started: 'Not started',
  studied: 'Studied',
  revision_required: 'Revise',
  completed: 'Completed',
}

export type TopicProgress = {
  topic_id: string
  title: string
  unit_id: string
  status: ProgressStatus
  studied_at: string | null
  questions_attempted: number
  questions_correct: number
  accuracy: number | null
  last_accuracy: number | null
  last_quiz_at: string | null
  revise_by: string | null
}

export type CourseProgress = {
  course_id: string
  topics: TopicProgress[]
  units: { unit_id: string; title: string; topics: number; completed: number; studied: number }[]
  completed: number
  studied: number
  revision_required: number
  questions_attempted: number
  accuracy: number | null
  weak_topics: string[]
  strong_topics: string[]
}

export const useProgress = (courseId: string | undefined) =>
  useQuery({
    queryKey: ['progress', courseId],
    queryFn: () => api<CourseProgress>(`/courses/${courseId}/progress`),
    enabled: !!courseId,
  })

export const useMarkStudied = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ topicId, studied }: { topicId: string; studied: boolean }) =>
      api<TopicProgress>(`/topics/${topicId}/progress`, send('PUT', { studied })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['progress'] }),
  })
}

export const percent = (share: number | null) => (share === null ? '–' : `${Math.round(share * 100)}%`)
