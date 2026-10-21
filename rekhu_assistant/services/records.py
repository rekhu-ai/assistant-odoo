"""Reading and writing Odoo records for the assistant, always in the user's own environment: access rights and record
rules decide, never the assistant. Values come in as the model writes them (names for related records, lists of
lines) and are turned into what the ORM takes."""

from datetime import date, datetime

from odoo.exceptions import AccessError, MissingError, UserError, ValidationError

# fields the assistant never writes, whatever the model
NEVER = {'id', 'create_uid', 'create_date', 'write_uid', 'write_date', '__last_update', 'display_name', 'message_ids', 'message_follower_ids', 'activity_ids', 'website_message_ids'}
# the operators a search may use
OPERATORS = {'=', '!=', '>', '>=', '<', '<=', 'like', 'ilike', 'not like', 'not ilike', 'in', 'not in', 'child_of', '=like', '=ilike'}
# the kinds of field shown when a search asks for none
SUMMARY_TYPES = ('char', 'selection', 'date', 'datetime', 'monetary', 'float', 'integer', 'many2one', 'boolean')
MAX_LIMIT = 50


class Refusal(Exception):
    """What the assistant is told when a read or a write is not possible, in one sentence."""


def may(model, operation):
    """Whether the user may `operation` ('read', 'create', 'write') on the model; Odoo 18 renamed the check."""
    if hasattr(model, 'has_access'):
        return model.has_access(operation)
    return model.check_access_rights(operation, raise_exception=False)


def record_url(model, rid):
    return '/web#model=%s&id=%d&view_type=form' % (model, int(rid))


def plain(value):
    """A read value as the assistant reads it: (id, name) pairs as {'id', 'name'}, dates as ISO text."""
    if isinstance(value, tuple) and len(value) == 2:
        return {'id': value[0], 'name': value[1]}
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is False:
        return None
    return value


def summary_fields(model, limit=8):
    found = model.fields_get(attributes=['type', 'store', 'string'])
    names = [n for n, f in found.items() if f.get('store') and f.get('type') in SUMMARY_TYPES and n not in NEVER and not n.startswith('message_') and not n.startswith('activity_')]
    priority = [n for n in ('name', 'partner_id', 'state', 'stage_id', 'date_order', 'invoice_date', 'amount_total', 'user_id', 'email', 'phone', 'date_deadline') if n in names]
    return list(dict.fromkeys(priority + names))[:limit]


def describe(model, limit=120):
    fields_ = model.fields_get(attributes=['string', 'type', 'relation', 'required', 'readonly', 'selection', 'store', 'help'])
    out = []
    for name, f in fields_.items():
        if name in NEVER or f.get('type') == 'binary':
            continue
        item = {'name': name, 'label': f.get('string'), 'type': f.get('type')}
        if f.get('relation'):
            item['relation'] = f['relation']
        if f.get('required'):
            item['required'] = True
        if f.get('readonly'):
            item['readonly'] = True
        if f.get('selection') and isinstance(f['selection'], list):
            item['choices'] = [s[0] for s in f['selection']][:30]
        out.append(item)
    out.sort(key=lambda i: (not i.get('required'), i.get('readonly', False), i['name']))
    return out[:limit]


def domain_of(model, given, query):
    """A search domain from [[field, operator, value], …] and a free text, checked against the model's fields."""
    known = model.fields_get(attributes=['type'])
    domain = []
    for part in given or []:
        if not isinstance(part, (list, tuple)) or len(part) != 3:
            raise Refusal('every filter is [field, operator, value]')
        field, operator, value = part
        if not isinstance(field, str) or field.split('.')[0] not in known or field.count('.') > 2:
            raise Refusal('the model has no field "%s"; use describe_model to see its fields' % field)
        if operator not in OPERATORS:
            raise Refusal('the operator "%s" is not allowed; use one of %s' % (operator, ', '.join(sorted(OPERATORS))))
        domain.append((field, operator, value))
    if query:
        name = model._rec_name if model._rec_name in known else ('name' if 'name' in known else None)
        if name:
            domain.append((name, 'ilike', str(query)))
    return domain


def search(env, model_name, domain=None, query=None, fields=None, limit=10, order=None):
    model = env[model_name]
    dom = domain_of(model, domain, query)
    names = [f for f in (fields or []) if f in model._fields and f not in NEVER] or summary_fields(model)
    limit = max(1, min(int(limit or 10), MAX_LIMIT))
    if order and not all(p.strip().split(' ')[0] in model._fields for p in str(order).split(',')):
        raise Refusal('the order names a field the model does not have')
    try:
        total = model.search_count(dom)
        rows = model.search_read(dom, names, limit=limit, order=order or None)
    except AccessError as error:
        raise Refusal('the user may not read these records: %s' % error) from error
    except (ValueError, UserError) as error:
        raise Refusal('the search was refused: %s' % error) from error
    records = [dict({k: plain(v) for k, v in row.items()}, url=record_url(model_name, row['id'])) for row in rows]
    return {'model': model_name, 'total': total, 'shown': len(records), 'records': records}


