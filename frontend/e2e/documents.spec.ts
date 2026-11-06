import { expect, test } from './fixtures'

// Full stack: `docker compose -f infrastructure/docker-compose.yml up -d` (db, redis, minio, worker) plus a real
// embedding key in .env. The file is tiny, so this costs a few hundred embedding tokens.
test('upload → processed live by the worker → search with citation → open source → delete', async ({ page }) => {
  test.setTimeout(180_000)
  const workspace = `E2E docs ${Date.now()}`
  const marker = `zorblax${Date.now()}` // unique word: search can only match this upload
  const notes = `# Deadlocks\nA deadlock needs mutual exclusion, hold and wait, no preemption and circular wait. Marker ${marker}.\n\n# Paging\nPaging maps virtual pages to physical frames.\n`
  const file = { name: 'os-notes.md', mimeType: 'text/markdown', buffer: Buffer.from(notes) }

  await page.goto('/')
  await page.getByLabel('Name').fill(workspace)
  await page.getByRole('button', { name: 'Create workspace' }).click()
  await expect(page.getByRole('heading', { level: 1, name: workspace })).toBeVisible()

  await page.getByLabel('Upload files').setInputFiles(file)
  await page.getByRole('button', { name: 'Upload', exact: true }).click()
  const row = page.getByRole('listitem').filter({ hasText: 'os-notes.md' })
  // No polling in the UI: reaching the final "ready" row (Reprocess appears only when done) without a reload
  // means the SSE stream reported completion and the list refetched.
  await expect(row.getByRole('button', { name: 'Reprocess' }), 'is the worker container running?').toBeVisible({ timeout: 120_000 })
  await expect(row).toContainText(/MD · 1 KB · 1 passage(?!s)/) // tiny file → one chunk, singular label
  await expect(row.getByRole('alert')).toHaveCount(0) // not failed

  await page.getByLabel('Upload files').setInputFiles(file) // same content again → rejected by checksum
  await page.getByRole('button', { name: 'Upload', exact: true }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'already in the workspace' })).toBeVisible()

  await page.getByLabel('Search query').fill(`what conditions cause a deadlock ${marker}`)
  await page.getByRole('button', { name: 'Search' }).click()
  const results = page.locator('section', { has: page.getByRole('heading', { name: 'Search your materials' }) })
  const top = results.getByRole('listitem').first()
  await expect(top).toContainText('circular wait', { timeout: 60_000 })
  const citation = top.getByRole('link', { name: /os-notes\.md/ })

  const source = await page.request.get((await citation.getAttribute('href'))!) // follows the signed-URL redirect
  expect(source.status()).toBe(200)
  expect(await source.text()).toContain(marker)

  await row.getByRole('button', { name: 'Delete' }).click()
  await row.getByRole('button', { name: 'Confirm delete' }).click()
  await expect(page.getByText('No materials uploaded yet.')).toBeVisible()

  await page.getByRole('button', { name: 'Delete workspace' }).click()
  await page.getByRole('button', { name: 'Confirm delete' }).click()
  await expect(page).toHaveURL('/')
})
