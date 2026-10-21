"""Your own actions: mark a model method and the assistant can do that job, as the signed-in user.

    from odoo import api, models
    from odoo.addons.rekhu_assistant.tools import tool

    class SaleOrder(models.Model):
        _inherit = 'sale.order'

        @api.model
        @tool('Reorder a past order: the same products for the same customer, as a new quotation',
              input={'order': 'string', 'quantity': 'integer?'}, groups='sales_team.group_sale_salesman')
        def rekhu_reorder(self, order, quantity=None):
            ...
            return {'message': 'Quotation S00042 is ready.', 'record': new_order}

The method is called on the model with the user's own environment, so access rights and record rules apply. Return a
dict for the assistant (a 'message', and a 'record' to give the user a button to open it), or raise UserError or
AccessError to refuse. An action that changes something waits for the user's click on Confirm, unless readonly=True.
"""

from .lib.schema import to_schema


def tool(description, input=None, confirm=None, readonly=False, danger=False, groups=None, label=None, hidden=()):
    """Marks a model method as an action of the assistant.

    description: what it does, for the assistant (be specific: when to use it, what it needs).
    input: the arguments, as JSON Schema or the short form {'order': 'string', 'quantity': 'integer?', 'size': ['s', 'l']}.
    confirm: whether the user confirms first; by default every action that is not readonly does.
    readonly: it only reads; it runs at once and shows no "done" card.
    danger: the confirm card shows it as destructive.
    groups: who may use it, as group xml ids, comma separated ('sales_team.group_sale_salesman'); empty is every user.
    label: what the user reads for it, a text or {'en': …, 'nl': …, 'ar': …}.
    hidden: input fields not shown on the confirm card.
    """
    schema = to_schema(input)

    def wrap(method):
        method._rekhu_tool = {
            'description': str(description).strip(),
            'schema': schema,
            'confirm': (not readonly) if confirm is None else bool(confirm),
            'readonly': bool(readonly),
            'danger': bool(danger),
            'groups': [g.strip() for g in (groups or '').split(',') if g.strip()],
            'label': label,
            'hidden': list(hidden or ()),
        }
        return method

    return wrap
