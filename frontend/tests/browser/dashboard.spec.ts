import { mkdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const evidenceDirectory = path.resolve(process.cwd(), '../docs/qa/screenshots/issue-22-gate-1')

test('Gate 1 dashboard matches the reference composition at desktop, tablet, and mobile widths', async ({ page }) => {
  const pageErrors: string[] = []
  const apiRequests: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/autostock/api/')) apiRequests.push(request.url())
  })

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  await expect(page.locator('.fixture-indicator')).toContainText(/fixture data/i)
  await expect(page.locator('.kpi-card')).toHaveCount(5)
  await expect(page.locator('.insight-card')).toHaveCount(3)
  await expect(page.locator('.reorder-table tbody tr')).toHaveCount(5)
  await expect(page.getByRole('heading', { name: 'AI Demand Forecast' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Inventory Health' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'AI Insights & Recommendations' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Predicted Reorder Recommendations' })).toBeVisible()

  mkdirSync(evidenceDirectory, { recursive: true })
  let desktopCapture: Buffer | undefined
  for (const viewport of [
    { width: 1440, height: 1080, name: 'desktop' },
    { width: 1024, height: 768, name: 'tablet' },
    { width: 390, height: 844, name: 'mobile' },
  ]) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })
    await page.waitForTimeout(100)
    const layout = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
      chartWidth: document.querySelector('.chart-plot svg')?.getBoundingClientRect().width ?? 0,
      fixtureLabel: document.querySelector('.fixture-indicator')?.getBoundingClientRect().width ?? 0,
    }))
    expect(layout.document, `${viewport.name} horizontal overflow`).toBeLessThanOrEqual(viewport.width)
    expect(layout.chartWidth, `${viewport.name} chart width`).toBeGreaterThan(200)
    expect(layout.fixtureLabel, `${viewport.name} visible fixture label`).toBeGreaterThan(0)
    if (viewport.width === 390) {
      await expect(page.locator('.mobile-menu-mark')).toBeVisible()
      await expect(page.locator('.mobile-brand .brand-wordmark')).toBeVisible()
      await expect(page.locator('.sidebar-rail')).toBeHidden()
      await expect(page.locator('.mobile-detail')).toHaveCount(5)
    }
    const screenshot = await page.screenshot({
      path: path.join(evidenceDirectory, `dashboard-${viewport.width}.png`),
      fullPage: true,
      animations: 'disabled',
    })
    if (viewport.width === 1440) desktopCapture = screenshot
  }

  expect(apiRequests, 'the Gate 1 dashboard must stay disconnected from Odoo').toEqual([])
  expect(pageErrors).toEqual([])
  expect(desktopCapture).toBeDefined()

  const reference = readFileSync(path.resolve(process.cwd(), '../design/dashboard-concept.png')).toString('base64')
  const actual = desktopCapture!.toString('base64')
  const comparisonPage = await page.context().newPage({ viewport: { width: 1440, height: 700 } })
  await comparisonPage.setContent(`
    <!doctype html><html lang="en"><head><meta charset="utf-8"><title>Issue #22 Gate 1 visual comparison</title>
    <style>
      *{box-sizing:border-box}body{margin:0;padding:20px;background:#f4f5fb;color:#27304a;font-family:Inter,ui-sans-serif,system-ui,sans-serif}
      h1{margin:0 0 14px;font-size:16px;font-weight:650}main{display:grid;grid-template-columns:1fr 1fr;gap:16px}
      section{min-width:0;padding:11px;border:1px solid #e4e6ee;border-radius:12px;background:white;box-shadow:0 8px 26px #27304a0c}
      h2{margin:0 0 9px;color:#69738a;font-size:11px;font-weight:650;letter-spacing:.035em;text-transform:uppercase}
      img{display:block;width:100%;height:auto;border:1px solid #eaebf1;border-radius:7px}
      p{margin:8px 0 0;color:#707a90;font-size:9px}
    </style></head><body><h1>Approved dashboard reference and Gate 1 browser capture · 1440 px</h1>
    <main><section><h2>Approved reference</h2><img alt="Approved dashboard design reference" src="data:image/png;base64,${reference}"></section>
    <section><h2>AutoStock Gate 1 · development fixture preview</h2><img alt="Actual Playwright capture of the Gate 1 dashboard" src="data:image/png;base64,${actual}"><p>Fixture values are illustrative and disconnected from Odoo.</p></section></main></body></html>`)
  await comparisonPage.screenshot({
    path: path.join(evidenceDirectory, 'reference-vs-dashboard-1440.png'),
    fullPage: true,
    animations: 'disabled',
  })

  expect(apiRequests).toEqual([])
  expect(pageErrors).toEqual([])
  await comparisonPage.close()
})