def read(env, model_name, rid, fields=None):
    model = env[model_name]
    names = [f for f in (fields or []) if f in model._fields and f not in NEVER] or summary_fields(model, limit=25)
    try:
        record = model.browse(int(rid)).exists()
        if not record:
            raise Refusal('there is no %s with id %s' % (model._description, rid))
        row = record.read(names)[0]
    except AccessError as error:
        raise Refusal('the user may not read this record: %s' % error) from error
    return dict({k: plain(v) for k, v in row.items()}, url=record_url(model_name, record.id))


def resolve(env, relation, value, label):
    """A related record named by its id or its name; a name that matches none or several is refused with the options."""
    target = env[relation]
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        record = target.browse(int(value)).exists()
        if not record:
            raise Refusal('%s: there is no %s with id %s' % (label, target._description, value))
        return record.id
    if isinstance(value, dict) and value.get('id'):
        return resolve(env, relation, value['id'], label)
    found = target.name_search(str(value), limit=5)
    exact = [f for f in found if f[1].strip().lower() == str(value).strip().lower()]
    if len(exact) == 1 or len(found) == 1:
        return (exact or found)[0][0]
    if not found:
        raise Refusal('%s: no %s is called "%s"; find it first, or ask the user' % (label, target._description, value))
    raise Refusal('%s: "%s" matches several: %s; ask the user which one' % (label, value, '; '.join('%s (id %s)' % (f[1], f[0]) for f in found)))


def values_of(env, model_name, given, depth=0):
    """The values to write, checked against the model: known, writable fields only; names and lists turned into ORM values."""
    model = env[model_name]
    if not isinstance(given, dict) or not given:
        raise Refusal('give the values as {field: value}')
    known = model.fields_get(attributes=['type', 'relation', 'readonly', 'string'])
    out = {}
    for name, value in given.items():
        f = known.get(name)
        if not f or name in NEVER:
            raise Refusal('the model has no field "%s" the assistant may write; use describe_model' % name)
        if f.get('readonly'):
            raise Refusal('"%s" cannot be set directly' % (f.get('string') or name))
        kind = f.get('type')
        if kind == 'binary':
            raise Refusal('"%s" holds a file; the assistant does not write files' % name)
        if kind == 'many2one':
            out[name] = resolve(env, f['relation'], value, f.get('string') or name)
        elif kind == 'many2many':
            items = value if isinstance(value, list) else [value]
            out[name] = [(6, 0, [resolve(env, f['relation'], v, f.get('string') or name) for v in items if v not in (None, '')])]
        elif kind == 'one2many':
            if depth or not isinstance(value, list):
                raise Refusal('"%s" takes a list of lines, each {field: value}' % name)
            out[name] = [(0, 0, values_of(env, f['relation'], line, depth + 1)) for line in value]
        else:
            out[name] = value
    return out


def readable_values(env, model_name, given):
    """The values as the user reads them on a confirm card: field labels in their language, related records by name."""
    model = env[model_name]
    known = model.fields_get(attributes=['type', 'relation', 'string', 'selection'])
    out = {}
    for name, value in (given or {}).items():
        f = known.get(name) or {}
        label = f.get('string') or name
        kind = f.get('type')
        if kind == 'many2one' and value not in (None, '', False):
            try:
                out[label] = env[f['relation']].browse(resolve(env, f['relation'], value, label)).display_name
            except Refusal:
                out[label] = value
        elif kind == 'many2many' and isinstance(value, list):
            out[label] = ', '.join(str(v) for v in value)
        elif kind == 'one2many' and isinstance(value, list):
            out[label] = '%d %s' % (len(value), 'line' if len(value) == 1 else 'lines')
        elif kind == 'selection' and isinstance(f.get('selection'), list):
            out[label] = dict(f['selection']).get(value, value)
        elif kind == 'boolean':
            out[label] = bool(value)
        else:
            out[label] = value
    return out


def create(env, model_name, values):
    try:
        record = env[model_name].create(values_of(env, model_name, values))
    except AccessError as error:
        raise Refusal('the user may not create this: %s' % error) from error
    except (UserError, ValidationError, ValueError) as error:
        raise Refusal('Odoo refused it: %s' % error) from error
    return {'id': record.id, 'name': record.display_name, 'message': '%s created.' % record.display_name, 'url': record_url(model_name, record.id)}


def write(env, model_name, rid, values):
    try:
        record = env[model_name].browse(int(rid)).exists()
        if not record:
            raise Refusal('there is no record with id %s' % rid)
        record.write(values_of(env, model_name, values))
    except AccessError as error:
        raise Refusal('the user may not change this: %s' % error) from error
    except (UserError, ValidationError, ValueError, MissingError) as error:
        raise Refusal('Odoo refused it: %s' % error) from error
    return {'id': record.id, 'name': record.display_name, 'message': '%s updated.' % record.display_name, 'url': record_url(model_name, record.id)}
