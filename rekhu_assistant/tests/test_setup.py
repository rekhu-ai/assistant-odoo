from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.discover import discover


@tagged('post_install', '-at_install', 'rekhu_assistant')
class TestSetup(TransactionCase):
    """The assistant runs only after the set-up: what it finds, what the administrator chooses, and the rules it writes."""

    def setUp(self):
        super().setUp()
        self.env['rekhu.assistant.scope'].search([]).unlink()
        self.env['ir.config_parameter'].sudo().set_param('rekhu_assistant.enabled', 'False')

    def test_discovery_lists_installed_apps_with_their_records(self):
        found = discover(self.env)
        models = {f['model'] for f in found}
        # mail is always installed with the module: its activities are offered
        self.assertIn('mail.activity', models)
        self.assertTrue(all(isinstance(f['records'], int) and f['label'] for f in found))
        self.assertEqual(len(models), len(found), 'each model is offered once')

    def test_without_rules_nothing_runs(self):
        config = self.env['rekhu.assistant.conversation']._rekhu_config()
        self.assertEqual(config['rules'], {'read': [], 'change': []})

    def test_the_setup_writes_the_rules_and_switches_on(self):
        setup = self.env['rekhu.assistant.setup'].create({})
        self.assertTrue(setup.line_ids, 'the set-up starts from what it discovered')
        setup.line_ids.write({'mode': 'off'})
        activities = setup.line_ids.filtered(lambda line: line.model_name == 'mail.activity')
        activities.mode = 'change'
        setup.action_apply()
        rules = self.env['rekhu.assistant.scope']._rekhu_rules()
        self.assertEqual(rules, {'read': ['mail.activity'], 'change': ['mail.activity']})
        self.assertEqual(self.env['ir.config_parameter'].sudo().get_param('rekhu_assistant.enabled'), 'True')

    def test_running_it_again_keeps_the_choices(self):
        self.env['rekhu.assistant.scope'].create({'model_id': self.env['ir.model']._get_id('mail.activity'), 'mode': 'read'})
        setup = self.env['rekhu.assistant.setup'].create({})
        line = setup.line_ids.filtered(lambda line: line.model_name == 'mail.activity')
        self.assertEqual(line.mode, 'read')
        others = setup.line_ids - line
        self.assertTrue(all(o.mode == 'off' for o in others), 'what was not chosen before stays off')

    def test_choosing_nothing_keeps_it_off(self):
        setup = self.env['rekhu.assistant.setup'].create({})
        setup.line_ids.write({'mode': 'off'})
        setup.action_apply()
        self.assertFalse(self.env['rekhu.assistant.scope'].search([]))
        self.assertEqual(self.env['ir.config_parameter'].sudo().get_param('rekhu_assistant.enabled'), 'False')
