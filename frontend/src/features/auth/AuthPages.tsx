import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, type ReactNode } from 'react'
import { Link, Navigate, useLocation, useNavigate, useParams, useSearchParams } from 'react-router'

import { SimpleForm } from '@/components/simple-form'
import { Button } from '@/components/ui/button'
import { safeNext, switchAccount, useLogin, useMe, useRegister, type User } from '@/features/auth/api'
import type { Workspace } from '@/features/workspaces/api'
import { api, ApiError, refreshSession, send, SIGNED_OUT } from '@/lib/api'

const REFRESH_EVERY_MS = 10 * 60_000 // access cookies last 15 minutes: refresh well before

/** Pages behind sign-in. Keeps the session fresh while open; on sign-out (or an expired session) goes to the
 * sign-in page and comes back afterwards. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe()
  const location = useLocation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const here = location.pathname + location.search
  const toLogin = `/login?next=${encodeURIComponent(here)}`

  useEffect(() => {
    const timer = setInterval(refreshSession, REFRESH_EVERY_MS)
    const signedOut = () => {
      navigate(toLogin)
      void switchAccount(qc)
    }
    window.addEventListener(SIGNED_OUT, signedOut)
    return () => {
      clearInterval(timer)
      window.removeEventListener(SIGNED_OUT, signedOut)
    }
  }, [qc, navigate, toLogin])

  if (me.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (me.error instanceof ApiError && me.error.status === 401) return <Navigate to={toLogin} replace />
  if (me.error) return <p role="alert" className="text-destructive">{me.error.message}</p>
  return children
}

function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mx-auto grid max-w-sm gap-6 py-8">
      <h1 className="text-2xl font-semibold">{title}</h1>
      {children}
    </div>
  )
}

const EMAIL = { name: 'email', label: 'Email', type: 'email', autoComplete: 'email', required: true } as const

export function LoginPage() {
  const [params] = useSearchParams()
  const login = useLogin()
  const navigate = useNavigate()
  const next = safeNext(params.get('next'))
  return (
    <AuthCard title="Sign in">
      <SimpleForm
        fields={[EMAIL, { name: 'password', label: 'Password', type: 'password', autoComplete: 'current-password', required: true }]}
        submitLabel="Sign in"
        pending={login.isPending}
        error={login.error}
        onSubmit={async (v) => {
          await login.mutateAsync({ email: v.email, password: v.password })
          navigate(next, { replace: true })
        }}
      />
      <div className="grid gap-1 text-sm">
        <Link className="underline" to={`/register?next=${encodeURIComponent(next)}`}>
          Create an account
        </Link>
        <Link className="text-muted-foreground underline" to="/forgot-password">
          Forgot your password?
        </Link>
      </div>
    </AuthCard>
  )
}

export function RegisterPage() {
  const [params] = useSearchParams()
  const register = useRegister()
  const navigate = useNavigate()
  const next = safeNext(params.get('next'))
  return (
    <AuthCard title="Create your account">
      <SimpleForm
        fields={[
          { name: 'display_name', label: 'Your name', autoComplete: 'name', required: true },
          EMAIL,
          { name: 'password', label: 'Password', type: 'password', autoComplete: 'new-password', required: true, minLength: 8,
            hint: 'At least 8 characters.' },
        ]}
        submitLabel="Create account"
        pending={register.isPending}
        error={register.error}
        onSubmit={async (v) => {
          await register.mutateAsync({ email: v.email, password: v.password, display_name: v.display_name })
          navigate(next, { replace: true })
        }}
      />
      <p className="text-sm">
        Already have an account?{' '}
        <Link className="underline" to={`/login?next=${encodeURIComponent(next)}`}>
          Sign in
        </Link>
      </p>
    </AuthCard>
  )
}

export function ForgotPasswordPage() {
  const forgot = useMutation({ mutationFn: (email: string) => api<void>('/auth/forgot-password', send('POST', { email })) })
  return (
    <AuthCard title="Reset your password">
      {forgot.isSuccess ? (
        <p role="status">If there's an account for that address, we've emailed it a link to choose a new password. The link works for 1 hour.</p>
      ) : (
        <SimpleForm fields={[EMAIL]} submitLabel="Email me a link" pending={forgot.isPending} error={forgot.error}
                    onSubmit={(v) => forgot.mutateAsync(v.email)} />
      )}
      <Link className="text-sm underline" to="/login">
        Back to sign in
      </Link>
    </AuthCard>
  )
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const reset = useMutation({
    mutationFn: (password: string) => api<void>('/auth/reset-password', send('POST', { token: params.get('token') ?? '', password })),
  })
  return (
    <AuthCard title="Choose a new password">
      {reset.isSuccess ? (
        <p role="status">
          Password changed. You've been signed out everywhere.{' '}
          <Link className="underline" to="/login">
            Sign in
          </Link>
        </p>
      ) : (
        <SimpleForm
          fields={[{ name: 'password', label: 'New password', type: 'password', autoComplete: 'new-password', required: true,
                     minLength: 8, hint: 'At least 8 characters.' }]}
          submitLabel="Change password"
          pending={reset.isPending}
          error={reset.error}
          onSubmit={(v) => reset.mutateAsync(v.password)}
        />
      )}
    </AuthCard>
  )
}

export function VerifyEmailPage() {
  const [params] = useSearchParams()
  const qc = useQueryClient()
  const verify = useMutation({
    mutationFn: () => api<void>('/auth/verify-email', send('POST', { token: params.get('token') ?? '' })),
    onSuccess: () => {
      // Drop the "confirm your email" banner now, not after the refetch's round trip; the refetch then confirms it.
      // Not returned: the mutation (and its "Confirming…") would wait for that refetch too.
      qc.setQueryData<User>(['me'], (u) => u && { ...u, email_verified: true })
      void qc.invalidateQueries({ queryKey: ['me'] })
    },
  })
  const sent = useRef(false)
  useEffect(() => {
    if (!sent.current) verify.mutate() // once, even under StrictMode's double effects: the link is single use
    sent.current = true
  }, [verify])
  return (
    <AuthCard title="Confirm your email">
      {verify.isPending && <p className="text-muted-foreground">Confirming…</p>}
      {verify.isSuccess && <p role="status">Your email address is confirmed.</p>}
      {verify.error && <p role="alert" className="text-destructive">{verify.error.message}</p>}
      <Link className="text-sm underline" to="/">
        Go to your dashboard
      </Link>
    </AuthCard>
  )
}

type Preview = { workspace_name: string; role: string; invited_by: string | null; email: string | null }

/** B3: what you're joining, then join (signing in or registering first, and coming back here). */
export function InvitePage() {
  const { token = '' } = useParams()
  const me = useMe()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const preview = useQuery({ queryKey: ['invitation', token], queryFn: () => api<Preview>(`/invitations/${token}`), retry: false })
  const accept = useMutation({
    mutationFn: () => api<Workspace>(`/invitations/${token}/accept`, send('POST')),
    onSuccess: (w) => {
      qc.invalidateQueries({ queryKey: ['workspaces'] })
      navigate(`/workspaces/${w.id}`)
    },
  })
  const here = encodeURIComponent(`/invite/${token}`)

  if (preview.isPending) return <p className="text-muted-foreground">Loading…</p>
  if (preview.error) return <AuthCard title="Invitation"><p role="alert" className="text-destructive">{preview.error.message}</p></AuthCard>
  const p = preview.data
  return (
    <AuthCard title={`Join “${p.workspace_name}”`}>
      <p>
        {p.invited_by ? `${p.invited_by} invited you` : "You're invited"} to join as <strong>{p.role}</strong>.
        {p.email && ` This invitation is for ${p.email}.`}
      </p>
      {me.data ? (
        <div className="grid gap-2">
          <p className="text-sm text-muted-foreground">Signed in as {me.data.email}.</p>
          <Button onClick={() => accept.mutate()} pending={accept.isPending}>
            Join workspace
          </Button>
          {accept.error && <p role="alert" className="text-sm text-destructive">{accept.error.message}</p>}
        </div>
      ) : me.isPending ? null : (
        <p className="flex gap-3 text-sm">
          <Link className="underline" to={`/login?next=${here}`}>Sign in to join</Link>
          <Link className="underline" to={`/register?next=${here}`}>Create an account</Link>
        </p>
      )}
    </AuthCard>
  )
}
