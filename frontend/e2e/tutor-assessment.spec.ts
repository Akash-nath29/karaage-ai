import { readFileSync } from 'node:fs'

import { type Page } from '@playwright/test'

import { CSRF, expect, test } from './fixtures'

// Workflows 5 and 6 on the full stack with real Gemini (worker running with the current code, keys in .env).
// The course structure is set through the API (the syllabus flow has its own spec) so no lesson batch starts.
// About six fast-tier AI calls: paper extraction, quiz writing, answer marking, two tutor answers.
const API = 'http://127.0.0.1:8000/api/v1'
const PAPER = readFileSync('../backend/tests/benchmark/SYNTHETIC_os_question_paper.pdf')
const NOTES = `# Deadlocks

A deadlock is a set of processes each waiting for a resource held by another process in the set. Four conditions
must hold at the same time: mutual exclusion, hold and wait, no preemption, and circular wait. Breaking any one of
them prevents deadlock. The Banker's algorithm avoids deadlock by granting a request only if the resulting state is
safe, meaning some order exists in which every process can finish.
`

async function upload(page: Page, name: string, buffer: Buffer, mimeType: string, kind: string) {
  const input = page.getByLabel('Upload files')
  await input.setInputFiles({ name, mimeType, buffer })
  await expect(input).toHaveJSProperty('files.length', 1)
  await page.getByLabel('Type').selectOption(kind)
  await page.getByRole('button', { name: 'Upload', exact: true }).click()
  const row = page.getByRole('listitem').filter({ hasText: name })
  await expect(row.getByRole('button', { name: 'Reprocess' }), 'is the worker running?').toBeVisible({ timeout: 180_000 })
}

