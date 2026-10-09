import { mkdir } from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const playwrightModule = process.env.PLAYWRIGHT_MODULE || "playwright";
const { chromium } = require(playwrightModule);

const baseUrl = (process.env.AUTOSTOCK_QA_URL || "http://127.0.0.1:8175").replace(/\/$/, "");
const database = process.env.AUTOSTOCK_QA_DB || "autostock_phase2_demo";
const login = process.env.AUTOSTOCK_QA_LOGIN;
const password = process.env.AUTOSTOCK_QA_PASSWORD;
const browserExecutable = process.env.AUTOSTOCK_QA_BROWSER;
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const screenshotDir = path.resolve(
    process.env.AUTOSTOCK_QA_SCREENSHOT_DIR || path.join(repoRoot, "docs/qa/screenshots/phase2-5")
);

if (!login || !password) {
    throw new Error("Set AUTOSTOCK_QA_LOGIN and AUTOSTOCK_QA_PASSWORD for the local Odoo QA user.");
}
if (!/^https?:\/\/((127\.0\.0\.1)|(localhost))(:\d+)?$/.test(baseUrl)) {
    throw new Error("Browser QA accepts only an Odoo server bound to localhost.");
}

await mkdir(screenshotDir, { recursive: true });
const browser = await chromium.launch({
    headless: true,
    ...(browserExecutable ? { executablePath: browserExecutable } : {}),
});
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce" });
let companyOptionsTransform = null;
let releaseStaleSnapshot = null;
await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.includes("get_forecast_options") && companyOptionsTransform) {
        const response = await route.fetch();
        const payload = await response.json();
        companyOptionsTransform(payload.result);
        await route.fulfill({ response, json: payload });
        return;
    }
    await route.continue();
});
const page = await context.newPage();
page.setDefaultTimeout(10000);
page.setDefaultNavigationTimeout(20000);
const browserErrors = [];
let testPhase = "login and dashboard load";
page.on("console", (message) => {
    if (message.type() === "error") {
        browserErrors.push(`console: ${message.text()}`);
    }
});
page.on("pageerror", (error) => browserErrors.push(`page: ${error.message}`));

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function shiftUtcDay(value, amount) {
    const date = new Date(`${value}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() + amount);
    return date.toISOString().slice(0, 10);
}

async function dashboardActionId() {
    const response = await context.request.post(`${baseUrl}/web/dataset/call_kw/ir.model.data/search_read`, {
        data: {
            jsonrpc: "2.0",
            method: "call",
            params: {
                model: "ir.model.data",
                method: "search_read",
                args: [[
                    ["module", "=", "autostock_ai"],
                    ["name", "=", "action_autostock_dashboard"],
                ], ["res_id"]],
                kwargs: { limit: 1 },
            },
            id: 1,
        },
    });
    const payload = await response.json();
    const record = payload.result?.[0];
    assert(response.ok() && record?.res_id, "Could not resolve the installed AutoStock dashboard action.");
    return record.res_id;
}

async function openDashboard(actionId) {
    await page.goto(`${baseUrl}/web#action=${actionId}`, { waitUntil: "domcontentloaded" });
    try {
        await page.locator(".as-app").waitFor({ timeout: 10000 });
    } catch (error) {
        const details = page.getByText("See technical details", { exact: true });
        if (await details.count()) {
            await details.click();
            await page.waitForTimeout(100);
        }
        const state = await page.evaluate(() => ({
            title: document.title,
            body: document.body?.innerText?.slice(0, 1600),
        }));
        console.log(JSON.stringify({ actionRoute: page.url(), state, browserErrors }));
        throw error;
    }
    await page.locator(".as-kpis").waitFor({ timeout: 20000 });
    await page.locator(".as-sidebar-status.is-connected").waitFor({ timeout: 20000 });
}

async function clickNavigation(label, mobile) {
    if (mobile) {
        await page.getByRole("button", { name: "Open AutoStock navigation" }).click();
        const dialog = page.getByRole("dialog", { name: "AutoStock AI navigation" });
        await dialog.waitFor();
        await dialog.getByRole("button", { name: label, exact: true }).click();
    } else {
        await page.getByRole("button", { name: label, exact: true }).click();
    }
}

async function takeScreenshot(filename) {
    await page.screenshot({
        path: path.join(screenshotDir, filename),
        type: "jpeg",
        quality: 88,
        fullPage: false,
    });
}

async function measureChartGeometry() {
    return page.locator(".as-forecast-chart").evaluate((svg) => {
        const round = (value) => Math.round(value * 100) / 100;
        const svgRect = svg.getBoundingClientRect();
        const panel = svg.closest(".as-forecast-panel");
        const figure = svg.closest(".as-forecast-figure");
        const panelRect = panel.getBoundingClientRect();
        const panelStyle = getComputedStyle(panel);
        const panelContentWidth = panelRect.width
            - parseFloat(panelStyle.borderLeftWidth)
            - parseFloat(panelStyle.borderRightWidth)
            - parseFloat(panelStyle.paddingLeft)
            - parseFloat(panelStyle.paddingRight);
        const matrix = svg.getScreenCTM();
        const boundsFor = (selector) => {
            const points = [...svg.querySelectorAll(selector)].flatMap((element) => {
                const box = element.getBBox();
                const corners = [
                    [box.x, box.y],
                    [box.x + box.width, box.y],
                    [box.x, box.y + box.height],
                    [box.x + box.width, box.y + box.height],
                ];
                return corners.map(([x, y]) => {
                    const point = svg.createSVGPoint();
                    point.x = x;
                    point.y = y;
                    return point.matrixTransform(matrix);
                });
            });
            const left = Math.min(...points.map((point) => point.x));
            const right = Math.max(...points.map((point) => point.x));
            const top = Math.min(...points.map((point) => point.y));
            const bottom = Math.max(...points.map((point) => point.y));
            return {
                left: round(left - svgRect.left),
                right: round(right - svgRect.left),
                width: round(right - left),
                top: round(top - svgRect.top),
                bottom: round(bottom - svgRect.top),
                height: round(bottom - top),
            };
        };
        const axes = boundsFor(".as-chart-axis");
        const plot = boundsFor(".as-chart-axis, .as-chart-gridline, .as-chart-edge, .as-chart-history, .as-chart-prediction, .as-chart-band");
        return {
            viewport: { width: window.innerWidth, height: window.innerHeight },
            panelWidth: round(panelRect.width),
            panelContentWidth: round(panelContentWidth),
            expectedChartWidthFromObserver: round(panelContentWidth - 28),
            figureWidth: round(figure.getBoundingClientRect().width),
            svg: { width: round(svgRect.width), height: round(svgRect.height) },
            viewBox: svg.getAttribute("viewBox"),
            viewBoxWidth: round(svg.viewBox.baseVal.width),
            viewBoxHeight: round(svg.viewBox.baseVal.height),
            preserveAspectRatio: svg.getAttribute("preserveAspectRatio") || "xMidYMid meet (SVG default)",
            axes,
            plot,
            plotWidthUtilization: round(plot.width / svgRect.width),
            axisWidthUtilization: round(axes.width / svgRect.width),
            plotFigureUtilization: round(plot.width / figure.getBoundingClientRect().width),
        };
    });
}

async function waitForChartWidthSync() {
    await page.waitForFunction(() => {
        const svg = document.querySelector(".as-forecast-chart");
        return svg && Math.abs(svg.viewBox.baseVal.width - Math.round(svg.getBoundingClientRect().width)) <= 1;
    });
}

function assertChartUsesAvailableWidth(label, geometry) {
    assert(
        geometry.plotFigureUtilization >= 0.68,
        `${label} plot uses only ${(geometry.plotFigureUtilization * 100).toFixed(1)}% of its figure width: ${JSON.stringify(geometry)}`
    );
    assert(
        Math.abs(geometry.viewBoxWidth - Math.round(geometry.svg.width)) <= 1,
        `${label} SVG viewBox (${geometry.viewBoxWidth}) does not track its rendered width (${geometry.svg.width}): ${JSON.stringify(geometry)}`
    );
}

try {
    await page.goto(`${baseUrl}/web/login?db=${encodeURIComponent(database)}`, { waitUntil: "domcontentloaded" });
    await page.locator('input[name="login"], #login').first().fill(login);
    await page.locator('input[name="password"], #password').first().fill(password);
    await page.locator('form button[type="submit"]').click();
    await page.locator(".o_main_navbar").waitFor({ timeout: 30000 });

    const actionId = await dashboardActionId();
    await openDashboard(actionId);
    await page.locator(".as-sidebar-status.is-connected").waitFor();
    assert((await page.locator(".as-sidebar-status").innerText()).includes("Connected to Odoo"), "The connected Odoo status was not shown after successful RPCs.");
    const pageText = await page.locator(".as-app").innerText();
    assert(pageText.includes("Live Odoo inventory data"), "Dashboard is not displaying live Odoo inventory data.");
    assert(pageText.includes("DEMO-QA-BP-001"), "The labeled synthetic automotive fixture is not visible in the inventory table.");
    assert(pageText.includes("[SYNTHETIC QA]"), "Inventory sample records are not visibly labeled synthetic.");

    const chart = page.locator(".as-forecast-figure");
    if (!(await chart.count())) {
        await page.getByRole("button", { name: "Run synthetic demo" }).click();
        await chart.waitFor({ timeout: 90000 });
    }
    assert(await page.locator(".as-pill-demo").count(), "The forecast chart is missing its synthetic data label.");

    const resolutions = [
        { name: "desktop", width: 1440, height: 1000, mobile: false },
        { name: "tablet", width: 1024, height: 900, mobile: false },
        { name: "mobile", width: 390, height: 844, mobile: true },
    ];
    for (const viewport of resolutions) {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        await page.waitForTimeout(150);
        await page.locator(".as-page-scroll").evaluate((element) => { element.scrollTop = 0; });
        const overflow = await page.evaluate(() => ({
            viewport: window.innerWidth,
            document: document.documentElement.scrollWidth,
            app: document.querySelector(".as-app").scrollWidth,
            appClient: document.querySelector(".as-app").clientWidth,
        }));
        assert(
            overflow.document <= overflow.viewport + 1 && overflow.app <= overflow.appClient + 1,
            `${viewport.name} layout overflows horizontally: ${JSON.stringify(overflow)}`
        );
        await takeScreenshot(`phase2-5-dashboard-${viewport.name}.jpg`);

        await clickNavigation("Forecasts", viewport.mobile);
        await page.locator(".as-forecast-panel").waitFor();
        assert((await page.locator(".as-appbar-context strong").innerText()) === "Dashboard", `${viewport.name} breadcrumb did not identify the dashboard route.`);
        assert((await page.locator(".as-topline h1").innerText()) === "Dashboard", `${viewport.name} page heading no longer identifies the current dashboard page.`);
        await page.locator(".as-forecast-figure").scrollIntoViewIfNeeded();
        await page.getByRole("button", { name: "30 days", exact: true }).click();
        await page.waitForFunction(() => document.querySelector(".as-chart-window-label")?.textContent.trim().startsWith("30 of "));
        await waitForChartWidthSync();
        assert((await page.locator(".as-chart-window-label").innerText()).startsWith("30 of "), `${viewport.name} 30-day chart window did not update.`);
        const chart30Geometry = await measureChartGeometry();
        assertChartUsesAvailableWidth(`${viewport.name} 30-day chart`, chart30Geometry);
        await page.getByRole("button", { name: "90 days", exact: true }).click();
        await page.waitForFunction(() => document.querySelector(".as-chart-window-label")?.textContent.trim().startsWith("90 of "));
        const chartLabel = await page.locator(".as-chart-window-label").innerText();
        assert(chartLabel.startsWith("90 of "), `${viewport.name} chart range did not update: ${chartLabel}`);
        assert(
            (await page.locator(".as-forecast-chart").getAttribute("aria-label"))?.includes("90 of"),
            `${viewport.name} chart accessibility label did not update with its history range.`
        );
        await page.getByRole("button", { name: "Full", exact: true }).click();
        await page.waitForFunction(() => document.querySelector(".as-chart-window-label")?.textContent.trim().startsWith("210 of "));
        await waitForChartWidthSync();
        assert((await page.locator(".as-chart-window-label").innerText()).startsWith("210 of "), `${viewport.name} full chart window did not restore all available history.`);
        const chartFullGeometry = await measureChartGeometry();
        assertChartUsesAvailableWidth(`${viewport.name} full-history chart`, chartFullGeometry);
        await page.getByRole("button", { name: "30 days", exact: true }).click();
        await page.waitForFunction(() => document.querySelector(".as-chart-window-label")?.textContent.trim().startsWith("30 of "));
        await takeScreenshot(`phase2-5-forecast-${viewport.name}.jpg`);

        await page.locator(".as-table-panel").scrollIntoViewIfNeeded();
        const tableRows = await page.locator(".as-table tbody tr").count();
        assert(tableRows >= 5, `${viewport.name} inventory table does not contain the synthetic stock records.`);
        await takeScreenshot(`phase2-5-inventory-${viewport.name}.jpg`);

        if (viewport.mobile) {
            const menuButton = page.getByRole("button", { name: "Open AutoStock navigation" });
            await menuButton.click();
            const drawer = page.getByRole("dialog", { name: "AutoStock AI navigation" });
            await drawer.waitFor();
            await page.waitForTimeout(120);
            const focusState = await page.evaluate(() => ({
                activeTag: document.activeElement?.tagName,
                activeClass: document.activeElement?.className,
                activeId: document.activeElement?.id,
                drawerContainsFocus: document.querySelector("#as-mobile-nav")?.contains(document.activeElement),
            }));
            assert(focusState.drawerContainsFocus, `Mobile navigation did not receive focus: ${JSON.stringify(focusState)}`);
            await page.keyboard.press("Shift+Tab");
            await page.waitForFunction(() => document.activeElement?.textContent?.includes("Forecasts"));
            await page.keyboard.press("Tab");
            await page.waitForFunction(() => document.activeElement?.matches("#as-mobile-nav .as-brand"));
            await takeScreenshot("phase2-5-navigation-mobile.jpg");
            await page.keyboard.press("Escape");
            await page.waitForFunction(() => document.querySelector('[aria-label="Open AutoStock navigation"]')?.getAttribute("aria-expanded") === "false");
        }
    }

    testPhase = "400-day full-history chart regression";
    await page.setViewportSize({ width: 1440, height: 1000 });
    await openDashboard(actionId);

    let expandedHistoryRange = null;
    let extendSyntheticHistory = true;
    const forecastSnapshotRoute = async (route) => {
        const response = await route.fetch();
        const payload = await response.json();
        const run = payload.result?.run;
        if (extendSyntheticHistory && run?.source_type === "synthetic_demo" && run.observations?.length === 210) {
            extendSyntheticHistory = false;
            const original = run.observations;
            const prefixStart = shiftUtcDay(original[0].day, -190);
            const prefix = Array.from({ length: 190 }, (_, index) => {
                const day = shiftUtcDay(prefixStart, index);
                const sample = original[index % original.length];
                return { ...sample, day };
            });
            run.observations = [...prefix, ...original];
            run.history_start = prefix[0].day;
            run.history_days = run.observations.length;
            expandedHistoryRange = { first: prefix[0].day, last: original.at(-1).day };
        }
        await route.fulfill({ response, json: payload });
    };
    await page.route("**/web/dataset/call_kw/autostock.forecast.run/get_forecast_snapshot", forecastSnapshotRoute);
    await page.getByRole("button", { name: "Refresh inventory data" }).click();
    await page.waitForFunction(() => document.querySelector(".as-chart-window-label")?.textContent.trim().startsWith("30 of 400"));
    await page.unroute("**/web/dataset/call_kw/autostock.forecast.run/get_forecast_snapshot", forecastSnapshotRoute);
    assert(expandedHistoryRange, "The synthetic browser fixture was not extended beyond the original 210-day history.");
    await page.getByRole("button", { name: "Full", exact: true }).click();
    await page.waitForFunction(() => document.querySelector(".as-chart-window-label")?.textContent.trim() === "400 of 400 days");
    await waitForChartWidthSync();
    const fullHistoryLabel = await page.locator(".as-forecast-chart").getAttribute("aria-label");
    assert(fullHistoryLabel.includes("400 of 400 history days"), `Full history accessibility label omitted the complete range: ${fullHistoryLabel}`);
    assert(fullHistoryLabel.includes(`from ${expandedHistoryRange.first} through ${expandedHistoryRange.last}`), `Full history accessibility label omitted its date range: ${fullHistoryLabel}`);
    assert(await page.locator(".as-forecast-chart .as-chart-date").count() === 3, "Full chart history rendered crowded date labels instead of spaced start, midpoint, and forecast-end ticks.");
    const firstChartDate = await page.locator(".as-forecast-chart .as-chart-date title").first().textContent();
    assert(firstChartDate === expandedHistoryRange.first, `The full chart starts at ${firstChartDate}, expected ${expandedHistoryRange.first}.`);
    for (const viewport of resolutions) {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        await page.getByRole("button", { name: "30 days", exact: true }).click();
        await page.waitForFunction(() => document.querySelector(".as-chart-window-label")?.textContent.trim() === "30 of 400 days");
        await waitForChartWidthSync();
        const chart30Of400Geometry = await measureChartGeometry();
        assertChartUsesAvailableWidth(`${viewport.name} 400-history 30-day mode`, chart30Of400Geometry);

        await page.getByRole("button", { name: "Full", exact: true }).click();
        await page.waitForFunction(() => document.querySelector(".as-chart-window-label")?.textContent.trim() === "400 of 400 days");
        await waitForChartWidthSync();
        const full400Geometry = await measureChartGeometry();
        assertChartUsesAvailableWidth(`${viewport.name} 400-day Full history`, full400Geometry);
        console.log(`[chart-geometry] ${viewport.name} 400-day 30/full toggle ${JSON.stringify({ thirtyDays: chart30Of400Geometry, fullHistory: full400Geometry })}`);

        await page.locator(".as-forecast-panel").scrollIntoViewIfNeeded();
        await takeScreenshot(`phase2-5-forecast-full-400-${viewport.name}.jpg`);
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await waitForChartWidthSync();
    await page.getByRole("button", { name: "90 days", exact: true }).click();
    await page.waitForFunction(() => document.querySelector(".as-chart-window-label")?.textContent.trim() === "90 of 400 days");
    let changedOptionsResponse = null;
    let previousProductId = "";
    let snapshotRequestCount = 0;
    let capturedStaleSkuResolve;
    let staleResponseAppliedResolve;
    const capturedStaleSku = new Promise((resolve) => { capturedStaleSkuResolve = resolve; });
    const staleResponseApplied = new Promise((resolve) => { staleResponseAppliedResolve = resolve; });
    const holdFirstForecastSnapshot = async (route) => {
        if (snapshotRequestCount++ === 0) {
            const response = await route.fetch();
            const payload = await response.json();
            capturedStaleSkuResolve(payload.result?.run?.sku || null);
            await new Promise((resolve) => { releaseStaleSnapshot = resolve; });
            await route.fulfill({ response, json: payload });
            staleResponseAppliedResolve();
            return;
        }
        await route.continue();
    };
    const provideSameNameCompanyOptions = (options) => {
        if (options?.company_id && options.company_name) {
            changedOptionsResponse = {
                companyId: options.company_id + 1000000,
                companyName: options.company_name,
                today: options.today_utc,
            };
            options.company_id = changedOptionsResponse.companyId;
            const nextProductIndex = options.products.findIndex((product) => String(product.id) !== previousProductId);
            if (previousProductId && nextProductIndex > 0) {
                options.products = [options.products[nextProductIndex], ...options.products.slice(0, nextProductIndex), ...options.products.slice(nextProductIndex + 1)];
            }
            changedOptionsResponse.productId = options.products[0]?.id;
            options.demo_skus = [{ sku: "DEMO-SP-104", name: "Synthetic company switch regression" }];
        }
    };
    testPhase = "same-name company switch while a synthetic chart is visible";
    await page.route("**/web/dataset/call_kw/autostock.forecast.run/get_forecast_snapshot", holdFirstForecastSnapshot);
    await page.locator(".as-forecast-form select").nth(1).evaluate((select) => select.dispatchEvent(new Event("change", { bubbles: true })));
    const capturedSku = await Promise.race([
        capturedStaleSku,
        page.waitForTimeout(10000).then(() => null),
    ]);
    assert(capturedSku === "DEMO-BP-001", "The browser did not capture the old company's pending forecast snapshot.");
    companyOptionsTransform = provideSameNameCompanyOptions;
    await page.getByRole("button", { name: "Refresh inventory data" }).click();
    await page.waitForFunction(() => document.querySelectorAll(".as-forecast-form select")[1]?.value === "DEMO-SP-104");
    assert(changedOptionsResponse, "The same-name company response was not exercised.");
    assert((await page.locator(".as-appbar-company strong").innerText()) === changedOptionsResponse.companyName, "The company display name unexpectedly changed in the same-name regression.");
    assert((await page.locator(".as-forecast-form select").nth(1).inputValue()) === "DEMO-SP-104", "Company switching did not reset the synthetic SKU to the new company's option.");
    assert((await page.locator(".as-forecast-form select").nth(2).inputValue()) === "30", "Company switching retained the previous forecast horizon.");
    assert((await page.locator(".as-sidebar-status").innerText()).includes("Connected to Odoo"), "A successful company refresh did not report Odoo connectivity.");
    if (!(await page.locator(".as-forecast-chart").count())) {
        await page.getByRole("button", { name: "Run synthetic demo" }).click();
        await page.locator(".as-forecast-chart").waitFor({ timeout: 90000 });
    }
    releaseStaleSnapshot();
    await staleResponseApplied;
    await page.waitForTimeout(100);
    const currentForecastLabel = await page.locator(".as-forecast-chart").getAttribute("aria-label");
    assert(currentForecastLabel.includes("for DEMO-SP-104"), "A late response replaced the new company's forecast.");
    assert(!currentForecastLabel.includes("for DEMO-BP-001"), "A late response restored the previous company's forecast.");
    await page.unroute("**/web/dataset/call_kw/autostock.forecast.run/get_forecast_snapshot", holdFirstForecastSnapshot);
    companyOptionsTransform = null;

    await openDashboard(actionId);
    if (!(await page.locator(".as-forecast-chart").count())) {
        await page.getByRole("button", { name: "Run synthetic demo" }).click();
        await page.locator(".as-forecast-chart").waitFor({ timeout: 90000 });
    }
    let changedFiltersResponse = null;
    const remapSameNameCompanyFilters = (options) => {
        if (options?.company_id && options.company_name) {
            changedFiltersResponse = {
                companyId: options.company_id + 2000000,
                companyName: options.company_name,
                today: options.today_utc,
            };
            options.company_id = changedFiltersResponse.companyId;
            const nextProductIndex = options.products.findIndex((product) => String(product.id) !== previousProductId);
            if (nextProductIndex > 0) {
                options.products = [options.products[nextProductIndex], ...options.products.slice(0, nextProductIndex), ...options.products.slice(nextProductIndex + 1)];
            }
            changedFiltersResponse.productId = options.products[0]?.id;
            options.demo_skus = [{ sku: "DEMO-SP-104", name: "Synthetic company switch regression" }];
        }
    };
    const filterSelects = page.locator(".as-forecast-form select");
    testPhase = "setting company-bound filters before the same-name switch";
    await filterSelects.nth(0).selectOption("completed_deliveries");
    await filterSelects.nth(1).selectOption({ index: 1 });
    previousProductId = await filterSelects.nth(1).inputValue();
    const oldWarehouseId = await filterSelects.nth(2).locator("option").nth(1).getAttribute("value");
    assert(previousProductId && oldWarehouseId, "The demo company must provide a synthetic product and warehouse for the switch test.");
    await filterSelects.nth(2).selectOption(oldWarehouseId);
    await filterSelects.nth(3).selectOption("60");
    const dateFields = page.locator(".as-forecast-form input[type=date]");
    const activeCompanyToday = await dateFields.nth(1).getAttribute("max");
    await dateFields.nth(0).fill(shiftUtcDay(activeCompanyToday, -10));
    await dateFields.nth(1).fill(shiftUtcDay(activeCompanyToday, -2));
    companyOptionsTransform = remapSameNameCompanyFilters;
    testPhase = "resetting company-bound filters after the company ID changes";
    await page.getByRole("button", { name: "Refresh inventory data" }).click();
    await page.waitForFunction(() => document.querySelectorAll(".as-forecast-form select")[1]?.value === "DEMO-SP-104");
    assert(changedFiltersResponse, "The product and warehouse reset response was not exercised.");
    assert((await filterSelects.nth(1).inputValue()) === "DEMO-SP-104", "Company switching did not select the new synthetic SKU.");
    assert((await filterSelects.nth(2).inputValue()) === "30", "Company switching retained the previous forecast horizon.");
    assert((await dateFields.nth(0).inputValue()) === shiftUtcDay(changedFiltersResponse.today, -209), "Company switching retained the previous history start date.");
    assert((await dateFields.nth(1).inputValue()) === changedFiltersResponse.today, "Company switching retained the previous history end date.");
    const resetForecastLabel = await page.locator(".as-forecast-chart").getAttribute("aria-label");
    assert(!resetForecastLabel || resetForecastLabel.includes("for DEMO-SP-104"), "Company switching retained the previous company's forecast.");
    await filterSelects.nth(0).selectOption("completed_deliveries");
    await page.waitForFunction(() => document.querySelectorAll(".as-forecast-form select")[1]?.options[0]?.textContent === "Choose a tracked part");
    const switchedProductSelect = filterSelects.nth(1);
    assert(!(await switchedProductSelect.inputValue()), `Company switching retained the previous company's product selection: ${await switchedProductSelect.inputValue()}.`);
    assert(String(changedFiltersResponse.productId) !== previousProductId, "The new company filter options did not replace the previous product.");
    await switchedProductSelect.selectOption({ index: 1 });
    assert((await switchedProductSelect.inputValue()) === String(changedFiltersResponse.productId), "The new company product could not be selected.");
    assert((await filterSelects.nth(2).inputValue()) === "", "Company switching retained the previous warehouse.");
    assert((await filterSelects.nth(3).inputValue()) === "30", "Company switching did not reset the filter horizon.");
    companyOptionsTransform = null;

    testPhase = "Odoo connection failure and recovery regression";
    const expectedFailureStart = browserErrors.length;
    const abortDashboardCall = (route) => route.abort("failed");
    await page.route("**/web/dataset/call_kw/autostock.dashboard/get_dashboard_data", abortDashboardCall);
    await page.getByRole("button", { name: "Refresh inventory data" }).click();
    await page.waitForFunction(() => document.querySelector(".as-sidebar-status.is-unavailable")?.textContent.includes("Odoo connection unavailable"));
    assert((await page.locator(".as-error").innerText()).includes("Could not load inventory"), "An inventory RPC failure did not produce the dashboard error state.");
    await page.unroute("**/web/dataset/call_kw/autostock.dashboard/get_dashboard_data", abortDashboardCall);
    await page.getByRole("button", { name: "Refresh inventory data" }).click();
    await page.locator(".as-sidebar-status.is-connected").waitFor();
    await page.waitForFunction(() => !document.querySelector(".as-error"));
    const expectedFailureLogs = browserErrors.slice(expectedFailureStart);
    assert(expectedFailureLogs.some((error) => error.includes("AutoStock dashboard request failed")), "The intentional RPC failure was not reported by the dashboard.");
    assert(
        expectedFailureLogs.every((error) => error.includes("AutoStock dashboard request failed") || error.includes("net::ERR_FAILED")),
        `The intentional RPC failure produced an unexpected browser error: ${expectedFailureLogs.join("; ")}`
    );

    const dataRow = page.locator(".as-table tbody tr").filter({ hasText: "DEMO-QA-BP-001" }).first();
    await dataRow.getByRole("button", { name: /Open/ }).click();
    await page.locator(".o_form_view").waitFor({ timeout: 20000 });
    assert((await page.locator(".o_form_view").innerText()).includes("[SYNTHETIC QA] Front brake pads"), "Inventory details did not open in the native Odoo product form.");
    const backButton = page.locator(".o_back_button").first();
    assert(await backButton.count(), "Odoo did not provide a return control from the product form.");
    await backButton.click();
    await page.locator(".as-app").waitFor({ timeout: 20000 });

    const expectedConnectionFailureSet = new Set(expectedFailureLogs);
    const unexpectedBrowserErrors = browserErrors.filter((error) => !expectedConnectionFailureSet.has(error));
    assert(unexpectedBrowserErrors.length === 0, `Browser reported unexpected errors: ${unexpectedBrowserErrors.join("; ")}`);
    console.log(JSON.stringify({
        result: "passed",
        database,
        screenshots: screenshotDir,
        browserErrors: unexpectedBrowserErrors.length,
        expectedConnectionFailureLogs: expectedFailureLogs.length,
        viewports: resolutions.map(({ name, width, height }) => ({ name, width, height })),
        syntheticInventoryRows: 5,
        chartWindows: [30, 90, "full (400 synthetic observations)"],
        checks: ["live Odoo data", "synthetic provenance", "responsive navigation and route breadcrumb", "chart range and accessible date ranges", "plot width stays aligned to SVG viewport through 30/full toggles at desktop/tablet/mobile", "company-id reset with same-name display and late-snapshot rejection", "Odoo connection failure and recovery", "inventory details", "Odoo return navigation", "keyboard drawer", "horizontal overflow"],
    }));
} catch (error) {
    const safeMessage = String(error?.message || error).split("\nCall log:")[0];
    console.error(`${testPhase}: ${error?.name || "Error"}: ${safeMessage}`);
    throw new Error("Browser QA failed; see the sanitized phase message above.");
} finally {
    releaseStaleSnapshot?.();
    await page.unrouteAll({ behavior: "ignoreErrors" });
    await context.close();
    await browser.close();
}
