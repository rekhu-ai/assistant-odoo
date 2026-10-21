from odoo import _, api, fields, models

from ..services.discover import discover
from .rekhu_scope import MODES


class RekhuAssistantSetup(models.TransientModel):
    """The set-up: what this Odoo holds, discovered; the administrator chooses per app where the assistant works and
    what it may do there, and who gets it. Applying writes the rules the assistant runs by, and switches it on."""

    _name = 'rekhu.assistant.setup'
    _description = 'Rekhu Assistant set-up'

    line_ids = fields.One2many('rekhu.assistant.setup.line', 'setup_id', 'Where it works')
    group_id = fields.Many2one('res.groups', 'Who gets the assistant', help='Empty: every internal user.')

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        current = {r.model_name: r.mode for r in self.env['rekhu.assistant.scope'].sudo().search([])}
        lines, known = [], set()
        for item in discover(self.env):
            known.add(item['model'])
            # a model already in the rules keeps its choice; a new one starts with the suggestion when there are no rules yet
            mode = current.get(item['model']) or ('off' if current else item['mode'])
            lines.append(fields.Command.create({'app': item['app'], 'model_name': item['model'], 'label': item['label'], 'records': item['records'], 'mode': mode}))
        for model, mode in current.items():
            if model not in known and model in self.env:
                lines.append(fields.Command.create({'app': _('Other'), 'model_name': model, 'label': self.env[model]._description, 'records': self.env[model].sudo().search_count([]), 'mode': mode}))
        values['line_ids'] = lines
        group = int(self.env['ir.config_parameter'].sudo().get_param('rekhu_assistant.group_id') or 0)
        values['group_id'] = group or False
        return values

    def action_apply(self):
        self.ensure_one()
        scope = self.env['rekhu.assistant.scope'].sudo()
        lines = self.line_ids.filtered(lambda line: line.model_name and line.model_name in self.env)
        chosen = {line.model_name: line.mode for line in lines if line.mode != 'off'}
        scope.search([('model_name', 'not in', list(chosen))]).unlink()
        existing = {r.model_name: r for r in scope.search([])}
        apps = {line.model_name: line.app for line in lines}
        for model, mode in chosen.items():
            if model in existing:
                existing[model].write({'mode': mode})
            else:
                scope.create({'model_id': self.env['ir.model']._get_id(model), 'app': apps.get(model), 'mode': mode})
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('rekhu_assistant.group_id', self.group_id.id or '')
        params.set_param('rekhu_assistant.enabled', 'True' if chosen else 'False')
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'type': 'success' if chosen else 'warning',
                'title': _('Rekhu Assistant is set up') if chosen else _('Rekhu Assistant is off'),
                'message': _('It works in %(count)s kinds of records. Reload the page to see the chat button.', count=len(chosen)) if chosen else _('No records were chosen, so the assistant stays off.'),
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class RekhuAssistantSetupLine(models.TransientModel):
    _name = 'rekhu.assistant.setup.line'
    _description = 'Rekhu Assistant set-up: one kind of record'
    _order = 'app, label'

    setup_id = fields.Many2one('rekhu.assistant.setup', required=True, ondelete='cascade')
    app = fields.Char(readonly=True)
    model_name = fields.Char(readonly=True)
    label = fields.Char('Records', readonly=True)
    records = fields.Integer('How many', readonly=True)
    mode = fields.Selection([('off', 'Not here')] + MODES, 'The assistant may', required=True, default='read')
