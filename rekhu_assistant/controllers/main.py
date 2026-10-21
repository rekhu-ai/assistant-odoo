"""The chat route of protocol 1 (PROTOCOL.md), for the signed-in Odoo user:

    POST   /rekhu/assistant/chat     one turn, answered as a stream of events
    GET    /rekhu/assistant/chat     the conversation so far, the greeting and the quick questions
    DELETE /rekhu/assistant/chat     forgets a conversation
    GET    /rekhu/assistant/config   whether this user has the assistant, for the chat button

A turn runs on a cursor of its own, in a thread, so its events reach the browser as they happen."""

import json
import logging
import queue
import threading
import time
from collections import defaultdict, deque

from odoo import api, http
from odoo.http import request

from ..lib import platform
from ..lib.messages import message as say
from ..lib.turn import Turn
from ..services.app import OdooApp

_logger = logging.getLogger(__name__)

PROTOCOL = '1'
TURNS_PER_MINUTE = 20
_recent = defaultdict(deque)   # uid → the moments of their last turns, for the per-minute cap


def _json(data, status=200):
    return request.make_response(json.dumps(data), headers=[('Content-Type', 'application/json'), ('Cache-Control', 'no-store')], status=status)


def _sse(event):
    """One server-sent event, as the bytes the response writes."""
    return ('event: %s\ndata: %s\n\n' % (event['type'], json.dumps(event, default=str))).encode()


def _groups_of(user):
    """Every group of the user, implied ones included: all_group_ids from Odoo 19, groups_id before."""
    user = user.sudo()
    return user.all_group_ids if 'all_group_ids' in user._fields else user.groups_id


def _too_many(uid):
    now, seen = time.monotonic(), _recent[uid]
    while seen and now - seen[0] > 60:
        seen.popleft()
    if len(seen) >= TURNS_PER_MINUTE:
        return True
    seen.append(now)
    return False


class RekhuAssistantController(http.Controller):

    def _config(self):
        return request.env['rekhu.assistant.conversation'].sudo()._rekhu_config()

    def _allowed(self, config):
        user = request.env.user
        # it runs only once it is set up: switched on, with rules for where it works
        if not config['enabled'] or not config['rules']['read'] or user._is_public() or not user._is_internal():
            return False
        group = request.env['res.groups'].sudo().browse(config['group_id']).exists() if config['group_id'] else None
        return not group or group.id in _groups_of(user).ids

    @http.route('/rekhu/assistant/config', type='http', auth='user', methods=['GET'])
    def config(self):
        config = self._config()
        user = request.env.user
        return _json({
            'enabled': self._allowed(config),
            'name': config['name'],
            'locale': (user.lang or 'en_US').replace('_', '-'),
            'protocol': int(PROTOCOL),
        })

    @http.route('/rekhu/assistant/chat', type='http', auth='user', methods=['GET', 'POST', 'DELETE'], csrf=False)
    def chat(self, **query):
        http_request = request.httprequest
        config = self._config()
        user = request.env.user
        locale_header = http_request.headers.get('Accept-Language')
        if http_request.headers.get('X-Rekhu-Protocol', PROTOCOL) != PROTOCOL:
            return _json({'message': 'This server speaks protocol 1.'}, 400)
        # the custom header is the defence against cross-site requests: a form on another site cannot send it
        if http_request.method != 'GET' and http_request.headers.get('X-Rekhu-Protocol') != PROTOCOL:
            return _json({'message': 'X-Rekhu-Protocol is required.'}, 403)
        if not self._allowed(config):
            return _json({'message': say('off', locale_header, user.lang)}, 403)
        conversations = request.env['rekhu.assistant.conversation']

        if http_request.method == 'GET':
            conversation = conversations._rekhu_open(user.id, query.get('conversation'))
            out = {'conversation': conversation.id, 'messages': conversation.seen() if query.get('conversation') else []}
            if config['greeting']:
                out['greeting'] = config['greeting']
            if not query.get('conversation') and config['quick']:
                out['quick'] = config['quick']
            return _json(out)

        try:
            body = json.loads(http_request.get_data(as_text=True) or '{}')
        except ValueError:
            return _json({'message': 'The body is not JSON.'}, 422)
        if not isinstance(body, dict):
            return _json({'message': 'The body is not a JSON object.'}, 422)

        if http_request.method == 'DELETE':
            conversations._rekhu_open(user.id, body.get('conversation')).forget()
            return request.make_response('', status=204)

        text, confirm = str(body.get('message') or '').strip(), body.get('confirm')
        if not text and not confirm:
            return _json({'message': say('empty', body.get('locale'), user.lang)}, 422)
        if _too_many(user.id):
            return _json({'message': say('busy', body.get('locale'), user.lang)}, 429)
        if not platform.parse_key(config['secret_key']):
            return _json({'message': say('unavailable', body.get('locale'), user.lang)}, 503)

        return self._stream(config, user, body, text, confirm)

    def _stream(self, config, user, body, text, confirm):
        """Runs the turn in a thread on a cursor of its own and hands its events to the response as they come."""
        registry, uid, context = request.env.registry, user.id, dict(request.env.context)
        locale = str(body.get('locale') or '')[:20] or None
        events = queue.Queue()
        conversation_id = body.get('conversation')

        def work():
            thread = threading.current_thread()
            thread.dbname, thread.uid = registry.db_name, uid
            try:
                with registry.cursor() as cr:
                    env = api.Environment(cr, uid, context)
                    conversation = env['rekhu.assistant.conversation']._rekhu_open(uid, conversation_id)
                    events.put({'type': 'start', 'conversation': conversation.id, 'protocol': int(PROTOCOL)})
                    company = env.user.company_id
                    who = {'tenant': {'id': company.id, 'name': company.name}, 'user_ref': str(uid), 'conversation': conversation.id, 'locale': locale}
                    app = OdooApp(env, dict(config, locale=(env.user.lang or 'en_US').replace('_', '-')), locale)
                    try:
                        Turn(app.config, conversation, events.put, who, app).turn(text, confirm)
                    finally:
                        # what happened so far stays, also when the model stopped halfway
                        conversation.save()
            except platform.Refused as refused:
                _logger.warning('rekhu assistant: %s', refused)
                events.put({'type': 'error', 'message': say('unavailable', locale)})
            except Exception:  # noqa: BLE001 never a stack trace in the chat; the log has it
                _logger.exception('rekhu assistant: the turn failed')
                events.put({'type': 'error', 'message': say('unavailable', locale)})
            finally:
                events.put({'type': 'done'})
                events.put(None)

        threading.Thread(target=work, name='rekhu-assistant-turn', daemon=True).start()

        def stream():
            while True:
                event = events.get()
                if event is None:
                    return
                yield _sse(event)

        return http.Response(stream(), status=200, headers=[('Content-Type', 'text/event-stream'), ('Cache-Control', 'no-store'), ('X-Accel-Buffering', 'no')], direct_passthrough=True)
