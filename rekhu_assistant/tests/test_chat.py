import json
from unittest.mock import patch

from odoo.tests import HttpCase, new_test_user, tagged


def answer(*blocks, stop='end_turn'):
    return {'content': list(blocks), 'stop_reason': stop}


@tagged('post_install', '-at_install', 'rekhu_assistant')
class TestChat(HttpCase):
    """The chat route as the widget uses it, with the Rekhu platform replaced by a stand-in."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        set_param = cls.env['ir.config_parameter'].sudo().set_param
        set_param('rekhu_assistant.enabled', 'True')
        set_param('rekhu_assistant.secret_key', 'agk_test-customer_assistant_secretsecretsecret')
        cls.env['rekhu.assistant.scope'].create({'model_id': cls.env['ir.model']._get_id('res.partner'), 'mode': 'change'})
        cls.user = new_test_user(cls.env, login='rekhu_chat', password='rekhu_chat_password', groups='base.group_user,base.group_partner_manager')

    def post(self, body, protocol=True):
        headers = {'Content-Type': 'application/json', 'Accept': 'text/event-stream'}
        if protocol:
            headers['X-Rekhu-Protocol'] = '1'
        return self.url_open('/rekhu/assistant/chat', data=json.dumps(body), headers=headers)

    def events(self, response):
        return [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith('data:')]

    def test_the_protocol_header_is_required_for_a_turn(self):
        self.authenticate('rekhu_chat', 'rekhu_chat_password')
        self.assertEqual(self.post({'message': 'hi'}, protocol=False).status_code, 403)

    def test_an_empty_turn_is_refused(self):
        self.authenticate('rekhu_chat', 'rekhu_chat_password')
        self.assertEqual(self.post({'message': '  '}).status_code, 422)

    def test_not_set_up_means_no_assistant(self):
        self.env['rekhu.assistant.scope'].search([]).unlink()
        self.authenticate('rekhu_chat', 'rekhu_chat_password')
        self.assertFalse(self.url_open('/rekhu/assistant/config').json()['enabled'])
        self.assertEqual(self.post({'message': 'hi'}).status_code, 403)

    def test_switched_off_means_no_assistant(self):
        self.env['ir.config_parameter'].sudo().set_param('rekhu_assistant.enabled', 'False')
        self.authenticate('rekhu_chat', 'rekhu_chat_password')
        config = self.url_open('/rekhu/assistant/config').json()
        self.assertFalse(config['enabled'])
        self.assertEqual(self.post({'message': 'hi'}).status_code, 403)

    def test_a_turn_streams_text(self):
        self.authenticate('rekhu_chat', 'rekhu_chat_password')

        def model(config, who, body, on_text):
            on_text('Hello ')
            on_text('there.')
            return answer({'type': 'text', 'text': 'Hello there.'})

        with patch('odoo.addons.rekhu_assistant.lib.turn.platform.message', side_effect=model):
            events = self.events(self.post({'message': 'Hi'}))
        self.assertEqual([e['type'] for e in events], ['start', 'text', 'text', 'done'])
        history = self.url_open('/rekhu/assistant/chat?conversation=%s' % events[0]['conversation'], headers={'X-Rekhu-Protocol': '1'}).json()
        self.assertEqual([m['role'] for m in history['messages']], ['user', 'bot'])

    def test_a_change_waits_for_the_click_and_runs_as_the_user(self):
        self.authenticate('rekhu_chat', 'rekhu_chat_password')
        calls = []

        def model(config, who, body, on_text):
            calls.append(body)
            if len(calls) == 1:
                return answer({'type': 'tool_use', 'id': 'call_1', 'name': 'create_record', 'input': {'model': 'res.partner', 'values': {'name': 'Made in the chat'}}}, stop='tool_use')
            return answer({'type': 'text', 'text': 'Done.'})

        with patch('odoo.addons.rekhu_assistant.lib.turn.platform.message', side_effect=model):
            first = self.events(self.post({'message': 'Make a contact called Made in the chat'}))
            card = next(e for e in first if e.get('kind') == 'confirm')
            self.assertFalse(self.env['res.partner'].search([('name', '=', 'Made in the chat')]))
            second = self.events(self.post({'conversation': first[0]['conversation'], 'confirm': card['id']}))
        self.assertTrue(any(e.get('kind') == 'done' for e in second))
        made = self.env['res.partner'].search([('name', '=', 'Made in the chat')])
        self.assertEqual(made.create_uid, self.user)

    def test_another_users_conversation_stays_closed(self):
        other = new_test_user(self.env, login='rekhu_other', password='rekhu_other_password', groups='base.group_user')
        self.authenticate('rekhu_chat', 'rekhu_chat_password')
        with patch('odoo.addons.rekhu_assistant.lib.turn.platform.message', return_value=answer({'type': 'text', 'text': 'Secret plans.'})):
            mine = self.events(self.post({'message': 'Tell me the plans'}))[0]['conversation']
        self.authenticate('rekhu_other', 'rekhu_other_password')
        seen = self.url_open('/rekhu/assistant/chat?conversation=%s' % mine, headers={'X-Rekhu-Protocol': '1'}).json()
        self.assertEqual(seen['messages'], [])
        self.assertTrue(other)
