import { readFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, expect } from '@playwright/test'

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryDirectory = path.resolve(frontendDirectory, '..')
const credentialPath = path.join(repositoryDirectory, '.showroom', 'credentials.txt')
const outputDirectory = path.join(repositoryDirectory, 'docs', 'qa', 'screenshots', 'issue-34-gate-7')
const frontendUrl = process.env.AUTOSTOCK_FRONTEND_URL || 'http://127.0.0.1:5173'

function parseCredentials(contents) {
  const entries = new Map()
  for (const line of contents.split(/\r?\n/)) {
    const match = line.match(/^\s*([^:=]+?)\s*[:=]\s*(.*?)\s*$/)
    if (match) entries.set(match[1].toLowerCase().replace(/\s+/g, '_'), match[2])
  }
  const credentials = { login: entries.get('login'), password: entries.get('password') }
  if (Object.values(credentials).some((value) => !value)) {
    throw new Error('The local showroom credential file is incomplete; screenshot capture stopped.')
  }
  return credentials
}

const credentials = parseCredentials(await readFile(credentialPath, 'utf8'))
await mkdir(outputDirectory, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
  colorScheme: 'light',
})
const page = await context.newPage()
const pageErrors = []
const consoleErrors = []
const apiFailures = []
const captures = []
const payloads = new Map()

page.on('pageerror', (error) => pageErrors.push(error.message))
page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push(message.text())
})
page.on('response', async (response) => {
  const pathname = new URL(response.url()).pathname
  if (pathname.startsWith('/autostock/api/v1/') && response.status() >= 400) {
    apiFailures.push(`${pathname} returned ${response.status()}`)
  }
  if (pathname === '/autostock/api/v1/forecasts' && response.status() === 200) {
    payloads.set('list', await response.json())
  }
  if (/^\/autostock\/api\/v1\/forecasts\/\d+$/.test(pathname) && response.status() === 200) {
    payloads.set(pathname, await response.json())
  }
})

async function settleLayout() {
  await page.evaluate(async () => {
    await document.fonts.ready
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  })
}

async function capture(width, height, filename, fullPage = true) {
  await page.setViewportSize({ width, height })
  await settleLayout()
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
  if (scrollWidth > width) throw new Error(`Forecasts page overflows horizontally at ${width}px.`)
  await page.screenshot({ path: path.join(outputDirectory, filename), fullPage, animations: 'disabled' })
  captures.push(filename)
}

try {
  await page.goto(`${frontendUrl}/forecasts`, { waitUntil: 'domcontentloaded' })
  const loginHeading = page.getByRole('heading', { name: 'Welcome back' })
  const forecastsHeading = page.getByRole('heading', { name: 'Forecasts', exact: true })
  const firstScreen = await Promise.race([
    loginHeading.waitFor({ state: 'visible', timeout: 60_000 }).then(() => 'login'),
    forecastsHeading.waitFor({ state: 'visible', timeout: 60_000 }).then(() => 'forecasts'),
  ])
  if (firstScreen === 'login') {
    await page.getByLabel('Email or username').fill(credentials.login)
    await page.getByLabel('Password', { exact: true }).fill(credentials.password)
    await page.getByRole('button', { name: 'Continue' }).click()
  }

  await forecastsHeading.waitFor({ timeout: 60_000 })
  await expect(page.getByRole('heading', { name: 'Saved forecasts' })).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('Demo environment', { exact: true })).toBeVisible()
  await expect(page.getByText('Atlas Auto Distribution', { exact: false }).first()).toBeVisible()
  await expect.poll(() => payloads.has('list'), { timeout: 45_000 }).toBe(true)

  const list = payloads.get('list')
  if (list.company?.name !== 'Atlas Auto Distribution' || !Array.isArray(list.runs)) {
    throw new Error('The live Forecasts API did not return the Atlas Auto Distribution company and run list.')
  }
  if (list.read_only !== true || !Number.isSafeInteger(list.pagination?.total_count)) {
    throw new Error('The live Forecasts response did not include read-only state and an exact numeric total.')
  }

  await capture(1440, 1000, 'forecasts-overview-1440.png')
  await capture(1024, 900, 'forecasts-overview-1024.png')
  await capture(390, 844, 'forecasts-overview-390.png')

  const selectedRun = list.runs.find((run) => run.source_type === 'completed_deliveries' && run.state === 'completed')
    ?? list.runs.find((run) => run.source_type === 'completed_deliveries')
    ?? list.runs[0]
  if (selectedRun) {
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.locator('.forecast-table-part').filter({ hasText: selectedRun.sku }).first().click()
    await expect(page.getByRole('heading', { name: selectedRun.product_name, exact: true })).toBeVisible({ timeout: 45_000 })
    const detailKey = `/autostock/api/v1/forecasts/${selectedRun.id}`
    await expect.poll(() => payloads.has(detailKey), { timeout: 45_000 }).toBe(true)
    const detail = payloads.get(detailKey)
    if (detail.run?.id !== selectedRun.id || detail.read_only !== true) {
      throw new Error('The detail response did not match the selected saved forecast run.')
    }
    if (selectedRun.state === 'completed') {
      await expect(page.getByRole('heading', { name: 'Delivered history and forecast' })).toBeVisible()
      await expect(page.getByText('Forecast starts', { exact: true })).toBeVisible()
    }
    await capture(1440, 1000, 'forecast-detail-1440.png')
    await capture(1024, 900, 'forecast-detail-1024.png')
    await capture(390, 844, 'forecast-detail-390.png')
    console.log(`Captured a live ${selectedRun.source_type} forecast detail (run ${selectedRun.id}, state ${selectedRun.state}).`)
  } else {
    console.log('The Atlas showroom returned no saved forecast runs; overview screenshots show the real empty state.')
  }

  if (pageErrors.length || consoleErrors.length || apiFailures.length) {
    throw new Error(JSON.stringify({ pageErrors, consoleErrors, apiFailures }, null, 2))
  }
  console.log(`Captured ${captures.length} live Atlas Forecasts screenshots in docs/qa/screenshots/issue-34-gate-7.`)
  console.log('Browser page errors: 0; browser console errors: 0; failed AutoStock API responses: 0.')
} catch (error) {
  const headings = await page.locator('h1,h2,[role="alert"]').allTextContents().catch(() => [])
  await page.screenshot({ path: path.join(outputDirectory, 'capture-debug.png'), fullPage: true }).catch(() => {})
  console.error(JSON.stringify({
    error: error instanceof Error ? error.message : String(error),
    url: page.url(),
    headings,
    pageErrors,
    consoleErrors,
    apiFailures,
  }, null, 2))
  throw error
} finally {
  await context.close()
  await browser.close()
}
