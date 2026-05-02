/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { OrderCard } from "./order_card";

/**
 * KDS App — ventana standalone /kds/ui
 *
 * Responsabilidad única: mostrar órdenes y permitir completarlas.
 * Toda la configuración y selección de estación se hace desde el
 * backend de Odoo (Panel de Control → Bitópolis KDS).
 */
export class KdsApp extends Component {
    static template = "bitopolis_kds.KdsApp";
    static components = { OrderCard };
    static props = {};

    setup() {
        this.orm         = useService("orm");
        this.bus         = useService("bus_service");
        this.notification = useService("notification");

        const companyId      = odoo.session_info?.user_companies?.current_company ?? 1;
        const initialStation = odoo.kds_station_id ?? null;

        this.state = useState({
            orders:        [],
            recentlyDone:  [],
            now:           Date.now(),
            connected:     false,
            companyId,
            keypadBuffer:  "",
            stationLabel:  "",   // nombre de estación para mostrar en header
            stationShowAll: false,

            // Umbrales de color (se cargan del servidor al iniciar)
            warnSeconds:   5  * 60,
            dangerSeconds: 15 * 60,
            undoCount:     5,
            pollInterval:  5,
            soundEnabled:  true,
            showUndoTray:  false,
        });

        this._stationId   = initialStation;
        this._tickTimer   = null;
        this._pollTimer   = null;
        this._numpadTimer = null;

        // Binds explícitos
        this._onKeydown         = this._onKeydown.bind(this);
        this._onBusNotification = this._onBusNotification.bind(this);
        this.completeOrder      = this.completeOrder.bind(this);
        this.reopenOrder        = this.reopenOrder.bind(this);

        onWillStart(async () => {
            await this._fetchConfig();
            await this._fetchOrders();
        });

        onMounted(() => {
            this._tickTimer = setInterval(() => { this.state.now = Date.now(); }, 1000);
            this._startPolling();

            const channel = `bitopolis_kds#${this.state.companyId}`;
            this.bus.addChannel(channel);
            this.bus.addEventListener("notification", this._onBusNotification);
            this.bus.start();
            this.state.connected = true;

            window.addEventListener("keydown", this._onKeydown);
        });

        onWillUnmount(() => {
            clearInterval(this._tickTimer);
            clearInterval(this._pollTimer);
            clearTimeout(this._numpadTimer);
            window.removeEventListener("keydown", this._onKeydown);
        });
    }

