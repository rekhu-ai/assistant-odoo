from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..lib.turn import Turn


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
