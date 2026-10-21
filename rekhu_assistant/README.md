<p align="center">
  <img alt="Rekhu Assistant for Odoo" src="static/description/icon.png" width="96">
</p>

<h1 align="center">Rekhu Assistant for Odoo</h1>

<p align="center">
  <img alt="Odoo 17, 18 and 19" src="https://img.shields.io/badge/Odoo-17%20%7C%2018%20%7C%2019-714B67">
  <img alt="Python 3.10 or newer" src="https://img.shields.io/badge/Python-3.10%2B-3776AB">
</p>

<p align="center">
  <a href="#getting-started">Getting started</a> ·
  <a href="#what-it-can-do">What it can do</a> ·
  <a href="#your-own-actions">Your own actions</a> ·
  <a href="#security">Security</a> ·
  <a href="#settings">Settings</a>
</p>

---

**Rekhu Assistant** is an AI assistant inside the Odoo back office, for the people who work in it. They ask in their
own words: *"which invoices of Acme are overdue?"*, *"make a lead for Gemini Furniture, 4,500 expected"*, *"schedule a
call with them on Monday"*. The assistant finds the records, answers, and does the work with the user's own access
rights. Every change waits for a click on **Confirm**.

| | |
|---|---|
| **Finds and reads** | Searches every model you allow, reads records, and gives a button to open them. |
| **Does the work** | Creates and changes records, adds notes to the chatter and schedules activities, after a click on Confirm. |
| **Your own actions** | Put `@tool` on a model method, and the assistant can do that job too. |
| **Knows your way of working** | Answers how-to questions from help topics you write, in the user's language. |
| **Opens the right menu** | Sends people to the menu they need, from the menus they can see. |
| **As the user** | Access rights and record rules decide what it sees and may do; it never works around them. |
| **Per company** | Usage is metered per Odoo company in your Rekhu account, with one monthly limit and a pause. |

## Requirements

