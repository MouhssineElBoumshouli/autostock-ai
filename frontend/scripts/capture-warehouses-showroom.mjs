import { readFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, expect } from '@playwright/test'

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryDirectory = path.resolve(frontendDirectory, '..')
const credentialPath = path.join(repositoryDirectory, '.showroom', 'credentials.txt')
const outputDirectory = path.join(repositoryDirectory, 'docs', 'qa', 'screenshots', 'issue-30-gate-5')
const frontendUrl = process.env.AUTOSTOCK_FRONTEND_URL || 'http://127.0.0.1:5173'

function parseCredentials(contents) {
  const entries = new Map()
  for (const line of contents.split(/\r?\n/)) {
    const match = line.match(/^\s*([^:=]+?)\s*[:=]\s*(.*?)\s*$/)
    if (match) entries.set(match[1].toLowerCase().replace(/\s+/g, '_'), match[2])
  }
  const credentials = { database: entries.get('database'), login: entries.get('login'), password: entries.get('password') }
  if (Object.values(credentials).some((value) => !value)) {
    throw new Error('The local showroom credential file is incomplete; screenshot capture stopped.')
  }
  return credentials
}

const credentials = parseCredentials(await readFile(credentialPath, 'utf8'))
await mkdir(outputDirectory, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'light' })
const page = await context.newPage()
const pageErrors = []
const consoleErrors = []
const apiFailures = []
page.on('pageerror', (error) => pageErrors.push(error.message))
page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
page.on('response', (response) => {
  const pathname = new URL(response.url()).pathname
  if (pathname.startsWith('/autostock/api/v1/') && response.status() >= 400) apiFailures.push(`${pathname} returned ${response.status()}`)
})

async function settleLayout() {
  await page.evaluate(async () => {
    await document.fonts.ready
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  })
}

async function capture(viewport, filename, fullPage = true) {
  await page.setViewportSize({ width: viewport.width, height: viewport.height })
  await settleLayout()
  const width = await page.evaluate(() => document.documentElement.scrollWidth)
  if (width > viewport.width) throw new Error(`Warehouses page overflows horizontally at ${viewport.width}px.`)
  await page.screenshot({ path: path.join(outputDirectory, filename), fullPage, animations: 'disabled' })
  return filename
}

