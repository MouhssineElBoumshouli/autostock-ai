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
const listPayloads = []
const unavailableLiveStates = []

page.on('pageerror', (error) => pageErrors.push(error.message))
page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push(message.text())
})
page.on('response', async (response) => {
  const pathname = new URL(response.url()).pathname
  if (pathname.startsWith('/autostock/api/v1/') && response.status() >= 400) {
    apiFailures.push(`${pathname} returned ${response.status()}`)
  }
  if (pathname === '/autostock/api/v1/session' && response.status() === 200) {
    payloads.set('session', await response.json())
  }
  if (pathname === '/autostock/api/v1/forecasts' && response.status() === 200) {
    const body = await response.json()
    payloads.set('list', body)
    listPayloads.push(body)
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

async function setListFilter(label, value, key) {
  await page.getByRole('combobox', { name: label }).selectOption(value)
  await expect.poll(async () => {
    const active = await page.evaluate(() => {
      const input = document.querySelector('input[type="search"]')
      const select = (name) => document.querySelector(`select[aria-label="${name}"]`)?.value ?? ''
      return {
        query: input?.value.trim() ?? '',
        warehouse_id: select('Filter forecasts by warehouse'),
        horizon_days: select('Filter forecasts by horizon') || 'all',
        state: select('Filter forecasts by run status') || 'all',
        review_status: select('Filter forecasts by review status') || 'all',
        source_type: select('Filter forecasts by source') || 'all',
      }
    })
    const match = listPayloads.find((item) => item.pagination.page === 1
      && item.filters.query === active.query
      && item.filters.horizon_days === active.horizon_days
      && item.filters.state === active.state
      && item.filters.review_status === active.review_status
      && item.filters.source_type === active.source_type
      && (active.warehouse_id ? String(item.filters.warehouse_id) === active.warehouse_id : item.filters.warehouse_id === false))
    if (!match || match.filters[key] !== value) return false
    payloads.set('list', match)
    return true
  }, { timeout: 45_000 }).toBe(true)
  return payloads.get('list')
}

async function clearListFilters() {
  const clear = page.locator('button.forecast-clear-filters')
  if (await clear.isVisible()) {
    await clear.click()
    await expect.poll(async () => {
      const query = await page.locator('input[type="search"]').inputValue()
      const source = await page.getByRole('combobox', { name: 'Filter forecasts by source' }).inputValue()
      const state = await page.getByRole('combobox', { name: 'Filter forecasts by run status' }).inputValue()
      const review = await page.getByRole('combobox', { name: 'Filter forecasts by review status' }).inputValue()
      const match = listPayloads.find((item) => item.pagination.page === 1 && item.filters.query === query.trim()
        && item.filters.source_type === (source || 'all')
        && item.filters.state === (state || 'all')
        && item.filters.review_status === (review || 'all'))
      if (!match) return false
      payloads.set('list', match)
      return true
    }, { timeout: 45_000 }).toBe(true)
  }
}

async function expectedSavedDate(timestamp, timezone) {
  return page.evaluate(({ value, zone }) => {
    const normalized = value.includes('T') ? value : value.replace(' ', 'T')
    const explicitZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
    const date = new Date(explicitZone ? normalized : `${normalized}Z`)
    return new Intl.DateTimeFormat(undefined, {
      timeZone: zone, month: 'short', day: 'numeric', year: 'numeric',
    }).format(date)
  }, { value: timestamp, zone: timezone })
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
  await expect.poll(() => payloads.has('session'), { timeout: 45_000 }).toBe(true)
  await expect.poll(() => payloads.has('list'), { timeout: 45_000 }).toBe(true)

  const session = payloads.get('session')
  const timezone = session.user?.timezone
  if (session.current_company?.name !== 'Atlas Auto Distribution' || typeof timezone !== 'string' || !timezone) {
    throw new Error('The live session did not provide the Atlas company and authenticated user timezone.')
  }
  console.log(`Authenticated Atlas user timezone: ${timezone}.`)
  const list = payloads.get('list')
  if (list.company?.name !== 'Atlas Auto Distribution' || !Array.isArray(list.runs)) {
    throw new Error('The live Forecasts API did not return the Atlas Auto Distribution company and run list.')
  }
  if (list.read_only !== true || !Number.isSafeInteger(list.pagination?.total_count)) {
    throw new Error('The live Forecasts response did not include read-only state and an exact numeric total.')
  }

  let selectedRun = list.runs.find((run) => run.source_type === 'completed_deliveries' && run.state === 'completed' && run.review_status === 'reviewed')
  if (!selectedRun) {
    await setListFilter('Filter forecasts by source', 'completed_deliveries', 'source_type')
    await setListFilter('Filter forecasts by run status', 'completed', 'state')
    const reviewedRuns = await setListFilter('Filter forecasts by review status', 'reviewed', 'review_status')
    selectedRun = reviewedRuns.runs.find((run) => run.source_type === 'completed_deliveries' && run.state === 'completed' && run.review_status === 'reviewed')
  }
  if (!selectedRun) {
    throw new Error('Atlas has no completed, reviewed forecast based on real deliveries in the server-filtered results; required detail screenshots were not skipped.')
  }
  const savedDateRow = page.locator('.forecast-table tbody tr').filter({ hasText: selectedRun.sku }).first()
  await expect(savedDateRow.getByTestId('forecast-saved-date')).toHaveText(await expectedSavedDate(selectedRun.created_at, timezone))
  await clearListFilters()

  await capture(1440, 1000, 'forecasts-overview-1440.png')
  await capture(1024, 900, 'forecasts-overview-1024.png')
  await capture(390, 844, 'forecasts-overview-390.png')

  await page.setViewportSize({ width: 1440, height: 1000 })
  await setListFilter('Filter forecasts by source', 'completed_deliveries', 'source_type')
  await setListFilter('Filter forecasts by run status', 'completed', 'state')
  const reviewedRuns = await setListFilter('Filter forecasts by review status', 'reviewed', 'review_status')
  selectedRun = reviewedRuns.runs.find((run) => run.source_type === 'completed_deliveries' && run.state === 'completed' && run.review_status === 'reviewed')
  if (!selectedRun) throw new Error('The required reviewed real-data run disappeared while selecting it for the detail capture.')
  const selectedRow = page.locator('.forecast-table tbody tr').filter({ hasText: selectedRun.sku }).first()
  await selectedRow.getByRole('link', { name: /^Open forecast for/ }).click()
  await expect(page.getByRole('heading', { name: selectedRun.product_name, exact: true })).toBeVisible({ timeout: 45_000 })
  const detailKey = `/autostock/api/v1/forecasts/${selectedRun.id}`
  await expect.poll(() => payloads.has(detailKey), { timeout: 45_000 }).toBe(true)
  const detail = payloads.get(detailKey)
  if (detail.run?.id !== selectedRun.id || detail.run?.source_type !== 'completed_deliveries'
    || detail.run?.state !== 'completed' || detail.run?.review_status !== 'reviewed' || detail.read_only !== true) {
    throw new Error('The selected detail is not the exact completed, reviewed, real-data, read-only Atlas run.')
  }
  const firstPrediction = detail.run.predictions?.[0]
  if (!firstPrediction) throw new Error('The selected completed Atlas run has no saved forecast points; chart evidence cannot be captured.')
  await expect(page.getByRole('heading', { name: 'Delivered history and forecast' })).toBeVisible()
  await expect(page.getByText('Forecast starts', { exact: true })).toBeVisible()
  const chart = page.locator('.forecast-chart-wrap')
  await expect(chart).toHaveAttribute('data-first-forecast-day', firstPrediction.day)
  await expect(chart).toHaveAttribute('data-first-forecast-units', String(firstPrediction.units))
  await expect(chart).toHaveAttribute('data-first-forecast-lower', String(firstPrediction.lower_heuristic))
  await expect(chart).toHaveAttribute('data-first-forecast-upper', String(firstPrediction.upper_heuristic))
  await page.getByText('How this forecast was calculated', { exact: true }).click()
  await expect(page.locator('.forecast-evaluation-body')).toBeVisible()
  await capture(1440, 1000, 'forecast-reviewed-detail-evaluation-open-1440.png')
  await capture(1024, 900, 'forecast-reviewed-detail-evaluation-open-1024.png')
  await capture(390, 844, 'forecast-reviewed-detail-evaluation-open-390.png')
  console.log(`Captured the reviewed real-delivery forecast detail (run ${selectedRun.id}) with its evaluation disclosure open.`)

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('link', { name: 'All forecasts' }).click()
  await expect(page.getByRole('heading', { name: 'Saved forecasts' })).toBeVisible()
  await clearListFilters()
  const noMatchQuery = `AUTOSTOCK-QA-NO-MATCH-${Date.now()}`
  const noMatchResponse = page.waitForResponse((item) => {
    const url = new URL(item.url())
    return url.pathname === '/autostock/api/v1/forecasts' && url.searchParams.get('q') === noMatchQuery && item.status() === 200
  }, { timeout: 45_000 })
  await page.getByRole('searchbox', { name: 'Search forecasts by part name or SKU' }).fill(noMatchQuery)
  await noMatchResponse
  await expect.poll(() => listPayloads.some((item) => item.filters.query === noMatchQuery
    && item.pagination.total_count === 0 && item.runs.length === 0), { timeout: 45_000 }).toBe(true)
  payloads.set('list', listPayloads.find((item) => item.filters.query === noMatchQuery))
  await expect(page.getByRole('heading', { name: 'No forecasts match these filters' })).toBeVisible({ timeout: 45_000 })
  const noResults = payloads.get('list')
  if (noResults?.pagination?.total_count !== 0 || noResults?.runs?.length !== 0) {
    throw new Error('The no-results screenshot would not represent a live empty result from the Atlas Forecasts API.')
  }
  await capture(1440, 1000, 'forecasts-no-results-1440.png')
  await clearListFilters()

  const unreviewedRuns = await setListFilter('Filter forecasts by source', 'completed_deliveries', 'source_type')
    .then(() => setListFilter('Filter forecasts by review status', 'unreviewed', 'review_status'))
  if (unreviewedRuns.runs.length) {
    await capture(1440, 1000, 'forecasts-real-unreviewed-1440.png')
  } else {
    unavailableLiveStates.push('No real completed-delivery forecasts are currently unreviewed.')
  }
  await clearListFilters()

  const insufficientRuns = await setListFilter('Filter forecasts by source', 'completed_deliveries', 'source_type')
    .then(() => setListFilter('Filter forecasts by run status', 'insufficient_history', 'state'))
  if (insufficientRuns.runs.length) {
    await capture(1440, 1000, 'forecasts-real-insufficient-history-1440.png')
  } else {
    unavailableLiveStates.push('No real completed-delivery forecasts currently have insufficient history.')
  }
  unavailableLiveStates.push('A restricted view was not captured: this authenticated Atlas user has Forecasts access, and no separate restricted Atlas account is configured for capture.')

  if (pageErrors.length || consoleErrors.length || apiFailures.length) {
    throw new Error(JSON.stringify({ pageErrors, consoleErrors, apiFailures }, null, 2))
  }
  console.log(`Captured ${captures.length} live Atlas Forecasts screenshots in docs/qa/screenshots/issue-34-gate-7.`)
  console.log(`Additional live states not present or unavailable: ${unavailableLiveStates.join(' ') || 'None.'}`)
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
