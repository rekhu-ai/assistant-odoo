import hashlib
import json
import re
import uuid
from datetime import timedelta

from odoo import api, fields, models

from ..lib import params as settings

KEEP_DAYS = 14
OWN = re.compile(r'^[a-zA-Z0-9-]{8,64}$')


class RekhuAssistantConversation(models.Model):
    """One user's conversation, kept on this server, never in the browser: the model only reads what Odoo itself
    recorded. Also holds the actions waiting for the user's confirmation. Reached only through the chat route, which
    opens a user's own conversations."""

    _name = 'rekhu.assistant.conversation'
    _description = 'Rekhu Assistant conversation'

    key = fields.Char(required=True, index=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    messages = fields.Text(default='[]')
    pending = fields.Text(default='{}')
    expires_at = fields.Datetime(index=True)

    # Odoo 19 declares constraints as models.Constraint; 17 and 18 as _sql_constraints
    if hasattr(models, 'Constraint'):
        _key_unique = models.Constraint('unique(key)', 'A conversation key is used once.')
    else:
        _sql_constraints = [('key_unique', 'unique(key)', 'A conversation key is used once.')]

    @api.model
    def _rekhu_key(self, uid, cid):
        return '%s:%s' % (hashlib.sha256(('user:%s' % uid).encode()).hexdigest()[:40], cid)

    @api.model
    def _rekhu_open(self, uid, cid):
        """The conversation `cid` of this user; another user's id, or none, opens a new and empty one."""
        cid = cid if isinstance(cid, str) and OWN.match(cid) else str(uuid.uuid4())
        row = self.sudo().search([('key', '=', self._rekhu_key(uid, cid))], limit=1)
        return Conversation(self.sudo(), uid, cid, row)

    @api.model
    def _rekhu_prune(self):
        self.sudo().search([('expires_at', '<', fields.Datetime.now())]).unlink()

    @api.model
    def _rekhu_config(self):
        def get(key, default=False):
            return settings.get(self.env, key, default)
        manifest = self.env['ir.module.module'].sudo().search([('name', '=', 'rekhu_assistant')], limit=1)
        return {
            'enabled': get('rekhu_assistant.enabled') in ('True', 'true', '1'),
            'secret_key': (get('rekhu_assistant.secret_key') or '').strip(),
            'platform': (get('rekhu_assistant.platform') or 'https://api.rekhu.ai').rstrip('/'),
            'model': get('rekhu_assistant.model') or None,
            'name': get('rekhu_assistant.name') or 'Assistant',
            'greeting': get('rekhu_assistant.greeting') or '',
            'quick': [q.strip() for q in (get('rekhu_assistant.quick') or '').split('|') if q.strip()],
            'instructions': get('rekhu_assistant.instructions') or '',
            # where it works: the rules of the set-up; without rules it does not run
            'rules': self.env['rekhu.assistant.scope']._rekhu_rules(),
            'group_id': int(get('rekhu_assistant.group_id') or 0),
            'version': manifest.latest_version or manifest.installed_version or '1.0',
            'max_steps': 8,
            'max_tokens': 16000,
        }


class Conversation:
    def __init__(self, model, uid, cid, row):
        self.model = model
        self.uid = uid
        self.id = cid
        self.row = row
        self.messages = json.loads(row.messages or '[]') if row else []
        self.pending = json.loads(row.pending or '{}') if row else {}

    def save(self):
        # the oldest turns go first when it grows long; a cut never starts on a tool result without its call
        while len(self.messages) > 60:
            self.messages.pop(0)
            while self.messages and (self.messages[0]['role'] != 'user' or not isinstance(self.messages[0]['content'], str)):
                self.messages.pop(0)
        values = {
            'messages': json.dumps(self.messages, default=str), 'pending': json.dumps(self.pending, default=str),
            'expires_at': fields.Datetime.now() + timedelta(days=KEEP_DAYS),
        }
        if self.row:
            self.row.write(values)
        else:
            self.row = self.model.create(dict(values, key=self.model._rekhu_key(self.uid, self.id), user_id=self.uid))

    def forget(self):
        if self.row:
            self.row.unlink()

    def seen(self):
        """What the user saw: their messages and the answers, without the tool traffic, at most the last 30."""
        out = []
        for m in self.messages:
            if m['role'] == 'user' and isinstance(m['content'], str) and not m['content'].startswith('I confirmed "') and not m['content'].startswith('I clicked confirm'):
                out.append({'role': 'user', 'text': m['content']})
            elif m['role'] == 'assistant':
                text = ''.join(b.get('text', '') for b in m['content'] if isinstance(b, dict) and b.get('type') == 'text').strip()
                if text:
                    out.append({'role': 'bot', 'text': text})
        return out[-30:]
