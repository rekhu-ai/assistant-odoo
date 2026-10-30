# Changelog

All notable changes to Rekhu Assistant for Odoo. The version in each Odoo branch is the series followed by this
version: 17.0.1.0.0, 18.0.1.0.0, 19.0.1.0.0 and 20.0.1.0.0 are all 1.0.0.

## 1.0.5

- **Long requests finish instead of breaking the chat.** An answer cut off at its length (a request for dozens of files at once) runs none of its half-written actions; the assistant is told and goes on in smaller steps in the same turn. Before, the cut-off answer was stored as it was, and the model refused every next message in that conversation.
- **Stuck conversations go on.** A conversation stored with an action and no result for it is sent to the model without that action, so a chat that broke this way works again after the update.
- **When one answer's steps run out**, the user reads where it stopped and how to go on (say "continue", or ask for a few at a time) instead of an empty answer.
- **The user reads what a failure means for them:** try again in a minute (the model is busy), let the administrator of this app know (paused, at its monthly limit, or the plan needs attention), or start a new chat (the conversation was refused). The log says the technical reason, as before. In English, Arabic and Dutch.
- One answer may be 16000 tokens long (was 4000), so longer answers are no longer cut off.

## 1.0.4

- **Models by name.** The Model setting takes a model's name as your Rekhu account lists it, and is empty by default: the assistant then answers with the account's default model.

## 1.0.3

- **Odoo 20.** The module now works on Odoo 20 as well: the 20.0 branch keeps its access rights in `ir.access`, the model Odoo 20 uses, and settings are read and written with Odoo 20's typed methods (`get_str`, `set_str`) where they exist.
- The requirements say where it runs: on your own server or Odoo.sh, not on Odoo Online, which takes no modules of its own or from the Apps store.

## 1.0.2

- **Start free.** The README and the store page say how to begin: [create a Rekhu account](https://rekhu.com/register?ref=assistant-odoo) and it starts with $10 credit, no card needed.
- The key setting and the message for a missing key say where to get one, with a link to sign-up.

## 1.0.1

- **Credit in the settings.** Settings → Rekhu Assistant opens with the credit left on the Rekhu account and a Top up button.
- **Tables in the chat.** An answer that lists records in a table now reads as a table.
- **Confirm without asking twice.** A change goes straight to its confirm card; the assistant no longer asks "shall I go ahead?" first.
- **Amounts as you read them.** Amounts on a confirm card show with the company's currency and thousands separators.
- **One button per record.** A record just created or changed is not offered a second time with another Open button.
- **Plain words.** The assistant names kinds of records as users know them (invoices, quotations), never by their technical name.
- The store page, with screenshots and a banner.

## 1.0.0

The first release, for Odoo 17, 18 and 19.

- A chat in the Odoo back office for internal users, speaking protocol 1 with the Rekhu widget.
- Actions that come with the module: find records, read a record, describe a model, open a record, create and change
  records, add an internal note, schedule an activity (to-do, call, meeting or e-mail). Every change waits for a click on
  Confirm; everything runs with the user's own access rights and record rules.
- Your own actions: `@tool` on a model method, with its input, its groups and a label per language.
- Odoo's menus as pages the assistant can open; help topics the company writes, answered from in the user's language.
- Settings: the secret key with a check, who gets the assistant, the models it may read and change, name, greeting,
  quick questions and the company's own rules.
- Usage metered per Odoo company in the Rekhu account; conversations kept 14 days on the Odoo server.
