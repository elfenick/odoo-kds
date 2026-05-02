/** @odoo-module **/

import {
    Component, useState, onWillStart, onMounted, onWillUnmount,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

// ---------------------------------------------------------------------------
// KDS Dashboard — componente principal del backend
// Carga datos via rutas HTTP dedicadas (bypass ACL) igual que el KDS window
// ---------------------------------------------------------------------------

class KdsDashboard extends Component {
    static template = "bitopolis_kds.Dashboard";
    static props = {};

    setup() {
        this.action   = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading:      true,
            saving:       false,
            saved:        false,
            showConfig:   false,
            totalPending: 0,
            stations:     [],

            // Config (editable inline)
            config: {
                warn_minutes:   5,
                danger_minutes: 15,
                sound_enabled:  true,
                poll_interval:  5,
                undo_count:     5,
            },

            // Copia de trabajo del formulario de config
            form: {
                warn_minutes:   5,
                danger_minutes: 15,
                sound_enabled:  true,
                poll_interval:  5,
                undo_count:     5,
            },
        });

        this._refreshTimer = null;

        onWillStart(async () => {
            await this._loadDashboard();
        });

        onMounted(() => {
            // Refresca pending count cada 30s
            this._refreshTimer = setInterval(
                () => this._loadDashboard(true),
                30000
            );
        });

        onWillUnmount(() => {
            clearInterval(this._refreshTimer);
        });
    }

    // -----------------------------------------------------------------------
    // HTTP helper (bypass ORM ACL — same pattern as KDS window)
    // -----------------------------------------------------------------------
    async _rpc(route, params = {}) {
        const resp = await fetch(route, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Csrf-Token": odoo.csrf_token,
            },
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", id: 1, params }),
        });
        const data = await resp.json();
        if (data.error) {
            throw new Error(
                data.error.data?.message || data.error.message || JSON.stringify(data.error)
            );
        }
        return data.result;
    }

    // -----------------------------------------------------------------------
    // Carga de datos
    // -----------------------------------------------------------------------
    async _loadDashboard(silentRefresh = false) {
        if (!silentRefresh) this.state.loading = true;
        try {
            const data = await this._rpc("/kds/dashboard");
            this.state.totalPending = data.total_pending || 0;
            this.state.stations     = data.stations || [];
            this.state.config       = { ...this.state.config, ...data.config };
            this.state.form         = { ...this.state.config };
        } catch (e) {
            console.error("KDS Dashboard load error:", e);
        } finally {
            this.state.loading = false;
        }
    }

    // -----------------------------------------------------------------------
    // Acciones de tarjetas
    // -----------------------------------------------------------------------
    openKds(stationId = null) {
        const url = stationId ? `/kds/ui?station_id=${stationId}` : "/kds/ui";
        window.open(url, "_blank");
    }

    openStationForm(stationId = null) {
        this.action.doAction({
            type:       "ir.actions.act_window",
            res_model:  "kds.station",
            view_mode:  "form",
            views:      [[false, "form"]],
            target:     "current",
            res_id:     stationId || false,
        });
    }

    openStationsList() {
        this.action.doAction("bitopolis_kds.action_kds_stations");
    }

    openOrderHistory() {
        this.action.doAction("bitopolis_kds.action_kds_order_admin");
    }

    // -----------------------------------------------------------------------
    // Config inline
    // -----------------------------------------------------------------------
    toggleConfigEditor() {
        this.state.showConfig = !this.state.showConfig;
        if (this.state.showConfig) {
            // Resetear form a valores actuales
            this.state.form = { ...this.state.config };
            this.state.saved = false;
        }
    }

    async saveConfig() {
        this.state.saving = true;
        try {
            // Validar
            let wm = Math.max(1, parseInt(this.state.form.warn_minutes)   || 5);
            let dm = Math.max(1, parseInt(this.state.form.danger_minutes) || 15);
            if (dm <= wm) dm = wm + 1;
            const vals = {
                warn_minutes:   wm,
                danger_minutes: dm,
                sound_enabled:  Boolean(this.state.form.sound_enabled),
                poll_interval:  Math.max(5, parseInt(this.state.form.poll_interval) || 5),
                undo_count:     Math.max(1, parseInt(this.state.form.undo_count)    || 5),
            };
            const result = await this._rpc("/kds/config/save", { vals });
            if (result?.ok) {
                this.state.config     = { ...vals };
                this.state.form       = { ...vals };
                this.state.saved      = true;
                setTimeout(() => {
                    this.state.saved      = false;
                    this.state.showConfig = false;
                }, 1800);
            }
        } catch (e) {
            this.notification.add("Error al guardar: " + e.message, { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    // -----------------------------------------------------------------------
    // Helpers para template
    // -----------------------------------------------------------------------
    get pendingClass() {
        return this.state.totalPending > 0 ? "has-orders" : "";
    }

    get configSummaryItems() {
        const c = this.state.config;
        return [
            { icon: "🟡", label: "Amarillo", value: `${c.warn_minutes} min` },
            { icon: "🔴", label: "Rojo",     value: `${c.danger_minutes} min` },
            { icon: c.sound_enabled ? "🔔" : "🔕", label: "Sonido",
              value: c.sound_enabled ? "Activado" : "Desactivado" },
            { icon: "⏱", label: "Polling",   value: `${c.poll_interval}s` },
        ];
    }
}

// Registrar como client action de Odoo
registry.category("actions").add("bitopolis_kds.dashboard", KdsDashboard);
