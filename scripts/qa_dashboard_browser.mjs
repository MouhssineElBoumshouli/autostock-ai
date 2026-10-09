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
const page = await context.newPage();
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

try {
    await page.goto(`${baseUrl}/web/login?db=${encodeURIComponent(database)}`, { waitUntil: "domcontentloaded" });
    await page.locator('input[name="login"], #login').first().fill(login);
    await page.locator('input[name="password"], #password').first().fill(password);
    await page.locator('form button[type="submit"]').click();
    await page.locator(".o_main_navbar").waitFor({ timeout: 30000 });

    const actionId = await dashboardActionId();
    await openDashboard(actionId);
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
        await page.locator(".as-forecast-figure").scrollIntoViewIfNeeded();
        await page.getByRole("button", { name: "30 days", exact: true }).click();
        await page.waitForFunction(() => document.querySelector(".as-chart-window-label")?.textContent.trim().startsWith("30 of "));
        assert((await page.locator(".as-chart-window-label").innerText()).startsWith("30 of "), `${viewport.name} 30-day chart window did not update.`);
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
        assert((await page.locator(".as-chart-window-label").innerText()).startsWith("210 of "), `${viewport.name} full chart window did not restore all history.`);
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

    await page.setViewportSize({ width: 1440, height: 1000 });
    await openDashboard(actionId);
    const dataRow = page.locator(".as-table tbody tr").filter({ hasText: "DEMO-QA-BP-001" }).first();
    await dataRow.getByRole("button", { name: /Open/ }).click();
    await page.locator(".o_form_view").waitFor({ timeout: 20000 });
    assert((await page.locator(".o_form_view").innerText()).includes("[SYNTHETIC QA] Front brake pads"), "Inventory details did not open in the native Odoo product form.");
    const backButton = page.locator(".o_back_button").first();
    assert(await backButton.count(), "Odoo did not provide a return control from the product form.");
    await backButton.click();
    await page.locator(".as-app").waitFor({ timeout: 20000 });

    assert(browserErrors.length === 0, `Browser reported errors: ${browserErrors.join("; ")}`);
    console.log(JSON.stringify({
        result: "passed",
        database,
        screenshots: screenshotDir,
        browserErrors: browserErrors.length,
        viewports: resolutions.map(({ name, width, height }) => ({ name, width, height })),
        syntheticInventoryRows: 5,
        chartWindows: [30, 90, 210],
        checks: ["live Odoo data", "synthetic provenance", "responsive navigation", "chart range controls", "inventory details", "Odoo return navigation", "keyboard drawer", "horizontal overflow"],
    }));
} finally {
    await context.close();
    await browser.close();
}
