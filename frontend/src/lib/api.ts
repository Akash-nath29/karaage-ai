export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Retrying a 4xx can't succeed; it only delays the error (React Query retries 3× with backoff).
export const shouldRetry = (failures: number, error: Error) =>
  !(error instanceof ApiError && error.status < 500) && failures < 3

// Every state-changing request carries a custom header: other sites can't add one to a cross-site request,
// which is what makes cookie sign-in safe from CSRF (docs/decisions.md D25).
export const CSRF = { 'X-Requested-With': 'semsaviour' }

let refreshing: Promise<boolean> | null = null

/** New access cookie from the refresh cookie. Concurrent callers share one request. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= fetch('/api/v1/auth/refresh', { method: 'POST', headers: CSRF })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => (refreshing = null))
  return refreshing
}

export const SIGNED_OUT = 'semsaviour:signed-out'

/** fetch() for the API: on 401, refresh the session once and retry (another tab may have refreshed already, so
 * retry either way); if it's still 401, the session is over and the app goes to the sign-in page. */
export async function apiFetch(path: string, init?: RequestInit, retried = false): Promise<Response> {
  const res = await fetch(`/api/v1${path}`, { ...init, headers: { ...CSRF, ...init?.headers } })
  if (res.status !== 401 || path.startsWith('/auth/')) return res
  if (!retried) {
    await refreshSession()
    return apiFetch(path, init, true)
  }
  window.dispatchEvent(new Event(SIGNED_OUT))
  return res
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  // JSON bodies are sent as strings; FormData (uploads) must let the browser set its multipart boundary.
  const json = typeof init?.body === 'string' ? { 'Content-Type': 'application/json' } : undefined
  const res = await apiFetch(path, { ...init, headers: { ...json, ...init?.headers } })
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail
    // FastAPI sends a string for HTTP errors and a list of issues for 422 validation errors.
    throw new ApiError(res.status, typeof detail === 'string' ? detail : (detail?.[0]?.msg ?? res.statusText))
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

export const send = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
})

/** The roles a workspace member can have, lowest first (PRD §4.2). */
export const ROLES = ['viewer', 'editor', 'admin', 'owner'] as const
export type Role = (typeof ROLES)[number]
export const atLeast = (role: Role | undefined, min: Role) => !!role && ROLES.indexOf(role) >= ROLES.indexOf(min)
