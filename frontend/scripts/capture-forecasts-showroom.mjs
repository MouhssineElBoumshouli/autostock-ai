import { readFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, expect } from '@playwright/test'

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryDirectory = path.resolve(frontendDirectory, '..')
const credentialPath = path.join(repositoryDirectory, '.showroom', 'credentials.txt')
const outputDirectory = path.join(repositoryDirectory, 'docs', 'qa', 'screenshots', 'issue-34-gate-7-employee-first')
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
  if (pathname === '/autostock/api/v1/session' && response.status() === 200) {
    payloads.set('session', await response.json())
  }
  if (pathname === '/autostock/api/v1/forecasts/parts' && response.status() === 200) {
    payloads.set('parts', await response.json())
  }
  if (pathname === '/autostock/api/v1/forecasts' && response.status() === 200) {
    payloads.set('history', await response.json())
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

async function capture(width, height, filename) {
  await page.setViewportSize({ width, height })
  await settleLayout()
  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
  if (scrollWidth > width) throw new Error(`Forecasts page overflows horizontally at ${width}px.`)
  await page.mouse.move(1, 1)
  await page.screenshot({ path: path.join(outputDirectory, filename), fullPage: true, animations: 'disabled' })
  captures.push(filename)
}

async function findCompleteThirtyDayRun(companyId) {
  return page.evaluate(async (selectedCompanyId) => {
    const result = []
    for (let pageNumber = 1; pageNumber <= 500; pageNumber += 1) {
      const params = new URLSearchParams({ company_id: String(selectedCompanyId), page: String(pageNumber), page_size: '50' })
      const response = await fetch(`/autostock/api/v1/forecasts/parts?${params}`, {
        credentials: 'include', headers: { Accept: 'application/json' },
      })
      if (!response.ok) throw new Error(`Atlas parts API returned ${response.status} while locating saved data.`)
      const data = await response.json()
      if (data.company?.id !== selectedCompanyId || data.read_only !== true) {
        throw new Error('Atlas did not return a company-scoped read-only Forecasts response.')
      }
      result.push(...data.parts)
      if (!data.pagination?.has_next) break
    }
    if (result.length >= 25_000) throw new Error('Forecast part discovery reached its safe scan bound.')
    const candidates = result.flatMap((part) => {
      const horizon = part.horizons.find((item) => item.horizon_days === 30)
      return horizon?.estimate.status === 'available' && horizon.latest_run?.state === 'completed'
        ? [{ part, horizon }]
        : []
    })
    return candidates.find(({ horizon }) => horizon.latest_run?.review_status === 'reviewed') ?? candidates[0] ?? null
  }, companyId)
}

async function waitForPartsResponse(query, warehouseId = '') {
  const response = await page.waitForResponse((item) => {
    const url = new URL(item.url())
    return url.pathname === '/autostock/api/v1/forecasts/parts'
      && url.searchParams.get('q') === query
      && (warehouseId ? url.searchParams.get('warehouse_id') === warehouseId : !url.searchParams.has('warehouse_id'))
      && item.status() === 200
  }, { timeout: 45_000 })
  return response.json()
}

try {
  await page.goto(`${frontendUrl}/forecasts`, { waitUntil: 'domcontentloaded' })
  const loginHeading = page.getByRole('heading', { name: 'Welcome back' })
  const pageHeading = page.getByRole('heading', { name: 'Forecasts', exact: true })
  const firstScreen = await Promise.race([
    loginHeading.waitFor({ state: 'visible', timeout: 60_000 }).then(() => 'login'),
    pageHeading.waitFor({ state: 'visible', timeout: 60_000 }).then(() => 'forecasts'),
  ])
  if (firstScreen === 'login') {
    await page.getByLabel('Email or username').fill(credentials.login)
    await page.getByLabel('Password', { exact: true }).fill(credentials.password)
    await page.getByRole('button', { name: 'Continue' }).click()
  }

  await pageHeading.waitFor({ timeout: 60_000 })
  await expect(page.getByRole('heading', { name: 'Forecasts by part' })).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('Demo environment', { exact: true })).toBeVisible()
  await expect.poll(() => payloads.has('session'), { timeout: 45_000 }).toBe(true)
  await expect.poll(() => payloads.has('parts'), { timeout: 45_000 }).toBe(true)
  const session = payloads.get('session')
  const companyId = session.current_company?.id
  const timezone = session.user?.timezone
  if (session.current_company?.name !== 'Atlas Auto Distribution' || !Number.isSafeInteger(companyId)
    || typeof timezone !== 'string' || !timezone) {
    throw new Error('The live session did not provide an authenticated Atlas company and user timezone.')
  }
  const livePage = payloads.get('parts')
  if (livePage.company?.id !== companyId || livePage.company?.name !== 'Atlas Auto Distribution'
    || livePage.read_only !== true || livePage.real_history_access !== true) {
    throw new Error('The live By part response is not the authenticated, read-only Atlas delivery history.')
  }
  await expect(page.locator('.forecast-part-row')).toHaveCount(livePage.parts.length)
  if (!livePage.parts.length) throw new Error('Atlas has no visible real parts to capture in the Forecasts list.')
  console.log(`Authenticated Atlas Forecasts session; user timezone: ${timezone}.`)
  console.log(`Capturing the unfiltered live By part page with ${livePage.parts.length} company-visible product/warehouse groups.`)

  for (const [width, height, suffix] of [[1440, 1000, '1440'], [1024, 900, '1024'], [390, 844, '390']]) {
    await capture(width, height, `forecasts-by-part-30-day-${suffix}.png`)
  }

  const selected = await findCompleteThirtyDayRun(companyId)
  if (!selected) {
    throw new Error('Atlas currently has no complete saved 30-day daily series for a truthful summary screenshot.')
  }
  const { part, horizon } = selected
  const selectedRun = horizon.latest_run
  if (!selectedRun || horizon.estimate.status !== 'available' || !Number.isFinite(horizon.estimate.estimated_units)
    || !horizon.estimate.date_start || !horizon.estimate.date_end) {
    throw new Error('The selected Atlas run does not contain a complete saved 30-day estimate and date range.')
  }
  console.log(`Selected live part ${part.sku} at ${part.warehouse_name || 'company-wide'}; exact saved period ${horizon.estimate.date_start} to ${horizon.estimate.date_end}.`)

  const searchBox = page.getByRole('searchbox', { name: 'Search forecast parts by name or SKU' })
  const searchResponsePromise = waitForPartsResponse(part.sku)
  await searchBox.fill(part.sku)
  const searchResponse = await searchResponsePromise
  if (!searchResponse.parts.some((item) => item.product_id === part.product_id && item.warehouse_id === part.warehouse_id)) {
    throw new Error('The live Odoo search response did not contain the selected part and warehouse group.')
  }
  if (part.warehouse_id) {
    const warehouseSelect = page.getByRole('combobox', { name: 'Choose forecast warehouse' })
    const warehouseResponsePromise = waitForPartsResponse(part.sku, String(part.warehouse_id))
    await warehouseSelect.selectOption(String(part.warehouse_id))
    const warehouseResponse = await warehouseResponsePromise
    if (warehouseResponse.parts.length !== 1 || warehouseResponse.parts[0].product_id !== part.product_id
      || warehouseResponse.parts[0].warehouse_id !== part.warehouse_id) {
      throw new Error('The filtered Atlas response did not show exactly the selected part and warehouse.')
    }
  }
  const selectedRow = page.locator(`.forecast-part-row[data-product-id="${part.product_id}"][data-warehouse-id="${part.warehouse_id || 'company'}"]`)
  await expect(selectedRow).toHaveCount(1)
  await expect(selectedRow.getByRole('button', { name: '30 days' })).toHaveAttribute('aria-pressed', 'true')
  await expect(selectedRow.getByTestId('forecast-estimated-total')).not.toBeEmpty()
  await expect(selectedRow.getByTestId('forecast-estimate-range')).toContainText(await page.evaluate(({ start, end }) => {
    const format = (value) => new Intl.DateTimeFormat(undefined, { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(`${value}T00:00:00Z`))
    return `${format(start)} – ${format(end)}`
  }, { start: horizon.estimate.date_start, end: horizon.estimate.date_end }))

  await page.setViewportSize({ width: 1440, height: 1000 })
  await selectedRow.getByRole('link', { name: new RegExp(`Open 30-day estimate for .*${part.sku}`) }).click()
  await expect(page.getByRole('heading', { name: part.product_name, exact: true })).toBeVisible({ timeout: 45_000 })
  const detailKey = `/autostock/api/v1/forecasts/${selectedRun.id}`
  await expect.poll(() => payloads.has(detailKey), { timeout: 45_000 }).toBe(true)
  const detail = payloads.get(detailKey)
  if (detail.company?.id !== companyId || detail.run?.id !== selectedRun.id || detail.run?.product_id !== part.product_id
    || detail.run?.warehouse_id !== part.warehouse_id || detail.run?.source_type !== 'completed_deliveries'
    || detail.estimate?.status !== 'available' || detail.read_only !== true) {
    throw new Error('The opened detail is not the selected complete real Atlas run.')
  }
  await expect(page.getByTestId('forecast-estimated-total')).not.toBeEmpty()
  await expect(page.getByRole('heading', { name: 'Past deliveries and saved estimate' })).toBeVisible()
  await expect(page.getByText(/This saved estimate|This demonstration example|Restock eligibility/).first()).toBeVisible()
  await expect(page.locator('.forecast-evaluation-disclosure')).not.toHaveAttribute('open', '')
  for (const [width, height, suffix] of [[1440, 1000, '1440'], [1024, 900, '1024'], [390, 844, '390']]) {
    await capture(width, height, `forecast-estimate-detail-${suffix}.png`)
  }

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('link', { name: 'Back to forecasts' }).click()
  await expect(page.getByRole('heading', { name: 'Forecasts by part' })).toBeVisible()
  await page.getByRole('button', { name: 'Saved run history' }).click()
  await expect(page.getByRole('heading', { name: 'Saved run history' })).toBeVisible()
  await expect.poll(() => payloads.has('history'), { timeout: 45_000 }).toBe(true)
  const history = payloads.get('history')
  if (history.company?.id !== companyId || history.read_only !== true
    || !history.runs.some((run) => run.id === selectedRun.id && run.source_type === 'completed_deliveries')) {
    throw new Error('Saved run history did not retain the exact selected Atlas record.')
  }
  for (const [width, height, suffix] of [[1440, 1000, '1440'], [1024, 900, '1024'], [390, 844, '390']]) {
    await capture(width, height, `forecast-saved-history-${suffix}.png`)
  }

  if (pageErrors.length || consoleErrors.length || apiFailures.length) {
    throw new Error(JSON.stringify({ pageErrors, consoleErrors, apiFailures }, null, 2))
  }
  console.log(`Captured ${captures.length} live Atlas Forecasts screenshots in docs/qa/screenshots/issue-34-gate-7-employee-first.`)
  console.log('Browser page errors: 0; browser console errors: 0; failed AutoStock API responses: 0.')
} catch (error) {
  const headings = await page.locator('h1,h2,[role="alert"]').allTextContents().catch(() => [])
  await page.screenshot({ path: path.join(outputDirectory, 'capture-debug.png'), fullPage: true }).catch(() => {})
  console.error(JSON.stringify({
    error: error instanceof Error ? error.message : String(error),
    url: page.url(), headings, pageErrors, consoleErrors, apiFailures,
  }, null, 2))
  throw error
} finally {
  await context.close()
  await browser.close()
}
