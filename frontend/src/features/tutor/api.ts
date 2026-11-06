import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Citation } from '@/features/lessons/api'
import { api, ApiError, apiFetch, send } from '@/lib/api'

export type Mode = 'learn' | 'doubt' | 'socratic' | 'exam' | 'revision'

export const MODES: { value: Mode; label: string; hint: string }[] = [
  { value: 'doubt', label: 'Doubt', hint: 'Direct answers with sources' },
  { value: 'learn', label: 'Learn', hint: 'Step by step, checks your understanding' },
  { value: 'socratic', label: 'Socratic', hint: 'Guides you with questions instead of answers' },
  { value: 'exam', label: 'Exam', hint: '2-, 5- and 10-mark answers, numericals' },
  { value: 'revision', label: 'Revision', hint: 'Notes, definitions, flashcards' },
]

export type TutorSession = {
  id: string
  workspace_id: string
  course_id: string | null
  topic_id: string | null
  lesson_id: string | null
  mode: Mode
  title: string
  created_at: string
  updated_at: string
  course_title: string | null
  topic_title: string | null
}

export type TutorCitation = Omit<Citation, 'available' | 'heading_path'> & { heading_path?: string | null }

export type TutorMessage = {
  id: string
  role: 'user' | 'assistant'
  mode: Mode
  content: string
  citations: TutorCitation[]
  suggestions: string[]
  status: 'complete' | 'interrupted' | 'error'
  model: string | null
  created_at: string
}

export type SessionContext = { workspace_id?: string; course_id?: string; topic_id?: string; lesson_id?: string; mode?: Mode }

export const useSession = (sessionId: string) =>
  useQuery({ queryKey: ['tutor-session', sessionId], queryFn: () => api<TutorSession>(`/tutor/sessions/${sessionId}`) })

export const useSessions = (workspaceId: string | undefined, filter: { course_id?: string; topic_id?: string } = {}) =>
  useQuery({
    queryKey: ['tutor-sessions', workspaceId, filter],
    queryFn: () =>
      api<TutorSession[]>(`/tutor/sessions?${new URLSearchParams({ workspace_id: workspaceId!, ...filter })}`),
    enabled: !!workspaceId,
  })

export const useMessages = (sessionId: string | null) =>
  useQuery({
    queryKey: ['tutor-messages', sessionId],
    queryFn: () => api<TutorMessage[]>(`/tutor/sessions/${sessionId}/messages`),
    enabled: !!sessionId,
  })

export const useCreateSession = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (context: SessionContext) => api<TutorSession>('/tutor/sessions', send('POST', context)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tutor-sessions'] }),
  })
}

export const useDeleteSession = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: string) => api<void>(`/tutor/sessions/${sessionId}`, send('DELETE')),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tutor-sessions'], refetchType: 'none' }),
  })
}

export type StreamHandlers = {
  onStatus: (message: string) => void
  onToken: (text: string) => void
  onError: (detail: string) => void
  onDone: (message: TutorMessage) => void
}

/** POST a question and read the answer's Server-Sent Events (EventSource can't POST). Errors before the stream
 * opens (budget, validation) are thrown as ApiError; errors during it arrive as an `error` event. */
export async function askTutor(
  sessionId: string,
  body: { content: string; mode: Mode; web: boolean },
  handlers: StreamHandlers,
  signal: AbortSignal,
) {
  const res = await apiFetch(`/tutor/sessions/${sessionId}/messages`, {
    ...send('POST', body),
    headers: { 'Content-Type': 'application/json' },
    signal,
  })
  if (!res.ok || !res.body) {
    const detail = (await res.json().catch(() => null))?.detail
    throw new ApiError(res.status, typeof detail === 'string' ? detail : (detail?.[0]?.msg ?? res.statusText))
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    buffer += value
    let end
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const lines = buffer.slice(0, end).split('\n')
      buffer = buffer.slice(end + 2)
      const event = lines.find((l) => l.startsWith('event: '))?.slice(7)
      const data = JSON.parse(lines.find((l) => l.startsWith('data: '))?.slice(6) ?? 'null')
      if (event === 'status') handlers.onStatus(data.message)
      else if (event === 'token') handlers.onToken(data.text)
      else if (event === 'error') handlers.onError(data.detail)
      else if (event === 'done') handlers.onDone(data.message)
    }
  }
}

/** Tutor citations as lesson citations, so the same link component renders them. */
export const asCitation = (c: TutorCitation): Citation => ({ heading_path: null, ...c, available: true })
