import re

from odoo import fields, models


class RekhuAssistantHelp(models.Model):
    """The company's own help, one topic per record: what the assistant answers how-to questions from."""

    _name = 'rekhu.assistant.help'
    _description = 'Rekhu Assistant help topic'
    _order = 'sequence, id'

    name = fields.Char('Title', required=True, translate=True)
    body = fields.Text('Text', required=True, translate=True, help='Markdown or plain text: how something works in this company, step by step.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    def _search_topics(self, question, limit=3):
        """The topics that share the most words with the question, title words counting more."""
        words = [w for w in re.split(r'[^\w]+', str(question).lower()) if len(w) > 2]
        if not words:
            return []
        scored = []
        for topic in self.search([], limit=500):
            head, body = (topic.name or '').lower(), (topic.body or '').lower()
            score = sum((5 if w in head else 0) + min(5, body.count(w)) for w in words)
            if score:
                scored.append((score, topic))
        scored.sort(key=lambda pair: -pair[0])
        return [{'title': t.name, 'text': (t.body or '')[:6000]} for _s, t in scored[:limit]]
