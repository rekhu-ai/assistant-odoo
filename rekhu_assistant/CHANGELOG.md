# Changelog

All notable changes to Rekhu Assistant for Odoo. The version in each Odoo branch is the series followed by this
version: 17.0.1.0.0, 18.0.1.0.0 and 19.0.1.0.0 are all 1.0.0.

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
