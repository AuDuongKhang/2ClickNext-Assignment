# Sales archive: file reference

The export contains exhibitors, contacts, stand enquiries and sales conversations. All data is fictional.

Keep these files unchanged. We replace the whole `data/` folder before review, then run `./reset.sh` and `./dev.sh`. Any conversion belongs in your importer.

## File format

- Encoding: UTF-8 without BOM.
- Delimiter: semicolon (`;`).
- Line endings: LF.
- Empty fields mean unknown or unavailable. There are no `NULL`, `N/A` or zero placeholders.
- Dates use `DD/MM/YYYY`.
- Date-times use `DD/MM/YYYY HH:mm` and should be interpreted in `Europe/Rome`.
- Monetary values are EUR and use a decimal comma with exactly two decimal places, for example `12500,00`.
- Areas are square metres and heights are metres, also with a decimal comma. An empty size, height or budget is unknown, not zero or an approval.
- Archive reference time: `2026-09-01 09:00 Europe/Rome`.

## `companies_and_contacts.csv`

There is one row per contact. Company details repeat when an exhibitor has several contacts.

| Column | Meaning |
|---|---|
| `legacy_row_id` | Unique source-export row identifier |
| `company_code` | Stable legacy company identifier |
| `company_name` | Display/legal name; names are not unique |
| `province_code` | Two-letter legacy location code |
| `region` | Region label |
| `sales_rep` | Legacy account owner name |
| `contact_code` | Stable legacy contact identifier |
| `contact_first_name`, `contact_last_name` | Contact name |
| `email`, `phone`, `fax` | Contact details; values may be empty |
| `legacy_print_layout` | Obsolete presentation metadata from the previous system |

Company and contact codes identify records. Company names are not unique.

## `opportunities.csv`

Each row is an opportunity for a stand at one fair edition. An exhibitor can have several opportunities, including different editions of the same fair.

| Column | Meaning |
|---|---|
| `opportunity_code` | Stable legacy opportunity identifier |
| `company_code` | Owning company |
| `contact_code` | Primary contact when known; may be empty |
| `description` | Short description of the proposed work |
| `amount_eur` | Sales team's recorded opportunity value in EUR, excluding VAT; not a calculated stand price or a confirmed customer budget |
| `legacy_status` | Status as exported; casing and surrounding whitespace are not fully consistent |
| `opened_on` | Opportunity opening date |
| `expected_close_on` | Expected close date when available |
| `historical_campaign_code` | Historical campaign attribution when available |
| `fair_edition_code` | Edition identifier from `fair_editions.csv` |
| `stand_area_sqm` | Allocated plot area, when known |
| `client_budget_eur` | Customer's stated stand budget, excluding VAT, when known; may differ from the opportunity value |
| `requested_height_m` | Height requested by the customer, not an approved height |
| `brief_notes` | Sales notes about the requested stand and outstanding information |

Status spelling varies in case and whitespace; for example, `Open` and ` open ` have the same meaning.

Commercial status doesn't record technical approval. A requested height may exceed the edition's limit: keep both values. Expected close dates refer to the sales decision. The archive includes past editions and early enquiries for future ones.

## `fair_editions.csv`

There are sixteen editions of four fairs, from 2024 to 2027.

| Column | Meaning |
|---|---|
| `fair_edition_code` | Stable identifier of this edition |
| `fair_name` | Name repeated across editions |
| `city`, `venue` | Edition location |
| `starts_on`, `ends_on` | First and last exhibition day |
| `max_stand_height_m` | Maximum stand height for the edition; no exceptions are recorded |

## `activity_log.csv`

Each row is a log entry, attached either to the company or to a particular opportunity.

| Column | Meaning |
|---|---|
| `entry_id` | Stable log-entry identifier |
| `company_code` | Related company |
| `opportunity_code` | Related opportunity when applicable; may be empty |
| `activity_type` | `call`, `email`, `meeting`, `note`, or `task` |
| `occurred_at` | When the entry occurred or was created |
| `details` | Free-text summary |
| `follow_up_on` | Requested follow-up date when one exists |
| `completion_marker` | `Y` for completed interactions, `N` for pending tasks, or empty when not applicable |
| `legacy_author` | Legacy username of the person who created the entry |

A completed `call`, `email` or `meeting` records customer contact. A `note` is internal; a `task` is work still to do.

## Manifest

`manifest.json` lists the record counts and SHA-256 checksums of the source files.
