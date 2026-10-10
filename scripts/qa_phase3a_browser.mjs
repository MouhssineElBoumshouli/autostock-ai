import { mkdir } from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { assertDisposableQADatabase } from "./qa_phase3a_browser_guard.mjs";

const baseUrl = (process.env.AUTOSTOCK_QA_URL || "http://127.0.0.1:8176").replace(/\/$/, "");
const database = process.env.AUTOSTOCK_QA_DB || "autostock_phase3a_qa";
assertDisposableQADatabase(database);

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const login = process.env.AUTOSTOCK_QA_LOGIN;
const password = process.env.AUTOSTOCK_QA_PASSWORD;
const browserExecutable = process.env.AUTOSTOCK_QA_BROWSER;
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const screenshotDir = path.resolve(
    process.env.AUTOSTOCK_QA_SCREENSHOT_DIR || path.join(repoRoot, "docs/qa/screenshots/phase3a")
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
const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    reducedMotion: "reduce",
});
const page = await context.newPage();
page.setDefaultTimeout(12000);
page.setDefaultNavigationTimeout(25000);
const browserErrors = [];
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

async function authenticatedDatabase() {
    const response = await context.request.post(`${baseUrl}/web/session/get_session_info`, {
        data: { jsonrpc: "2.0", method: "call", params: {}, id: 2 },
    });
    const payload = await response.json();
    const actualDatabase = payload.result?.db;
    assert(
        response.ok() && actualDatabase === database,
        `Authenticated Odoo session is using ${actualDatabase || "an unknown database"}; expected ${database}.`
    );
    return actualDatabase;
}

let rpcSequence = 10;
async function callKw(model, method, args, kwargs = {}) {
    const response = await context.request.post(
        `${baseUrl}/web/dataset/call_kw/${model}/${method}`,
        {
            data: {
                jsonrpc: "2.0",
                method: "call",
                params: { model, method, args, kwargs },
                id: rpcSequence++,
            },
        }
    );
    const payload = await response.json();
    if (!response.ok() || payload.error || payload.result === undefined) {
        const details = payload.error?.data?.message || payload.error?.message || `HTTP ${response.status()}`;
        throw new Error(`Odoo ${model}.${method} failed: ${details}`);
    }
    return payload.result;
}

async function screenshot(name) {
    await page.screenshot({
        path: path.join(screenshotDir, name),
        type: "jpeg",
        quality: 90,
        fullPage: false,
    });
}

async function navigateToRisks(mobile) {
    if (mobile) {
        await page.getByRole("button", { name: "Open AutoStock navigation" }).click();
        const drawer = page.getByRole("dialog", { name: "AutoStock AI navigation" });
        await drawer.waitFor();
        await drawer.getByRole("button", { name: "Stock risks", exact: true }).click();
        await drawer.waitFor({ state: "hidden" });
    } else {
        await page.getByRole("button", { name: "Stock risks", exact: true }).click();
    }
    await page.locator(".as-risk-panel").waitFor({ state: "visible" });
    await page.locator(".as-risk-table tbody tr[data-risk-key]").first().waitFor({ state: "attached" });
    await page.waitForFunction(
        () => document.querySelector(".as-risk-panel")?.innerText.includes("Read-only planning guidance")
    );
    await page.locator(".as-risk-panel").scrollIntoViewIfNeeded();
    await page.waitForTimeout(250);
}

async function checkNoHorizontalOverflow(name) {
    const measure = await page.evaluate(() => ({
        viewport: window.innerWidth,
        document: document.documentElement.scrollWidth,
        body: document.body.scrollWidth,
        app: document.querySelector(".as-app")?.scrollWidth || 0,
        appClient: document.querySelector(".as-app")?.clientWidth || 0,
    }));
    assert(
        measure.document <= measure.viewport + 1
            && measure.body <= measure.viewport + 1
            && measure.app <= measure.appClient + 1,
        `${name} layout overflows horizontally: ${JSON.stringify(measure)}`
    );
}

