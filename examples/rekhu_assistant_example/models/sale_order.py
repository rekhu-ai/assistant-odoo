from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.rekhu_assistant.tools import tool


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    @tool(
        'How much a customer bought from us: the number of confirmed orders and their total, this year and in all. Use it for "how much did X buy" questions.',
        input={'customer': 'string'},
        readonly=True,
        label={'en': 'Sales of a customer', 'nl': 'Verkoop aan een klant', 'ar': 'مبيعات عميل'},
    )
    def rekhu_customer_sales(self, customer):
        partner = self.env['res.partner'].search([('name', 'ilike', customer), ('is_company', '=', True)], limit=1)
        if not partner:
            raise UserError(_('No customer is called "%s".', customer))
        orders = self.search([('partner_id', 'child_of', partner.id), ('state', '=', 'sale')])
        this_year = orders.filtered(lambda o: o.date_order.year == self.env.cr.now().year)
        currency = partner.company_id.currency_id or self.env.company.currency_id
        return {
            'customer': partner.name,
            'currency': currency.name,
            'orders': len(orders), 'total': sum(orders.mapped('amount_total')),
            'orders_this_year': len(this_year), 'total_this_year': sum(this_year.mapped('amount_total')),
        }

    @api.model
    @tool(
        'Reorders a past sales order: the same products and quantities for the same customer, as a new quotation. "order" is its number, such as S00042.',
        input={'order': 'string'},
        groups='sales_team.group_sale_salesman',
        label={'en': 'Reorder', 'nl': 'Opnieuw bestellen', 'ar': 'إعادة الطلب'},
    )
    def rekhu_reorder(self, order):
        source = self.search([('name', '=', order.strip().upper())], limit=1)
        if not source:
            raise UserError(_('There is no order %s.', order))
        new = source.copy({'origin': source.name})
        return {'message': _('Quotation %(new)s is ready, a copy of %(old)s.', new=new.name, old=source.name), 'record': new}
