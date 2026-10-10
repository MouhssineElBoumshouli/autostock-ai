import { readFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, expect } from '@playwright/test'

const frontendDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryDirectory = path.resolve(frontendDirectory, '..')
const credentialPath = path.join(repositoryDirectory, '.showroom', 'credentials.txt')
const outputDirectory = path.join(repositoryDirectory, 'docs', 'qa', 'screenshots', 'issue-26-gate-3')
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
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, colorScheme: 'light' })
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

async function settleLayout() {
  await page.evaluate(async () => {
    await document.fonts.ready
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  })
}

async function captureDashboard(viewport) {
  await page.setViewportSize({ width: viewport.width, height: viewport.height })
  await settleLayout()
  const layout = await page.evaluate(() => {
    const plot = document.querySelector('[data-testid="forecast-plot"] svg')
    const plotContainer = document.querySelector('[data-testid="forecast-plot"]')
    return {
      viewport: window.innerWidth,
      pageWidth: document.documentElement.scrollWidth,
      plotWidth: plot?.getBoundingClientRect().width ?? 0,
      plotContainerWidth: plotContainer?.getBoundingClientRect().width ?? 0,
      kpis: Array.from(document.querySelectorAll('.kpi-card .kpi-value'), (node) => node.textContent?.trim() ?? ''),
      restockPositions: document.querySelectorAll('.reorder-table tbody tr').length,
    }
  })
  if (layout.pageWidth > viewport.width) throw new Error(`Dashboard overflows horizontally at ${viewport.width}px.`)
  if (layout.plotWidth < layout.plotContainerWidth - 2) throw new Error(`Forecast plot does not fill the available width at ${viewport.width}px.`)
  if (layout.kpis.length !== 5) throw new Error(`Expected five live KPI cards at ${viewport.width}px.`)
  const fileName = `dashboard-${viewport.name}.png`
  await page.screenshot({ path: path.join(outputDirectory, fileName), fullPage: true, animations: 'disabled' })
  return { viewport: viewport.width, plotWidth: Math.round(layout.plotWidth), restockPositions: layout.restockPositions, fileName }
}

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
  await page.locator('.kpi-card').first().waitFor({ timeout: 45_000 })
  await page.locator('[data-testid="forecast-plot"] svg, .dashboard-chart-state').first().waitFor({ timeout: 45_000 })
  await page.locator('.health-donut').waitFor({ timeout: 45_000 })
  await page.locator('.reorder-table tbody tr').first().waitFor({ timeout: 45_000 })
  await expect(page.getByText('Demo environment', { exact: true })).toBeVisible()

  const evidence = []
  for (const viewport of [
    { width: 1440, height: 1000, name: '1440' },
    { width: 1024, height: 900, name: '1024' },
    { width: 390, height: 844, name: '390' },
  ]) evidence.push(await captureDashboard(viewport))

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.keyboard.press('Control+k')
  const searchDialog = page.getByRole('dialog', { name: 'Search AutoStock' })
  await searchDialog.waitFor({ timeout: 10_000 })
  const firstPart = page.locator('.reorder-table tbody tr').first()
  const searchTerm = (await firstPart.locator('.sku-cell').innerText()).trim()
  const searchInput = searchDialog.getByRole('combobox', { name: 'Search parts, SKUs, suppliers, and references' })
  await searchInput.fill(searchTerm)
  const searchResult = searchDialog.getByRole('option').first()
  await searchResult.waitFor({ timeout: 20_000 })
  const searchProductName = (await searchResult.locator('.search-result-copy strong').innerText()).trim()
  await settleLayout()
  await page.screenshot({ path: path.join(outputDirectory, 'search-open-1440.png'), fullPage: false, animations: 'disabled' })
  await searchInput.press('ArrowDown')
  await searchInput.press('Enter')
  await page.getByRole('dialog', { name: new RegExp(searchProductName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).waitFor({ timeout: 20_000 })
  await page.keyboard.press('Escape')

  const forecastHorizon = page.getByLabel('Forecast horizon')
  const forecastRequest = page.waitForResponse((response) => {
    const url = new URL(response.url())
    return url.pathname.endsWith('/dashboard/forecast-preview') && url.searchParams.get('horizon_days') === '7'
  })
  await forecastHorizon.selectOption('7')
  await forecastRequest
  await settleLayout()
  const plot = page.getByTestId('forecast-plot')
  if (await plot.isVisible().catch(() => false)) {
    const bounds = await plot.boundingBox()
    if (bounds) await page.mouse.move(bounds.x + bounds.width * 0.8, bounds.y + bounds.height * 0.4)
  }
  await page.screenshot({ path: path.join(outputDirectory, 'forecast-interaction-1440.png'), fullPage: false, animations: 'disabled' })

  await forecastHorizon.selectOption('30')
  await expect(page.getByTestId('forecast-selection-status')).toHaveText(/next 30 days/i)
  await page.locator('[data-testid="forecast-plot"] svg, .dashboard-chart-state').first().waitFor({ timeout: 15_000 })
  const recommendationButton = page.locator('.reorder-table tbody tr').first().locator('.part-name')
  const recommendationName = (await recommendationButton.innerText()).split('\n')[0].trim()
  await recommendationButton.click()
  await page.getByRole('dialog', { name: new RegExp(recommendationName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).waitFor({ timeout: 20_000 })
  await settleLayout()
  await page.screenshot({ path: path.join(outputDirectory, 'reorder-detail-1440.png'), fullPage: false, animations: 'disabled' })
  await page.keyboard.press('Escape')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: 'Open navigation menu' }).click()
  await page.getByRole('dialog', { name: 'AutoStock navigation' }).waitFor({ timeout: 10_000 })
  await page.screenshot({ path: path.join(outputDirectory, 'mobile-navigation-390.png'), fullPage: false, animations: 'disabled' })
  await page.keyboard.press('Escape')

  if (pageErrors.length) throw new Error(`Browser page errors: ${pageErrors.join(' | ')}`)
  if (consoleErrors.length) throw new Error(`Browser console errors: ${consoleErrors.join(' | ')}`)
  if (failedApiResponses.length) throw new Error(`Odoo API errors: ${failedApiResponses.join(' | ')}`)
  for (const item of evidence) console.log(`Captured ${item.fileName}: ${item.viewport}px, chart ${item.plotWidth}px, ${item.restockPositions} real restock positions.`)
  console.log('Authenticated showroom interactions passed: product search and quick view, 7-day forecast selection, reorder details, and mobile navigation. Page/console errors: 0. API failures: 0.')
} finally {
  await context.close()
  await browser.close()
}
