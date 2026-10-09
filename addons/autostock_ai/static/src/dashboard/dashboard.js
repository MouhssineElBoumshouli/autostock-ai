/** @odoo-module **/
import { Component, onWillDestroy, onWillStart, useState } from "@odoo/owl";
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
        this.state = useState({
            loading: true,
            error: null,
            data: null,
            forecastOptions: null,
            forecast: null,
            forecastBusy: false,
            forecastError: null,
            forecastNotice: null,
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
        onWillStart(() => this.load());
        onWillDestroy(() => {
            this.destroyed = true;
        });
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const [data, options] = await Promise.all([
                this.orm.call("autostock.dashboard", "get_dashboard_data", []),
                this.orm.call("autostock.forecast.run", "get_forecast_options", []),
            ]);
            const companyChanged = this.state.forecastOptions?.company_name !== options.company_name;
            this.state.data = data;
            this.state.forecastOptions = options;
            if (companyChanged) {
                this.state.forecast = null;
                this.state.filters.sourceType = DEMO_SOURCE;
                this.state.filters.productId = options.products[0]?.id ? String(options.products[0].id) : "";
                this.state.filters.sku = options.demo_skus[0]?.sku || "DEMO-BP-001";
                this.state.filters.warehouseId = "";
                this.resetHistoryRange();
            }
            await this.loadForecastSnapshot();
        } catch (error) {
            this.state.error = "Could not load inventory and forecast controls. Check your permissions and try again.";
            console.error("AutoStock dashboard request failed", error);
        } finally {
            this.state.loading = false;
        }
    }

    get healthStyle() {
        const kpis = this.state.data?.kpis;
        if (!kpis || !kpis.total) {
            return "background: #efedf5";
        }
        const healthy = (100 * kpis.healthy) / kpis.total;
        const low = (100 * kpis.low) / kpis.total;
        const second = healthy + low;
        return `background: conic-gradient(#35b882 0% ${healthy}%, #eda94c ${healthy}% ${second}%, #ef6b79 ${second}% 100%)`;
    }

    get selectedProduct() {
        return this.state.forecastOptions?.products.find(
            (product) => String(product.id) === String(this.state.filters.productId)
        );
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
        const actual = run.observations;
        const future = run.predictions;
        const values = [
            ...actual.map((point) => point.units),
            ...future.map((point) => point.upper_heuristic),
        ];
        const max = Math.max(1, ...values);
        const width = 800;
        const left = 44;
        const right = 780;
        const top = 20;
        const bottom = 178;
        const count = actual.length + future.length;
        const x = (index) => left + ((right - left) * index) / Math.max(1, count - 1);
        const y = (value) => bottom - ((bottom - top) * value) / max;
        const pathFor = (points, offset = 0) =>
            points.map((point, index) => `${index ? "L" : "M"}${x(index + offset).toFixed(1)},${y(point.units).toFixed(1)}`).join(" ");
        const historyPath = pathFor(actual);
        const forecastPath = pathFor([actual.at(-1), ...future], actual.length - 1);
        const upper = future.map((point, index) => `${x(actual.length + index).toFixed(1)},${y(point.upper_heuristic).toFixed(1)}`);
        const lower = future
            .map((point, index) => `${x(actual.length + index).toFixed(1)},${y(point.lower_heuristic).toFixed(1)}`)
            .reverse();
        const forecastBand = `M${upper.join(" L")} L${lower.join(" L")} Z`;
        return {
            width,
            historyPath,
            forecastPath,
            forecastBand,
            max: Math.ceil(max),
            firstDate: actual[0].day,
            cutoffDate: run.history_end,
            cutoffX: x(actual.length - 1).toFixed(1),
            lastDate: future.at(-1).day,
        };
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
            this.state.forecast = result.run || null;
            this.state.forecastError = null;
        } catch (error) {
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
        return this.action.doAction("autostock_ai.action_autostock_products");
    }

    openProduct(event) {
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