    // ------------------------------------------------------------------
    // HTTP helper (bypass ORM ACL)
    // ------------------------------------------------------------------
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
        if (data.error) throw new Error(
            data.error.data?.message || data.error.message || JSON.stringify(data.error)
        );
        return data.result;
    }

    // ------------------------------------------------------------------
    // Config (solo lectura — se edita desde el backend)
    // ------------------------------------------------------------------
    async _fetchConfig() {
        try {
            const cfg = await this._rpc("/kds/config/get");
            if (!cfg) return;
            this.state.warnSeconds   = (cfg.warn_minutes   || 5)  * 60;
            this.state.dangerSeconds = (cfg.danger_minutes || 15) * 60;
            this.state.pollInterval  = cfg.poll_interval || 5;
            this.state.undoCount     = cfg.undo_count    || 5;
            this.state.soundEnabled  = cfg.sound_enabled !== false;

            // Nombre de estación
            if (this._stationId) {
                const dash = await this._rpc("/kds/dashboard");
                const station = (dash?.stations || []).find(
                    (s) => s.id === this._stationId
                );
                this.state.stationLabel = station?.name || "";
                this.state.stationShowAll = !!station?.show_all;
            }
        } catch (e) {
            console.warn("KDS: usando config default.", e);
        }
    }

    // ------------------------------------------------------------------
    // Órdenes
    // ------------------------------------------------------------------
    async _fetchOrders() {
        try {
            const stationId = this._stationId || false;
            const [active, recent] = await Promise.all([
                this.orm.call("kds.order", "kds_get_active_orders", [stationId]),
                this.orm.call("kds.order", "kds_get_recently_done", [this.state.undoCount, this._stationId || false]),
            ]);
            const prevIds = new Set(this.state.orders.map((o) => o.id));
            const hasNew  = active.some((o) => !prevIds.has(o.id));
            if (hasNew && this.state.soundEnabled && prevIds.size > 0) {
                this._playBeep();
            }
            this.state.orders      = active;
            this.state.recentlyDone = recent.slice(0, this.state.undoCount);
        } catch (e) {
            console.error("KDS fetch error:", e);
        }
    }

    _startPolling() {
        clearInterval(this._pollTimer);
        this._pollTimer = setInterval(
            () => this._fetchOrders(),
            (this.state.pollInterval || 5) * 1000
        );
    }

    // ------------------------------------------------------------------
    // Bus
    // ------------------------------------------------------------------
    _onBusNotification(ev) {
        const notifications = ev.detail || [];
        const relevant = notifications.some(
            (n) => (n.type || n?.[1]?.type) === "kds.update"
        );
        if (relevant) this._fetchOrders();
    }

    // ------------------------------------------------------------------
    // Completar / Deshacer
    // ------------------------------------------------------------------
    async completeOrder(orderId) {
        const idx = this.state.orders.findIndex((o) => o.id === orderId);
        if (idx >= 0) this.state.orders[idx]._removing = true;
        try {
            await this.orm.call("kds.order", "kds_complete", [orderId, this._stationId || false]);
            setTimeout(async () => {
                this.state.orders = this.state.orders.filter((o) => o.id !== orderId);
                await this._refreshRecentlyDone();
            }, 130);
        } catch (e) {
            if (idx >= 0) this.state.orders[idx]._removing = false;
            this.notification.add("Error al completar la orden", { type: "danger" });
        }
    }

    async reopenOrder(orderId) {
        try {
            const order = await this.orm.call("kds.order", "kds_reopen", [orderId, this._stationId || false]);
            if (order) {
                this.state.recentlyDone = this.state.recentlyDone.filter(
                    (o) => (o.done_id || o.id) !== orderId
                );
                this.state.orders = [order, ...this.state.orders];
                this.notification.add(
                    `↩ Orden #${order.tracking_number || order.name} reabierta`,
                    { type: "success" }
                );
            }
        } catch (e) {
            console.error("KDS reopen error:", e);
        }
    }

    async reopenLastOrder() {
        if (!this.state.recentlyDone.length) {
            this.notification.add("No hay órdenes recientes para deshacer", {
                type: "warning",
            });
            return;
        }
        await this.reopenOrder(this.state.recentlyDone[0].done_id || this.state.recentlyDone[0].id);
    }

    async _refreshRecentlyDone() {
        try {
            const recent = await this.orm.call("kds.order", "kds_get_recently_done", [
                this.state.undoCount,
                this._stationId || false,
            ]);
            this.state.recentlyDone = recent.slice(0, this.state.undoCount);
        } catch (e) { /* silencioso */ }
    }

    async _completeByTracking(tracking) {
        try {
            const completedId = await this.orm.call(
                "kds.order", "kds_complete_by_tracking", [tracking, this._stationId || false]
            );
            if (completedId) {
                const idx = this.state.orders.findIndex((o) => o.id === completedId);
                if (idx >= 0) this.state.orders[idx]._removing = true;
                setTimeout(async () => {
                    this.state.orders = this.state.orders.filter(
                        (o) => o.id !== completedId
                    );
                    await this._refreshRecentlyDone();
                }, 130);
                this.notification.add(`Orden #${tracking} lista ✓`, { type: "success" });
            } else {
                this.notification.add(`Orden #${tracking} no encontrada`, {
                    type: "warning",
                });
            }
        } catch (e) {
            console.error("KDS complete by tracking error:", e);
        }
    }

    // ------------------------------------------------------------------
    // Numpad
    // ------------------------------------------------------------------
    _resetNumpadBuffer() {
        this.state.keypadBuffer = "";
        clearTimeout(this._numpadTimer);
        this._numpadTimer = null;
    }

    _scheduleNumpadReset() {
        clearTimeout(this._numpadTimer);
        this._numpadTimer = setTimeout(() => this._resetNumpadBuffer(), 3500);
    }

    _onKeydown(ev) {
        const tag = ev.target?.tagName || "";
        if (tag === "INPUT" || tag === "TEXTAREA" || ev.target.isContentEditable) return;

        // "-" o Ctrl+Z → deshacer última
        if (ev.key === "-" || ev.key === "Subtract" ||
            (ev.ctrlKey && (ev.key === "z" || ev.key === "Z"))) {
            this.reopenLastOrder();
            ev.preventDefault();
            return;
        }
        // Dígitos
        if (/^[0-9]$/.test(ev.key)) {
            this.state.keypadBuffer += ev.key;
            this._scheduleNumpadReset();
            return;
        }
        // Enter o "+" → commit
        if (ev.key === "Enter" || ev.key === "+" || ev.key === "Add") {
            const buf = this.state.keypadBuffer.trim();
            if (buf) this._completeByTracking(buf);
            this._resetNumpadBuffer();
            ev.preventDefault();
            return;
        }
        if (ev.key === "Backspace" || ev.key === "Delete") {
            this.state.keypadBuffer = this.state.keypadBuffer.slice(0, -1);
            this._scheduleNumpadReset();
            return;
        }
        if (ev.key === "Escape") {
            this._resetNumpadBuffer();
            return;
        }
    }

    // ------------------------------------------------------------------
    // Sonido (Web Audio, sin archivos)
    // ------------------------------------------------------------------
    _playBeep() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const play = (freq, start, dur) => {
                const osc  = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = "sine";
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.25, ctx.currentTime + start);
                gain.gain.exponentialRampToValueAtTime(
                    0.001, ctx.currentTime + start + dur
                );
                osc.start(ctx.currentTime + start);
                osc.stop(ctx.currentTime + start + dur);
            };
            play(880, 0, 0.12);
            play(1100, 0.15, 0.12);
        } catch (e) { /* sin Web Audio */ }
    }

    // ------------------------------------------------------------------
    // Helpers para template
    // ------------------------------------------------------------------
    get pendingCount() {
        return this.state.orders.filter((o) => !o._removing).length;
    }

    get currentTimeLabel() {
        const d = new Date(this.state.now);
        const p = (n) => String(n).padStart(2, "0");
        return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
    }
}
