/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { OrderCard } from "./order_card";

const DEFAULT_BINDINGS = {
    key_nav_up:    "Numpad8",
    key_nav_down:  "Numpad5",
    key_nav_left:  "Numpad4",
    key_nav_right: "Numpad6",
    key_complete:  "NumpadEnter",
    key_undo:      "NumpadSubtract",
};

const KEY_LABELS = {
    Numpad0: "Num 0", Numpad1: "Num 1", Numpad2: "Num 2", Numpad3: "Num 3",
    Numpad4: "Num 4", Numpad5: "Num 5", Numpad6: "Num 6", Numpad7: "Num 7",
    Numpad8: "Num 8", Numpad9: "Num 9",
    NumpadAdd: "Num +", NumpadSubtract: "Num −", NumpadMultiply: "Num ×",
    NumpadDivide: "Num /", NumpadEnter: "Num Enter", NumpadDecimal: "Num .",
    ArrowUp: "↑", ArrowDown: "↓", ArrowLeft: "←", ArrowRight: "→",
    Enter: "Enter", Escape: "Esc",
};

function keyLabel(code) {
    if (!code) return "—";
    if (KEY_LABELS[code]) return KEY_LABELS[code];
    if (code.startsWith("Key"))   return code.slice(3);
    if (code.startsWith("Digit")) return code.slice(5);
    return code;
}

export class KdsApp extends Component {
    static template = "bitopolis_kds.KdsApp";
    static components = { OrderCard };
    static props = {};

    setup() {
        this.orm          = useService("orm");
        this.bus          = useService("bus_service");
        this.notification = useService("notification");

        const companyId      = odoo.session_info?.user_companies?.current_company ?? 1;
        const initialStation = odoo.kds_station_id ?? null;

        this.state = useState({
            orders:         [],
            recentlyDone:   [],
            now:            Date.now(),
            connected:      false,
            lastPollSuccess: Date.now() + 20000,  // grace period 20s al arrancar
            companyId,
            selectedIndex:  0,
            stationLabel:   "",
            stationShowAll: false,
            warnSeconds:    5  * 60,
            dangerSeconds:  15 * 60,
            undoCount:      5,
            pollInterval:   2,
            soundEnabled:   true,
            soundVolume:    1.0,
            showUndoTray:   false,
            bindings:       { ...DEFAULT_BINDINGS },
            fontSize:       17,
            licenseValid:   true,   // default true — demo mode funciona
            stationInvalid: false,
            stationToken:   null,
        });

        this._stationId        = initialStation;
        this._tickTimer        = null;
        this._pollTimer        = null;
        this._reopenInProgress = false;

        // Persistir en sessionStorage para sobrevivir F5
        const _ssKey = `kds_recalled_${initialStation || 'all'}`;
        try {
            const saved = sessionStorage.getItem(_ssKey);
            this._recalledIds = saved ? new Set(JSON.parse(saved)) : new Set();
        } catch (e) {
            this._recalledIds = new Set();
        }
        this._ssKey = _ssKey;

        this._onKeydown         = this._onKeydown.bind(this);
        this._onBusNotification = this._onBusNotification.bind(this);
        this.completeOrder      = this.completeOrder.bind(this);
        this.reopenOrder        = this.reopenOrder.bind(this);

        onWillStart(async () => {
            // Capturar token inyectado por el servidor
            if (odoo.kds_station_token) {
                this.state.stationToken = odoo.kds_station_token;
            }
            // Si station_id es -1, el token era inválido
            if (odoo.kds_station_id === -1) {
                this.state.stationInvalid = true;
                return;
            }
            await this._fetchConfig();
            await this._fetchOrders();
        });

        onMounted(() => {
            this._tickTimer = setInterval(() => {
                this.state.now = Date.now();
                const sinceLastPoll = Date.now() - this.state.lastPollSuccess;
                const wasConnected  = this.state.connected;
                const isConnected   = sinceLastPoll < 15000;
                this.state.connected = isConnected;
                if (!wasConnected && isConnected) {
                    this._fetchOrders();
                }
            }, 1000);
            this._startPolling();

            const channel = `bitopolis_kds#${this.state.companyId}`;
            this.bus.addChannel(channel);
            this.bus.addEventListener("notification", this._onBusNotification);
            this.bus.start();
            this.state.connected = true;

            this._fetchOrders();

            window.addEventListener("keydown", this._onKeydown);
        });

        onWillUnmount(() => {
            clearInterval(this._tickTimer);
            clearInterval(this._pollTimer);
            window.removeEventListener("keydown", this._onKeydown);
        });
    }

