/** @odoo-module **/
import { Component } from "@odoo/owl";

export class OrderCard extends Component {
    static template = "bitopolis_kds.OrderCard";
    static props = {
        order: Object,
        now: Number,
        warnSeconds: Number,
        dangerSeconds: Number,
        onComplete: Function,
    };

    get sentAtMs() {
        const iso = this.props.order.sent_at;
        if (!iso) return this.props.now;
        const norm = iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z";
        const t = Date.parse(norm);
        return isNaN(t) ? this.props.now : t;
    }

    get elapsedSeconds() {
        return Math.max(0, Math.floor((this.props.now - this.sentAtMs) / 1000));
    }

    get elapsedLabel() {
        const s = this.elapsedSeconds;
        const m = Math.floor(s / 60);
        const sec = s % 60;
        if (m >= 60) {
            const h = Math.floor(m / 60);
            return `${h}h ${String(m % 60).padStart(2, "0")}m`;
        }
        return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
    }

    get severity() {
        const s = this.elapsedSeconds;
        if (s >= this.props.dangerSeconds) return "danger";
        if (s >= this.props.warnSeconds)   return "warning";
        return "ok";
    }

    get cardClass() {
        const cls = ["o_kds_card", `o_kds_card_${this.severity}`];
        if (this.props.order._removing) cls.push("o_kds_card_removing");
        return cls.join(" ");
    }

    onCompleteClick() {
        this.props.onComplete(this.props.order.id);
    }
}
