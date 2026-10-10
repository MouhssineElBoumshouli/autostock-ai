import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const showroomDatabase = process.env.AUTOSTOCK_SHOWROOM_DB || "autostock_showroom_demo";
if (showroomDatabase !== "autostock_showroom_demo") {
    throw new Error("Showroom browser QA is read-only and accepts only autostock_showroom_demo.");
}

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const credentialsFile = path.join(repoRoot, ".showroom", "credentials.txt");
const screenshotDirectory = path.resolve(
    process.env.AUTOSTOCK_SHOWROOM_SCREENSHOT_DIR
        || path.join(repoRoot, "docs", "qa", "screenshots", "showroom")
);
const credentialText = await readFile(credentialsFile, "utf8");
const credentials = Object.fromEntries(
    credentialText.split(/\r?\n/).map((line) => {
        const index = line.indexOf("=");
        return index > 0 ? [line.slice(0, index), line.slice(index + 1)] : ["", ""];
    }).filter(([key]) => key)
);
const defaultUrl = new URL(credentials.URL || "http://localhost:8177/web");
const baseUrl = (process.env.AUTOSTOCK_SHOWROOM_URL || defaultUrl.origin).replace(/\/$/, "");
const login = process.env.AUTOSTOCK_SHOWROOM_LOGIN || credentials.Login;
const password = process.env.AUTOSTOCK_SHOWROOM_PASSWORD || credentials.Password;
const browserExecutable = process.env.AUTOSTOCK_SHOWROOM_BROWSER
    || process.env.AUTOSTOCK_QA_BROWSER
    || [
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    ].find((candidate) => existsSync(candidate));

assert(/^https?:\/\/((127\.0\.0\.1)|(localhost))(:\d+)?$/.test(baseUrl), "Showroom QA accepts only localhost.");
assert(login && password, `Local showroom credentials are missing from ${credentialsFile}.`);
await mkdir(screenshotDirectory, { recursive: true });

const launchOptions = { headless: true };
if (typeof browserExecutable === "string" && browserExecutable) {
    launchOptions.executablePath = browserExecutable;
}
const browser = await chromium.launch(launchOptions);
const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    reducedMotion: "reduce",
});
const page = await context.newPage();
page.setDefaultTimeout(15000);
page.setDefaultNavigationTimeout(30000);
const browserErrors = [];
page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(`console: ${message.text()}`);
});
page.on("pageerror", (error) => browserErrors.push(`page: ${error.message}`));
let rpcId = 10;

async function callKw(model, method, args = [], kwargs = {}) {
    const response = await context.request.post(`${baseUrl}/web/dataset/call_kw/${model}/${method}`, {
        data: {
            jsonrpc: "2.0",
            method: "call",
            params: { model, method, args, kwargs },
            id: rpcId++,
        },
    });
    const payload = await response.json();
    assert(response.ok() && !payload.error && payload.result !== undefined,
        `Odoo ${model}.${method} failed: ${payload.error?.data?.message || payload.error?.message || response.status()}`);
    return payload.result;
}

async function takeScreenshot(name) {
    await page.screenshot({
        path: path.join(screenshotDirectory, name),
        type: "jpeg",
        quality: 92,
        fullPage: false,
    });
}

async function navigate(label, mobile) {
    if (mobile) {
        await page.getByRole("button", { name: "Open AutoStock navigation" }).click();
        const drawer = page.getByRole("dialog", { name: "AutoStock AI navigation" });
        await drawer.waitFor({ state: "visible" });
        await drawer.getByRole("button", { name: label, exact: true }).click();
        await drawer.waitFor({ state: "hidden" });
    } else {
        await page.getByRole("button", { name: label, exact: true }).click();
    }
    if (label === "Forecasts") {
        await page.locator(".as-forecast-panel").waitFor({ state: "visible" });
        await page.locator(".as-forecast-result-head h3").waitFor({ state: "visible" });
    }
    if (label === "Restock") {
        await page.locator(".as-risk-panel").waitFor({ state: "visible" });
        const riskSelector = await page.evaluate(() => window.innerWidth <= 1100)
            ? ".as-risk-mobile-card[data-risk-key]"
            : ".as-risk-table tbody tr[data-risk-key]";
        await page.locator(riskSelector).first().waitFor({ state: "visible" });
    }
}

async function assertNoOverflow(viewportName) {
    const widths = await page.evaluate(() => ({
        viewport: window.innerWidth,
        document: document.documentElement.scrollWidth,
        body: document.body.scrollWidth,
        app: document.querySelector(".as-app")?.scrollWidth || 0,
        appClient: document.querySelector(".as-app")?.clientWidth || 0,
    }));
    assert(widths.document <= widths.viewport + 1 && widths.body <= widths.viewport + 1
        && widths.app <= widths.appClient + 1,
    `${viewportName} has horizontal overflow: ${JSON.stringify(widths)}`);
}

