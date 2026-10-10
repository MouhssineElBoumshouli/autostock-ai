/** @odoo-module **/
import { Component, onMounted, onPatched, onWillDestroy, onWillStart, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DEMO_SOURCE = "synthetic_demo";
const REAL_SOURCE = "completed_deliveries";

function shiftDate(value, amount) {
    const date = new Date(`${value}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() + amount);
    return date.toISOString().slice(0, 10);
}

function maxDate(...values) {
    return values.filter(Boolean).sort().at(-1) || "";
}

/** Live Odoo inventory with an evaluated, explicitly sourced demand forecast. */
export class AutoStockDashboard extends Component {
    static template = "autostock_ai.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.destroyed = false;
        this.forecastSnapshotRequestId = 0;
        this.riskRequestId = 0;
        this.mobileMenuButton = useRef("mobileMenuButton");
        this.mobileNavDrawer = useRef("mobileNavDrawer");
        this.dashboardScroll = useRef("dashboardScroll");
        this.chartFrame = useRef("chartFrame");
        this.mobileQuery = window.matchMedia("(max-width: 900px)");
        this.handleMobileChange = (event) => {
            this.state.mobileView = event.matches;
            if (!event.matches) {
                this.state.navOpen = false;
            }
        };
        this.state = useState({
            loading: true,
            connectionStatus: "connecting",
            error: null,
            data: null,
            forecastOptions: null,
            forecast: null,
            forecastBusy: false,
            forecastError: null,
            forecastNotice: null,
            riskData: null,
            riskLoading: false,
            riskError: null,
            riskSearch: "",
            riskWarehouseId: "",
            riskSupplierId: "",
            riskStatusFilter: "all",
            riskOffset: 0,
            riskHistoryFrom: "",
            riskHistoryTo: "",
            riskSort: "risk",
            mobileView: this.mobileQuery.matches,
            navOpen: false,
            activeSection: "dashboard",
            chartWindowDays: 30,
            chartWidth: 800,
            filters: {
                sourceType: DEMO_SOURCE,
                productId: "",
                sku: "DEMO-BP-001",
                warehouseId: "",
                horizon: "30",
                historyStart: "",
                historyEnd: "",
            },
        });
        this.mobileQuery.addEventListener("change", this.handleMobileChange);
        onPatched(() => this.syncChartWidth());
        onMounted(() => {
            if (typeof ResizeObserver === "undefined" || !this.chartFrame.el) {
                return;
            }
            this.chartResizeObserver = new ResizeObserver(() => {
                window.requestAnimationFrame(() => this.syncChartWidth());
            });
            this.chartResizeObserver.observe(this.chartFrame.el);
            this.syncChartWidth();
        });
        onWillStart(() => this.load());
        onWillDestroy(() => {
            this.destroyed = true;
            this.mobileQuery.removeEventListener("change", this.handleMobileChange);
            this.chartResizeObserver?.disconnect();
            window.clearTimeout(this.riskSearchTimer);
        });
    }

    async load() {
        this.state.loading = true;
        this.state.connectionStatus = "connecting";
        this.state.error = null;
        try {
            const [data, options] = await Promise.all([
                this.orm.call("autostock.dashboard", "get_dashboard_data", []),
                this.orm.call("autostock.forecast.run", "get_forecast_options", []),
            ]);
            const previousCompanyId = this.state.forecastOptions?.company_id;
            const companyChanged = previousCompanyId === undefined
                || String(previousCompanyId) !== String(options.company_id);
            this.state.data = data;
            this.state.forecastOptions = options;
            if (companyChanged) {
                const demoForecast = options.demo_environment ? options.demo_forecast : false;
                this.state.forecast = null;
                this.state.forecastError = null;
                this.state.forecastNotice = null;
                this.state.chartWindowDays = 30;
                this.state.filters.sourceType = demoForecast ? REAL_SOURCE : DEMO_SOURCE;
                this.state.filters.productId = demoForecast ? String(demoForecast.product_id) : "";
                this.state.filters.sku = demoForecast
                    ? ""
                    : (options.demo_skus[0]?.sku || "DEMO-BP-001");
                this.state.filters.warehouseId = demoForecast?.warehouse_id
                    ? String(demoForecast.warehouse_id)
                    : "";
                this.state.filters.horizon = String(demoForecast?.horizon_days || 30);
                this.resetHistoryRange();
                if (demoForecast) {
                    this.state.filters.historyStart = demoForecast.history_start;
                    this.state.filters.historyEnd = demoForecast.history_end;
                }
                this.state.riskData = null;
                this.state.riskWarehouseId = "";
                this.state.riskSupplierId = "";
                this.state.riskStatusFilter = "all";
                this.state.riskOffset = 0;
                this.state.riskHistoryFrom = "";
                this.state.riskHistoryTo = "";
            }
            this.state.connectionStatus = "connected";
            await this.loadForecastSnapshot();
            await this.loadRiskData();
        } catch (error) {
            this.state.connectionStatus = "unavailable";
            this.state.error = "Could not load inventory and forecast controls. Check your permissions and try again.";
            console.error("AutoStock dashboard request failed", error);
        } finally {
            this.state.loading = false;
        }
    }

    get activeSectionLabel() {
        return {
            dashboard: "Dashboard",
            forecast: "Forecasts",
            risks: "Restock",
            inventory: "Inventory",
        }[this.state.activeSection] || "Dashboard";
    }

    get riskRows() {
        const data = this.state.riskData;
        if (!data) {
            return [];
        }
        const rows = data.rows || [];
        const statusRank = { out: 0, shortage: 1, low: 2, overstock: 3, slow_moving: 4, healthy: 5, policy_missing: 6 };
        const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
        return [...rows].sort((left, right) => {
            if (this.state.riskSort === "part") {
                return collator.compare(left.name, right.name);
            }
            if (this.state.riskSort === "available") {
                return left.free_qty - right.free_qty || collator.compare(left.name, right.name);
            }
            if (this.state.riskSort === "suggested") {
                return right.recommended_qty - left.recommended_qty || collator.compare(left.name, right.name);
            }
            return (statusRank[left.risk] ?? 9) - (statusRank[right.risk] ?? 9)
                || Number(right.reorder_needed) - Number(left.reorder_needed)
                || collator.compare(left.name, right.name);
        });
    }

    // Show only bounded, explicitly scoped server risk data; never claim global top risks.
    get dashboardAlerts() {
        return this.riskRows
            .filter((row) => row.reorder_needed && Number(row.recommended_qty) > 0)
            .slice(0, 3);
    }

    async loadRiskData() {
        const options = this.state.forecastOptions;
        if (!options) {
            return;
        }
        const requestId = ++this.riskRequestId;
        const companyId = String(options.company_id);
        this.state.riskLoading = true;
        this.state.riskError = null;
        try {
            const result = await this.orm.call(
                "autostock.inventory.risk",
                "get_risk_data",
                [
                    Number(this.state.riskWarehouseId) || false,
                    this.state.riskSearch,
                    Number(this.state.riskSupplierId) || false,
                    this.state.riskStatusFilter,
                    this.state.riskHistoryFrom || false,
                    this.state.riskHistoryTo || false,
                    this.state.riskOffset,
                ]
            );
            if (
                this.destroyed
                || requestId !== this.riskRequestId
                || String(this.state.forecastOptions?.company_id) !== companyId
            ) {
                return;
            }
            this.state.riskData = result;
        } catch (error) {
            if (this.destroyed || requestId !== this.riskRequestId) {
                return;
            }
            this.state.riskError = "Stock-risk data is unavailable for the active company or your Odoo permissions.";
            console.error("AutoStock stock-risk request failed", error);
        } finally {
            if (requestId === this.riskRequestId) {
                this.state.riskLoading = false;
            }
        }
    }

    changeRiskSearch(event) {
        this.state.riskSearch = event.currentTarget.value;
        this.state.riskOffset = 0;
        window.clearTimeout(this.riskSearchTimer);
        this.riskSearchTimer = window.setTimeout(() => this.loadRiskData(), 250);
    }

    changeRiskWarehouse(event) {
        this.state.riskWarehouseId = event.currentTarget.value;
        this.state.riskOffset = 0;
        return this.loadRiskData();
    }

    changeRiskDates(event) {
        const key = event.currentTarget.dataset.key;
        if (key === "from") {
            this.state.riskHistoryFrom = event.currentTarget.value;
        } else if (key === "to") {
            this.state.riskHistoryTo = event.currentTarget.value;
        }
        this.state.riskOffset = 0;
        return this.loadRiskData();
    }

    changeRiskSupplier(event) {
        this.state.riskSupplierId = event.currentTarget.value;
        this.state.riskOffset = 0;
        return this.loadRiskData();
    }

    changeRiskStatus(event) {
        this.state.riskStatusFilter = event.currentTarget.value;
        this.state.riskOffset = 0;
        return this.loadRiskData();
    }

    changeRiskPage(event) {
        const pagination = this.state.riskData?.pagination;
        const direction = Number(event.currentTarget.dataset.direction);
        const target = direction < 0 ? pagination?.previous_offset : pagination?.next_offset;
        if (target === false || target === undefined || target === null) {
            return;
        }
        this.state.riskOffset = target;
        return this.loadRiskData();
    }

    changeRiskSort(event) {
        const key = event.currentTarget.dataset.sort;
        if (["risk", "part", "available", "suggested"].includes(key)) {
            this.state.riskSort = key;
        }
    }

    clearRiskFilters() {
        this.state.riskSearch = "";
        this.state.riskSupplierId = "";
        this.state.riskStatusFilter = "all";
        this.state.riskOffset = 0;
        this.state.riskHistoryFrom = "";
        this.state.riskHistoryTo = "";
        this.state.riskWarehouseId = "";
        return this.loadRiskData();
    }

    get healthStyle() {
        const kpis = this.state.data?.kpis;
        if (!kpis || !kpis.total) {
            return "background: #efedf5";
        }
        const healthy = (100 * kpis.healthy) / kpis.total;
        const low = (100 * kpis.low) / kpis.total;
        const second = healthy + low;
        return `background: conic-gradient(var(--as-green) 0% ${healthy}%, var(--as-amber) ${healthy}% ${second}%, var(--as-red) ${second}% 100%)`;
    }

    // A business-readable forecast total, always derived from the persisted run.
    get forecastDemandSummary() {
        const run = this.state.forecast;
        if (run?.state !== "completed" || !Array.isArray(run.predictions) || !run.predictions.length) {
            return null;
        }
        const numbers = run.predictions.map((point) => Number(point.units));
        if (numbers.some((value) => !Number.isFinite(value) || value < 0)) {
            return null;
        }
        const total = numbers.reduce((sum, value) => sum + value, 0);
        return {
            units: Math.round(total * 10) / 10,
            horizon: Number(run.horizon_days),
            uom: run.uom || "units",
        };
    }

    get selectedProduct() {
        return this.state.forecastOptions?.products.find(
            (product) => String(product.id) === String(this.state.filters.productId)
        );
    }

    isSelectedProduct(product) {
        return this.selectedProduct?.id === product.id;
    }

    get selectedWarehouse() {
        return this.state.forecastOptions?.warehouses.find(
            (warehouse) => String(warehouse.id) === String(this.state.filters.warehouseId)
        );
    }

    get selectedCoverageStart() {
        if (this.state.filters.sourceType !== REAL_SOURCE) {
            return false;
        }
        return this.state.filters.warehouseId
            ? this.selectedWarehouse?.coverage_start || false
            : this.state.forecastOptions?.coverage_start || false;
    }

    get forecastStateLabel() {
        const labels = {
            queued: "Queued",
            running: "Evaluating",
            completed: "Evaluated",
            insufficient_history: "Insufficient history",
            no_observed_demand: "No completed demand observed",
            failed: "Forecast unavailable",
        };
        return labels[this.state.forecast?.state] || "Ready for evaluation";
    }

    get forecastChart() {
        const run = this.state.forecast;
        if (run?.state !== "completed" || !run.observations?.length || !run.predictions?.length) {
            return null;
        }
        const allActual = run.observations;
        const future = run.predictions;
        const visibleHistoryDays = this.state.chartWindowDays === "full"
            ? allActual.length
            : Math.min(Number(this.state.chartWindowDays) || 30, allActual.length);
        const actual = allActual.slice(-visibleHistoryDays);
        const values = [
            ...actual.map((point) => point.units),
            ...future.map((point) => point.upper_heuristic),
        ];
        const max = Math.max(1, ...values);
        const axisMax = Math.max(4, Math.ceil(max / 4) * 4);
        const width = this.state.chartWidth;
        const left = 56;
        const right = width - 16;
        const top = 20;
        const bottom = 174;
        const count = actual.length + future.length;
        const x = (index) => left + ((right - left) * index) / Math.max(1, count - 1);
        const y = (value) => bottom - ((bottom - top) * value) / axisMax;
        const pathFor = (points, offset = 0) =>
            points.map((point, index) => `${index ? "L" : "M"}${x(index + offset).toFixed(1)},${y(point.units).toFixed(1)}`).join(" ");
        const historyPath = pathFor(actual);
        const forecastPath = pathFor([actual.at(-1), ...future], actual.length - 1);
        const upper = future.map((point, index) => `${x(actual.length + index).toFixed(1)},${y(point.upper_heuristic).toFixed(1)}`);
        const lower = future
            .map((point, index) => `${x(actual.length + index).toFixed(1)},${y(point.lower_heuristic).toFixed(1)}`)
            .reverse();
        const forecastBand = `M${upper.join(" L")} L${lower.join(" L")} Z`;
        const dateAt = (index) => index < actual.length
            ? actual[index].day
            : future[Math.min(index - actual.length, future.length - 1)].day;
        const dateIndexes = this.state.chartWindowDays === "full"
            ? [0, Math.floor((actual.length - 1) / 2), count - 1]
            : [
                0,
                Math.floor((actual.length - 1) / 2),
                actual.length - 1,
                actual.length - 1 + Math.floor(future.length / 2),
                count - 1,
            ];
        const dateTicks = [...new Set(dateIndexes)].map((index) => {
            const date = dateAt(index);
            return { x: x(index).toFixed(1), date, label: date.slice(5).replace("-", "/") };
        });
        const valueTicks = Array.from({ length: 5 }, (_, index) => {
            const value = (axisMax * (4 - index)) / 4;
            const tickY = y(value);
            return { y: tickY.toFixed(1), labelY: (tickY + 4).toFixed(1), label: String(Math.round(value)) };
        });
        return {
            width,
            viewBox: `0 0 ${width} 220`,
            accessibleLabel: `Daily delivered units and ${run.horizon_days} day forecast for ${run.sku}, showing ${visibleHistoryDays} of ${allActual.length} history days from ${actual[0].day} through ${actual.at(-1).day}. Units: ${run.uom}`,
            left,
            right,
            historyPath,
            forecastPath,
            forecastBand,
            axisMax,
            valueTicks,
            dateTicks,
            visibleHistoryDays,
            totalHistoryDays: allActual.length,
            firstDate: actual[0].day,
            cutoffDate: run.history_end,
            cutoffX: x(actual.length - 1).toFixed(1),
            lastDate: future.at(-1).day,
        };
    }

    syncChartWidth() {
        if (this.destroyed || !this.chartFrame.el) {
            return;
        }
        const svg = this.chartFrame.el.querySelector(".as-forecast-chart");
        const renderedWidth = svg?.getBoundingClientRect().width;
        if (!renderedWidth) {
            return;
        }
        // The viewBox must track the SVG viewport. A stale, smaller viewBox is
        // centered by SVG's default preserveAspectRatio and leaves empty sides.
        const width = Math.max(260, Math.round(renderedWidth));
        if (width !== this.state.chartWidth) {
            this.state.chartWidth = width;
        }
    }

    toggleMobileNav() {
        if (!this.state.mobileView) {
            return;
        }
        this.state.navOpen = !this.state.navOpen;
        if (this.state.navOpen) {
            window.requestAnimationFrame(() => {
                window.requestAnimationFrame(() => this.mobileNavDrawer.el?.focus());
            });
        } else {
            window.requestAnimationFrame(() => this.mobileMenuButton.el?.focus());
        }
    }

    closeMobileNav(restoreFocus = true) {
        if (!this.state.navOpen) {
            return;
        }
        this.state.navOpen = false;
        if (restoreFocus && this.state.mobileView) {
            window.requestAnimationFrame(() => this.mobileMenuButton.el?.focus());
        }
    }

    onShellKeydown(event) {
        if (!this.state.mobileView || !this.state.navOpen) {
            return;
        }
        if (event.key === "Escape") {
            event.preventDefault();
            this.closeMobileNav();
            return;
        }
        if (event.key !== "Tab") {
            return;
        }
        const drawer = this.mobileNavDrawer.el;
        const focusable = drawer?.querySelectorAll("a[href], button:not([disabled])");
        if (!focusable?.length) {
            event.preventDefault();
            drawer?.focus();
            return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && (document.activeElement === first || document.activeElement === drawer)) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    // Navigation selects a real workspace screen, not a scroll position in one long page.
    navigateWorkspace(section) {
        this.state.activeSection = section;
        this.closeMobileNav();
        this.dashboardScroll?.el?.scrollTo({ top: 0, behavior: "instant" });
        window.requestAnimationFrame(() => {
            this.dashboardScroll?.el?.querySelector(".as-topline h1")?.focus({ preventScroll: true });
            this.syncChartWidth();
        });
    }

    scrollToDashboard() {
        this.navigateWorkspace("dashboard");
    }

    scrollToForecast() {
        this.navigateWorkspace("forecast");
    }

    scrollToRisks() {
        this.navigateWorkspace("risks");
    }

    changeChartWindow(event) {
        const range = event.currentTarget.dataset.days;
        if (range === "full") {
            this.state.chartWindowDays = "full";
            return;
        }
        const days = Number(range);
        if ([30, 90].includes(days)) {
            this.state.chartWindowDays = days;
        }
    }

    resetHistoryRange() {
        const options = this.state.forecastOptions;
        if (!options) {
            return;
        }
        const filters = this.state.filters;
        const today = options.today_utc;
        filters.historyEnd = today;
        if (filters.sourceType === DEMO_SOURCE) {
            filters.historyStart = shiftDate(today, -209);
            return;
        }
        filters.historyStart = maxDate(
            shiftDate(today, -209),
            this.selectedProduct?.created_on,
            this.state.filters.warehouseId
                ? this.selectedWarehouse?.coverage_start
                : options.coverage_start
        );
    }

    changeSource(event) {
        this.state.filters.sourceType = event.currentTarget.value;
        this.resetHistoryRange();
        return this.loadForecastSnapshot();
    }

    changeProduct(event) {
        this.state.filters.productId = event.currentTarget.value;
        this.resetHistoryRange();
        return this.loadForecastSnapshot();
    }

    changeWarehouse(event) {
        this.state.filters.warehouseId = event.currentTarget.value;
        this.resetHistoryRange();
        return this.loadForecastSnapshot();
    }

    async loadForecastSnapshot() {
        const options = this.state.forecastOptions;
        if (!options) {
            return;
        }
        const requestId = ++this.forecastSnapshotRequestId;
        const companyId = String(options.company_id);
        const filters = this.state.filters;
        try {
            const result = await this.orm.call(
                "autostock.forecast.run",
                "get_forecast_snapshot",
                [
                    filters.sourceType,
                    filters.sourceType === REAL_SOURCE ? Number(filters.productId) || false : false,
                    filters.sourceType === DEMO_SOURCE ? filters.sku : false,
                    Number(filters.horizon),
                    filters.sourceType === REAL_SOURCE ? Number(filters.warehouseId) || false : false,
                    filters.historyStart || false,
                    filters.historyEnd || false,
                    filters.historyStart || false,
                    filters.historyEnd || false,
                ]
            );
            if (
                this.destroyed
                || requestId !== this.forecastSnapshotRequestId
                || String(this.state.forecastOptions?.company_id) !== companyId
            ) {
                return;
            }
            this.state.forecast = result.run || null;
            this.state.forecastError = null;
        } catch (error) {
            if (
                this.destroyed
                || requestId !== this.forecastSnapshotRequestId
                || String(this.state.forecastOptions?.company_id) !== companyId
            ) {
                return;
            }
            this.state.forecast = null;
            this.state.forecastError = "Forecast results are unavailable for the selected company or account permissions.";
            console.error("AutoStock forecast snapshot request failed", error);
        }
    }

    async submitForecast() {
        if (this.state.forecastBusy) {
            return;
        }
        this.state.forecastBusy = true;
        this.state.forecastError = null;
        this.state.forecastNotice = null;
        try {
            const filters = this.state.filters;
            let queued;
            if (filters.sourceType === DEMO_SOURCE) {
                queued = await this.orm.call(
                    "autostock.forecast.run",
                    "seed_synthetic_demo",
                    [filters.sku, Number(filters.horizon), filters.historyStart, filters.historyEnd]
                );
            } else {
                if (!this.state.forecastOptions.can_forecast_real || !filters.productId) {
                    throw new Error("A tracked SKU and sales access are required for an Odoo delivery forecast.");
                }
                queued = await this.orm.call(
                    "autostock.forecast.run",
                    "request_forecast",
                    [
                        Number(filters.productId),
                        Number(filters.horizon),
                        filters.historyStart,
                        filters.historyEnd,
                        Number(filters.warehouseId) || false,
                    ]
                );
            }
            await this.loadForecastSnapshot();
            if (queued.state === "queued") {
                for (let attempt = 0; attempt < 18 && !this.destroyed; attempt++) {
                    if (!["queued", "running"].includes(this.state.forecast?.state)) {
                        break;
                    }
                    await new Promise((resolve) => window.setTimeout(resolve, 4000));
                    if (!this.destroyed) {
                        await this.loadForecastSnapshot();
                    }
                }
                if (["queued", "running"].includes(this.state.forecast?.state)) {
                    this.state.forecastNotice = "The background job is still queued. Refresh results in a moment.";
                }
            }
        } catch (error) {
            this.state.forecastError =
                error.message || "Could not queue this forecast. Review the history dates and your Odoo permissions.";
            console.error("AutoStock forecast request failed", error);
        } finally {
            this.state.forecastBusy = false;
        }
    }

    openProducts() {
        this.state.activeSection = "inventory";
        this.closeMobileNav(false);
        return this.action.doAction("autostock_ai.action_autostock_products");
    }

    openProduct(event) {
        this.state.activeSection = "inventory";
        const id = Number(event.currentTarget.dataset.productTemplateId);
        if (!Number.isInteger(id) || id <= 0) {
            return;
        }
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "Automotive Part",
            res_model: "product.template",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("autostock_ai.dashboard", AutoStockDashboard);
