import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, send } from '@/lib/api'

// --- Lesson document (schema 1.0, backend/app/modules/lessons/document.py) ---------------------------------------

type Cited = { citations: string[] }
export type Block = Cited &
  (
    | { type: 'paragraph'; markdown: string }
    | { type: 'heading'; text: string }
    | { type: 'concept'; term: string; markdown: string }
    | { type: 'diagram'; kind: string; caption: string; renderer: 'mermaid'; source: string }
    | { type: 'table'; caption: string; headers: string[]; rows: string[][] }
    | { type: 'comparison'; caption: string; items: string[]; rows: { aspect: string; values: string[] }[] }
    | { type: 'formula'; latex: string; explanation: string }
    | { type: 'code'; language: string; code: string; explanation: string }
    | { type: 'example'; title: string; problem: string; solution: string }
    | { type: 'callout'; variant: 'note' | 'tip' | 'warning' | 'exam'; markdown: string }
    | { type: 'steps'; title: string; steps: string[] }
    | { type: 'quiz'; questions: { question: string; options: string[]; answer: number; explanation: string }[] }
    | { type: 'flashcards'; cards: { front: string; back: string }[] }
    | { type: 'summary'; points: string[] }
  )

export type Section = { id: string; role: string; title: string; blocks: Block[] }
export type LessonDocument = {
  schema_version: string
  title: string
  topic_id: string
  depth: string
  estimated_minutes: number
  learning_objectives: string[]
  prerequisites: string[]
  sections: Section[]
}

export type Citation = {
  label: string
  kind: 'material' | 'web'
  document_id: string | null
  filename: string | null
  page_start: number | null
  page_end: number | null
  heading_path: string | null
  url: string | null
  title: string | null
  domain: string | null
  quote: string
  available: boolean
}

export type LessonStatus = 'queued' | 'generating' | 'ready' | 'failed' | 'cancelled'
export type Visibility = 'workspace' | 'private'
export type Lesson = {
  id: string
  topic_id: string
  course_id: string
  depth: string
  visibility: Visibility // D28: shared with the workspace, or only its owner's
  owner_id: string | null
  status: LessonStatus
  job_id: string | null
  error: string | null
  current_version: number
  outdated_reason: string | null
  created_at: string
}

export type VersionMeta = {
  version: number
  kind: 'generated' | 'enriched'
  model: string
  prompt_version: string
  warnings: string[]
  input_tokens: number
  output_tokens: number
  created_at: string
}

export type LessonDetail = {
  lesson: Lesson
  workspace_id: string
  course_id: string
  course_title: string
  unit_title: string
  topic_title: string
  version: VersionMeta
  document: LessonDocument
  citations: Citation[]
}

export const DEPTHS: [string, string][] = [
  ['detailed', 'Detailed academic explanation'],
  ['conceptual', 'Conceptual understanding'],
  ['beginner', 'Beginner-friendly'],
  ['exam', 'Exam-oriented'],
  ['revision', 'Quick revision'],
  ['advanced', 'Advanced exploration'],
]
export const depthLabel = (depth: string) => DEPTHS.find(([d]) => d === depth)?.[1] ?? depth
export const isBusy = (l: Pick<Lesson, 'status'>) => l.status === 'queued' || l.status === 'generating'

export function citationLabel(c: Citation) {
  if (c.kind === 'web') return c.domain ?? 'web'
  const pages = c.page_start ? (c.page_start === c.page_end ? `p. ${c.page_start}` : `pp. ${c.page_start}–${c.page_end}`) : ''
  return [c.filename, pages].filter(Boolean).join(', ')
}

// --- Queries and mutations -----------------------------------------------------------------------------------------

export const useLesson = (lessonId: string, version?: number) =>
  useQuery({
    queryKey: ['lesson', lessonId, version ?? 'current'],
    queryFn: () => api<LessonDetail>(`/lessons/${lessonId}${version ? `?version=${version}` : ''}`),
    placeholderData: keepPreviousData, // switching versions keeps the page instead of flashing "Loading"
  })

export const useVersions = (lessonId: string) =>
  useQuery({ queryKey: ['lesson', lessonId, 'versions'], queryFn: () => api<VersionMeta[]>(`/lessons/${lessonId}/versions`) })

export const useTopicLessons = (topicId: string) =>
  useQuery({ queryKey: ['topic-lessons', topicId], queryFn: () => api<Lesson[]>(`/topics/${topicId}/lessons`) })

function useLessonMutation<In, Out>(fn: (input: In) => Promise<Out>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: async () => {
      await Promise.all(['lesson', 'topic-lessons', 'structure', 'topic'].map((k) => qc.invalidateQueries({ queryKey: [k] })))
    },
  })
}

export const useGenerateLesson = (topicId: string) =>
  useLessonMutation(({ depth, visibility }: { depth: string; visibility?: Visibility }) =>
    api<Lesson>(`/topics/${topicId}/lessons/generate`, send('POST', { depth, visibility })),
  )

export const usePublish = (lessonId: string) =>
  useLessonMutation(() => api<Lesson>(`/lessons/${lessonId}/publish`, send('POST')))

export type LessonListItem = Lesson & { course_title: string; topic_title: string; updated_at: string | null }

/** Lessons you can read across a workspace: shared ones and your private ones. */
export const useWorkspaceLessons = (workspaceId: string) =>
  useQuery({ queryKey: ['topic-lessons', 'workspace', workspaceId], queryFn: () => api<LessonListItem[]>(`/workspaces/${workspaceId}/lessons`) })

export const useRegenerate = (lessonId: string) =>
  useLessonMutation(() => api<Lesson>(`/lessons/${lessonId}/regenerate`, send('POST')))

export const useEnrich = (lessonId: string) =>
  useLessonMutation((request: string) => api<Lesson>(`/lessons/${lessonId}/enrich`, send('POST', { request })))

export const useFeedback = (lessonId: string) =>
  useMutation({
    mutationFn: (body: { rating: 1 | -1; comment: string }) => api<void>(`/lessons/${lessonId}/feedback`, send('POST', body)),
  })

export const useCancelBatch = (courseId: string) =>
  useLessonMutation(() => api<{ count: number }>(`/courses/${courseId}/lessons/cancel`, send('POST')))

export const useGenerateMissing = (courseId: string) =>
  useLessonMutation(() => api<{ count: number }>(`/courses/${courseId}/lessons/generate`, send('POST')))

export type PinnedDocument = { id: string; filename: string; kind: string }

export const usePins = (topicId: string) =>
  useQuery({ queryKey: ['pins', topicId], queryFn: () => api<PinnedDocument[]>(`/topics/${topicId}/documents`) })

export const useSetPins = (topicId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (documentIds: string[]) =>
      api<PinnedDocument[]>(`/topics/${topicId}/documents`, send('PUT', { document_ids: documentIds })),
    onSuccess: (data) => qc.setQueryData(['pins', topicId], data),
  })
}
