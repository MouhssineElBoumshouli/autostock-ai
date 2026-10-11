import { readFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, expect } from '@playwright/test'

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryDirectory = path.resolve(frontendDirectory, '..')
const credentialPath = path.join(repositoryDirectory, '.showroom', 'credentials.txt')
const outputDirectory = path.join(repositoryDirectory, 'docs', 'qa', 'screenshots', 'issue-28-gate-4')
const frontendUrl = process.env.AUTOSTOCK_FRONTEND_URL || 'http://127.0.0.1:5173'

function parseCredentials(contents) {
  const entries = new Map()
  for (const line of contents.split(/\r?\n/)) {
    const match = line.match(/^\s*([^:=]+?)\s*[:=]\s*(.*?)\s*$/)
    if (match) entries.set(match[1].toLowerCase().replace(/\s+/g, '_'), match[2])
  }
  const credentials = {
    database: entries.get('database'),
    login: entries.get('login'),
    password: entries.get('password'),
  }
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
page.on('pageerror', (error) => pageErrors.push(error.message))
page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push(message.text())
})
page.on('response', (response) => {
  const pathname = new URL(response.url()).pathname
  if (pathname.startsWith('/autostock/api/v1/') && response.status() >= 400) {
    apiFailures.push(pathname + ' returned ' + response.status())
  }
})

async function settleLayout() {
  await page.evaluate(async () => {
    await document.fonts.ready
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  })
}

async function capture(viewport, fileName, fullPage = true) {
  await page.setViewportSize({ width: viewport.width, height: viewport.height })
  await settleLayout()
  const width = await page.evaluate(() => document.documentElement.scrollWidth)
  if (width > viewport.width) throw new Error('Inventory page overflows horizontally at ' + viewport.width + 'px.')
  await page.screenshot({
    path: path.join(outputDirectory, fileName),
    fullPage,
    animations: 'disabled',
  })
  return fileName
}

