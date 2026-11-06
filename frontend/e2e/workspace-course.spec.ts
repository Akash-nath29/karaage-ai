import { expect, test } from './fixtures'

test('create workspace → create, edit and open course → delete workspace', async ({ page }) => {
  const name = `E2E ${Date.now()}`
  const h1 = (text: string) => page.getByRole('heading', { level: 1, name: text })

  await page.goto('/')
  await page.getByLabel('Name').fill(name)
  await page.getByLabel('Description').fill('Created by Playwright')
  await page.getByRole('button', { name: 'Create workspace' }).click()
  await expect(h1(name)).toBeVisible()

  await page.getByLabel('Course title').fill('Database Systems')
  await page.getByLabel('Course code').fill('CS501')
  await page.getByRole('button', { name: 'Create course' }).click()
  await page.getByRole('link', { name: /Database Systems/ }).click()
  await expect(h1('Database Systems')).toBeVisible()
  await expect(page.getByText('CS501')).toBeVisible()

  await page.getByRole('button', { name: 'Edit' }).click()
  await page.getByLabel('Course title').fill('DBMS')
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(h1('DBMS')).toBeVisible()

  await page.reload() // persisted server-side, not just client state
  await expect(h1('DBMS')).toBeVisible()

  await page.getByRole('button', { name: 'Delete course' }).click()
  await page.getByRole('button', { name: 'Confirm delete' }).click()
  await expect(h1(name)).toBeVisible() // back on the workspace
  await expect(page.getByText('No courses in this workspace yet.')).toBeVisible()

  await page.getByRole('button', { name: 'Delete workspace' }).click()
  await page.getByRole('button', { name: 'Confirm delete' }).click()
  await expect(page).toHaveURL('/')
  await expect(page.getByText(name)).toHaveCount(0)
})

test('unknown workspace shows not-found without retry delay', async ({ page }) => {
  await page.goto('/workspaces/00000000-0000-0000-0000-000000000000')
  await expect(page.getByRole('alert')).toHaveText('Workspace not found', { timeout: 2000 })
})
