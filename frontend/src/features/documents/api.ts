import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, send } from '@/lib/api'

export const KINDS = [
  ['notes', 'Notes'],
  ['textbook', 'Textbook'],
  ['syllabus', 'Syllabus'],
  ['question_paper', 'Question paper'],
  ['other', 'Other'],
] as const
export type DocumentKind = (typeof KINDS)[number][0]

export type Document = {
  id: string
  workspace_id: string
  course_id: string | null
  kind: DocumentKind
  filename: string
  file_type: string
  size_bytes: number
  status: 'queued' | 'processing' | 'ready' | 'failed'
  error: string | null
  page_count: number | null
  chunk_count: number
  job_id: string | null
  uploaded_by: string | null
  created_at: string
}

export type Passage = {
  chunk_id: string
  document_id: string
  filename: string
  page_start: number | null
  page_end: number | null
  heading_path: string
  content: string
  score: number
}

export const ACCEPT = '.pdf,.docx,.pptx,.txt,.md,.markdown,.png,.jpg,.jpeg'

export const useDocuments = (workspaceId: string, courseId?: string) =>
  useQuery({
    queryKey: ['documents', { workspaceId, courseId }],
    queryFn: () => api<Document[]>(`/workspaces/${workspaceId}/documents${courseId ? `?course_id=${courseId}` : ''}`),
  })

// Unlike workspace/course deletes, a document is deleted while its list stays on screen: always refetch.
function useDocumentMutation<In, Out>(fn: (input: In) => Promise<Out>) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }) })
}

export const useUploadDocument = (workspaceId: string) =>
  useDocumentMutation(({ file, kind, courseId }: { file: File; kind: DocumentKind; courseId?: string }) => {
    const form = new FormData()
    form.append('file', file)
    form.append('kind', kind)
    if (courseId) form.append('course_id', courseId)
    return api<Document>(`/workspaces/${workspaceId}/documents`, { method: 'POST', body: form })
  })

export const useUpdateDocument = () =>
  useDocumentMutation(({ id, ...body }: { id: string; course_id?: string | null; kind?: DocumentKind }) =>
    api<Document>(`/documents/${id}`, send('PATCH', body)),
  )

export const useReprocessDocument = () =>
  useDocumentMutation((id: string) => api<Document>(`/documents/${id}/reprocess`, send('POST')))

export const useDeleteDocument = () =>
  useDocumentMutation((id: string) => api<void>(`/documents/${id}`, send('DELETE')))

export const useSearch = (workspaceId: string) =>
  useMutation({
    mutationFn: (body: { query: string; course_id?: string }) =>
      api<Passage[]>(`/workspaces/${workspaceId}/search`, send('POST', body)),
  })

export const fileUrl = (id: string, page?: number | null) => `/api/v1/documents/${id}/file${page ? `#page=${page}` : ''}`

export const formatSize = (bytes: number) =>
  bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`