try {
  await page.goto(frontendUrl + '/inventory', { waitUntil: 'domcontentloaded' })
  const loginTitle = page.getByRole('heading', { name: 'Welcome back' })
  const inventoryTitle = page.getByRole('heading', { name: 'Inventory', level: 1 })
  const firstScreen = await Promise.race([
    loginTitle.waitFor({ state: 'visible', timeout: 60_000 }).then(() => 'login'),
    inventoryTitle.waitFor({ state: 'visible', timeout: 60_000 }).then(() => 'inventory'),
  ])
  if (firstScreen === 'login') {
    await page.getByLabel('Email or username').fill(credentials.login)
    await page.getByLabel('Password', { exact: true }).fill(credentials.password)
    await page.getByRole('button', { name: 'Continue' }).click()
  }

  await inventoryTitle.waitFor({ timeout: 60_000 })
  await page.getByRole('heading', { name: 'Parts catalog' }).waitFor({ timeout: 45_000 })
  await page.locator('.inventory-part-link').first().waitFor({ timeout: 45_000 })
  await expect(page.getByText('Demo environment', { exact: true })).toBeVisible()
  await expect(page.getByText('Atlas Auto Distribution', { exact: false }).first()).toBeVisible()
  const initialCount = await page.locator('[data-testid="inventory-row"]').count()
  if (!initialCount) throw new Error('The showroom catalog returned no visible products.')

  const captures = []
  captures.push(await capture({ width: 1440, height: 1000 }, 'inventory-desktop-1440.png'))
  captures.push(await capture({ width: 1024, height: 900 }, 'inventory-tablet-1024.png'))
  captures.push(await capture({ width: 390, height: 844 }, 'inventory-mobile-390.png'))

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('combobox', { name: 'Filter by stock status' }).selectOption('low_stock')
  await page.locator('.inventory-status.is-low_stock').first().waitFor({ timeout: 20_000 })
  captures.push(await capture({ width: 1440, height: 1000 }, 'inventory-low-stock-1440.png'))
  await page.getByRole('combobox', { name: 'Filter by stock status' }).selectOption('all')
  await page.locator('[data-testid="inventory-row"]').first().waitFor({ timeout: 15_000 })

  const firstSku = (await page.locator('.inventory-cell-sku').first().innerText()).trim()
  const filteredInventoryResponse = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname === '/autostock/api/v1/inventory'
      && url.searchParams.get('q') === firstSku
      && response.status() === 200
  }, { timeout: 30_000 })
  await page.getByRole('searchbox', { name: /Search by part name/ }).fill(firstSku)
  await filteredInventoryResponse
  await expect(page.locator('.inventory-results-bar > div:first-child > strong')).toHaveText('1', { timeout: 20_000 })
  await expect(page.locator('.inventory-results-bar > div:first-child > span').first()).toHaveText('part match your filters')
  const filteredRows = page.locator('[data-testid="inventory-row"]:visible')
  await expect(filteredRows).toHaveCount(1, { timeout: 20_000 })
  await expect(filteredRows.first()).toContainText(firstSku)
  captures.push(await capture({ width: 1440, height: 1000 }, 'inventory-filtered-1440.png'))

  await page.getByRole('button', { name: 'Clear filters' }).first().click()
  await page.locator('[data-testid="inventory-row"]').first().waitFor({ timeout: 15_000 })
  await page.locator('.inventory-part-link').first().click()
  await page.getByRole('heading', { name: 'Company-wide stock' }).waitFor({ timeout: 20_000 })
  await page.getByRole('heading', { name: 'Stock by warehouse' }).waitFor({ timeout: 20_000 })
  captures.push(await capture({ width: 1440, height: 1000 }, 'inventory-product-detail-1440.png', false))
  await page.locator('.inventory-detail-sheet').evaluate((element) => { element.scrollTop = element.scrollHeight })
  await expect(page.getByRole('heading', { name: 'Recent stock activity' })).toBeInViewport({ timeout: 10_000 })
  captures.push(await capture({ width: 1440, height: 1000 }, 'inventory-product-detail-lower-1440.png', false))
  await page.keyboard.press('Escape')
  await page.locator('.inventory-detail-sheet').waitFor({ state: 'hidden', timeout: 5_000 })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.locator('.inventory-mobile-card').first().waitFor({ state: 'visible', timeout: 10_000 })
  await page.locator('.inventory-mobile-card').first().click()
  await page.getByRole('heading', { name: 'Company-wide stock' }).waitFor({ timeout: 20_000 })
  await expect(page.locator('.inventory-detail-metrics')).toHaveCSS('display', 'grid')
  captures.push(await capture({ width: 390, height: 844 }, 'inventory-product-detail-390.png', false))
  await page.keyboard.press('Escape')
  await page.locator('.inventory-detail-sheet').waitFor({ state: 'hidden', timeout: 5_000 })

  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  await page.getByRole('dialog', { name: 'AutoStock navigation' }).waitFor({ timeout: 10_000 })
  captures.push(await capture({ width: 390, height: 844 }, 'inventory-mobile-navigation-390.png', false))
  await page.keyboard.press('Escape')

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('searchbox', { name: /Search by part name/ }).fill('AUTOSTOCK-ISSUE-28-NO-MATCH')
  await page.getByRole('heading', { name: 'No parts match these filters' }).waitFor({ timeout: 20_000 })
  captures.push(await capture({ width: 1440, height: 1000 }, 'inventory-no-results-1440.png'))

  if (pageErrors.length) throw new Error('Browser page errors: ' + pageErrors.join(' | '))
  if (consoleErrors.length) throw new Error('Browser console errors: ' + consoleErrors.join(' | '))
  if (apiFailures.length) throw new Error('Inventory API failures: ' + apiFailures.join(' | '))
  console.log('Captured real showroom inventory screenshots: ' + captures.join(', '))
  console.log('Initial visible catalog rows: ' + initialCount + '. Authenticated Odoo API failures: 0. Browser page and console errors: 0.')
} finally {
  await context.close()
  await browser.close()
}
