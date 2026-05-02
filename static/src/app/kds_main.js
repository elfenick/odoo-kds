/** @odoo-module **/

import { whenReady } from "@odoo/owl";
import { mountComponent } from "@web/env";
import { KdsApp } from "./kds_app";

/**
 * Bootstrap del KDS.
 *
 * Montamos en #kds-root (no en document.body) para que startWebClient
 * no colisione con nuestro componente OWL. startWebClient intenta montar
 * en body y fallará silenciosamente, sin afectar nuestro app.
 */
(async function startKds() {
    await whenReady();
    const root = document.getElementById("kds-root") || document.body;
    await mountComponent(KdsApp, root);
})();
