from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib.schema import to_schema, validate


@tagged('post_install', '-at_install', 'rekhu_assistant')
class TestSchema(BaseCase):
    def test_short_form_becomes_json_schema(self):
        schema = to_schema({'order': 'string', 'quantity': 'integer?', 'size': ['s', 'l']})
        self.assertEqual(schema['required'], ['order', 'size'])
        self.assertEqual(schema['properties']['size'], {'type': 'string', 'enum': ['s', 'l']})

    def test_unknown_type_is_refused(self):
        with self.assertRaises(ValueError):
            to_schema({'when': 'datetime'})

    def test_values_are_checked_and_cleaned(self):
        schema = to_schema({'order': 'string', 'quantity': 'integer?'})
        ok, value = validate(schema, {'order': 'S00042', 'quantity': '3', 'extra': 'dropped'})
        self.assertTrue(ok)
        self.assertEqual(value, {'order': 'S00042', 'quantity': 3})

    def test_missing_and_wrong_values_are_named(self):
        ok, errors = validate(to_schema({'order': 'string', 'quantity': 'integer?'}), {'quantity': 'many'})
        self.assertFalse(ok)
        self.assertIn('order', errors)
        self.assertIn('quantity', errors)

    def test_a_boolean_is_never_a_number(self):
        ok, _errors = validate(to_schema({'quantity': 'integer'}), {'quantity': True})
        self.assertFalse(ok)
