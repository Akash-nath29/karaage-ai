import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, send } from '@/lib/api'

export type ClaimStatus = 'verified' | 'unverified' | 'disputed'
export type Claim = { claim: string; status: ClaimStatus; sources: string[]; materials: string[]; contradicting: string[] }

export type Research = {
  id: string
  topic_id: string
  job_id: string | null
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  error: string | null
  sufficient: boolean | null
  covered: string[]
  missing: string[]
  queries: string[]
  claims: Claim[]
  source_count: number
  model: string | null
  created_at: string
  finished_at: string | null
}

export type Source = {
  id: string
  url: string
  title: string
  domain: string
  source_type: string
  quality: number
  relevance: number
  content_kind: 'page' | 'snippet'
  passages: string[]
  verification_status: ClaimStatus
}

export const SOURCE_TYPE: Record<string, string> = {
  academic: 'Academic',
  official_docs: 'Official docs',
  encyclopedia: 'Encyclopedia',
  educational: 'Educational site',
  forum: 'Forum',
  blog: 'Blog',
  user_uploads: 'User uploads',
  web: 'Website',
}

export const useLatestResearch = (topicId: string) =>
  useQuery({ queryKey: ['research', topicId], queryFn: () => api<Research | null>(`/topics/${topicId}/research`) })

export const useSources = (researchId: string | undefined) =>
  useQuery({
    queryKey: ['research-sources', researchId],
    queryFn: () => api<Source[]>(`/research/${researchId}/sources`),
    enabled: !!researchId,
  })

export const useStartResearch = (topicId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (refresh: boolean) => api<Research>(`/topics/${topicId}/research`, send('POST', { refresh })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['research', topicId] }),
  })
}
