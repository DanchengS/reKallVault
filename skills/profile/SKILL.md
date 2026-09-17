---
name: profile
description: Create, inspect, and edit the user's local career vault (~/.rekall-vault/vault.json). Use when the user wants to set up rekall-vault, import or upload an existing résumé/CV (PDF, DOCX, text) to seed their profile, view their vault or career profile, fix or edit an entry (company, role, contribution, skill, education, certification, patent), or asks "what's in my vault". First-run onboarding starts here.
---

# Career vault — set up, view, edit

The vault is one JSON file at `~/.rekall-vault/vault.json`. It holds the user's career as a
tree — employment → role → contribution — plus skills, education, certifications, patents.
Every item has a short id; those ids are what make résumé bullets traceable later.

**Data directory:** run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py home` once at the start and use the printed path wherever this file says `~/.rekall-vault` (it honours `$REKALL_VAULT_HOME`).

Scripts live in this plugin: `${CLAUDE_PLUGIN_ROOT}/scripts/vault.py`. Always call it with
`python3`. It validates everything it writes and exits non-zero with a reason on failure —
read the reason and fix the input rather than working around it.

## Privacy note — say this once, on first run

The vault contains personal data (name, contact, employers). It lives in the user's home
directory, not in any project, and nothing in this plugin sends it anywhere. Tell the user
where the file is and that they should not commit it to a repository.

**Language:** reply in the language the user writes in. Vault entries keep the language of
their source — a résumé imported in Chinese yields Chinese entries; an edit keeps the entry's
existing language unless the user asks to translate.

## Which sub-flow?

| User wants | Do |
|---|---|
| set up / start / import a résumé | **Init from a résumé** |
| start from scratch, no résumé | **Init empty** |
| see the vault / profile | **View** |
| change / fix / add / remove something | **Edit** |

If `vault.py view` fails with "no vault", the user is new — go to init.

## Init from a résumé

1. Read the résumé file with the Read tool (PDF, DOCX, or text all work natively). If the
   user gave no path, ask for one.
2. Read `${CLAUDE_PLUGIN_ROOT}/skills/profile/references/extraction.md` and follow it exactly to
   produce the extraction JSON. Transcribe; never invent. Dates as `YYYY-MM`.
3. Write the JSON to `~/.rekall-vault/import-<YYYYMMDD-HHMMSS>.json`.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py init <that file>`. It assigns ids, writes
   the vault, and prints a readable snapshot. If a vault already exists, **stop and ask** before
   using `--force` — it overwrites everything.
5. Show the user the snapshot and ask them to skim it for anything wrong (a missed job, a
   mangled date, a split role that should be one). Fix via **Edit** below.
6. Point them to the next step: `/rekall-vault:interview` to add depth — the résumé gives
   breadth, but ownership, real numbers and tech stacks come from talking.

## Init empty

Ask for the user's name and email (email optional), then:
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py init --empty --name "<name>" --email "<email>"`.
Then send them to `/rekall-vault:interview` — the interview builds the timeline as it goes.

## View

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py view --full` and show the output. Add `--ids`
only when the user asks for ids or you need them for an edit. Each contribution carries a
confidence tag — `[LOW]`/`[NA]` means thin, not doubted; suggest an interview for those.

## Edit

Two kinds of edit:

- **Structure** (a new employer or role): use the script so ids are minted correctly —
  `vault.py add-employment --company … --start YYYY-MM [--end YYYY-MM]` prints the new
  employment id; `vault.py add-role <employmentId> --title … [--level …] [--start …] [--end …]`
  prints the new role id.
- **Everything else** (fix a date, reword a contribution, add a skill, delete an item, change
  a header field): edit `~/.rekall-vault/vault.json` directly with the Edit tool, keeping the
  existing shape, then run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py validate`. If you
  added an item by hand without an id, run `validate --assign-ids` instead.

Never change an existing id — résumés already generated reference them. Confirm destructive
edits (deleting a role or employment) before doing them.
