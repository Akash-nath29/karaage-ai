import { test as base, expect, type APIRequestContext, type Page } from '@playwright/test'

export { expect }
export const PASSWORD = 'playwright-password-1'
export const CSRF = { 'X-Requested-With': 'playwright' } // the app's CSRF guard (docs/decisions.md D25)
export const MAILPIT = 'http://127.0.0.1:8025/api/v1'

export const uniqueEmail = (who: string) =>
  `e2e-${who.toLowerCase().replace(/\W+/g, '-')}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@example.com`

/** Registers through the API; the page's context keeps the session cookies, so the page is signed in. */
export async function register(page: Page, name: string, email = uniqueEmail(name)) {
  const res = await page.request.post('/api/v1/auth/register', { headers: CSRF, data: { email, password: PASSWORD, display_name: name } })
  expect(res.ok(), await res.text()).toBeTruthy()
  return email
}

/** Deletes the signed-in account and the workspaces it owns (cleanup). */
export const deleteAccount = (page: Page) =>
  page.request.delete('/api/v1/users/me', { headers: CSRF, data: { password: PASSWORD } })

/** The first link in the newest email to `to`, waiting for it to arrive in Mailpit. */
export async function emailLink(request: APIRequestContext, to: string, path: string): Promise<string> {
  for (let i = 0; i < 40; i++) {
    const found = await (await request.get(`${MAILPIT}/search?query=${encodeURIComponent(`to:"${to}"`)}`)).json()
    for (const m of found.messages ?? []) {
      const text: string = (await (await request.get(`${MAILPIT}/message/${m.ID}`)).json()).Text
      const link = text.match(new RegExp(`https?://\\S+${path}\\S+`))?.[0]
      if (link) return link
    }
    await new Promise((r) => setTimeout(r, 250))
  }
  throw new Error(`no email with a ${path} link reached ${to} (is Mailpit running?)`)
}

/** Every test runs as a fresh account, removed afterwards with everything it owns. */
export const test = base.extend<{ account: string }>({
  account: [
    async ({ page }, use) => {
      await use(await register(page, 'E2E Student'))
      await deleteAccount(page)
    },
    { auto: true },
  ],
})