try {
  await page.goto(`${frontendUrl}/warehouses`, { waitUntil: 'domcontentloaded' })
  const loginTitle = page.getByRole('heading', { name: 'Welcome back' })
  const warehouseTitle = page.getByRole('heading', { name: 'Warehouses', level: 1 })
  const firstScreen = await Promise.race([
    loginTitle.waitFor({ state: 'visible', timeout: 60_000 }).then(() => 'login'),
    warehouseTitle.waitFor({ state: 'visible', timeout: 60_000 }).then(() => 'warehouses'),
  ])
  if (firstScreen === 'login') {
    await page.getByLabel('Email or username').fill(credentials.login)
    await page.getByLabel('Password', { exact: true }).fill(credentials.password)
    await page.getByRole('button', { name: 'Continue' }).click()
  }

  await warehouseTitle.waitFor({ timeout: 60_000 })
  await page.getByRole('heading', { name: 'Your locations' }).waitFor({ timeout: 45_000 })
  await expect(page.getByText('Demo environment', { exact: true })).toBeVisible()
  await expect(page.getByText('Atlas Auto Distribution', { exact: false }).first()).toBeVisible()
  await expect(page.locator('.warehouse-card')).toHaveCount(2, { timeout: 30_000 })
  const captures = []
  captures.push(await capture({ width: 1440, height: 1000 }, 'warehouses-overview-1440.png'))
  captures.push(await capture({ width: 1024, height: 900 }, 'warehouses-overview-1024.png'))
  captures.push(await capture({ width: 390, height: 844 }, 'warehouses-overview-390.png'))

  await page.setViewportSize({ width: 1440, height: 1000 })
  const attentionFilter = page.getByRole('combobox', { name: 'Filter warehouses by stock status' })
  const attentionResponse = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname === '/autostock/api/v1/warehouses' && url.searchParams.get('status') === 'attention' && response.status() === 200
  }, { timeout: 30_000 })
  await attentionFilter.selectOption('attention')
  const attentionPayload = await (await attentionResponse).json()
  if (attentionPayload.pagination?.total_count !== 2 || attentionPayload.warehouses?.length !== 2
      || attentionPayload.warehouses.some((warehouse) => warehouse.status !== 'needs_attention')) {
    throw new Error('Live warehouse attention filtering did not return the two warehouses needing attention.')
  }
  await expect(page.locator('.warehouse-card')).toHaveCount(2)
  await expect(page.locator('.warehouse-card .warehouse-status').first()).toContainText('Needs attention')
  captures.push(await capture({ width: 1440, height: 1000 }, 'warehouses-attention-1440.png'))

  await attentionFilter.selectOption('all')
  await expect(page.locator('.warehouse-card')).toHaveCount(2)
  const searchInput = page.getByRole('searchbox', { name: 'Search warehouses by name or code' })
  const warehouseFilterResponse = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname === '/autostock/api/v1/warehouses' && url.searchParams.get('q') === 'Central' && response.status() === 200
  }, { timeout: 30_000 })
  await searchInput.fill('Central')
  const filteredResponse = await warehouseFilterResponse
  const filteredPayload = await filteredResponse.json()
  if (filteredPayload.pagination?.total_count !== 1 || filteredPayload.warehouses?.length !== 1) {
    throw new Error('Live warehouse name filtering did not return exactly one Odoo warehouse.')
  }
  await expect(page.locator('.warehouse-card')).toHaveCount(1)
  await expect(page.locator('.warehouse-card').first()).toContainText('Central')
  captures.push(await capture({ width: 1440, height: 1000 }, 'warehouses-filtered-1440.png'))

  await searchInput.fill('')
  await expect(page.locator('.warehouse-card')).toHaveCount(2, { timeout: 20_000 })
  const warehouseCards = page.locator('.warehouse-card')
  let activeWarehouseIndex = 0
  for (let index = 0; index < await warehouseCards.count(); index++) {
    if (!(await warehouseCards.nth(index).innerText()).includes('No completed changes')) {
      activeWarehouseIndex = index
      break
    }
  }
  const selectedWarehouseLink = warehouseCards.nth(activeWarehouseIndex)
  await selectedWarehouseLink.click()
  await expect(page).toHaveURL(/\/warehouses\/\d+$/)
  await expect(page.getByRole('heading', { level: 1 })).not.toHaveText('Warehouses')
  await expect(page.getByRole('heading', { name: 'Parts in this warehouse' })).toBeVisible({ timeout: 45_000 })
  await expect(page.getByRole('heading', { name: 'Recent stock activity' })).toBeVisible()
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.locator('.warehouse-stock-part').first().waitFor({ state: 'visible', timeout: 45_000 })
  captures.push(await capture({ width: 1440, height: 1000 }, 'warehouse-detail-1440.png'))
  captures.push(await capture({ width: 1024, height: 900 }, 'warehouse-detail-1024.png'))
  captures.push(await capture({ width: 390, height: 844 }, 'warehouse-detail-390.png'))

  await page.setViewportSize({ width: 1440, height: 1000 })
  await settleLayout()
  const activity = page.locator('.warehouse-activity')
  await expect(activity).toBeVisible()
  if (await page.locator('.warehouse-activity-list').count()) {
    await expect(page.locator('.warehouse-activity-row').first()).toBeVisible()
  }
  await activity.screenshot({ path: path.join(outputDirectory, 'warehouse-activity-1440.png'), animations: 'disabled' })
  await page.locator('.warehouse-stock-part').first().click()
  await expect(page.getByRole('heading', { name: 'Stock by warehouse' })).toBeVisible({ timeout: 30_000 })
  captures.push(await capture({ width: 1440, height: 1000 }, 'warehouse-product-detail-1440.png', false))
  await page.keyboard.press('Escape')
  await page.locator('.inventory-detail-sheet').waitFor({ state: 'hidden', timeout: 10_000 })

  await page.setViewportSize({ width: 1440, height: 1000 })
  const firstSku = (await page.locator('.warehouse-stock-table tbody tr:first-child .warehouse-stock-sku').innerText()).trim()
  if (!firstSku) throw new Error('The showroom inventory row has no SKU to verify.')
  const skuResponse = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname.endsWith('/inventory') && url.pathname.includes('/warehouses/')
      && url.searchParams.get('q') === firstSku && response.status() === 200
  }, { timeout: 30_000 })
  await page.getByRole('searchbox', { name: 'Search by part name, SKU, OEM reference' }).fill(firstSku)
  const skuPayload = await (await skuResponse).json()
  if (skuPayload.pagination?.total_count !== 1 || skuPayload.items?.length !== 1 || skuPayload.items[0]?.sku !== firstSku) {
    throw new Error('Warehouse SKU search did not return exactly the searched Odoo part.')
  }
  await expect(page.locator('.warehouse-stock-table tbody tr:visible')).toHaveCount(1)
  await expect(page.locator('.warehouse-stock-table tbody tr:visible').first()).toContainText(firstSku)
  captures.push(await capture({ width: 1440, height: 1000 }, 'warehouse-filtered-part-1440.png'))

  const emptyResponse = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname.endsWith('/inventory') && url.pathname.includes('/warehouses/')
      && url.searchParams.get('q') === 'no-such-showroom-part' && response.status() === 200
  }, { timeout: 30_000 })
  await page.getByRole('searchbox', { name: 'Search by part name, SKU, OEM reference' }).fill('no-such-showroom-part')
  const emptyPayload = await (await emptyResponse).json()
  if (emptyPayload.pagination?.total_count !== 0 || emptyPayload.items?.length !== 0) {
    throw new Error('The live showroom no-results search returned unexpected inventory rows.')
  }
  await expect(page.getByRole('heading', { name: 'No parts match these filters' })).toBeVisible()
  captures.push(await capture({ width: 1440, height: 1000 }, 'warehouse-no-results-1440.png'))

  await page.goto(`${frontendUrl}/warehouses`)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  await expect(page.getByRole('dialog', { name: 'AutoStock navigation' })).toBeVisible()
  captures.push(await capture({ width: 390, height: 844 }, 'warehouses-mobile-navigation-390.png', false))

  if (pageErrors.length || consoleErrors.length || apiFailures.length) {
    throw new Error(JSON.stringify({ pageErrors, consoleErrors, apiFailures }, null, 2))
  }
  console.log(`Captured ${captures.length} live showroom screenshots in docs/qa/screenshots/issue-30-gate-5.`)
  console.log('Browser page errors: 0; browser console errors: 0; failed AutoStock API responses: 0.')
} finally {
  await context.close()
  await browser.close()
}
