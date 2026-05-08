/** @odoo-module **/

import {
    Component, useState, onWillStart, onMounted, onWillUnmount,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

// ---------------------------------------------------------------------------
// Helpers de teclas
// ---------------------------------------------------------------------------
const KEY_LABELS = {
    Numpad0: "Num 0", Numpad1: "Num 1", Numpad2: "Num 2", Numpad3: "Num 3",
    Numpad4: "Num 4", Numpad5: "Num 5", Numpad6: "Num 6", Numpad7: "Num 7",
    Numpad8: "Num 8", Numpad9: "Num 9",
    NumpadAdd: "Num +", NumpadSubtract: "Num −", NumpadMultiply: "Num ×",
    NumpadDivide: "Num /", NumpadEnter: "Num Enter", NumpadDecimal: "Num .",
    ArrowUp: "↑", ArrowDown: "↓", ArrowLeft: "←", ArrowRight: "→",
    Enter: "Enter", Escape: "Esc", Space: "Espacio",
};

function keyLabel(code) {
    if (!code) return "—";
    if (KEY_LABELS[code]) return KEY_LABELS[code];
    if (code.startsWith("Key"))   return code.slice(3);
    if (code.startsWith("Digit")) return code.slice(5);
    return code;
}

const DEFAULT_KEYS = {
    key_nav_up:    "Numpad8",
    key_nav_down:  "Numpad5",
    key_nav_left:  "Numpad4",
    key_nav_right: "Numpad6",
    key_complete:  "NumpadEnter",
    key_undo:      "NumpadSubtract",
};

// ---------------------------------------------------------------------------
// KDS Dashboard
// ---------------------------------------------------------------------------
class KdsDashboard extends Component {
    static template = "bitopolis_kds.Dashboard";
    static props = {
        action:             { optional: true },
        actionId:           { optional: true },
        updateActionState:  { optional: true },
        className:          { optional: true },
    };

    setup() {
        this.action       = useService("action");
        this.notification = useService("notification");

        const emptyConfig = {
            warn_minutes: 5, danger_minutes: 15,
            sound_enabled: true, poll_interval: 2, undo_count: 5,
            font_size: 17, sound_volume: 0.5,
            ...DEFAULT_KEYS,
        };

        this.state = useState({
            licenseValid: false,
            loading:       true,
            saving:        false,
            saved:         false,
            showConfig:    false,
            totalPending:  0,
            stations:      [],
            config:        { ...emptyConfig },
            form:          { ...emptyConfig },
            capturingFor:  null,   // campo que espera una tecla
        });

        this._refreshTimer  = null;
        this._captureHandler = this._captureHandler.bind(this);

        onWillStart(async () => {
            await this._checkLicense(); await this._loadDashboard(); });

        onMounted(() => {
            this._refreshTimer = setInterval(() => this._loadDashboard(true), 30000);
        });

        onWillUnmount(() => {
            clearInterval(this._refreshTimer);
            window.removeEventListener("keydown", this._captureHandler);
        });
    }

    // -----------------------------------------------------------------------
    async _rpc(route, params = {}) {
        const resp = await fetch(route, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Csrf-Token": odoo.csrf_token },
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", id: 1, params }),
        });
        const data = await resp.json();
        if (data.error) throw new Error(
            data.error.data?.message || data.error.message || JSON.stringify(data.error)
        );
        return data.result;
    }

    // -----------------------------------------------------------------------
    async _loadDashboard(silentRefresh = false) {
        if (!silentRefresh) this.state.loading = true;
        try {
            const data = await this._rpc("/kds/dashboard");
            this.state.totalPending  = data.total_pending || 0;
            this.state.stations      = data.stations      || [];
            if (data.license_valid !== undefined) {
                this.state.licenseValid = data.license_valid;
            }
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
    openKds(stationId = null, token = null) {
        const url = token
            ? `/kds/ui?token=${token}`
            : stationId
                ? `/kds/ui?station_id=${stationId}`
                : '/kds/ui';
        window.open(url, "_blank");
    }

    openStationForm(stationId = null) {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "kds.station",
            view_mode: "form", views: [[false, "form"]],
            target: "current", res_id: stationId || false,
        });
    }

    openStationsList()  { this.action.doAction("bitopolis_kds.action_kds_stations"); }
    openOrderHistory()  { this.action.doAction("bitopolis_kds.action_kds_order_admin"); }

    // -----------------------------------------------------------------------
    // Config inline
    // -----------------------------------------------------------------------
    toggleConfigEditor() {
        this.stopCapture();
        this.state.showConfig = !this.state.showConfig;
        if (this.state.showConfig) {
            this.state.form  = { ...this.state.config };
            this.state.saved = false;
        }
    }

    async saveConfig() {
        this.stopCapture();
        this.state.saving = true;
        try {
            let wm = Math.max(1, parseInt(this.state.form.warn_minutes)   || 5);
            let dm = Math.max(1, parseInt(this.state.form.danger_minutes) || 15);
            if (dm <= wm) dm = wm + 1;
            const vals = {
                warn_minutes:   wm,
                danger_minutes: dm,
                sound_enabled:  Boolean(this.state.form.sound_enabled),
                poll_interval:  Math.max(5, parseInt(this.state.form.poll_interval) || 5),
                undo_count:     Math.max(1, parseInt(this.state.form.undo_count)    || 5),
                font_size:      String(Math.min(60, Math.max(10, parseInt(this.state.form.font_size) || 17))),
                sound_volume:   Math.min(1, Math.max(0.1, parseFloat(this.state.form.sound_volume) || 0.5)),
                key_nav_up:     this.state.form.key_nav_up    || DEFAULT_KEYS.key_nav_up,
                key_nav_down:   this.state.form.key_nav_down  || DEFAULT_KEYS.key_nav_down,
                key_nav_left:   this.state.form.key_nav_left  || DEFAULT_KEYS.key_nav_left,
                key_nav_right:  this.state.form.key_nav_right || DEFAULT_KEYS.key_nav_right,
                key_complete:   this.state.form.key_complete  || DEFAULT_KEYS.key_complete,
                key_undo:       this.state.form.key_undo      || DEFAULT_KEYS.key_undo,
            };
            const result = await this._rpc("/kds/config/save", { vals });
            if (result?.ok) {
                this.state.config = { ...vals };
                this.state.form   = { ...vals };
                this.state.saved  = true;
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
    // Captura de tecla para key bindings
    // -----------------------------------------------------------------------
    startCapture(field) {
        if (this.state.capturingFor === field) {
            this.stopCapture();
            return;
        }
        this.state.capturingFor = field;
        window.addEventListener("keydown", this._captureHandler);
    }

    stopCapture() {
        this.state.capturingFor = null;
        window.removeEventListener("keydown", this._captureHandler);
    }

    _captureHandler(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        if (ev.code === "Escape") { this.stopCapture(); return; }

        const field   = this.state.capturingFor;
        const newCode = ev.code;

        // Verificar conflicto con otros campos de tecla
        const keyFields = Object.keys(DEFAULT_KEYS);
        const conflict  = keyFields.find(
            (k) => k !== field && this.state.form[k] === newCode
        );
        if (conflict) {
            this.notification.add(
                `"${keyLabel(newCode)}" ya está asignada a otra acción`,
                { type: "warning" }
            );
            return;
        }
        this.state.form[field] = newCode;
        this.stopCapture();
    }

    resetKeys() {
        for (const [k, v] of Object.entries(DEFAULT_KEYS)) {
            this.state.form[k] = v;
        }
        this.stopCapture();
    }

    // -----------------------------------------------------------------------
    // Helpers template
    // -----------------------------------------------------------------------
    keyLabel(code) { return keyLabel(code); }

    get keyBindingRows() {
        return [
            { field: "key_nav_up",    icon: "⬆",  label: "Arriba" },
            { field: "key_nav_down",  icon: "⬇",  label: "Abajo" },
            { field: "key_nav_left",  icon: "⬅",  label: "Izquierda" },
            { field: "key_nav_right", icon: "➡",  label: "Derecha" },
            { field: "key_complete",  icon: "✓",  label: "Completar orden" },
            { field: "key_undo",      icon: "↩",  label: "Deshacer última" },
        ];
    }

    async deleteStation(stationId) {
        if (!confirm("¿Eliminar esta estación? Esta acción no se puede deshacer.")) return;
        try {
            await this.action.doAction({
                type: "ir.actions.server",
                model_name: "kds.station",
            });
            // Fallback: delete via ORM directly
            const env = this.__owl__.app?.env;
            await fetch("/web/dataset/call_kw/kds.station/unlink", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-Csrf-Token": odoo.csrf_token },
                body: JSON.stringify({
                    jsonrpc: "2.0", method: "call", id: 1,
                    params: { model: "kds.station", method: "unlink", args: [[stationId]], kwargs: {} }
                }),
            });
            await this._loadDashboard();
            this.notification.add("Estación eliminada", { type: "success" });
        } catch (e) {
            this.notification.add("Error al eliminar: " + e.message, { type: "danger" });
        }
    }

    async _deleteStationDirect(stationId) {
        const resp = await fetch("/web/dataset/call_kw/kds.station/unlink", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Csrf-Token": odoo.csrf_token },
            body: JSON.stringify({
                jsonrpc: "2.0", method: "call", id: 1,
                params: { model: "kds.station", method: "unlink", args: [[stationId]], kwargs: {} }
            }),
        });
        const data = await resp.json();
        if (data.error) throw new Error(data.error.data?.message || data.error.message);
        return data.result;
    }

    async confirmDeleteStation(stationId, stationName) {
        if (!confirm(`¿Eliminar la estación "${stationName}"? Esta acción no se puede deshacer.`)) return;
        try {
            await this._deleteStationDirect(stationId);
            await this._loadDashboard();
            this.notification.add(`Estación "${stationName}" eliminada`, { type: "success" });
        } catch (e) {
            this.notification.add("Error al eliminar: " + e.message, { type: "danger" });
        }
    }

    get volumeLabel() {
        const v = this.state.form.sound_volume || 0.5;
        if (v >= 0.9) return "🔊 Máximo";
        if (v >= 0.6) return "🔉 Alto";
        if (v >= 0.3) return "🔈 Medio";
        return "🔇 Bajo";
    }

    get fontSizePresets() {
        return [
            { label: 'Pequeño', value: 14 },
            { label: 'Normal',  value: 17 },
            { label: 'Grande',  value: 21 },
            { label: 'XL',      value: 27 },
            { label: 'XXL',     value: 34 },
        ];
    }

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
            { icon: "⏱",  label: "Polling",  value: `${c.poll_interval}s` },
        ];
    }

    async _checkLicense() {
        try {
            const r = await fetch('/kds/license/check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Csrf-Token': odoo.csrf_token },
                body: JSON.stringify({ jsonrpc: '2.0', method: 'call', id: 1, params: {} }),
            });
            const data = await r.json();
            this.state.licenseValid = data?.result?.valid ?? false;
        } catch {
            this.state.licenseValid = false;
        }
    }
}

registry.category("actions").add("bitopolis_kds.dashboard", KdsDashboard);

