"""One model call through the Rekhu platform (/v1/messages, the Anthropic Messages format), streamed: text is handed
on as it arrives, and the whole message comes back at the end. Every call names the customer (x-tenant, the Odoo
company) and the user (x-user), so Rekhu meters it per company, and the conversation (x-session)."""

import json
import re

import requests

KEY = re.compile(r'^agk_([a-z0-9-]+)_([a-z0-9-]+)_[A-Za-z0-9_-]+$')


class Refused(Exception):
    """Rekhu refused a call. `kind` says why: "app_limit" (the app is paused or at its monthly limit) or
    "billing_error" (the account's credit is used up), among others."""

    def __init__(self, message, status, kind=''):
        super().__init__(message)
        self.status = status
        self.kind = kind


def parse_key(key):
    m = KEY.match(str(key or '').strip())
    return {'key': m.group(0), 'customer': m.group(1), 'agent': m.group(2)} if m else None


def headers(key, version, tenant=None, user_ref=None, conversation=None):
    out = {
        'content-type': 'application/json',
        'x-api-key': key['key'],
        'x-agent': key['agent'],
        'anthropic-version': '2023-06-01',
        'user-agent': 'rekhu-assistant-odoo/%s' % version,
    }
    if tenant:
        out['x-tenant'] = str(tenant['id'])
        out['x-tenant-name'] = str(tenant.get('name') or tenant['id'])
    if user_ref:
        out['x-user'] = str(user_ref)
    if conversation:
        out['x-session'] = 'assistant-%s' % conversation
    return out


def message(config, who, body, on_text):
    """Streams one model call; on_text gets every piece of text; returns {'content': [...], 'stop_reason': ...}."""
    key = parse_key(config['secret_key'])
    if not key:
        raise Refused('The Rekhu secret key is missing or not a secret key (agk_…). Set it under Settings → Rekhu Assistant. No Rekhu account yet? Create one at https://rekhu.com/register?ref=assistant-odoo: it starts with $10 credit, no card needed.', 400, 'config')
    response = requests.post(
        '%s/v1/messages' % config['platform'],
        headers=headers(key, config['version'], who['tenant'], who['user_ref'], who['conversation']),
        data=json.dumps(dict(body, stream=True)),
        stream=True,
        timeout=(10, 180),
    )
    if response.status_code >= 400:
        try:
            error = response.json().get('error') or {}
        except ValueError:
            error = {}
        raise Refused('Rekhu answered %s: %s' % (response.status_code, error.get('message') or 'no reason given'), response.status_code, error.get('type') or '')
    return read(response, on_text)


def balance(config, timeout=15):
    """The account's credit, to check a key from the settings: {'prepaid': …, 'balance': {'display': …}}."""
    key = parse_key(config['secret_key'])
    if not key:
        raise Refused('That is not a Rekhu secret key (agk_…).', 400, 'config')
    response = requests.get('%s/v1/balance' % config['platform'], headers=headers(key, config['version']), timeout=timeout)
    if response.status_code >= 400:
        try:
            error = response.json().get('error') or {}
        except ValueError:
            error = {}
        raise Refused('Rekhu refused the key (%s): %s' % (response.status_code, error.get('message') or 'no reason given'), response.status_code, error.get('type') or '')
    return response.json()


def read(response, on_text):
    """Folds the server-sent events of a streamed message into the message itself."""
    blocks, partial, stop = {}, {}, None
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith('data:'):
            continue
        try:
            data = json.loads(line[5:].strip())
        except ValueError:
            continue
        kind, i = data.get('type'), data.get('index')
        if kind == 'content_block_start':
            blocks[i] = dict(data.get('content_block') or {})
            partial[i] = ''
        elif kind == 'content_block_delta':
            delta = data.get('delta') or {}
            if delta.get('type') == 'text_delta':
                blocks[i]['text'] = blocks[i].get('text', '') + delta.get('text', '')
                on_text(delta.get('text', ''))
            elif delta.get('type') == 'input_json_delta':
                partial[i] += delta.get('partial_json') or ''
            elif delta.get('type') == 'thinking_delta':
                # the model's thinking goes back unchanged with its signature on the next call, never to the user
                blocks[i]['thinking'] = blocks[i].get('thinking', '') + delta.get('thinking', '')
            elif delta.get('type') == 'signature_delta':
                blocks[i]['signature'] = blocks[i].get('signature', '') + delta.get('signature', '')
        elif kind == 'content_block_stop':
            if blocks.get(i, {}).get('type') == 'tool_use':
                try:
                    value = json.loads(partial[i]) if partial.get(i) else {}
                except ValueError:
                    value = {}
                blocks[i]['input'] = value if isinstance(value, dict) else {}
        elif kind == 'message_delta':
            stop = (data.get('delta') or {}).get('stop_reason') or stop
        elif kind == 'error':
            raise Refused('the model stopped: %s' % ((data.get('error') or {}).get('message') or 'unknown error'), 502, 'model')
    return {'content': [blocks[k] for k in sorted(blocks)], 'stop_reason': stop}
