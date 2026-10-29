/** @odoo-module **/
// The chat button in the back office: when this user has the assistant, the Rekhu widget is mounted on the chat route
// of this module. The widget sends the Odoo session cookie and the protocol header; the secret key stays on the server.

import { registry } from "@web/core/registry";

const rekhuAssistantService = {
    async start() {
        const widget = window.RekhuAssistant;
        if (!widget) {
            return;
        }
        let config;
        try {
            const response = await fetch("/rekhu/assistant/config", { headers: { Accept: "application/json" } });
            config = response.ok ? await response.json() : null;
        } catch {
            config = null;
        }
        if (!config || !config.enabled) {
            return;
        }
        widget.mount({
            endpoint: "/rekhu/assistant/chat",
            locale: config.locale,
            name: config.name,
            color: "#714B67",
        });
    },
};

registry.category("services").add("rekhu_assistant", rekhuAssistantService);