| Requirement | Version |
|---|---|
| Odoo | 17, 18 or 19, Community or Enterprise |
| Python | the one your Odoo runs on (3.10 or newer); `requests`, which Odoo already uses |
| Rekhu | an account with credit and a secret key: [sign up](https://rekhu.com/register), then top up from $10 under **Billing** |
| Network | the Odoo server reaches `https://api.rekhu.ai` over HTTPS; nothing calls into Odoo |

## Getting started

### 1. Get a secret key

In your Rekhu account, under **Projects → New project**, choose **Odoo** and name it. On its **Connection** tab, add a
key for the database (`production`, and `staging` if you have one). The key starts with `agk_` and is shown once.

### 2. Install the module

From the Odoo Apps store, or from source:

```bash
git clone --branch 18.0 https://github.com/rekhu-ai/assistant-odoo.git
```

Put `rekhu_assistant` in your addons path, update the apps list, and install **Rekhu Assistant**. Use the branch of
your Odoo version: `17.0`, `18.0` or `19.0`.

### 3. Set it up

**Settings → Rekhu Assistant**: paste the key and press **Check the key**. Then **Set up the assistant**: the set-up
lists the apps installed here and their records, and per kind of record you choose *not here*, *read*, or *read and
change*. **Save and switch on**, reload, and the chat button appears at the bottom right for the users you chose
(every internal user by default). Until the set-up is done, the assistant does not run.

Ask: *"Which leads above 10,000 are in the pipeline?"*

## What it can do

The module comes with these actions. Each one is offered only when the user may use it.

| Action | What it does | Confirm |
|---|---|---|
| Find records | Searches a model by name and by filters, sorted, with the fields asked for | no |
| Read a record | Reads one record with its main fields | no |
| Describe a model | Lists a model's fields, so the assistant uses the right ones | no |
| Open a record | Gives the user a button to open it | no |
| Create a record | Creates a record; related records by name, lines as a list | **yes** |
| Change a record | Changes fields of one record | **yes** |
| Add a note | An internal note in the chatter; followers are not e-mailed | **yes** |
| Schedule an activity | A to-do, call, meeting or e-mail, for the user or a colleague | **yes** |

The models it may read and the models it may create and change are set under **Settings → Rekhu Assistant**. The
confirm card shows what will happen in the user's words: *Lead: Office chairs · Customer: Acme Corporation · Expected
revenue: 4,500*.

## Your own actions

Mark a model method with `@tool` and the assistant can do that job, as the signed-in user:

```python
from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.rekhu_assistant.tools import tool


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    @tool(
        'Reorders a past sales order: the same products for the same customer, as a new quotation. "order" is its number, such as S00042.',
        input={'order': 'string'},
        groups='sales_team.group_sale_salesman',
        label={'en': 'Reorder', 'nl': 'Opnieuw bestellen', 'ar': 'إعادة الطلب'},
    )
    def rekhu_reorder(self, order):
        source = self.search([('name', '=', order.strip().upper())], limit=1)
        if not source:
            raise UserError(_('There is no order %s.', order))
        new = source.copy({'origin': source.name})
        return {'message': _('Quotation %s is ready.', new.name), 'record': new}
```

| Option | |
|---|---|
| `description` | What it does and when to use it, for the assistant. Be specific. |
| `input` | The arguments: `{'order': 'string', 'quantity': 'integer?', 'size': ['s', 'm', 'l']}`, or a JSON Schema. The input is checked before your method runs. |
| `readonly` | It only reads: it runs at once and shows no "done" card. |
| `confirm` | Whether the user confirms first. By default, every action that is not `readonly`. |
| `danger` | The confirm card shows it as destructive. |
| `groups` | Who may use it, as group XML ids, comma separated. Empty: every user of the assistant. |
| `label` | What the user reads for it, a text or one per language. |
| `hidden` | Input fields not shown on the confirm card. |

Return a dict for the assistant: a `message`, and a `record` (a recordset) to give the user a button to open it.
Raise `UserError` or `AccessError` to refuse; the user reads why. The module `rekhu_assistant_example` has a read
action and a change action to copy from.

## Help topics

Under **Settings → Rekhu Assistant → Help topics**, write how things work in your company, one topic each: *How we
handle a return*, *When a quotation needs approval*. The assistant answers how-to questions from them, in the user's
language.

## Security

- **The secret key stays on the Odoo server**, readable by administrators only. The browser talks to Odoo's own chat
  route; Odoo calls Rekhu. Nothing calls into Odoo.
- **Everything runs as the user**, with their access rights and record rules. The assistant cannot see a record the
  user cannot see, and Odoo refuses what the user may not do.
- **Changes wait for a click.** The confirm card shows exactly what will be written; a typed "yes" runs nothing.
- **Fields are checked:** only fields that exist and can be written; never files, ids or technical fields.
- **Conversations stay in Odoo**, per user, and are removed after 14 days. Rekhu meters each call by company and by
  user id, never by name or e-mail.
- **A custom header** (`X-Rekhu-Protocol`) is required on every change, so a page on another site cannot post to the
  chat route.

## Settings

| Setting | |
|---|---|
| Credit | The credit left on the Rekhu account, read when the settings open, with a **Top up** button. |
| Where it works | **Set up the assistant** (or run it again); **The rules** lists and edits what it may read and change. |
| Rekhu Assistant | On or off; the set-up switches it on. |
| Secret key | `agk_…` from your Rekhu project; **Check the key** tests it. |
| Who gets the assistant | A group; empty is every internal user. |
| Name, greeting, quick questions | The chat's title, its first message, and questions to start with (separated by `|`). |
| Your own rules | How the assistant works in your company, in a sentence or two. |
| Model, Rekhu address | Leave these as they are unless Rekhu tells you otherwise. |

## Usage and limits

Your Rekhu account shows the project's usage per Odoo company and per month, with a CSV. Set a monthly limit and pause
the assistant on the project's **Assistant** tab. At the limit, or paused, the chat tells users it is not available
right now.

## Development

Run the tests in any Odoo of this branch's version with the module on its addons path:

```bash
odoo -d rekhu_test -i rekhu_assistant --test-tags /rekhu_assistant --stop-after-init
```

The tests replace the Rekhu platform with a stand-in, so they need no key and use no credit. An example of your own
actions with `@tool` is in [examples/rekhu_assistant_example](examples/rekhu_assistant_example).

## License

Licensed, not sold, to holders of a Rekhu account; see [LICENSE](LICENSE).
