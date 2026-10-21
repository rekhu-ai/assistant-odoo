from odoo.tests.common import TransactionCase, new_test_user


class RekhuCase(TransactionCase):
    """A switched-on assistant and two users: an administrator, and a plain employee who may read and change contacts
    but nothing of sales."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        set_param = cls.env['ir.config_parameter'].sudo().set_param
        set_param('rekhu_assistant.enabled', 'True')
        set_param('rekhu_assistant.secret_key', 'agk_test-customer_assistant_secretsecretsecret')
        set_param('rekhu_assistant.platform', 'https://rekhu.invalid')
        rule = cls.env['rekhu.assistant.scope'].create
        rule({'model_id': cls.env['ir.model']._get_id('res.partner'), 'mode': 'change'})
        rule({'model_id': cls.env['ir.model']._get_id('res.users'), 'mode': 'read'})
        rule({'model_id': cls.env['ir.model']._get_id('ir.config_parameter'), 'mode': 'read'})
        cls.employee = new_test_user(cls.env, login='rekhu_employee', groups='base.group_user,base.group_partner_manager', name='Rekhu Employee')
        cls.partner = cls.env['res.partner'].create({'name': 'Rekhu Test Company', 'is_company': True, 'email': 'hello@rekhu-test.example'})
        cls.config = cls.env['rekhu.assistant.conversation']._rekhu_config()
