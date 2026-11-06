import { expect, test } from './fixtures'

// Full stack with real Gemini + Tavily: worker container running, GEMINI_API_KEY and TAVILY_API_KEY in .env.
// Costs: a few small LLM calls and ~4 Tavily searches.
test('syllabus: upload → parse → edit draft → confirm → topic → web research', async ({ page }) => {
  test.setTimeout(480_000)
  const workspace = `E2E syllabus ${Date.now()}`
  const syllabus = `# Operating Systems (CS301)

## Unit 1: Process Management (10 hours)
Processes and threads. CPU scheduling: FCFS, SJF and Round Robin.

## Unit 2: Deadlocks (6 hours)
Deadlock conditions, prevention, avoidance with the Banker's algorithm, detection and recovery.

Textbook: Silberschatz, Galvin and Gagne, Operating System Concepts.
`

  await page.goto('/')
  await page.getByLabel('Name').fill(workspace)
  await page.getByRole('button', { name: 'Create workspace' }).click()
  await page.getByLabel('Course title').fill('Operating Systems')
  await page.getByLabel('Course code').fill('CS301')
  await page.getByRole('button', { name: 'Create course' }).click()
  await page.getByRole('link', { name: /Operating Systems/ }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Operating Systems' })).toBeVisible()

  // Upload the syllabus as course material of type Syllabus
  await page.getByLabel('Upload files').setInputFiles({ name: 'os-syllabus.md', mimeType: 'text/markdown', buffer: Buffer.from(syllabus) })
  await page.getByLabel('Type').selectOption('syllabus')
  await page.getByRole('button', { name: 'Upload', exact: true }).click()

  // Parse it (worker + LLM), review the draft
  await expect(page.getByLabel('Syllabus document')).toBeVisible()
  await page.getByRole('button', { name: 'Parse syllabus' }).click()
  await expect(page.getByText(/^Draft from/), 'is the worker running with the new code?').toBeVisible({ timeout: 180_000 })
  await expect(page.getByLabel('Unit 2 title')).toHaveValue(/Deadlock/i)
  await expect(page.getByLabel('Unit 1 lecture hours')).toHaveValue('10')

  // Edit: add a topic to unit 2, then confirm
  const unit2 = page.getByRole('group', { name: 'Unit 2' })
  await unit2.getByRole('button', { name: 'Topic', exact: true }).click()
  await unit2.getByLabel(/^Unit 2, topic \d+$/).last().fill('Thrashing')
  await page.getByRole('button', { name: 'Confirm structure' }).click()

  await expect(page.getByRole('heading', { name: /^Unit 2: .*Deadlock/i })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(/\d+ topics · \d+% have study materials/)).toBeVisible()
  // Confirming queued the lesson batch (Phase 4). This test is about research: stop what hasn't started.
  await page.getByRole('button', { name: 'Cancel queued lessons' }).click()
  const thrashingRow = page.getByRole('link', { name: 'Thrashing', exact: true }).locator('xpath=ancestor::li[1]')
  await thrashingRow.getByRole('link', { name: /topic details/ }).click()

  // Topic page → research (worker + LLM + Tavily)
  await expect(page.getByRole('heading', { level: 1, name: 'Thrashing' })).toBeVisible()
  // A lesson the worker had already started may have run this topic's research itself.
  await page.getByRole('button', { name: /^(Research this topic|Search again)$/ }).click()
  await expect(page.getByRole('heading', { name: /^Sources \(\d+\)$/ })).toBeVisible({ timeout: 240_000 })
  const firstSource = page.getByRole('link').filter({ hasText: /\S/ }).and(page.locator('a[rel~="nofollow"]')).first()
  await expect(firstSource).toHaveAttribute('href', /^https?:\/\//)
  await expect(firstSource).toHaveAttribute('rel', 'noopener noreferrer nofollow')
  await expect(page.getByText(/^Searched: /)).toBeVisible()

  // Reload: research is stored and reused, not re-run
  await page.reload()
  await expect(page.getByRole('heading', { name: /^Sources \(\d+\)$/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Search again' })).toBeEnabled()

  // Clean up
  await page.getByRole('link', { name: '← Operating Systems' }).click()
  await page.getByRole('link', { name: '← Back to workspace' }).click()
  await page.getByRole('button', { name: 'Delete workspace' }).click()
  await page.getByRole('button', { name: 'Confirm delete' }).click()
  await expect(page).toHaveURL('/')
})
