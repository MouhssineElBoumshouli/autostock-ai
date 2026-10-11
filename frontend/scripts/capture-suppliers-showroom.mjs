import { readFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, expect } from '@playwright/test'

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryDirectory = path.resolve(frontendDirectory, '..')
const credentialPath = path.join(repositoryDirectory, '.showroom', 'credentials.txt')
const outputDirectory = path.join(repositoryDirectory, 'docs', 'qa', 'screenshots', 'issue-32-gate-6')
const frontendUrl = process.env.AUTOSTOCK_FRONTEND_URL || 'http://127.0.0.1:5173'

function parseCredentials(contents) {
  const entries = new Map()
  for (const line of contents.split(/\r?\n/)) {
    const match = line.match(/^\s*([^:=]+?)\s*[:=]\s*(.*?)\s*$/)
    if (match) entries.set(match[1].toLowerCase().replace(/\s+/g, '_'), match[2])
  }
  const credentials = { database: entries.get('database'), login: entries.get('login'), password: entries.get('password') }
  if (Object.values(credentials).some((value) => !value)) throw new Error('The local showroom credential file is incomplete; screenshot capture stopped.')
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
const captures = []
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

async function capture(width, height, filename, fullPage = true) {
  await page.setViewportSize({ width, height })
  await settleLayout()
  const documentWidth = await page.evaluate(() => document.documentElement.scrollWidth)
  if (documentWidth > width) throw new Error(`Suppliers page overflows horizontally at ${width}px.`)
  await page.screenshot({ path: path.join(outputDirectory, filename), fullPage, animations: 'disabled' })
  captures.push(filename)
}

try {
  await page.goto(`${frontendUrl}/suppliers`, { waitUntil: 'domcontentloaded' })
  const loginTitle = page.getByRole('heading', { name: 'Welcome back' })
  const suppliersTitle = page.getByRole('heading', { name: 'Suppliers', level: 1 })
  const firstScreen = await Promise.race([
    loginTitle.waitFor({ state: 'visible', timeout: 60_000 }).then(() => 'login'),
    suppliersTitle.waitFor({ state: 'visible', timeout: 60_000 }).then(() => 'suppliers'),
  ])
  if (firstScreen === 'login') {
    await page.getByLabel('Email or username').fill(credentials.login)
    await page.getByLabel('Password', { exact: true }).fill(credentials.password)
    await page.getByRole('button', { name: 'Continue' }).click()
  }

  await suppliersTitle.waitFor({ timeout: 60_000 })
  await page.getByRole('heading', { name: 'Your suppliers' }).waitFor({ timeout: 45_000 })
  await expect(page.getByText('Demo environment', { exact: true })).toBeVisible()
  await expect(page.getByText('Atlas Auto Distribution', { exact: false }).first()).toBeVisible()
  const supplierRows = page.locator('.supplier-table tbody tr')
  await expect(supplierRows.first()).toBeVisible()
  let supplierId
  let supplierName
  for (let index = 0; index < await supplierRows.count(); index += 1) {
    const row = supplierRows.nth(index)
    const partCount = Number.parseInt(await row.locator('td').nth(1).innerText(), 10)
    const reorderText = await row.locator('td').nth(3).innerText()
    const termCount = Number.parseInt(await row.locator('td').nth(5).innerText(), 10)
    if (partCount > 0 && termCount > 0 && reorderText.includes('parts to restock')) {
      const supplierLink = row.locator('a.supplier-table-name')
      const supplierHref = await supplierLink.getAttribute('href')
      supplierId = supplierHref?.match(/\/suppliers\/(\d+)$/)?.[1]
      supplierName = (await supplierLink.locator('strong').innerText()).trim()
      break
    }
  }
  if (!supplierId) throw new Error('The showroom did not render a supplier link to inspect.')
  await expect(page.getByRole('link', { name: /Parts without a supplier/ })).toBeVisible()

  await capture(1440, 1000, 'suppliers-overview-1440.png')
  await capture(1024, 900, 'suppliers-overview-1024.png')
  await capture(390, 844, 'suppliers-overview-390.png')

  await page.setViewportSize({ width: 1440, height: 1000 })
  const supplierSearch = page.getByRole('searchbox', { name: 'Search suppliers by name or vendor code' })
  const supplierSearchResponse = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname === '/autostock/api/v1/suppliers'
      && url.searchParams.get('q') === supplierName
      && response.status() === 200
  }, { timeout: 45_000 })
  await supplierSearch.fill(supplierName)
  await supplierSearchResponse
  await expect(page.getByText('Showing 1–1 of 1', { exact: true })).toBeVisible()
  await expect(page.locator('a.supplier-table-name:visible')).toHaveCount(1)
  await expect(page.locator('.supplier-summary-grid .inventory-summary-card').filter({ hasText: 'Active suppliers' }).locator('strong')).toHaveText('4')
  await capture(1440, 1000, 'suppliers-search-1440.png')

  const attentionFilter = page.getByRole('combobox', { name: 'Filter suppliers by reorder needs' })
  const attentionResponse = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname === '/autostock/api/v1/suppliers'
      && url.searchParams.get('q') === supplierName
      && url.searchParams.get('attention') === 'reorder'
      && response.status() === 200
  }, { timeout: 45_000 })
  await attentionFilter.selectOption('reorder')
  await attentionResponse
  await expect(page.getByText('Showing 1–1 of 1', { exact: true })).toBeVisible()
  await expect(page.locator('.supplier-summary-grid .inventory-summary-card').filter({ hasText: 'Active suppliers' }).locator('strong')).toHaveText('4')
  await capture(1440, 1000, 'suppliers-reorder-filter-1440.png')

  await page.goto(`${frontendUrl}/suppliers/${supplierId}`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: supplierName, exact: true })).toBeVisible({ timeout: 45_000 })
  await expect(page.getByRole('heading', { name: 'Parts supplied' })).toBeVisible({ timeout: 45_000 })
  await expect(page.locator('.supplier-part-table tbody tr:visible, .supplier-part-mobile-list .supplier-part-card:visible').first()).toBeVisible({ timeout: 45_000 })
  await capture(1440, 1000, 'supplier-detail-1440.png')
  await capture(1024, 900, 'supplier-detail-1024.png')
  await capture(390, 844, 'supplier-detail-390.png')

  await page.setViewportSize({ width: 1440, height: 1000 })
  const firstPart = page.locator('.supplier-part-table tbody tr:visible').first()
  const searchedSku = (await firstPart.locator('.supplier-part-name small').innerText()).split('·')[0].trim()
  const partSearch = page.getByRole('searchbox', { name: "Search this supplier's parts by name, SKU, or reference" })
  const partSearchResponse = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname.endsWith(`/suppliers/${supplierId}/parts`)
      && url.searchParams.get('q') === searchedSku
      && response.status() === 200
  }, { timeout: 45_000 })
  await partSearch.fill(searchedSku)
  await partSearchResponse
  await expect(page.locator('.supplier-part-table tbody tr:visible')).toHaveCount(1)
  await expect(page.getByText('Showing 1–1 of 1', { exact: true })).toBeVisible()
  await capture(1440, 1000, 'supplier-parts-search-1440.png')

  const termsResponse = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname.endsWith('/terms') && response.status() === 200
  }, { timeout: 45_000 })
  await page.getByRole('button', { name: /View terms/ }).first().click()
  const termsPayload = await (await termsResponse).json()
  if (!Array.isArray(termsPayload.terms) || !termsPayload.terms.length) throw new Error('The selected showroom part had no readable vendor terms.')
  await expect(page.getByText('Configured price').first()).toBeVisible()
  await capture(1440, 1000, 'supplier-vendor-terms-1440.png')
  await capture(390, 844, 'supplier-vendor-terms-390.png')
  await page.keyboard.press('Escape')

  await page.goto(`${frontendUrl}/suppliers/missing`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Parts without a supplier', level: 1 })).toBeVisible({ timeout: 45_000 })
  await expect(page.locator('.supplier-gap-banner strong')).toBeVisible({ timeout: 45_000 })
  await expect(page.locator('.supplier-part-table tbody tr:visible, .supplier-part-mobile-list .supplier-part-card:visible').first()).toBeVisible({ timeout: 45_000 })
  await capture(1440, 1000, 'supplier-gaps-1440.png')
  await capture(1024, 900, 'supplier-gaps-1024.png')
  await capture(390, 844, 'supplier-gaps-390.png')

  if (pageErrors.length || consoleErrors.length || apiFailures.length) {
    throw new Error(JSON.stringify({ pageErrors, consoleErrors, apiFailures }, null, 2))
  }
  console.log(`Captured ${captures.length} live Atlas showroom screenshots in docs/qa/screenshots/issue-32-gate-6.`)
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
