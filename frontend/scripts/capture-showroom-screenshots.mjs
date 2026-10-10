import { readFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryDirectory = path.resolve(frontendDirectory, '..')
const credentialPath = path.join(repositoryDirectory, '.showroom', 'credentials.txt')
const outputDirectory = path.join(repositoryDirectory, 'docs', 'qa', 'screenshots', 'react-dashboard')
const frontendUrl = process.env.AUTOSTOCK_FRONTEND_URL || 'http://127.0.0.1:5173'

function parseCredentials(contents) {
  const entries = new Map()
  for (const line of contents.split(/\r?\n/)) {
    const match = line.match(/^\s*([^:=]+?)\s*[:=]\s*(.*?)\s*$/)
    if (match) entries.set(match[1].toLowerCase().replace(/\s+/g, '_'), match[2])
  }
  const credentials = {
    url: entries.get('url'),
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
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 })
const page = await context.newPage()
const pageErrors = []
const consoleErrors = []
const failedApiResponses = []
page.on('pageerror', (error) => pageErrors.push(error.message))
page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()) })
page.on('response', (response) => {
  const pathname = new URL(response.url()).pathname
  if (pathname.startsWith('/autostock/api/v1/') && response.status() >= 400) {
    failedApiResponses.push(`${pathname} returned ${response.status()}`)
  }
})

try {
  await page.goto(frontendUrl, { waitUntil: 'domcontentloaded' })
  const loginTitle = page.getByRole('heading', { name: 'Welcome back' })
  const dashboardTitle = page.getByRole('heading', { name: 'Dashboard' })
  const initialScreen = await Promise.race([
    loginTitle.waitFor({ state: 'visible', timeout: 60_000 }).then(() => 'login'),
    dashboardTitle.waitFor({ state: 'visible', timeout: 60_000 }).then(() => 'dashboard'),
  ])
  if (initialScreen === 'login') {
    await page.getByLabel('Email or username').fill(credentials.login)
    await page.getByLabel('Password', { exact: true }).fill(credentials.password)
    await page.getByRole('button', { name: 'Continue' }).click()
  }

  await dashboardTitle.waitFor({ timeout: 60_000 })
  await page.locator('.kpi-card').first().waitFor()
  await page.locator('.chart-area svg').waitFor({ timeout: 45_000 })
  await page.locator('.health-chart-wrap svg').waitFor({ timeout: 45_000 })
  await page.locator('.reorder-row').first().waitFor({ timeout: 45_000 })
  if (!await page.getByText('Demo environment', { exact: false }).first().isVisible().catch(() => false)) {
    throw new Error('The signed-in company is not marked as a demo environment; no screenshot was written.')
  }

  const evidence = []
  for (const viewport of [
    { width: 1440, height: 1000, name: '1440' },
    { width: 1024, height: 900, name: '1024' },
    { width: 390, height: 844, name: '390' },
  ]) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await page.waitForTimeout(300)
    await page.evaluate(async () => {
      await document.fonts.ready
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    })
    const layout = await page.evaluate(() => {
      const plot = document.querySelector('.chart-area svg')
      const container = document.querySelector('.chart-area')
      const svgWidth = plot?.getBoundingClientRect().width ?? 0
      const style = container ? getComputedStyle(container) : undefined
      const containerWidth = container && style
        ? container.clientWidth - Number.parseFloat(style.paddingLeft) - Number.parseFloat(style.paddingRight)
        : 0
      return {
        viewport: window.innerWidth,
        pageWidth: document.documentElement.scrollWidth,
        svgWidth,
        containerWidth,
        kpis: Array.from(document.querySelectorAll('.kpi-card .kpi-value'), (node) => node.textContent?.trim() ?? ''),
        restockAlerts: document.querySelectorAll('.reorder-row').length,
      }
    })
    if (layout.pageWidth > viewport.width) throw new Error(`Dashboard overflows horizontally at ${viewport.width}px.`)
    if (layout.svgWidth < layout.containerWidth - 4) throw new Error(`Forecast plot is narrower than its container at ${viewport.width}px.`)
    if (layout.kpis.length !== 5) throw new Error(`Expected five live KPI cards at ${viewport.width}px.`)
    const file = path.join(outputDirectory, `dashboard-${viewport.name}.png`)
    await page.screenshot({ path: file, fullPage: true, animations: 'disabled' })
    evidence.push({ viewport: viewport.width, chartWidth: Math.round(layout.svgWidth), kpis: layout.kpis, restockAlerts: layout.restockAlerts, file: path.basename(file) })
  }

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('button', { name: 'Search inventory' }).click()
  await page.getByPlaceholder('Search by part name, SKU, or OEM reference…').fill('AT-FLT-001')
  const showroomProduct = page.getByRole('option', { name: /AT-FLT-001/ })
  await showroomProduct.waitFor({ timeout: 20_000 })
  await page.keyboard.press('Escape')

  const warehousePicker = page.getByLabel('Filter stock alerts by warehouse')
  if (await warehousePicker.isVisible()) {
    const firstWarehouse = warehousePicker.locator('option').nth(1)
    const warehouseId = await firstWarehouse.getAttribute('value')
    const warehouseName = (await firstWarehouse.innerText()).trim()
    if (warehouseId) {
      const filteredResponse = page.waitForResponse((response) => {
        const url = new URL(response.url())
        return url.pathname.endsWith('/dashboard/restock-preview') && url.searchParams.get('warehouse_id') === warehouseId
      })
      await warehousePicker.selectOption(warehouseId)
      if (!(await filteredResponse).ok()) throw new Error('The selected company warehouse filter failed.')
      await page.locator('.reorder-row').first().waitFor({ timeout: 20_000 })
      const alertWarehouses = await page.locator('.reorder-row .reorder-warehouse').allTextContents()
      if (!alertWarehouses.length || alertWarehouses.some((name) => !name.includes(warehouseName))) {
        throw new Error('The restock preview included an item outside the selected showroom warehouse.')
      }
      await warehousePicker.selectOption('')
      await page.waitForFunction((count) => document.querySelectorAll('.reorder-row').length === count, evidence[0].restockAlerts)
      if (await page.locator('.reorder-row').count() !== evidence[0].restockAlerts) {
        throw new Error('The all-warehouses preview did not restore its original results.')
      }
    }
  }

  if (pageErrors.length) throw new Error(`Browser page errors: ${pageErrors.join(' | ')}`)
  if (consoleErrors.length) throw new Error(`Browser console errors: ${consoleErrors.join(' | ')}`)
  if (failedApiResponses.length) throw new Error(`Odoo API errors: ${failedApiResponses.join(' | ')}`)
  for (const item of evidence) console.log(`Captured ${item.file}: ${item.viewport}px, chart ${item.chartWidth}px, ${item.restockAlerts} live restock alerts.`)
  console.log(`Company demo environment verified; database: ${credentials.database}. Live product search and warehouse filter passed. Browser page/console errors: 0. API failures: 0.`)
} finally {
  await context.close()
  await browser.close()
}
