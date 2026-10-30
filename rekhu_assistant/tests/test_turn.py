from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib import platform
from ..lib.messages import message
from ..lib.turn import CUT_OFF, Turn, failure_kind, paired


class _App:
    """The least of an app a turn needs: one action, no pages, no help."""

    def actions(self):
        return [{'name': 'export_file', 'description': 'Export a file', 'confirm': False, 'schema': {'type': 'object', 'properties': {}}}]

    def system(self):
        return 'You help.'

    def pages(self):
        return {}

    def has_help(self):
        return False


@tagged('post_install', '-at_install', 'rekhu_assistant')
class TestTurn(BaseCase):

    def test_one_button_per_record(self):
        sent = []
        emit = Turn._once(sent.append)
        emit({'type': 'card', 'kind': 'done', 'title': 'Lead', 'url': '/web#model=crm.lead&id=7'})
        emit({'type': 'card', 'kind': 'page', 'label': 'Open lead', 'url': '/web#model=crm.lead&id=7'})
        emit({'type': 'card', 'kind': 'page', 'label': 'Pipeline', 'url': '/web#menu_id=5'})
        emit({'type': 'text', 'text': 'Done.'})
        self.assertEqual([e.get('kind') or e['type'] for e in sent], ['done', 'page', 'text'])
        self.assertEqual(sent[1]['label'], 'Pipeline')

    def _turn(self, answers, steps=8):
        """A turn against model answers given in order; returns (events, conversation, bodies sent)."""
        sent, bodies = [], []
        conversation = SimpleNamespace(messages=[], pending={})
        config = {'model': None, 'max_tokens': 16000, 'max_steps': steps, 'locale': 'en'}
        turn = Turn(config, conversation, sent.append, {'locale': 'en'}, _App())
        ran = []
        turn.call = lambda name, given: ran.append(name) or {'ok': True, 'result': {}}

        def answer(_config, _who, body, _on_text):
            bodies.append(body)
            return answers.pop(0)
        with patch.object(platform, 'message', answer):
            turn.turn('Export all of them', None)
        return sent, conversation, bodies, ran

    def test_an_answer_cut_off_at_its_length_runs_none_of_its_actions_and_goes_on(self):
        cut = {'content': [{'type': 'text', 'text': 'Looking. '}, {'type': 'tool_use', 'id': 'tu_cut', 'name': 'export_file', 'input': {}}], 'stop_reason': 'max_tokens'}
        done = {'content': [{'type': 'text', 'text': 'Done.'}], 'stop_reason': 'end_turn'}
        _sent, _conversation, bodies, ran = self._turn([cut, done])
        self.assertEqual(ran, [])
        second = str(bodies[1]['messages'])
        self.assertNotIn('tu_cut', second)
        self.assertIn(CUT_OFF, second)

    def test_when_the_steps_run_out_the_user_reads_how_to_go_on(self):
        call = lambda n: {'content': [{'type': 'tool_use', 'id': 'tu_%d' % n, 'name': 'export_file', 'input': {}}], 'stop_reason': 'tool_use'}  # noqa: E731
        sent, conversation, _bodies, ran = self._turn([call(1), call(2)], steps=2)
        self.assertEqual(ran, ['export_file', 'export_file'])
        self.assertIn(message('too_big', 'en'), ''.join(e.get('text', '') for e in sent if e['type'] == 'text'))
        self.assertEqual(conversation.messages[-1]['role'], 'assistant')

    def test_a_stored_action_without_its_result_is_left_out(self):
        fixed = paired([
            {'role': 'user', 'content': 'Export the files'},
            {'role': 'assistant', 'content': [{'type': 'text', 'text': 'On it.'}, {'type': 'tool_use', 'id': 'tu_orphan', 'name': 'export_file', 'input': {}}]},
            {'role': 'user', 'content': 'I did not get them'},
        ])
        self.assertNotIn('tu_orphan', str(fixed))
        self.assertEqual([m['role'] for m in fixed], ['user', 'assistant', 'user'])
        whole = [
            {'role': 'user', 'content': 'Export'},
            {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 'tu_1', 'name': 'export_file', 'input': {}}]},
            {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'tu_1', 'content': '{}'}]},
        ]
        self.assertEqual(paired(whole), whole)

    def test_the_user_reads_what_a_failure_means_for_them(self):
        for status, kind, key in ((402, 'app_limit', 'paused'), (402, 'billing_error', 'credit'), (529, 'overloaded_error', 'overloaded'),
                                  (400, 'invalid_request_error', 'conversation'), (502, 'api_error', 'unavailable')):
            self.assertEqual(failure_kind(platform.Refused('refused', status, kind)), key)
            self.assertTrue(message(key, 'ar'))

