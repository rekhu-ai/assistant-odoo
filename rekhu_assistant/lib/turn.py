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
# what the model is told when its answer reached the length limit: the actions in it were cut and none ran
CUT_OFF = 'Your last answer reached its length limit and was cut off, so none of the actions in it ran. Go on in smaller steps: fewer actions in one answer, or shorter text.'


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
        stop, said = None, False
        for _step in range(self.config['max_steps']):
            body = {'model': self.config['model'], 'max_tokens': self.config['max_tokens'], 'system': instructions, 'messages': cached(paired(self.conversation.messages))}
            if tools:
                body['tools'] = tools
            answer = platform.message(self.config, self.who, body, lambda delta: self.emit({'type': 'text', 'text': delta}))
            stop = answer['stop_reason']
            content = answer['content']
            if stop == 'max_tokens':
                # an action cut off halfway never runs: the answer keeps its text, and the model goes on in smaller steps
                content = [b for b in content if b.get('type') != 'tool_use']
            if any(b.get('type') in ('text', 'tool_use') for b in content):
                self.conversation.messages.append({'role': 'assistant', 'content': content})
            said = said or any(b.get('type') == 'text' and b.get('text') for b in content)
            if stop == 'max_tokens':
                self.conversation.messages.append({'role': 'user', 'content': [{'type': 'text', 'text': CUT_OFF}]})
                continue
            if stop != 'tool_use':
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
        if stop in ('tool_use', 'max_tokens'):
            # the steps of one answer ran out before the work was done: the user reads where it stopped and how to go on
            text = say('too_big', *self.lang)
            self.emit({'type': 'text', 'text': ('\n\n' if said else '') + text})
            self.conversation.messages.append({'role': 'assistant', 'content': [{'type': 'text', 'text': text}]})

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


def paired(messages):
    """The messages with every action call followed by its result, as the model requires: a call without a result (an
    answer that broke off before its actions ran) and a result without its call are left out, and so is a message that
    is empty without them. A conversation stored with such a gap goes on instead of being refused."""
    def blocks(message, kind):
        content = (message or {}).get('content')
        return [b for b in content if isinstance(b, dict) and b.get('type') == kind] if isinstance(content, list) else []

    kept = {}
    for i, message in enumerate(messages):
        if message['role'] == 'assistant':
            answered = {b.get('tool_use_id') for b in blocks(messages[i + 1] if i + 1 < len(messages) else None, 'tool_result')}
            kept[i] = {b.get('id') for b in blocks(message, 'tool_use') if b.get('id') in answered}
    out = []
    for i, message in enumerate(messages):
        if not isinstance(message['content'], list):
            out.append(message)
            continue
        calls = kept[i] if message['role'] == 'assistant' else (kept.get(i - 1, set()) if i and messages[i - 1]['role'] == 'assistant' else set())
        content = [b for b in message['content'] if not isinstance(b, dict)
                   or (b.get('id') in calls if b.get('type') == 'tool_use' else b.get('tool_use_id') in calls if b.get('type') == 'tool_result' else True)]
        if any(not isinstance(b, dict) or b.get('type') != 'thinking' for b in content):
            out.append(dict(message, content=content))
    return out


def failure_kind(error):
    """paused, credit, overloaded, conversation or unavailable: what a failed turn means for the user."""
    kind = getattr(error, 'kind', '') if isinstance(error, platform.Refused) else ''
    status = getattr(error, 'status', 0) if isinstance(error, platform.Refused) else 0
    if kind == 'app_limit':
        return 'paused'
    if kind == 'billing_error' or status == 402:
        return 'credit'
    if kind in ('rate_limit_error', 'overloaded_error') or status in (429, 529) or 'overloaded' in str(error).lower():
        return 'overloaded'
    if kind == 'invalid_request_error' or status == 400:
        return 'conversation'
    return 'unavailable'
