from odoo.tests import tagged

from ..services.app import OdooApp
from .common import RekhuCase


@tagged('post_install', '-at_install', 'rekhu_assistant')
class TestApp(RekhuCase):
    def names(self, env):
        return {a['name'] for a in OdooApp(env, self.config).actions()}

    def test_a_user_gets_only_what_they_may_use(self):
        admin = self.names(self.env)
        employee = self.names(self.env(user=self.employee))
        self.assertIn('find_records', employee)
        self.assertIn('create_record', employee)
        # the employee may read contacts, but not the system parameters listed in the settings
        employee_models = OdooApp(self.env(user=self.employee), self.config).readable()
        self.assertIn('res.partner', employee_models)
        self.assertNotIn('ir.config_parameter', employee_models)
        self.assertIn('ir.config_parameter', OdooApp(self.env, self.config).readable())
        self.assertTrue(employee <= admin)

    def test_precheck_stops_what_cannot_work(self):
        app = OdooApp(self.env, self.config)
        create = next(a for a in app.actions() if a['name'] == 'create_record')
        self.assertIsNone(app.precheck(create, {'model': 'res.partner', 'values': {'name': 'Fine'}}))
        self.assertIn('no field', app.precheck(create, {'model': 'res.partner', 'values': {'colour_of_the_sky': 'blue'}}))

    def test_confirm_card_in_plain_words(self):
        app = OdooApp(self.env, self.config)
        create = next(a for a in app.actions() if a['name'] == 'create_record')
        title, shown = app.present(create, {'model': 'res.partner', 'values': {'name': 'New contact', 'parent_id': self.partner.id}})
        self.assertIn('New contact', title)
        self.assertIn('Rekhu Test Company', shown.values())

    def test_running_an_action_reports_refusals(self):
        app = OdooApp(self.env(user=self.employee), self.config)
        find = next(a for a in app.actions() if a['name'] == 'find_records')
        outcome = app.run(find, {'model': 'res.partner', 'filters': [['nope', '=', 1]]}, lambda e: None)
        self.assertFalse(outcome['ok'])
        self.assertIn('no field', outcome['error'])

    def test_settings_show_the_version(self):
        module = self.env['ir.module.module'].search([('name', '=', 'rekhu_assistant')])
        settings = self.env['res.config.settings'].new({})
        self.assertTrue(settings.rekhu_assistant_version.startswith(module.latest_version.split('.', 2)[2] + ' · Odoo '))
        self.assertFalse(settings.rekhu_assistant_version_note)

    def test_the_menus_are_pages(self):
        pages = OdooApp(self.env, self.config).pages()
        self.assertTrue(pages)
        self.assertTrue(all(p['url'].startswith('/web#menu_id=') for p in pages.values()))

    def test_the_instructions_name_the_company_and_the_models(self):
        text = ' '.join(b['text'] for b in OdooApp(self.env, self.config).system())
        self.assertIn(self.env.company.name, text)
        self.assertIn('res.partner', text)
