"""What this Odoo holds, for the set-up: the installed apps and the records the assistant could work with in each, with
how many there are and what the set-up suggests (read, or read and change)."""

# app name, the module that brings it, and its records: (model, suggested mode)
APPS = (
    ('Contacts', 'contacts', (('res.partner', 'change'),)),
    ('CRM', 'crm', (('crm.lead', 'change'),)),
    ('Sales', 'sale', (('sale.order', 'change'), ('sale.order.line', 'read'))),
    ('Invoicing', 'account', (('account.move', 'read'), ('account.payment', 'read'))),
    ('Purchase', 'purchase', (('purchase.order', 'change'),)),
    ('Inventory', 'stock', (('stock.picking', 'read'), ('stock.quant', 'read'))),
    ('Products', 'product', (('product.template', 'read'), ('product.product', 'read'))),
    ('Project', 'project', (('project.project', 'read'), ('project.task', 'change'))),
    ('Helpdesk', 'helpdesk', (('helpdesk.ticket', 'change'),)),
    ('Employees', 'hr', (('hr.employee', 'read'),)),
    ('Time Off', 'hr_holidays', (('hr.leave', 'read'),)),
    ('Calendar', 'calendar', (('calendar.event', 'change'),)),
    ('Manufacturing', 'mrp', (('mrp.production', 'read'),)),
    ('Point of Sale', 'point_of_sale', (('pos.order', 'read'),)),
    ('Website', 'website_sale', (('sale.order', 'read'),)),
    ('Activities', 'mail', (('mail.activity', 'read'),)),
)


def discover(env):
    """Every model of an installed app that exists here, once, with its app, its name, its record count and a suggestion."""
    installed = set(env['ir.module.module'].sudo().search([('state', '=', 'installed')]).mapped('name'))
    found, seen = [], set()
    for app, module, items in APPS:
        if module not in installed:
            continue
        for model, mode in items:
            if model in seen or model not in env:
                continue
            seen.add(model)
            found.append({
                'app': app,
                'model': model,
                'label': env[model]._description,
                'records': env[model].sudo().search_count([]),
                'mode': mode,
            })
    return found
