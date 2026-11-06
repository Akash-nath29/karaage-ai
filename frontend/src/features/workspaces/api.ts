import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { Person } from '@/features/auth/api'
import { api, send, type Role } from '@/lib/api'

export type Workspace = { id: string; name: string; description: string; created_at: string; role: Role }
export type WorkspaceInput = { name: string; description: string }
export type Member = { user: Person; role: Role; joined_at: string }
export type InviteRole = Exclude<Role, 'owner'>
export type Invitation = {
  id: string
  email: string | null
  role: InviteRole
  expires_at: string
  max_uses: number | null
  uses: number
  created_at: string
}
export type InvitationCreated = Invitation & { url: string; emailed: boolean }
export type AuditEntry = { action: string; actor: string | null; target: string; details: Record<string, unknown>; created_at: string }
export type WorkspaceUsage = {
  month_start: string
  tokens: number
  token_budget: number
  searches: number
  search_budget: number
  embedding_tokens: number
  by_operation: { operation: string; calls: number; tokens: number }[]
  by_member: { user_id: string | null; name: string; tokens: number; searches: number }[] | null
}

export const useWorkspaces = () =>
  useQuery({ queryKey: ['workspaces'], queryFn: () => api<Workspace[]>('/workspaces') })

export const useWorkspace = (id: string | undefined) =>
  useQuery({ queryKey: ['workspaces', id], queryFn: () => api<Workspace>(`/workspaces/${id}`), enabled: !!id })

/** Your role in a workspace (the server enforces it; the UI only hides what you can't do). */
export const useRole = (workspaceId: string | undefined) => useWorkspace(workspaceId).data?.role

// Deletes pass refetchType 'none': mark caches stale without refetching the just-deleted
// item while its page is still mounted (that refetch 404s and would hold the mutation pending).
function useWorkspaceMutation<In, Out>(fn: (input: In) => Promise<Out>, refetchType: 'active' | 'none' = 'active') {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: ['workspaces'], refetchType }) })
}

export const useCreateWorkspace = () =>
  useWorkspaceMutation((body: WorkspaceInput) => api<Workspace>('/workspaces', send('POST', body)))

export const useUpdateWorkspace = (id: string) =>
  useWorkspaceMutation((body: Partial<WorkspaceInput>) => api<Workspace>(`/workspaces/${id}`, send('PATCH', body)))

export const useDeleteWorkspace = (id: string) =>
  useWorkspaceMutation(() => api<void>(`/workspaces/${id}`, send('DELETE')), 'none')

export const workspaceFields = [
  { name: 'name', label: 'Name', required: true },
  { name: 'description', label: 'Description', multiline: true },
]

// --- Members and invitations (B3, A11–A12) --------------------------------------------------------------------

export const useMembers = (id: string) =>
  useQuery({ queryKey: ['workspaces', id, 'members'], queryFn: () => api<Member[]>(`/workspaces/${id}/members`) })

export const useInvitations = (id: string, enabled: boolean) =>
  useQuery({
    queryKey: ['workspaces', id, 'invitations'],
    queryFn: () => api<Invitation[]>(`/workspaces/${id}/invitations`),
    enabled,
  })

export const useAudit = (id: string, enabled: boolean) =>
  useQuery({ queryKey: ['workspaces', id, 'audit'], queryFn: () => api<AuditEntry[]>(`/workspaces/${id}/audit`), enabled })

export const useChangeRole = (id: string) =>
  useWorkspaceMutation(({ userId, role }: { userId: string; role: InviteRole }) =>
    api<Member>(`/workspaces/${id}/members/${userId}`, send('PATCH', { role })),
  )

export const useRemoveMember = (id: string) =>
  useWorkspaceMutation((userId: string) => api<void>(`/workspaces/${id}/members/${userId}`, send('DELETE')))

export const useInvite = (id: string) =>
  useWorkspaceMutation((body: { email: string | null; role: InviteRole; max_uses?: number | null }) =>
    api<InvitationCreated>(`/workspaces/${id}/invitations`, send('POST', body)),
  )

export const useRevokeInvitation = (id: string) =>
  useWorkspaceMutation((invitationId: string) => api<void>(`/workspaces/${id}/invitations/${invitationId}`, send('DELETE')))

export const useWorkspaceUsage = (id: string) =>
  useQuery({ queryKey: ['workspaces', id, 'usage'], queryFn: () => api<WorkspaceUsage>(`/workspaces/${id}/usage`) })
