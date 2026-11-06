import { CSRF, deleteAccount, emailLink, expect, PASSWORD, register, test, uniqueEmail } from './fixtures'

// Workflows 1 (onboarding) and 7 (tenant isolation) with two people in two browsers. No AI calls.
test('register and confirm email → workspace and course → invite → join → roles and privacy', async ({ browser, request }) => {
  const alice = await (await browser.newContext()).newPage()
  const bob = await (await browser.newContext()).newPage()
  const aliceEmail = uniqueEmail('alice')
  const bobEmail = uniqueEmail('bob')
  const workspace = `Study group ${Date.now()}`
  try {
    // Workflow 1.1: a student registers (signed-out visitors land on sign-in).
    await alice.goto('/')
    await expect(alice).toHaveURL(/\/login/)
    await alice.getByRole('link', { name: 'Create an account' }).click()
    await alice.getByLabel('Your name').fill('Alice Rao')
    await alice.getByLabel('Email').fill(aliceEmail)
    await alice.getByLabel('Password').fill(PASSWORD)
    await alice.getByRole('button', { name: 'Create account' }).click()
    await expect(alice.getByRole('heading', { level: 1, name: 'Welcome back, Alice' })).toBeVisible()
    await expect(alice.getByText('Confirm your email address')).toBeVisible()
    await alice.goto(await emailLink(request, aliceEmail, '/verify-email'))
    await expect(alice.getByText('Your email address is confirmed.')).toBeVisible()

    // 1.2–1.3: creates a workspace and a course; a private conversation lives there too.
    await alice.goto('/')
    await expect(alice.getByText('Confirm your email address')).toHaveCount(0)
    await alice.getByLabel('Name').fill(workspace)
    await alice.getByRole('button', { name: 'Create workspace' }).click()
    await expect(alice.getByRole('heading', { level: 1, name: workspace })).toBeVisible()
    const workspaceUrl = alice.url()
    await alice.getByLabel('Course title').fill('Operating Systems')
    await alice.getByRole('button', { name: 'Create course' }).click()
    await alice.getByRole('link', { name: /Operating Systems/ }).click()
    const courseId = alice.url().split('/').pop()!
    const talk = await alice.request.post('/api/v1/tutor/sessions', { headers: CSRF, data: { course_id: courseId } })
    const sessionId = (await talk.json()).id

    // Workflow 7.1–7.3: someone else can't reach any of it.
    await register(bob, 'Bob', bobEmail)
    await bob.goto(workspaceUrl)
    await expect(bob.getByRole('alert')).toHaveText('Workspace not found')
    await bob.goto(`/courses/${courseId}`)
    await expect(bob.getByRole('alert')).toHaveText('Course not found')

    // 1.4 / 7.4: Alice invites with a link (viewer).
    await alice.goto(workspaceUrl)
    await alice.getByRole('button', { name: 'Invite', exact: true }).click()
    const link = await alice.getByLabel('Invitation link').inputValue()
    expect(link).toContain('/invite/')

    // 1.5: Bob opens it and joins.
    await bob.goto(link.replace(/^https?:\/\/[^/]+/, ''))
    await expect(bob.getByRole('heading', { name: `Join “${workspace}”` })).toBeVisible()
    await expect(bob.getByText('Alice Rao invited you to join as viewer.')).toBeVisible()
    await bob.getByRole('button', { name: 'Join workspace' }).click()
    await expect(bob.getByRole('heading', { level: 1, name: workspace })).toBeVisible()

    // 1.6 / 7.5: shared resources yes, only what a viewer may do.
    await expect(bob.getByText('Your role: viewer')).toBeVisible()
    await expect(bob.getByRole('link', { name: /Operating Systems/ })).toBeVisible()
    await expect(bob.getByRole('button', { name: 'Create course' })).toHaveCount(0)
    await expect(bob.getByRole('button', { name: 'Delete workspace' })).toHaveCount(0)
    await expect(bob.getByLabel('Upload files')).toHaveCount(0)
    await bob.getByRole('link', { name: /Operating Systems/ }).click()
    await expect(bob.getByRole('heading', { level: 1, name: 'Operating Systems' })).toBeVisible()
    await expect(bob.getByRole('button', { name: 'Edit', exact: true })).toHaveCount(0)
    const forbidden = await bob.request.patch(`/api/v1/courses/${courseId}`, { headers: CSRF, data: { title: 'Mine' } })
    expect(forbidden.status()).toBe(403) // the server enforces it, not only the UI

    // 7.6: still no access to Alice's private conversation.
    await bob.goto(`/tutor/${sessionId}`)
    await expect(bob.getByRole('alert')).toHaveText('Tutor session not found')

    // Alice sees Bob join, makes him an editor; his page now offers uploads.
    await alice.reload()
    await alice.getByLabel('Role of Bob').selectOption('editor')
    await expect(alice.getByRole('listitem').filter({ hasText: /changed .* from viewer to editor/ })).toBeVisible()
    await bob.goto(workspaceUrl)
    await expect(bob.getByText('Your role: editor')).toBeVisible()
    await expect(bob.getByLabel('Upload files')).toBeVisible()

    // Signing out ends the session.
    await bob.getByRole('button', { name: 'Sign out' }).click()
    await expect(bob).toHaveURL(/\/login/)
    await bob.goto(workspaceUrl)
    await expect(bob).toHaveURL(/\/login\?next=/)
  } finally {
    for (const [page, email] of [[alice, aliceEmail], [bob, bobEmail]] as const) {
      await page.request.post('/api/v1/auth/login', { headers: CSRF, data: { email, password: PASSWORD } })
      await deleteAccount(page) // Alice's workspace goes with her account
      await page.context().close()
    }
  }
})
