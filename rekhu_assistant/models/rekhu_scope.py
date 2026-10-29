from odoo import api, fields, models

MODES = [('read', 'Read'), ('change', 'Read and change')]


class RekhuAssistantScope(models.Model):
    """Where the assistant works: one rule per model, made in the set-up. The assistant reads only the models with a
    rule, changes only those set to "Read and change", and does not run at all until there is a rule. Each user still
    sees and does only what their own access rights allow."""

    _name = 'rekhu.assistant.scope'
    _description = 'Rekhu Assistant: where it works'
    _order = 'app, model_name'
    _rec_name = 'model_name'

    model_id = fields.Many2one('ir.model', 'Records', required=True, ondelete='cascade', domain=[('transient', '=', False)])
    model_name = fields.Char(related='model_id.model', store=True, index=True)
    app = fields.Char('App')
    mode = fields.Selection(MODES, 'The assistant may', required=True, default='read')

    if hasattr(models, 'Constraint'):
        _model_unique = models.Constraint('unique(model_id)', 'Each model has one rule.')
    else:
        _sql_constraints = [('model_unique', 'unique(model_id)', 'Each model has one rule.')]

    @api.model
    def _rekhu_rules(self):
        """{'read': [model, …], 'change': [model, …]}: what the rules allow, before any user's own rights."""
        rules = self.sudo().search([])
        return {
            'read': rules.mapped('model_name'),
            'change': rules.filtered(lambda r: r.mode == 'change').mapped('model_name'),
        }
