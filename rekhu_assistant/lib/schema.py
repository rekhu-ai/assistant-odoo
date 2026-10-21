"""An action's input: JSON Schema (an object schema), or the short form {'order': 'string', 'quantity': 'integer?',
'size': ['small', 'large']}. The model sees the schema; what it sends is checked against it before the action runs."""

import re

TYPES = ('string', 'integer', 'number', 'boolean', 'array', 'object')


def to_schema(spec):
    """The JSON Schema of an action's input, from either form."""
    if not spec:
        return {'type': 'object', 'properties': {}}
    if spec.get('type') == 'object':
        return {'properties': {}, **spec}
    properties, required = {}, []
    for name, rule in spec.items():
        if isinstance(rule, (list, tuple)):
            properties[name] = {'type': 'string', 'enum': list(rule)}
            required.append(name)
        elif isinstance(rule, str):
            optional = rule.endswith('?')
            kind = rule[:-1] if optional else rule
            if kind not in TYPES:
                raise ValueError('input "%s": unknown type "%s" (use %s, with ? when optional)' % (name, rule, ', '.join(TYPES)))
            properties[name] = {'type': kind}
            if not optional:
                required.append(name)
        elif isinstance(rule, dict):
            rule = dict(rule)
            optional = rule.pop('optional', False)
            properties[name] = rule
            if not optional:
                required.append(name)
        else:
            raise ValueError('input "%s": give a type such as "string", a list of choices, or a JSON Schema' % name)
    out = {'type': 'object', 'properties': properties}
    if required:
        out['required'] = required
    return out


def _numeric(text):
    """Whether a text the model sent is a number written out ("3", "4.5", "-2")."""
    return bool(re.fullmatch(r'\s*-?\d+(\.\d+)?\s*', text))


def _wrong(kind, value):
    if kind == 'string':
        return not isinstance(value, str)
    if kind == 'integer':
        return isinstance(value, bool) or not isinstance(value, int)
    if kind == 'number':
        return isinstance(value, bool) or not isinstance(value, (int, float))
    if kind == 'boolean':
        return not isinstance(value, bool)
    if kind == 'array':
        return not isinstance(value, list)
    if kind == 'object':
        return not isinstance(value, dict)
    return False


def validate(schema, given):
    """(True, value) with only the declared fields, or (False, {field: [message]})."""
    errors, value = {}, {}
    given = given if isinstance(given, dict) else {}
    required = schema.get('required') or []

    def add(field, message):
        errors.setdefault(field, []).append(message)

    for field in required:
        if given.get(field) in (None, ''):
            add(field, 'is required')
    for field, rule in (schema.get('properties') or {}).items():
        v = given.get(field)
        if v is None or (v == '' and field not in required):
            continue
        kind = rule.get('type')
        if kind in ('integer', 'number') and isinstance(v, str) and _numeric(v):
            number = float(v)
            v = int(number) if kind == 'integer' and number.is_integer() else number
        if kind == 'integer' and isinstance(v, float) and v.is_integer():
            v = int(v)
        if kind == 'boolean' and v in ('true', 'false'):
            v = v == 'true'
        if _wrong(kind, v):
            add(field, 'must be a whole number' if kind == 'integer' else 'must be a %s' % kind)
            continue
        if rule.get('enum') and v not in rule['enum']:
            add(field, 'must be one of: %s' % ', '.join(map(str, rule['enum'])))
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if 'minimum' in rule and v < rule['minimum']:
                add(field, 'must be at least %s' % rule['minimum'])
            if 'maximum' in rule and v > rule['maximum']:
                add(field, 'must be at most %s' % rule['maximum'])
        if isinstance(v, str):
            if 'minLength' in rule and len(v) < rule['minLength']:
                add(field, 'must be at least %s characters' % rule['minLength'])
            if 'maxLength' in rule and len(v) > rule['maxLength']:
                add(field, 'must be at most %s characters' % rule['maxLength'])
            if rule.get('pattern') and not re.search(rule['pattern'], v):
                add(field, 'has the wrong format')
        if isinstance(v, list):
            if 'minItems' in rule and len(v) < rule['minItems']:
                add(field, 'needs at least %s items' % rule['minItems'])
            if 'maxItems' in rule and len(v) > rule['maxItems']:
                add(field, 'takes at most %s items' % rule['maxItems'])
        value[field] = v
    return (False, errors) if errors else (True, value)
