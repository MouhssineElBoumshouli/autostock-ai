/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Phase 1: live read-only inventory dashboard. Future phases will connect
 * independently evaluated ML forecasts and reviewed purchasing workflows.
 */
export class AutoStockDashboard extends Component {
    static template = "autostock_ai.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, error: null, data: null });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call("autostock.dashboard", "get_dashboard_data", []);
        } catch (error) {
            this.state.error = "Could not load inventory. Check your permissions and try again.";
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