try {
    await page.goto(`${baseUrl}/web/login?db=${encodeURIComponent(showroomDatabase)}`, { waitUntil: "domcontentloaded" });
    await page.locator('input[name="login"], #login').first().fill(login);
    await page.locator('input[name="password"], #password').first().fill(password);
    await page.locator('form button[type="submit"]').click();
    await page.locator(".o_main_navbar").waitFor({ timeout: 40000 });

    const sessionResponse = await context.request.post(`${baseUrl}/web/session/get_session_info`, {
        data: { jsonrpc: "2.0", method: "call", params: {}, id: 2 },
    });
    const sessionPayload = await sessionResponse.json();
    assert(sessionResponse.ok() && sessionPayload.result?.db === showroomDatabase,
        `Authenticated Odoo session database was ${sessionPayload.result?.db || "unknown"}; expected ${showroomDatabase}.`);

    const actionRows = await callKw("ir.model.data", "search_read", [[
        ["module", "=", "autostock_ai"],
        ["name", "=", "action_autostock_dashboard"],
    ], ["res_id"]], { limit: 1 });
    assert(actionRows[0]?.res_id, "AutoStock dashboard action was not installed.");

    const [options, dashboard] = await Promise.all([
        callKw("autostock.forecast.run", "get_forecast_options"),
        callKw("autostock.dashboard", "get_dashboard_data"),
    ]);
    assert.equal(options.company_name, "Atlas Auto Distribution");
    assert.equal(options.demo_environment, true);
    assert.match(options.demo_environment_note, /Fictional.*generated.*no real-world accuracy claim/i);
    assert.equal(options.products.length, 64, "Forecast product selector did not return the full showroom catalogue.");
    assert(options.products.some((product) => product.sku === "AT-FLT-001" && product.name.includes("Engine Oil Filter")),
        "The real Odoo product catalogue is missing the featured natural-name showroom part.");
    assert.equal(dashboard.total_tracked, 64);
    assert(options.demo_forecast?.product_id, "The showroom has no visible reviewed real-history default forecast.");

    await page.goto(`${baseUrl}/web#action=${actionRows[0].res_id}`, { waitUntil: "domcontentloaded" });
    await page.locator(".as-app").waitFor({ timeout: 30000 });
    await page.locator(".as-kpis").waitFor({ timeout: 30000 });
    await page.locator(".as-sidebar-status.is-connected").waitFor({ timeout: 30000 });
    await page.locator(".as-demo-environment").waitFor({ state: "visible" });
    await page.locator(".as-overview-actions").waitFor({ state: "visible" });
    assert.equal(await page.locator(".as-risk-panel").isVisible(), false,
        "Detailed risk table must not clutter the Dashboard view.");
    assert.equal(await page.locator(".as-table-panel").isVisible(), false,
        "The full inventory table must be in Inventory, not dumped on the Dashboard.");
    assert(await page.locator(".as-panels").isVisible(),
        "The Dashboard must retain a real forecast chart preview and stock health.");
    assert.match(await page.locator(".as-demo-environment").getAttribute("title"), /Fictional/);
    assert((await page.locator(".as-table-panel tbody tr").count()) >= 10,
        "Live Odoo inventory table did not show the populated showroom.");
    const firstInventoryName = await page.locator(".as-table-panel td.as-part-name").first().innerText();
    assert(firstInventoryName && !/^AT-[A-Z0-9-]+$/.test(firstInventoryName.trim()),
        "The live inventory table did not show readable business product names.");
    const productFilter = page.locator(".as-forecast-form select").nth(1);
    const productFilterState = await productFilter.evaluate((select) => ({
        value: select.value,
        options: [...select.options].slice(0, 4).map((option) => ({ value: option.value, selected: option.selected })),
        matchingOptions: [...select.options].filter((option) => option.textContent.includes("AT-FLT-001"))
            .map((option) => ({ value: option.value, text: option.textContent })),
    }));
    assert.equal(productFilterState.value, String(options.demo_forecast.product_id),
        `The default real-history forecast must select its own product in the filter: ${JSON.stringify({
            product: options.products.find((product) => product.sku === "AT-FLT-001"),
            selectedRunProductId: options.demo_forecast.product_id,
            productFilterState,
        })}.`);
    const selectedProductLabel = productFilterState.matchingOptions[0]?.text || "";
    assert.equal(selectedProductLabel.match(/AT-FLT-001/g)?.length, 1,
        `The selected product label should show the natural Odoo product name and SKU only once: ${selectedProductLabel}.`);

    const reports = [];
    const viewports = [
        { name: "desktop", width: 1440, height: 1000, mobile: false },
        { name: "tablet", width: 1024, height: 900, mobile: false },
        { name: "mobile", width: 390, height: 844, mobile: true },
    ];

    for (const viewport of viewports) {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        if (viewport.name !== "desktop") {
            await page.goto(`${baseUrl}/web#action=${actionRows[0].res_id}`, { waitUntil: "domcontentloaded" });
            await page.locator(".as-app").waitFor({ state: "visible" });
            await page.locator(".as-kpis").waitFor({ state: "visible" });
        }
        if (viewport.mobile) {
            await page.getByRole("button", { name: "Open AutoStock navigation" }).click();
            await page.getByRole("dialog", { name: "AutoStock AI navigation" }).waitFor({ state: "visible" });
            await takeScreenshot("showroom-navigation-mobile.jpg");
            await page.getByRole("dialog", { name: "AutoStock AI navigation" })
                .getByRole("button", { name: "Dashboard", exact: true }).click();
            await page.getByRole("dialog", { name: "AutoStock AI navigation" }).waitFor({ state: "hidden" });
        }
        await page.locator(".as-page-scroll").evaluate((element) => { element.scrollTop = 0; });
        await page.waitForTimeout(150);
        await assertNoOverflow(`${viewport.name} dashboard`);
        await page.locator(".as-overview-actions").waitFor({ state: "visible" });
        assert.equal(await page.locator(".as-risk-panel").isVisible(), false,
            "Dashboard unexpectedly showed the detailed Restock table.");
        await takeScreenshot(`showroom-dashboard-${viewport.name}.jpg`);

        if (viewport.name === "desktop") {
            await page.getByRole("button", { name: "Inventory", exact: true }).click();
            await page.locator(".o_list_view").waitFor({ state: "visible" });
            const inventorySearch = page.locator(".o_searchview_input").first();
            await inventorySearch.waitFor({ state: "visible" });
            await inventorySearch.fill("AT-FLT-001");
            await inventorySearch.press("Enter");
            const filteredProduct = page.locator(".o_list_view .o_data_row").filter({ hasText: "AT-FLT-001" });
            await filteredProduct.waitFor({ state: "visible" });
            assert((await filteredProduct.innerText()).includes("Engine Oil Filter"),
                "The native Odoo product list did not find the natural-name showroom product.");
            await takeScreenshot("showroom-odoo-inventory-desktop.jpg");
            await page.goto(`${baseUrl}/web#action=${actionRows[0].res_id}`, { waitUntil: "domcontentloaded" });
            await page.locator(".as-app").waitFor({ state: "visible" });
        }

        await navigate("Forecasts", viewport.mobile);
        await page.locator(".as-demand-takeaway").waitFor({ state: "visible" });
        assert(await page.locator(".as-demand-takeaway").innerText().then((value) => value.includes("Expected demand")),
            "Forecast page did not show a plain-language demand total.");
        assert(await page.locator(".as-model-metrics").isVisible(),
            "Forecast evaluation details should be available on demand.");
        assert.equal(await page.locator(".as-kpis").isVisible(), false,
            "Forecasts should be its own screen, without Dashboard KPIs.");
        assert.equal(await page.locator(".as-risk-panel").isVisible(), false,
            "Forecasts unexpectedly displayed the Restock table.");
        const selectedForecast = await page.locator(".as-forecast-result-head h3").innerText();
        assert(selectedForecast.includes("AT-FLT-001") && selectedForecast.includes("30 day"),
            `${viewport.name} did not open the stored real-history demo forecast: ${selectedForecast}`);
        assert(await page.locator(".as-pill-real").isVisible(), "Forecast provenance did not identify Odoo history.");
        assert((await page.locator(".as-chart-window-label").innerText()).includes("180 days"),
            "Forecast chart did not load the complete 180-day generated delivery history.");
        for (const horizon of ["7", "30", "60"]) {
            await page.getByLabel("Horizon").selectOption(horizon);
            await page.waitForFunction((value) => (
                document.querySelector(".as-forecast-result-head h3")?.innerText.includes(`${value} day`)
                && document.querySelector(".as-forecast-chart")
            ), horizon);
        }
        await page.getByLabel("Horizon").selectOption("30");
        await page.waitForFunction(() => document.querySelector(".as-forecast-result-head h3")?.innerText.includes("30 day"));
        await page.getByRole("button", { name: "Full", exact: true }).click();
        await page.getByText("180 of 180 days", { exact: true }).waitFor({ state: "visible" });
        await page.locator(".as-forecast-figure").scrollIntoViewIfNeeded();
        await assertNoOverflow(`${viewport.name} forecast`);
        await takeScreenshot(`showroom-forecast-${viewport.name}.jpg`);
        const forecastDetails = page.locator(".as-forecast-details");
        await forecastDetails.locator("summary").click();
        assert(await forecastDetails.evaluate((element) => element.open),
            "The forecast evidence disclosure did not open in the interface.");
        assert((await page.locator(".as-source-details").innerText()).includes("Completed Odoo 19 stock moves"),
            "Forecast evidence does not explain its Odoo delivery source.");
        await page.locator(".as-forecast-details").scrollIntoViewIfNeeded();
        await takeScreenshot(`showroom-forecast-evidence-${viewport.name}.jpg`);
        await page.locator(".as-forecast-details summary").click();

        await navigate("Restock", viewport.mobile);
        assert.equal(await page.locator(".as-panels").isVisible(), false,
            "Restock unexpectedly displayed the complete forecasting page.");
        assert.equal((await page.locator(".as-appbar-context strong").innerText()).trim(), "Restock",
            "Breadcrumb should identify the selected Restock view.");
        const warehouseFilter = page.getByTestId("risk-warehouse-filter");
        const centralOption = await warehouseFilter.locator("option").evaluateAll((optionsInSelect) => {
            const match = optionsInSelect.find((option) => option.textContent.includes("Atlas Central Warehouse"));
            return match ? { value: match.value, label: match.textContent.trim() } : null;
        });
        assert(centralOption, "Atlas Central Warehouse is missing from the warehouse filter.");
        await warehouseFilter.selectOption(centralOption.value);
        await page.getByTestId("risk-search").fill("AT-FLT-001");
        await page.waitForFunction(({ sku, warehouse }) => {
            const rows = [...document.querySelectorAll(`.as-risk-table tbody tr[data-risk-sku='${sku}']`)];
            return rows.length === 1 && rows[0].innerText.includes(warehouse);
        }, { sku: "AT-FLT-001", warehouse: "Atlas Central Warehouse" });
        const rowSelector = viewport.width <= 1100 ? ".as-risk-mobile-card[data-risk-sku='AT-FLT-001']" : ".as-risk-table tbody tr[data-risk-sku='AT-FLT-001']";
        await page.locator(rowSelector).first().waitFor({ state: "visible" });
        const riskData = await callKw(
            "autostock.inventory.risk", "get_risk_data",
            [centralOption.value, "AT-FLT-001", false, "all", false, false, 0]
        );
        const forecastRisk = riskData.rows.find((row) => row.sku === "AT-FLT-001");
        assert(forecastRisk?.forecast.used, `Real reviewed forecast was not used in risk calculation: ${forecastRisk?.forecast.reason}`);
        assert(forecastRisk.recommended_qty > 0, "The selected Odoo stock/policy scenario did not produce a calculated recommendation.");
        const riskEvidence = page.locator(rowSelector).first().locator("details.as-risk-evidence");
        const riskSummary = riskEvidence.locator("summary");
        await riskSummary.scrollIntoViewIfNeeded();
        await page.waitForTimeout(250);
        await riskSummary.click();
        assert(await riskEvidence.evaluate((element) => element.open),
            `${viewport.name}: the stock-risk explanation disclosure did not open in the interface.`);
        await riskEvidence.locator("dl").scrollIntoViewIfNeeded();
        await assertNoOverflow(`${viewport.name} stock risks`);
        await takeScreenshot(`showroom-stock-risk-evidence-${viewport.name}.jpg`);
        reports.push({
            viewport: viewport.name,
            size: `${viewport.width}x${viewport.height}`,
            trackedProducts: options.products.length,
            dashboardTableRows: await page.locator(".as-table-panel tbody tr").count(),
            defaultForecast: selectedForecast,
            forecastHistoryDays: 180,
            chartHorizonsChecked: [7, 30, 60],
            riskWarehouse: centralOption.label,
            riskSource: "reviewed real Odoo delivery forecast",
            recommendedQty: forecastRisk.recommended_qty,
            overflow: "none",
        });
    }

    assert.equal(browserErrors.length, 0, `Browser console/page errors: ${JSON.stringify(browserErrors)}`);
    console.log(JSON.stringify({
        outcome: "passed",
        database: showroomDatabase,
        screenshots: screenshotDirectory,
        syntheticBusinessRecords: "fictional and generated locally; Odoo sale/delivery history, quants and recommendations are actual isolated database records",
        reports,
        browserErrors,
    }, null, 2));
} catch (error) {
    console.error(JSON.stringify({
        outcome: "failed",
        database: showroomDatabase,
        message: error.message,
        browserErrors,
    }, null, 2));
    process.exitCode = 1;
} finally {
    await context.close();
    await browser.close();
}
