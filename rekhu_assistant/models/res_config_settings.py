from odoo import _, fields, models
from odoo.exceptions import UserError

from ..lib import platform



class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rekhu_assistant_enabled = fields.Boolean('Rekhu Assistant', config_parameter='rekhu_assistant.enabled')
    rekhu_assistant_key = fields.Char('Secret key', config_parameter='rekhu_assistant.secret_key', help='The secret key (agk_…) from the Connection tab of your project in your Rekhu account. It stays on this server.')
    rekhu_assistant_platform = fields.Char('Rekhu address', config_parameter='rekhu_assistant.platform', default='https://api.rekhu.ai')
    rekhu_assistant_model = fields.Char('Model', config_parameter='rekhu_assistant.model', default='claude-sonnet-5')
    rekhu_assistant_name = fields.Char('Name in the chat', config_parameter='rekhu_assistant.name', default='Assistant')
    rekhu_assistant_greeting = fields.Char('Greeting', config_parameter='rekhu_assistant.greeting', help='The first message of a new chat. Empty: a short greeting in the user\'s language.')
    rekhu_assistant_quick = fields.Char('Quick questions', config_parameter='rekhu_assistant.quick', help='Shown in a new chat, separated by |, for example: Which invoices are overdue? | My activities for today')
    rekhu_assistant_instructions = fields.Char('Your own rules', config_parameter='rekhu_assistant.instructions', help='How the assistant should work in this company, in a sentence or two: tone, what to check first, what never to do.')
    rekhu_assistant_group_id = fields.Many2one('res.groups', 'Who gets the assistant', config_parameter='rekhu_assistant.group_id', help='The users of this group see the chat. Empty: every internal user.')

    rekhu_assistant_rules = fields.Integer('Rules', compute='_compute_rekhu_assistant_rules')

    def _compute_rekhu_assistant_rules(self):
        count = self.env['rekhu.assistant.scope'].sudo().search_count([])
        for settings in self:
            settings.rekhu_assistant_rules = count

    def action_rekhu_assistant_setup(self):
        """Opens the set-up: what this Odoo holds, and where the assistant works."""
        return self.env['ir.actions.act_window']._for_xml_id('rekhu_assistant.rekhu_assistant_setup_action')

    def action_rekhu_assistant_check(self):
        """Asks Rekhu whether the key works, and what is left on the account."""
        self.ensure_one()
        self.set_values()
        config = self.env['rekhu.assistant.conversation']._rekhu_config()
        try:
            answer = platform.balance(config)
        except platform.Refused as error:
            raise UserError(str(error)) from error
        except Exception as error:  # noqa: BLE001 the network, a proxy, a wrong address
            raise UserError(_('Rekhu could not be reached at %(address)s: %(error)s', address=config['platform'], error=error)) from error
        shown = (answer.get('balance') or {}).get('display') or ''
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'success', 'title': _('The key works'), 'message': _('Connected to Rekhu. Credit on the account: %s', shown) if shown else _('Connected to Rekhu.'), 'sticky': False},
        }
