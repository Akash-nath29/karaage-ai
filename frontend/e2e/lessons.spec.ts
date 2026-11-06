import { expect, test } from './fixtures'

// Full stack with real Gemini (+ Tavily only if the notes don't cover a topic): worker container running with the
// current code, keys in .env. Generates two small lessons and one extension, so it takes a few minutes.
test('confirm syllabus → batch writes lessons → read with diagrams, math, citations → extend → feedback', async ({ page }) => {
  test.setTimeout(900_000)
  const problems: string[] = []
  page.on('pageerror', (e) => problems.push(e.message))
  // Event-stream diagnostics, printed if the extension step times out
  const network: string[] = []
  const at = () => new Date().toISOString().slice(11, 19)
  page.on('request', (r) => r.url().includes('/events') && network.push(`${at()} open ${r.url()}`))
  page.on('requestfinished', (r) => r.url().includes('/events') && network.push(`${at()} done ${r.url()}`))
  page.on('requestfailed', (r) => r.url().includes('/events') && network.push(`${at()} failed ${r.url()} ${r.failure()?.errorText}`))

  const workspace = `E2E lessons ${Date.now()}`
  const syllabus = `# Operating Systems (CS302)

## Unit 1: Deadlocks (6 hours)
Deadlock conditions and the Banker's algorithm for deadlock avoidance.
Paging and page tables.
`
  const notes = `# Deadlocks

A deadlock is a set of processes each waiting for a resource held by another. Four conditions must hold at once:
mutual exclusion, hold and wait, no preemption, and circular wait. Breaking any one prevents deadlock.

The Banker's algorithm avoids deadlock: before granting a request it checks that the resulting state is safe, meaning
some order exists in which every process can finish. With n processes and m resource types it takes O(m n^2) time.

# Paging

Paging splits memory into fixed-size frames and processes into pages of the same size. A page table maps each page
number to a frame number. A logical address is a page number p and an offset d; the physical address is f * size + d.
`
  await page.goto('/')
  await page.getByLabel('Name').fill(workspace)
  await page.getByRole('button', { name: 'Create workspace' }).click()
  await page.getByLabel('Course title').fill('Operating Systems')
  await page.getByLabel('Course code').fill('CS302')
  await page.getByRole('button', { name: 'Create course' }).click()
  await page.getByRole('link', { name: /Operating Systems/ }).click()

  // Notes and syllabus as course materials
  await expect(page.getByRole('heading', { level: 1, name: 'Operating Systems' })).toBeVisible()
  const upload = async (name: string, content: string, kind: string) => {
    const input = page.getByLabel('Upload files')
    await input.setInputFiles({ name, mimeType: 'text/markdown', buffer: Buffer.from(content) })
    await expect(input).toHaveJSProperty('files.length', 1) // selection survived any re-render
    await page.getByLabel('Type').selectOption(kind)
    await page.getByRole('button', { name: 'Upload', exact: true }).click()
    const row = page.getByRole('listitem').filter({ hasText: name })
    await expect(row.getByRole('button', { name: 'Reprocess' }), 'is the worker running?').toBeVisible({ timeout: 180_000 })
  }
  await upload('os-notes.md', notes, 'notes')
  await upload('os-syllabus.md', syllabus, 'syllabus')

  // Parse → the draft shows what confirming will cost (Q3) → confirm starts the batch
  await page.getByLabel('Syllabus document').selectOption({ label: 'os-syllabus.md (syllabus)' })
  await page.getByRole('button', { name: 'Parse syllabus' }).click()
  await expect(page.getByText(/^Confirming starts writing \d+ lessons/)).toBeVisible({ timeout: 240_000 })
  await page.getByRole('button', { name: 'Confirm structure' }).click()
  await expect(page.getByText(/Writing lessons: \d+ of \d+ ready/)).toBeVisible({ timeout: 30_000 })

  // The structure view polls while the batch runs; wait for a lesson, open it
  const ready = page.getByText('Lesson ready').first()
  await expect(ready).toBeVisible({ timeout: 600_000 })
  const lessonLink = ready.locator('xpath=ancestor::li[1]').getByRole('link').first() // the badge's own topic row
  await lessonLink.click()

  // Learning page
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('heading', { name: "You'll be able to" })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Sections in this lesson' }).getByRole('link')).not.toHaveCount(0)
  await expect(page.getByText(/^(From your materials|From the web|AI-written explanation)/).first()).toBeVisible()
  const diagrams = page.locator('figure')
  if (await diagrams.count()) await expect(diagrams.first().locator('svg')).toBeVisible({ timeout: 30_000 }) // Mermaid rendered
  await expect(page.locator('[role="alert"]', { hasText: "couldn't be drawn" })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Sources', exact: true })).toBeVisible() // cites the notes and/or the web
  await expect(page.getByLabel('Version', { exact: true })).toHaveValue('1')

  // On-demand extension (PRD F1 mode 2) → version 2 with one more section
  const sectionsBefore = await page.locator('article section[id^="s"]').count()
  await page.getByLabel(/Need more\?/).fill('one more short worked example')
  await page.getByRole('button', { name: 'Add to lesson' }).click()
  await expect(page.getByLabel('Version', { exact: true })).toHaveValue('2', { timeout: 120_000 }).catch((e) => {
    console.log(network.join(' | '))
    throw e
  })
  await expect(page.locator('article section[id^="s"]')).toHaveCount(sectionsBefore + 1)

  // Older versions stay readable
  await page.getByLabel('Version', { exact: true }).selectOption('1')
  await expect(page.getByText("You're reading an older version.")).toBeVisible()
  await page.getByRole('button', { name: 'Go to the latest' }).click()

  // Feedback
  await page.getByRole('button', { name: 'Helpful', exact: true }).click()
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText('Thanks for the feedback.')).toBeVisible()

  // Tutor panel beside the lesson (Phase 5): the conversation starts with the first question
  const panel = page.getByRole('region', { name: 'Ask the tutor about this lesson' })
  await panel.getByLabel('Your question').fill('Explain the safe state in one sentence.')
  await panel.getByRole('button', { name: 'Ask', exact: true }).click()
  await expect(panel.getByRole('list', { name: 'Conversation' }).getByText('Tutor:')).toHaveCount(1, { timeout: 120_000 })
  await expect(panel.getByRole('link', { name: 'Open as a full conversation' })).toBeVisible()
  expect(problems, 'page errors').toEqual([])

  // Clean up: stop anything still queued, delete the workspace
  await page.getByRole('link', { name: 'Operating Systems' }).first().click()
  const cancel = page.getByRole('button', { name: 'Cancel queued lessons' })
  if (await cancel.isVisible()) await cancel.click()
  await page.getByRole('link', { name: '← Back to workspace' }).click()
  await page.getByRole('button', { name: 'Delete workspace' }).click()
  await page.getByRole('button', { name: 'Confirm delete' }).click()
  await expect(page).toHaveURL('/')
})