try {
    await page.goto(`${baseUrl}/web/login?db=${encodeURIComponent(database)}`, { waitUntil: "domcontentloaded" });
    await page.locator('input[name="login"], #login').first().fill(login);
    await page.locator('input[name="password"], #password').first().fill(password);
    await page.locator('form button[type="submit"]').click();
    await page.locator(".o_main_navbar").waitFor({ timeout: 30000 });
    await authenticatedDatabase();

    const actionId = await dashboardActionId();
    await page.goto(`${baseUrl}/web#action=${actionId}`, { waitUntil: "domcontentloaded" });
    await page.locator(".as-app").waitFor({ timeout: 20000 });
    await page.locator(".as-kpis").waitFor({ timeout: 30000 });
    await page.locator(".as-sidebar-status.is-connected").waitFor({ timeout: 30000 });
    const pageText = await page.locator(".as-app").innerText();
    assert(pageText.includes("Live Odoo inventory data"), "The dashboard did not show live Odoo inventory.");
    assert(pageText.includes("[SYNTHETIC QA]"), "The automotive QA records are missing their synthetic label.");
    assert(pageText.includes("QA3A-OF-001"), "The labeled oil-filter fixture was not shown.");

    const results = [];
    const viewports = [
        { name: "desktop", width: 1440, height: 1000, mobile: false },
        { name: "tablet", width: 1024, height: 900, mobile: false },
        { name: "mobile", width: 390, height: 844, mobile: true },
    ];

    for (const viewport of viewports) {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        if (viewport.mobile) {
            await page.getByRole("button", { name: "Open AutoStock navigation" }).waitFor({ state: "visible" });
        }
        await page.locator(".as-page-scroll").evaluate((element) => { element.scrollTop = 0; });
        await page.waitForTimeout(150);
        await checkNoHorizontalOverflow(`${viewport.name} dashboard`);
        await screenshot(`phase3a-dashboard-${viewport.name}.jpg`);

        await navigateToRisks(viewport.mobile);
        assert(
            (await page.locator(".as-appbar-context strong").innerText()).trim() === "Stock risks",
            `${viewport.name} navigation context did not identify Stock risks.`
        );
        const layoutModes = await page.evaluate(() => ({
            desktopList: getComputedStyle(document.querySelector(".as-risk-desktop-list")).display,
            mobileList: getComputedStyle(document.querySelector(".as-risk-mobile-list")).display,
        }));
        const dateFilterLayout = await page.locator(".as-risk-date-filter")
            .evaluate((fieldset) => ({
                display: getComputedStyle(fieldset).display,
                width: Math.round(fieldset.getBoundingClientRect().width),
                columns: getComputedStyle(fieldset).gridTemplateColumns,
                legendWidth: Math.round(fieldset.querySelector("legend").getBoundingClientRect().width),
                inputs: [...fieldset.querySelectorAll("input[type='date']")].map((input) => ({
                    width: Math.round(input.getBoundingClientRect().width),
                    parentWidth: Math.round(input.parentElement.getBoundingClientRect().width),
                    computedWidth: getComputedStyle(input).width,
                })),
            }));
        const dateFilterWidths = dateFilterLayout.inputs.map((input) => input.width);
        assert(
            dateFilterWidths.length === 2 && dateFilterWidths.every((width) => width >= 110),
            `${viewport.name} forecast-history date fields are too narrow: ${JSON.stringify(dateFilterLayout)}`
        );
        if (viewport.width <= 1100) {
            assert(layoutModes.desktopList === "none" && layoutModes.mobileList !== "none", `${viewport.name} did not switch to risk cards.`);
            assert(await page.locator(".as-risk-mobile-card[data-risk-key]").count() === 5, `${viewport.name} risk cards do not cover all five fixture parts.`);
        } else {
            assert(layoutModes.desktopList !== "none" && layoutModes.mobileList === "none", `${viewport.name} did not use the desktop risk table.`);
        }
        await checkNoHorizontalOverflow(`${viewport.name} stock risks`);
        await screenshot(`phase3a-stock-risk-${viewport.name}-overview.jpg`);

        const usesRiskCards = viewport.width <= 1100;
        const evidence = page.locator(usesRiskCards ? ".as-risk-mobile-card" : ".as-risk-table tbody tr").first().locator("details.as-risk-evidence");
        await evidence.locator("summary").click();
        const evidenceText = await evidence.innerText();
        assert(evidenceText.includes("No completed real delivery forecast"), "Missing forecasts were not explained in the row evidence.");
        assert(/No (purchase order|order or stock record)/i.test(evidenceText), "Read-only boundary was not explained in row evidence.");
        await screenshot(`phase3a-stock-risk-${viewport.name}.jpg`);
        await evidence.locator("summary").click();

        const selector = usesRiskCards ? ".as-risk-mobile-card" : ".as-risk-table tbody tr";
        const scenarioRows = await page.locator(`${selector}[data-risk-key]`).evaluateAll((nodes) => Object.fromEntries(
            nodes.map((node) => [node.dataset.riskSku, {
                status: node.dataset.riskStatus,
                quantity: Number(node.dataset.riskQty),
                reorder: node.dataset.riskReorder === "true",
            }])
        ));
        assert(scenarioRows["QA3A-BP-002"]?.status === "out" && scenarioRows["QA3A-BP-002"]?.quantity === 12,
            `${viewport.name} zero-stock brake pads did not show the expected unit-based top-up: ${JSON.stringify(scenarioRows)}`);
        assert(scenarioRows["QA3A-OF-001"]?.status === "shortage" && scenarioRows["QA3A-OF-001"]?.quantity === 24,
            `${viewport.name} oil-filter recommendation did not round up to its dozen-unit pack: ${JSON.stringify(scenarioRows)}`);
        assert(scenarioRows["QA3A-SP-003"]?.status === "low" && !scenarioRows["QA3A-SP-003"]?.reorder,
            `${viewport.name} at-trigger spark-plug stock did not report a low/no-order state.`);
        assert(scenarioRows["QA3A-AL-004"]?.status === "overstock" && !scenarioRows["QA3A-AL-004"]?.reorder,
            `${viewport.name} over-target alternator stock was classified incorrectly.`);
        assert(scenarioRows["QA3A-CF-005"]?.status === "policy_missing" && !scenarioRows["QA3A-CF-005"]?.reorder,
            `${viewport.name} part without a verified reorder policy received a quantity.`);

        await page.getByTestId("risk-status-filter").selectOption("recommendations");
        const recommendationRows = page.locator(`${selector}[data-risk-reorder="true"]`);
        await recommendationRows.first().waitFor({ state: "visible" });
        await page.waitForFunction((target) => (
            document.querySelectorAll(`${target}[data-risk-reorder="false"]`).length === 0
        ), selector);
        const recommendationCount = await recommendationRows.count();
        assert(recommendationCount > 0, `${viewport.name} recommendation filter returned no risk rows.`);
        assert(
            await page.locator(`${selector}[data-risk-reorder="false"]`).count() === 0,
            `${viewport.name} recommendation filter included a row without a suggested quantity.`
        );

        await page.getByTestId("risk-status-filter").selectOption("all");
        const firstSupplier = await page.locator("[data-testid='risk-supplier-filter'] option").nth(1).getAttribute("value");
        assert(firstSupplier, "The synthetic vendor is missing from the supplier filter.");
        await page.getByTestId("risk-supplier-filter").selectOption(firstSupplier);
        await page.locator(`${selector}[data-supplier-id="${firstSupplier}"]`).first().waitFor({ state: "visible" });
        await page.waitForFunction(({ target, supplierId }) => (
            [...document.querySelectorAll(`${target}[data-risk-key]`)]
                .every((node) => node.dataset.supplierId === supplierId)
        ), { target: selector, supplierId: firstSupplier });
        const supplierFilteredCount = await page.locator(`${selector}[data-risk-key]`).count();
        assert(
            await page.locator(`${selector}[data-supplier-id]:not([data-supplier-id="${firstSupplier}"])`).count() === 0,
            `${viewport.name} supplier filter returned a different vendor.`
        );

        await page.getByTestId("risk-search").fill("QA3A-OF-001");
        await page.waitForFunction((target) => (
            document.querySelectorAll(`${target}[data-risk-key]`).length === 1
        ), selector);
        assert(await page.locator(`${selector}[data-risk-key]`).count() === 1, `${viewport.name} part search did not narrow to one row.`);
        assert((await page.locator(`${selector}[data-risk-key]`).first().innerText()).includes("QA3A-OF-001"), "Part search returned the wrong row.");

        const historyDate = await page.evaluate(() => {
            const date = new Date();
            date.setUTCDate(date.getUTCDate() + 2);
            return date.toISOString().slice(0, 10);
        });
        await page.getByLabel("Forecast history from date").fill(historyDate);
        await page.getByLabel("Forecast history to date").fill(historyDate);
        await page.getByRole("heading", { name: "No risk rows match the active filters on this page" }).waitFor({ state: "visible" });
        await page.getByRole("button", { name: "Clear filters", exact: true }).last().click();
        await page.locator(`${selector}[data-risk-key]`).first().waitFor({ state: "visible" });

        assert(
            !(await page.getByRole("button", { name: /create.*(rfq|purchase|order)|confirm.*order|reorder now/i }).count()),
            "A Phase 3A screen action could mutate purchasing or stock records."
        );
        results.push({
            viewport: viewport.name,
            dimensions: `${viewport.width}x${viewport.height}`,
            rows: await page.locator(`${selector}[data-risk-key]`).count(),
            recommendationRows: recommendationCount,
            supplierFilteredRows: supplierFilteredCount,
            dateFilterWidths,
            calculatedScenarios: scenarioRows,
            overflow: "none",
        });
    }

    // Exercise the full Odoo path with a catalog larger than one server page.
    // The fixture is created and removed through the authenticated Odoo RPC;
    // it is synthetic, database-local, and never appears in committed screenshots.
    const initialRiskData = await callKw(
        "autostock.inventory.risk",
        "get_risk_data",
        [false, "", false, "all", false, false, 0]
    );
    const scaleCompanyId = initialRiskData.company_id;
    const scaleWarehouseCount = initialRiskData.warehouses.length;
    const scalePageCount = Math.ceil((251 * scaleWarehouseCount) / 100);
    assert(scaleWarehouseCount > 0, "The catalog regression needs at least one active-company warehouse.");
    const unitRows = await callKw(
        "ir.model.data",
        "search_read",
        [[
            ["module", "=", "uom"],
            ["name", "=", "product_uom_unit"],
        ], ["res_id"]],
        { limit: 1 }
    );
    const unitId = unitRows[0]?.res_id;
    assert(unitId, "Could not resolve the inventory unit for the synthetic scale fixture.");
    const scaleSuffix = Date.now().toString();
    const scalePrefix = `QA3A-SCALE-${scaleSuffix}-`;
    let scaleProductIds = [];
    let scaleVendorId = false;
    let scaleSupplierInfoIds = [];
    try {
        scaleVendorId = await callKw("res.partner", "create", [{
            name: `[SYNTHETIC SCALE] Supplier ${scaleSuffix}`,
            supplier_rank: 1,
        }]);
        scaleProductIds = await callKw(
            "product.template",
            "create",
            [[...Array(251)].map((_, index) => ({
                name: `[SYNTHETIC SCALE] Automotive part ${String(index + 1).padStart(3, "0")}`,
                default_code: `${scalePrefix}${String(index + 1).padStart(3, "0")}`,
                company_id: scaleCompanyId,
                is_storable: true,
                uom_id: unitId,
                autostock_enabled: true,
                autostock_safety_stock: index === 250 ? 1 : 0,
                autostock_lead_time_days: 7,
            }))]
        );
        assert(Array.isArray(scaleProductIds) && scaleProductIds.length === 251, "Odoo did not create all 251 synthetic tracked parts.");
        const supplierInfoCreated = await callKw("product.supplierinfo", "create", [{
            partner_id: scaleVendorId,
            product_tmpl_id: scaleProductIds[250],
            company_id: scaleCompanyId,
            product_uom_id: unitId,
            delay: 7,
            autostock_min_order_qty: 1,
        }]);
        scaleSupplierInfoIds = Array.isArray(supplierInfoCreated) ? supplierInfoCreated : [supplierInfoCreated];

        const firstScalePage = await callKw(
            "autostock.inventory.risk",
            "get_risk_data",
            [false, scalePrefix, false, "out", false, false, 0]
        );
        const targetSku = `${scalePrefix}251`;
        assert(firstScalePage.total_products === 251, `Odoo returned ${firstScalePage.total_products} parts for the 251-part search.`);
        assert(firstScalePage.total_pairs === 251 * scaleWarehouseCount, "The candidate count did not include each selected warehouse.");
        assert(firstScalePage.rows.length === 100, "The risk service did not keep the first catalog page within its 100-row limit.");
        assert(firstScalePage.pagination.summary_scope === "current_page_after_supplier_and_history_filters", "The summary scope was not exposed.");
        assert(firstScalePage.pagination.summary_row_count === 100 && firstScalePage.summary.out === 100,
            "The out-of-stock KPI did not describe only the current page.");
        assert(firstScalePage.pagination.has_next, "The first catalog page did not offer continuation.");
        assert(!firstScalePage.rows.some((row) => row.sku === targetSku), "The last synthetic part unexpectedly appeared in the first page.");

        const laterRiskPage = await callKw(
            "autostock.inventory.risk",
            "get_risk_data",
            [false, scalePrefix, false, "out", false, false, 200]
        );
        const laterTarget = laterRiskPage.rows.find((row) => row.sku === targetSku);
        assert(laterTarget?.risk === "out", "Server-side status filtering failed to find the at-risk part outside the first 250 products.");
        assert(laterRiskPage.recommendation_count === 1, "The page-scoped recommendation count did not include the later part.");

        const supplierRiskPage = await callKw(
            "autostock.inventory.risk",
            "get_risk_data",
            [false, scalePrefix, scaleVendorId, "out", false, false, 0]
        );
        assert(supplierRiskPage.total_products === 1, "Supplier filtering did not search the complete tracked catalog.");
        assert(supplierRiskPage.row_count === scaleWarehouseCount, "Supplier results were not returned for each in-scope warehouse.");
        assert(supplierRiskPage.rows.every((row) => row.sku === targetSku && row.supplier?.id === scaleVendorId),
            "The selected supplier returned an unrelated catalog part.");
        assert(supplierRiskPage.recommendation_count === scaleWarehouseCount, "Supplier-filtered summary counts were not page-scoped.");

        await page.setViewportSize({ width: 1440, height: 1000 });
        await page.waitForTimeout(150);
        await page.getByRole("button", { name: "Refresh stock-risk data" }).click();
        await page.getByTestId("risk-search").fill(scalePrefix);
        await page.waitForFunction((count) => document.querySelector(".as-risk-pagination")?.innerText.includes(`Page 1 of ${count}`), scalePageCount);
        const pagedSummaryNote = await page.locator(".as-risk-page-note").innerText();
        assert(pagedSummaryNote.includes("regardless of the selected risk filter") && pagedSummaryNote.includes("other pages"),
            "The multi-page UI did not explain the KPI scope and the need to inspect other pages.");
        await page.getByTestId("risk-status-filter").selectOption("out");
        await page.waitForFunction((count) => document.querySelector(".as-risk-pagination")?.innerText.includes(`Page 1 of ${count}`), scalePageCount);
        for (const pageNumber of [2, 3]) {
            await page.getByRole("button", { name: "Next page" }).click();
            await page.waitForFunction(({ number, count }) => (
                document.querySelector(".as-risk-pagination")?.innerText.includes(`Page ${number} of ${count}`)
            ), { number: pageNumber, count: scalePageCount });
        }
        const desktopSelector = ".as-risk-table tbody tr";
        await page.locator(`${desktopSelector}[data-risk-sku="${targetSku}"]`).first().waitFor({ state: "visible" });
        await page.getByTestId("risk-supplier-filter").selectOption(String(scaleVendorId));
        await page.waitForFunction(({ sku, expectedRows }) => {
            const rows = [...document.querySelectorAll(".as-risk-table tbody tr[data-risk-key]")];
            return rows.length === expectedRows
                && rows.every((node) => node.dataset.riskSku === sku);
        }, { sku: targetSku, expectedRows: scaleWarehouseCount });
        const scaleUiRows = page.locator(`${desktopSelector}[data-risk-key]`);
        const supplierUiCount = await scaleUiRows.count();
        assert(supplierUiCount === scaleWarehouseCount,
            `The UI supplier filter returned ${supplierUiCount} rows for ${scaleWarehouseCount} selected warehouses.`);
        assert(await page.locator(`${desktopSelector}[data-supplier-id="${scaleVendorId}"]`).count() === scaleWarehouseCount,
            "The UI supplier filter did not keep the selected vendor on every row.");
        assert(await page.locator(".as-risk-page-note").innerText().then((value) => value.includes("one page")),
            "The UI did not explain that all rows in the selected supplier scope fit on one page.");
        const scaleKpis = await page.locator(".as-risk-kpi").allTextContents();
        assert(scaleKpis[0].includes(String(scaleWarehouseCount)), "The out-of-stock KPI did not reflect supplier-filtered page rows.");
        assert(scaleKpis[2].includes(String(scaleWarehouseCount)), "The recommendation KPI did not reflect supplier-filtered page rows.");
        results.push({
            catalogRegression: "passed",
            trackedParts: 251,
            selectedWarehouses: scaleWarehouseCount,
            supplierPartOutsideFirst250: targetSku,
            firstPageSummaryRows: firstScalePage.pagination.summary_row_count,
            serverStatusPage: laterRiskPage.pagination.page_number,
            vendorFilteredRows: supplierRiskPage.row_count,
        });
    } finally {
        const cleanupFailures = [];
        if (scaleSupplierInfoIds.length) {
            try {
                await callKw("product.supplierinfo", "unlink", [scaleSupplierInfoIds]);
            } catch (error) {
                cleanupFailures.push(`supplier term IDs ${scaleSupplierInfoIds.join(", ")}: ${error.message}`);
            }
        }
        if (scaleProductIds.length) {
            try {
                await callKw("product.template", "unlink", [scaleProductIds]);
            } catch (error) {
                cleanupFailures.push(`product template IDs ${scaleProductIds.join(", ")}: ${error.message}`);
            }
        }
        if (scaleVendorId) {
            try {
                await callKw("res.partner", "unlink", [[scaleVendorId]]);
            } catch (error) {
                cleanupFailures.push(`vendor partner ID ${scaleVendorId}: ${error.message}`);
            }
        }
        if (cleanupFailures.length) {
            process.exitCode = 1;
            console.error(
                `WARNING: QA fixture cleanup was incomplete in ${database}. `
                + `${cleanupFailures.join("; ")} Remove only these listed fixture records after signing in to ${database}.`
            );
        }
        await page.getByRole("button", { name: "Clear filters", exact: true }).click();
        await page.waitForFunction(() => document.querySelector(".as-risk-panel")?.innerText.includes("Read-only planning guidance"));
    }

    assert(browserErrors.length === 0, `Browser errors: ${JSON.stringify(browserErrors)}`);
    console.log(JSON.stringify({
        outcome: "passed",
        database,
        screenshots: screenshotDir,
        syntheticFixture: "5 labeled automotive parts; actual Odoo stock, rules and vendor terms; no synthetic forecast input",
        results,
        browserErrors,
    }, null, 2));
} catch (error) {
    console.error(JSON.stringify({
        outcome: "failed",
        message: error.message,
        url: page.url(),
        browserErrors,
    }, null, 2));
    process.exitCode = 1;
} finally {
    await context.close();
    await browser.close();
}
