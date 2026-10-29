"""One turn of the conversation: the user's words (or their click on a confirm button) in, the model's answer out,
with the actions, pages and help it used along the way. Events go to `emit` as they happen:
    text {text} · step {label} · card {kind: page | confirm | done | failed, …}

The Odoo side is the `app`: it lists the actions this user may use, runs them in the user's environment, and knows
the pages and the help. The turn itself does not know Odoo."""

import hashlib
import json

from . import platform
from .messages import message as say
from .schema import validate

RESULT_LIMIT = 30000


def confirm_id(tool, value):
    return hashlib.sha256(('%s|%s' % (tool, json.dumps(value, sort_keys=True, default=str))).encode()).hexdigest()[:24]


def label_of(label, *tags):
    if not label:
        return None
    if isinstance(label, str):
        return label
    for tag in tags:
        lang = str(tag or '').split(',')[0].strip().lower().replace('_', '-').split('-')[0]
        if lang and label.get(lang):
            return label[lang]
    return label.get('en') or next(iter(label.values()), None)


class Turn:
    def __init__(self, config, conversation, emit, who, app):
        self.config = config
        self.conversation = conversation
        self.emit = self._once(emit)
        self.who = who
        self.app = app
        self.actions = {a['name']: a for a in app.actions()}
        self.lang = (who.get('locale'), config.get('locale'))

    @staticmethod
    def _once(emit):
        """Each record or page gets one button per turn: a "page" card for a link already on screen (the done card of a
        change just made, say) is left out."""
        shown = set()

        def send(event):
            url = event.get('url') if event.get('type') == 'card' else None
            if url and event.get('kind') == 'page' and url in shown:
                return
            if url:
                shown.add(url)
            emit(event)
        return send

    def label(self, action):
        return label_of(action.get('label'), *self.lang) or action['description']

    def turn(self, text, confirm):
        if confirm:
            self.confirmed(confirm)
        else:
            self.conversation.messages.append({'role': 'user', 'content': str(text).strip()[:4000]})
        instructions = self.app.system()
        tools = self.tools()
        for _step in range(self.config['max_steps']):
            body = {'model': self.config['model'], 'max_tokens': self.config['max_tokens'], 'system': instructions, 'messages': cached(self.conversation.messages)}
            if tools:
                body['tools'] = tools
            answer = platform.message(self.config, self.who, body, lambda delta: self.emit({'type': 'text', 'text': delta}))
            self.conversation.messages.append({'role': 'assistant', 'content': answer['content']})
            if answer['stop_reason'] != 'tool_use':
                break
            results = []
            for block in answer['content']:
                if block.get('type') != 'tool_use':
                    continue
                outcome = self.call(block['name'], block.get('input') or {})
                if outcome.get('ok'):
                    body_text = json.dumps(outcome.get('result'), default=str)
                else:
                    body_text = json.dumps({k: v for k, v in (('error', outcome.get('error')), ('errors', outcome.get('errors'))) if v}, default=str)
                if len(body_text) > RESULT_LIMIT:
                    body_text = body_text[:RESULT_LIMIT] + ' … [cut: ask for less]'
                result = {'type': 'tool_result', 'tool_use_id': block['id'], 'content': body_text}
                if not outcome.get('ok'):
                    result['is_error'] = True
                results.append(result)
            self.conversation.messages.append({'role': 'user', 'content': results})

    def confirmed(self, cid):
        """The user clicked confirm: the action runs now with exactly the input they saw, and the model is told."""
        pending = self.conversation.pending.pop(cid, None)
        action = self.actions.get(pending['tool']) if pending else None
        if not action:
            self.conversation.messages.append({'role': 'user', 'content': 'I clicked confirm, but that action is no longer available.'})
            return
        self.emit({'type': 'step', 'label': self.label(action)})
        outcome = self.run(action, pending['input'])
        self.card(action, outcome, pending.get('title'))
        if outcome.get('ok'):
            told = 'It ran. The result: %s' % json.dumps(outcome.get('result'), default=str)
        else:
            told = 'It failed: %s' % json.dumps({k: v for k, v in (('error', outcome.get('error')), ('errors', outcome.get('errors'))) if v}, default=str)
        self.conversation.messages.append({'role': 'user', 'content': 'I confirmed "%s". %s' % (action['description'], told)})

    def call(self, name, given):
        if name == 'open_page':
            return self.open_page(given)
        if name == 'help':
            self.emit({'type': 'step', 'label': say('help', *self.lang)})
            found = self.app.search_help(given.get('question') or '')
            return {'ok': True, 'result': {'topics': found} if found else {'topics': [], 'note': 'nothing in the help about this'}}
        action = self.actions.get(name)
        if not action:
            return {'ok': False, 'error': 'there is no such action for this user'}
        if action['confirm']:
            ok, value = validate(action['schema'], given)
            if not ok:
                return {'ok': False, 'error': 'the input was refused', 'errors': value}
            # the app may check more before anything is shown (a model and fields that exist, a record the user may see)
            problem = self.app.precheck(action, value)
            if problem:
                return {'ok': False, 'error': problem}
            cid = confirm_id(name, value)
            # what the user reads on the card: the app's own words where it has them, else the input as given
            title, shown = self.app.present(action, value) if hasattr(self.app, 'present') else (None, None)
            self.conversation.pending[cid] = {'tool': name, 'input': value, 'title': title}
            if shown is None:
                shown = {k: v for k, v in value.items() if k not in action.get('hidden', [])}
            self.emit({'type': 'card', 'kind': 'confirm', 'id': cid, 'title': title or self.label(action), 'input': shown, 'danger': bool(action.get('danger'))})
            return {'ok': True, 'result': {'status': 'needs_confirmation', 'note': 'The user sees a confirm button for exactly this input. Nothing has happened yet.'}}
        self.emit({'type': 'step', 'label': self.label(action) if not action.get('readonly') else say('searching', *self.lang)})
        outcome = self.run(action, given)
        self.card(action, outcome)
        return outcome

    def run(self, action, given):
        ok, value = validate(action['schema'], given)
        if not ok:
            return {'ok': False, 'error': 'the input was refused', 'errors': value}
        return self.app.run(action, value, self.emit)

    def open_page(self, given):
        page = self.app.pages().get(str(given.get('page') or ''))
        if not page:
            return {'ok': False, 'error': 'no such page for this user; pick one from the list'}
        self.emit({'type': 'card', 'kind': 'page', 'label': str(given.get('label') or page['label']), 'url': page['url']})
        return {'ok': True, 'result': {'status': 'shown', 'note': 'The user has a button to open it.'}}

    def card(self, action, outcome, title=None):
        # reading needs no card: the answer says what was found
        if outcome.get('ok') and action.get('readonly'):
            return
        if outcome.get('ok'):
            result = outcome.get('result') if isinstance(outcome.get('result'), dict) else {}
            card = {'type': 'card', 'kind': 'done', 'title': title or self.label(action)}
            if isinstance(result.get('message'), str):
                card['message'] = result['message']
            if isinstance(result.get('url'), str):
                card['url'] = result['url']
            self.emit(card)
        else:
            self.emit({'type': 'card', 'kind': 'failed', 'title': title or self.label(action), 'message': outcome.get('error')})

    def tools(self):
        out = [{'name': a['name'], 'description': a['description'] + (' (The user confirms before it runs.)' if a['confirm'] else ''), 'input_schema': a['schema']} for a in self.actions.values()]
        pages = self.app.pages()
        if pages:
            out.append({'name': 'open_page', 'description': 'Gives the user a button that opens a menu of Odoo. "page" is a name from the page list.', 'input_schema': {
                'type': 'object', 'properties': {'page': {'type': 'string', 'enum': list(pages)}, 'label': {'type': 'string', 'description': 'The button text, short'}}, 'required': ['page'],
            }})
        if self.app.has_help():
            out.append({'name': 'help', 'description': "Searches the company's own help for how something works or how to do it.", 'input_schema': {
                'type': 'object', 'properties': {'question': {'type': 'string'}}, 'required': ['question'],
            }})
        return out


def cached(messages):
    """The whole conversation is sent every time; a cache mark on its last block makes it a cheap cache read next time."""
    if not messages:
        return messages
    copy = list(messages[:-1])
    last = messages[-1]
    blocks = [{'type': 'text', 'text': last['content']}] if isinstance(last['content'], str) else [dict(b) for b in last['content']]
    blocks[-1] = dict(blocks[-1], cache_control={'type': 'ephemeral'})
    copy.append({'role': last['role'], 'content': blocks})
    return copy