test('paper → review → topic quiz → marked results → progress → tutor with citations and history', async ({ page }) => {
  test.setTimeout(900_000)
  const problems: string[] = []
  page.on('pageerror', (e) => problems.push(e.message))

  await page.goto('/')
  await page.getByLabel('Name').fill(`E2E practice ${Date.now()}`)
  await page.getByRole('button', { name: 'Create workspace' }).click()
  await page.getByLabel('Course title').fill('Operating System')
  await page.getByLabel('Course code').fill('AM401')
  await page.getByRole('button', { name: 'Create course' }).click()
  await page.getByRole('link', { name: /Operating System/ }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Operating System' })).toBeVisible()
  const courseId = page.url().split('/').pop()!

  const res = await page.request.put(`${API}/courses/${courseId}/structure`, {
    headers: CSRF, // signed in through the page's cookies
    data: {
      units: [
        { title: 'Processes, Threads and CPU Scheduling', topics: [{ title: 'CPU Scheduling' }, { title: 'Threads' }] },
        {
          title: 'Process Synchronization and Deadlocks',
          topics: [
            { title: 'Process Synchronization', subtopics: [{ title: 'Semaphores' }, { title: 'Monitors' }] },
            { title: 'Deadlocks', subtopics: [{ title: 'Deadlock characterization' }, { title: 'Deadlock avoidance' }] },
          ],
        },
        { title: 'Memory Management', topics: [{ title: 'Virtual Memory', subtopics: [{ title: 'Page replacement algorithms' }] }] },
      ],
    },
  })
  expect(res.ok()).toBeTruthy()
  const structure = await res.json()
  const deadlocks = structure.units[1].topics[1].id as string
  await page.reload()

  await upload(page, 'os-notes.md', Buffer.from(NOTES), 'text/markdown', 'notes')
  await upload(page, 'SYNTHETIC_os_paper.pdf', PAPER, 'application/pdf', 'question_paper')

  // H3: the paper's questions were extracted on their own; review one draft and approve it
  await page.getByRole('link', { name: /Question bank/ }).click()
  await expect(page.getByText(/^\d+ questions · \d+ to review$/)).toBeVisible({ timeout: 240_000 })
  const card = page.getByRole('listitem').filter({ hasText: 'NOT a necessary condition for deadlock' })
  await expect(card.getByText('Draft')).toBeVisible()
  await expect(card.getByText(/Deadlocks/)).toBeVisible() // mapped to its syllabus topic
  await card.getByRole('button', { name: 'Edit' }).click()
  const key = page.getByLabel('Correct answer')
  await key.selectOption((await key.locator('option', { hasText: 'Preemption' }).getAttribute('value'))!)
  await page.getByRole('button', { name: 'Save' }).click()
  await card.getByRole('button', { name: 'Approve' }).click()
  await expect(card.getByText('Approved')).toBeVisible()

  // H4: a topic quiz uses the approved question and writes the rest
  await page.goto(`/topics/${deadlocks}`)
  await page.getByRole('button', { name: 'Quiz me (5 questions)' }).click()
  await expect(page.getByRole('button', { name: 'Submit answers' })).toBeVisible({ timeout: 240_000 })
  await expect(page.getByText('NOT a necessary condition for deadlock').first()).toBeVisible()
  const form = page.locator('form').filter({ has: page.getByRole('button', { name: 'Submit answers' }) })
  for (const group of await form.locator('fieldset').all()) await group.getByRole('radio').first().check() // "Mutual exclusion": wrong
  for (const box of await form.locator('textarea').all())
    await box.fill('Deadlock needs mutual exclusion, hold and wait, no preemption and circular wait; avoid it with the Banker’s algorithm.')
  for (const box of await form.locator('input:not([type=radio])').all()) await box.fill('4')
  await page.getByRole('button', { name: 'Submit answers' }).click()

  // H5: objective answers marked at once, written ones by the AI (an estimate)
  await expect(page.getByRole('heading', { name: 'Results' })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('Marking…')).toHaveCount(0, { timeout: 240_000 })
  const approved = page.getByRole('listitem').filter({ hasText: 'NOT a necessary condition for deadlock' })
  await expect(approved.getByText('Incorrect')).toBeVisible()
  await expect(approved.getByText('Preemption').last()).toBeVisible() // reference answer
  if (await page.getByText('AI estimate').count()) await expect(page.getByText('Estimated', { exact: true })).toBeVisible()

  // H6: progress updated from the quiz; mark the topic studied
  await page.getByRole('link', { name: 'See your progress' }).click()
  const row = page.getByRole('row').filter({ hasText: 'Deadlocks' })
  await expect(row.getByRole('cell').nth(2)).toHaveText(/^\d+%$/)
  await row.getByRole('button', { name: 'Mark Deadlocks as studied' }).click()
  await expect(row.getByRole('button', { name: 'Unmark Deadlocks as studied' })).toHaveAttribute('aria-pressed', 'true')

  // Workflow 5: tutor on the topic, streamed answer with citations, follow-up in another mode, history kept
  await page.goto(`/topics/${deadlocks}`)
  await page.getByRole('button', { name: 'Ask the tutor' }).click()
  await expect(page.getByRole('heading', { name: 'AI tutor' })).toBeVisible()
  await page.getByLabel('Your question').fill('What are the four conditions for a deadlock?')
  await page.getByRole('button', { name: 'Ask', exact: true }).click()
  const conversation = page.getByRole('list', { name: 'Conversation' })
  await expect(conversation.getByText('Sources', { exact: true })).toBeVisible({ timeout: 120_000 })
  await expect(conversation.getByRole('link', { name: 'os-notes.md' }).first()).toBeVisible()
  await page.getByLabel('Mode').selectOption('socratic')
  await page.getByLabel('Your question').fill('How could I prevent the circular wait condition?')
  await page.getByRole('button', { name: 'Ask', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Ask', exact: true })).toBeVisible({ timeout: 120_000 }) // answer finished
  await expect(conversation.getByText('Tutor:')).toHaveCount(2)
  await page.reload()
  await expect(page.getByRole('list', { name: 'Conversation' }).getByText('Tutor:')).toHaveCount(2)
  await expect(page.getByRole('navigation', { name: 'Conversations' }).getByRole('link', { name: 'What are the four conditions for a deadlock?' })).toBeVisible()
  expect(problems, 'page errors').toEqual([])

  // Clean up
  await page.goto(`/courses/${courseId}`)
  await page.getByRole('link', { name: '← Back to workspace' }).click()
  await page.getByRole('button', { name: 'Delete workspace' }).click()
  await page.getByRole('button', { name: 'Confirm delete' }).click()
  await expect(page).toHaveURL('/')
})
