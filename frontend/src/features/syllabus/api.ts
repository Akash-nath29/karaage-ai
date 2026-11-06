import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Passage } from '@/features/documents/api'
import { api, send } from '@/lib/api'

// Structure tree sent to the API. Nodes with an id update that unit/topic (so renames keep lessons/progress).
export type SubtopicNode = { id?: string | null; title: string }
export type TopicNode = { id?: string | null; title: string; subtopics: SubtopicNode[] }
export type UnitNode = { id?: string | null; title: string; hours: number | null; topics: TopicNode[] }
export type Structure = { units: UnitNode[] }
export type SyllabusDraft = Structure & {
  subject_name: string
  subject_code: string
  exam_structure: string
  references: string[]
}

export type Syllabus = {
  id: string
  course_id: string
  document_id: string | null
  status: 'parsing' | 'draft' | 'confirmed' | 'failed'
  job_id: string | null
  error: string | null
  page_start: number | null
  page_end: number | null
  draft: SyllabusDraft | null
  confirmed: SyllabusDraft | null
  model: string | null
  confirmed_at: string | null
  generation_estimate: { lessons: number; ai_calls: number; tokens: number; web_searches_max: number } | null
}

export type TopicStatus = 'not_started' | 'materials_available' | 'generation_pending' | 'lesson_available'
export type TopicOut = {
  id: string
  title: string
  status: TopicStatus
  material_count: number
  lesson_id: string | null
  lesson_status: string | null
  subtopics: { id: string; title: string }[]
}
export type UnitOut = { id: string; title: string; hours: number | null; coverage: number; topics: TopicOut[] }
export type StructureOut = { units: UnitOut[]; topic_count: number; coverage: number; lessons_ready: number; lessons_pending: number }

export type TopicDetail = {
  id: string
  title: string
  parent_id: string | null
  course_id: string
  course_title: string
  workspace_id: string
  unit_id: string
  unit_title: string
  status: TopicStatus
  material_count: number
  subtopics: { id: string; title: string }[]
  materials: Passage[]
}

export const STATUS_LABEL: Record<TopicStatus, string> = {
  not_started: 'Not started',
  materials_available: 'Materials available',
  generation_pending: 'Lesson in progress',
  lesson_available: 'Lesson ready',
}

export const useSyllabus = (courseId: string) =>
  useQuery({ queryKey: ['syllabus', courseId], queryFn: () => api<Syllabus | null>(`/courses/${courseId}/syllabus`) })

export const useStructure = (courseId: string) =>
  useQuery({
    queryKey: ['structure', courseId],
    queryFn: () => api<StructureOut>(`/courses/${courseId}/units`),
    // ponytail: polls every 5 s while a lesson batch runs; one query beats an SSE stream per lesson
    refetchInterval: (query) => (query.state.data?.lessons_pending ? 5000 : false),
  })

export const useTopic = (topicId: string) =>
  useQuery({ queryKey: ['topic', topicId], queryFn: () => api<TopicDetail>(`/topics/${topicId}`) })

function useCourseMutation<In, Out>(courseId: string, fn: (input: In) => Promise<Out>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['syllabus', courseId] }),
        qc.invalidateQueries({ queryKey: ['structure', courseId] }),
      ])
    },
  })
}

export const useLinkSyllabus = (courseId: string) =>
  useCourseMutation(courseId, (documentId: string) =>
    api<Syllabus>(`/courses/${courseId}/syllabus`, send('POST', { document_id: documentId })),
  )

export const useReparse = (courseId: string) =>
  useCourseMutation(courseId, () => api<Syllabus>(`/courses/${courseId}/syllabus/parse`, send('POST')))

export const useSaveDraft = (courseId: string) =>
  useCourseMutation(courseId, (draft: SyllabusDraft) =>
    api<Syllabus>(`/courses/${courseId}/syllabus/draft`, send('PUT', draft)),
  )

export const useConfirm = (courseId: string) =>
  useCourseMutation(courseId, () => api<StructureOut>(`/courses/${courseId}/syllabus/confirm`, send('POST')))

export const useSaveStructure = (courseId: string) =>
  useCourseMutation(courseId, (structure: Structure) =>
    api<StructureOut>(`/courses/${courseId}/structure`, send('PUT', structure)),
  )

/** The read model (with statuses) as an editable tree, ids kept. */
export const toStructure = (s: StructureOut): Structure => ({
  units: s.units.map((u) => ({
    id: u.id,
    title: u.title,
    hours: u.hours,
    topics: u.topics.map((t) => ({ id: t.id, title: t.title, subtopics: t.subtopics.map((st) => ({ ...st })) })),
  })),
})
