from odoo.tests import tagged

from ..services import records
from ..services.records import Refusal
from .common import RekhuCase


@tagged('post_install', '-at_install', 'rekhu_assistant')
class TestRecords(RekhuCase):
    def test_search_by_name_and_filters(self):
        found = records.search(self.env, 'res.partner', [['is_company', '=', True]], 'Rekhu Test', ['name', 'email'])
        self.assertEqual(found['total'], 1)
        self.assertEqual(found['records'][0]['email'], 'hello@rekhu-test.example')
        self.assertIn('/web#model=res.partner', found['records'][0]['url'])

    def test_unknown_fields_and_operators_are_refused(self):
        with self.assertRaises(Refusal):
            records.search(self.env, 'res.partner', [['no_such_field', '=', 1]])
        with self.assertRaises(Refusal):
            records.search(self.env, 'res.partner', [['name', 'sql', 'x']])

    def test_a_related_record_by_its_name(self):
        values = records.values_of(self.env, 'res.partner', {'name': 'A contact', 'parent_id': 'Rekhu Test Company'})
        self.assertEqual(values['parent_id'], self.partner.id)

    def test_an_unknown_name_is_refused_with_a_reason(self):
        with self.assertRaisesRegex(Refusal, 'no .* is called'):
            records.values_of(self.env, 'res.partner', {'parent_id': 'Nobody at all 4711'})

    def test_readonly_and_technical_fields_are_never_written(self):
        with self.assertRaises(Refusal):
            records.values_of(self.env, 'res.partner', {'create_uid': 1})
        with self.assertRaises(Refusal):
            records.values_of(self.env, 'res.partner', {'display_name': 'x'})

    def test_access_rights_decide(self):
        """A plain employee may not read the system parameters, whatever the assistant is told."""
        employee_env = self.env(user=self.employee)
        with self.assertRaises(Refusal):
            records.search(employee_env, 'ir.config_parameter', None, 'rekhu')

    def test_create_and_write_as_the_user(self):
        employee_env = self.env(user=self.employee)
        made = records.create(employee_env, 'res.partner', {'name': 'Made by the assistant', 'parent_id': self.partner.id})
        partner = self.env['res.partner'].browse(made['id'])
        self.assertEqual(partner.create_uid, self.employee)
        records.write(employee_env, 'res.partner', partner.id, {'phone': '+31 20 000 0000'})
        self.assertEqual(partner.phone, '+31 20 000 0000')

    def test_readable_values_for_the_confirm_card(self):
        shown = records.readable_values(self.env, 'res.partner', {'parent_id': self.partner.id, 'is_company': False})
        self.assertIn('Rekhu Test Company', shown.values())