    // ------------------------------------------------------------------
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

    // ------------------------------------------------------------------

    async _checkLicense() {
            this.state.licenseValid = true;
    }


    async _validateToken() {
        const token     = this.state.stationToken;
        const stationId = odoo.kds_station_id;
        if (!token && !stationId) return;
        try {
            const r = await fetch('/kds/station/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-Csrf-Token': odoo.csrf_token },
                body: JSON.stringify({ jsonrpc: '2.0', method: 'call', id: 1,
                    params: { token: token, station_id: stationId } }),
            });
            const data = await r.json();
            if (data?.result?.valid === false) {
                this.state.stationInvalid = true;
            }
        } catch { /* silencioso */ }
    }

    async _fetchConfig() {
        try {
            const cfg = await this._rpc("/kds/config/get");
            if (!cfg) return;
            this.state.warnSeconds   = (cfg.warn_minutes   || 5)  * 60;
            this.state.dangerSeconds = (cfg.danger_minutes || 15) * 60;
            this.state.pollInterval  = cfg.poll_interval || 5;
            this.state.undoCount     = cfg.undo_count    || 5;
            this.state.soundEnabled  = cfg.sound_enabled !== false;
            this.state.soundVolume   = Math.min(1, Math.max(0, parseFloat(cfg.sound_volume) || 1.0));

            const legacyMap = { sm: 14, md: 17, lg: 21, xl: 27 };
            const rawFs = cfg.font_size;
            this.state.fontSize = (typeof rawFs === 'number')
                ? rawFs : (legacyMap[rawFs] || parseInt(rawFs) || 17);

            this.state.bindings = {
                key_nav_up:    cfg.key_nav_up    || DEFAULT_BINDINGS.key_nav_up,
                key_nav_down:  cfg.key_nav_down  || DEFAULT_BINDINGS.key_nav_down,
                key_nav_left:  cfg.key_nav_left  || DEFAULT_BINDINGS.key_nav_left,
                key_nav_right: cfg.key_nav_right || DEFAULT_BINDINGS.key_nav_right,
                key_complete:  cfg.key_complete  || DEFAULT_BINDINGS.key_complete,
                key_undo:      cfg.key_undo      || DEFAULT_BINDINGS.key_undo,
            };

            if (this._stationId) {
                const dash = await this._rpc("/kds/dashboard");
                const station = (dash?.stations || []).find((s) => s.id === this._stationId);
                this.state.stationLabel   = station?.name || "";
                this.state.stationShowAll = !!station?.show_all;
            }
        } catch (e) {
            console.warn("KDS: usando config default.", e);
        }
    }

    // ------------------------------------------------------------------
    async _fetchOrders() {
        try {
            const stationId = this._stationId || false;
            const [active, recent] = await Promise.all([
                this.orm.call("kds.order", "kds_get_active_orders", [stationId]),
                this.orm.call("kds.order", "kds_get_recently_done", [this.state.undoCount, this._stationId || false]),
            ]);
            this.state.lastPollSuccess = Date.now();
            this.state.connected = true;
            const prevIds = new Set(this.state.orders.map((o) => o.id));
            const hasNew  = active.some((o) => !prevIds.has(o.id));
            if (hasNew && this.state.soundEnabled && prevIds.size > 0) this._playBeep();
            this.state.orders       = active;
            this.state.recentlyDone = recent.slice(0, this.state.undoCount);
            this._applyRecalledFlags();
            this._clampSelection();
        } catch (e) {
            console.error("KDS fetch error:", e);
            // Fetch fallido — no actualizar lastPollSuccess (watchdog lo detectará)
        }
    }

    _startPolling() {
        clearInterval(this._pollTimer);
        this._pollTimer = setInterval(
            () => this._fetchOrders(),
            (this.state.pollInterval || 5) * 1000
        );
    }

    _onBusNotification(ev) {
        const notifications = ev.detail || [];
        if (notifications.some((n) => (n.type || n?.[1]?.type) === "kds.update")) {
            this.state.lastPollSuccess = Date.now();
            this.state.connected = true;
            this._fetchOrders();
        }
    }

    // ------------------------------------------------------------------
    async completeOrder(orderId) {
        const idx = this.state.orders.findIndex((o) => o.id === orderId);
        this._recalledIds.delete(orderId);
        this._saveRecalledIds();
        try {
            await this.orm.call("kds.order", "kds_complete", [orderId, this._stationId || false]);
            this.state.orders = this.state.orders.filter((o) => o.id !== orderId);
            this._clampSelection();
            await this._refreshRecentlyDone();
        } catch (e) {
            if (idx >= 0 && this.state.orders[idx]) this.state.orders[idx]._removing = false;
            this._clampSelection();
            this.notification.add("Error al completar la orden", { type: "danger" });
        }
    }

    async reopenOrderWithLimit(orderId) {
        const pendingRecalls = this._visibleOrders.filter((o) => o._recalled).length;
        if (pendingRecalls >= this.state.undoCount) {
            this.notification.add(
                `Máximo de recalls alcanzado (${this.state.undoCount}). Completa alguna antes.`,
                { type: "warning" }
            );
            return;
        }
        await this.reopenOrder(orderId);
    }

    async reopenOrder(orderId) {
        try {
            const order = await this.orm.call("kds.order", "kds_reopen", [orderId, this._stationId || false]);
            if (order) {
                this._recalledIds.add(order.id);
                this._saveRecalledIds();
                this.state.recentlyDone = this.state.recentlyDone.filter(
                    (o) => (o.done_id || o.id) !== orderId
                );
                await this._fetchOrders();
                this.notification.add(`↩ Orden #${order.tracking_number || order.name} reabierta`, { type: "success" });
            }
        } catch (e) { console.error("KDS reopen error:", e); }
    }

    async reopenLastOrder() {
        if (this._reopenInProgress) return;
        // No permitir más recalls que el undo_count configurado
        const pendingRecalls = this._visibleOrders.filter((o) => o._recalled).length;
        if (pendingRecalls >= this.state.undoCount) {
            this.notification.add(
                `Máximo de recalls alcanzado (${this.state.undoCount}). Completa alguna antes.`,
                { type: "warning" }
            );
            return;
        }
        await this._refreshRecentlyDone();
        if (!this.state.recentlyDone.length) {
            this.notification.add("No hay órdenes recientes para deshacer", { type: "warning" });
            return;
        }
        this._reopenInProgress = true;
        try {
            await this.reopenOrder(this.state.recentlyDone[0].done_id || this.state.recentlyDone[0].id);
        } finally {
            this._reopenInProgress = false;
        }
    }

    async _refreshRecentlyDone() {
        try {
            const recent = await this.orm.call("kds.order", "kds_get_recently_done", [
                this.state.undoCount, this._stationId || false,
            ]);
            this.state.recentlyDone = recent.slice(0, this.state.undoCount);
        } catch (e) { /* silencioso */ }
    }

    // ------------------------------------------------------------------
    get _visibleOrders() { return this.state.orders.filter((o) => !o._removing); }

    _clampSelection() {
        const n = this._visibleOrders.length;
        this.state.selectedIndex = n === 0 ? 0 : Math.min(this.state.selectedIndex, n - 1);
    }

    _scrollSelectedIntoView() {
        const sel = this._visibleOrders[this.state.selectedIndex];
        if (!sel) return;
        setTimeout(() => {
            document.querySelector(`[data-order-id="${sel.id}"]`)
                ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }, 0);
    }

    _applyRecalledFlags() {
        if (this._recalledIds.size === 0) return;
        for (const o of this.state.orders) {
            if (this._recalledIds.has(o.id)) o._recalled = true;
        }
        // Limpiar IDs que ya no están en la lista activa
        const activeIds = new Set(this.state.orders.map((o) => o.id));
        for (const id of this._recalledIds) {
            if (!activeIds.has(id)) this._recalledIds.delete(id);
        }
        this._saveRecalledIds();
    }

    _saveRecalledIds() {
        try { sessionStorage.setItem(this._ssKey, JSON.stringify([...this._recalledIds])); } catch (e) {}
    }

    _getNumColumns() {
        const grid = document.querySelector(".o_kds_grid");
        if (!grid) return 1;
        const cols = getComputedStyle(grid).gridTemplateColumns.split(" ").filter(Boolean).length;
        return cols > 0 ? cols : 1;
    }

    // ------------------------------------------------------------------
    _onKeydown(ev) {
        const tag = ev.target?.tagName || "";
        if (tag === "INPUT" || tag === "TEXTAREA" || ev.target.isContentEditable) return;

        const c = ev.code;
        const b = this.state.bindings;
        const n = this._visibleOrders.length;

        if (c === b.key_undo) {
            this.reopenLastOrder();
            ev.preventDefault();
            return;
        }
        if (n === 0) return;

        const numCols = this._getNumColumns();
        let idx = this.state.selectedIndex;

        if (c === b.key_nav_up) {
            idx = Math.max(0, idx - numCols);
            this.state.selectedIndex = idx;
            this._scrollSelectedIntoView();
            ev.preventDefault();
            return;
        }
        if (c === b.key_nav_down) {
            idx = Math.min(n - 1, idx + numCols);
            this.state.selectedIndex = idx;
            this._scrollSelectedIntoView();
            ev.preventDefault();
            return;
        }
        if (c === b.key_nav_left) {
            const rowStart = Math.floor(idx / numCols) * numCols;
            this.state.selectedIndex = Math.max(rowStart, idx - 1);
            this._scrollSelectedIntoView();
            ev.preventDefault();
            return;
        }
        if (c === b.key_nav_right) {
            const rowEnd = Math.min(n - 1, Math.floor(idx / numCols) * numCols + numCols - 1);
            this.state.selectedIndex = Math.min(rowEnd, idx + 1);
            this._scrollSelectedIntoView();
            ev.preventDefault();
            return;
        }
        if (c === b.key_complete) {
            const sel = this._visibleOrders[this.state.selectedIndex];
            if (sel) this.completeOrder(sel.id);
            ev.preventDefault();
            return;
        }
    }

    // ------------------------------------------------------------------
    _playBeep() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const vol = this.state.soundVolume ?? 1.0;
            const play = (freq, start, dur, type = "sine") => {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = type;
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(vol, ctx.currentTime + start);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
                osc.start(ctx.currentTime + start);
                osc.stop(ctx.currentTime + start + dur);
            };

            if (vol > 0.7) {
                // Tono fuerte: square wave, más largo, doble golpe
                play(880,  0,    0.18, "square");
                play(1100, 0.22, 0.18, "square");
                play(880,  0.44, 0.15, "square");
            } else if (vol > 0.4) {
                // Tono medio: sawtooth
                play(880,  0,    0.14, "sawtooth");
                play(1100, 0.18, 0.14, "sawtooth");
            } else {
                // Tono suave: sine
                play(880,  0,    0.12, "sine");
                play(1100, 0.15, 0.12, "sine");
            }
        } catch (e) { /* sin Web Audio */ }
    }

    // ------------------------------------------------------------------
    get pendingCount()       { return this._visibleOrders.length; }
    get selectedOrderId()    { return this._visibleOrders[this.state.selectedIndex]?.id ?? null; }
    get selectedOrderLabel() {
        const sel = this._visibleOrders[this.state.selectedIndex];
        return sel ? `#${sel.tracking_number || sel.name}` : "—";
    }
    keyLabel(code) { return keyLabel(code); }
    get fontSizeStyle() {
        const fs = Math.min(60, Math.max(10, this.state.fontSize || 17));
        return `--kds-card-font-base:${fs}px`;
    }
    get currentTimeLabel() {
        const d = new Date(this.state.now);
        const p = (n) => String(n).padStart(2, "0");
        return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
    }
}
