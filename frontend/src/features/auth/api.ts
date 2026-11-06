import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import { api, send } from '@/lib/api'

export type User = {
  id: string
  email: string
  display_name: string
  avatar_url: string | null
  preferred_language: string
  academic_level: string
  learning_preferences: string
  email_verified: boolean
  created_at: string
}
export type Person = Pick<User, 'id' | 'email' | 'display_name' | 'avatar_url'>

export const useMe = () =>
  useQuery({ queryKey: ['me'], queryFn: () => api<User>('/users/me'), retry: false, staleTime: 60_000 })

/** After signing in, out or as someone else: drop the previous account's cached data, and update "me" in place.
 * (Not queryClient.clear(): components already showing "me" wouldn't hear about the change.) */
export async function switchAccount(qc: QueryClient, user?: User) {
  qc.removeQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
  if (user) qc.setQueryData(['me'], user)
  else await qc.resetQueries({ queryKey: ['me'] })
}

function useSessionChange<In>(fn: (input: In) => Promise<User | void>) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: (user) => switchAccount(qc, user ?? undefined) })
}

export const useLogin = () =>
  useSessionChange((body: { email: string; password: string }) => api<User>('/auth/login', send('POST', body)))

export const useRegister = () =>
  useSessionChange((body: { email: string; password: string; display_name: string }) =>
    api<User>('/auth/register', send('POST', body)),
  )

export const useLogout = () => useSessionChange(() => api<void>('/auth/logout', send('POST')))

export const useDeleteAccount = () =>
  useSessionChange((password: string) => api<void>('/users/me', send('DELETE', { password })))

function useMeMutation<In>(fn: (input: In) => Promise<User>) {
  const qc = useQueryClient()
  return useMutation({ mutationFn: fn, onSuccess: (user) => qc.setQueryData(['me'], user) })
}

export const useUpdateProfile = () =>
  useMeMutation((body: Partial<Pick<User, 'display_name' | 'preferred_language' | 'academic_level' | 'learning_preferences'>>) =>
    api<User>('/users/me', send('PATCH', body)),
  )

export const useSetAvatar = () =>
  useMeMutation((file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api<User>('/users/me/avatar', { method: 'PUT', body: form })
  })

export const useRemoveAvatar = () => useMeMutation(() => api<User>('/users/me/avatar', send('DELETE')))

export const useResendVerification = () =>
  useMutation({ mutationFn: () => api<void>('/auth/resend-verification', send('POST')) })

/** Only same-site paths: `?next=https://evil.example` must not become a redirect. */
export const safeNext = (next: string | null) => (next?.startsWith('/') && !next.startsWith('//') ? next : '/')
