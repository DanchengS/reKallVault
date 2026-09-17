---
name: resume
description: Generate a résumé tailored to one job description from the user's local vault — match vault material to the JD, let the user pick what goes in, polish bullets, and render an HTML résumé where every bullet traces to a real vault item. Use when the user pastes or points at a JD/job posting and wants a résumé or CV for it, asks "tailor my résumé for this role", "which of my experience fits this job", or "what am I missing for this JD".
---

# Tailored résumé from the vault

Three steps, in order: **match → select → tailor+render**. The model decides *what to say*;
scripts decide *what's allowed* and *what it looks like*. Never write résumé HTML yourself.

**Data directory:** run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py home` once at the start and use the printed path wherever this file says `~/.rekall-vault` (it honours `$REKALL_VAULT_HOME`).

Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/vault.py`, `${CLAUDE_PLUGIN_ROOT}/scripts/render.py`
(always `python3`).

## 0. Inputs

- **Vault:** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py view --ids --full`. If there is no
  vault, or it has no contributions, stop: send the user to `/rekall-vault:profile` (import a
  résumé) or `/rekall-vault:interview` — there is nothing to tailor yet.
- **JD:** pasted text, or a file/URL the user points at (read it). If you only have a title
  and no description, ask for the posting — matching against a title alone is guesswork.
- **Today's date:** from your context; needed for certification expiry.

Make a working folder `~/.rekall-vault/out/<company>-<role>-<YYYYMMDD>/` (lowercase, hyphens)
and save the JD there as `jd.md`.

## 1. Match

Read `${CLAUDE_PLUGIN_ROOT}/skills/resume/references/match.md` and apply it to the vault
snapshot + JD. Write the result to `<folder>/match.json`.

Show the user, compactly:

1. The parsed JD (role, seniority, required skills, key responsibilities) — one short block,
   so they can correct a misread.
2. Contributions by tier — STRONG, then MODERATE, then WEAK — each as
   `[id] Company · Role — name — one-line rationale`, with `(thin)` where flagged.
3. Credentials recommended / not, one line each.
4. Gaps, HARD first. These are for the user's eyes; they never get papered over in the résumé.

## 2. Select

Propose a default selection: all STRONG + MODERATE contributions, recommended credentials,
and every education entry. Ask the user to adjust — add a WEAK item they care about, drop a
MODERATE one, exclude a `(thin)` item they'd rather firm up first. Keep it to one exchange
unless they want to iterate.

Write the final selection to `<folder>/selected.json` as `{"ids": ["c_…", "ed_…", "ct_…", "p_…"]}`.

## 3. Tailor

Read `${CLAUDE_PLUGIN_ROOT}/skills/resume/references/tailor.md`. Build its input from the
vault snapshot and `match.json`:

- `<job>` — the parsed JD block, plus a line `Output language: <language>` (the JD's language,
  or what the user chose).
- `<selected_experience>` — for each selected contribution, grouped under its company/role:
  the `[contributionId: …]`, what / ownership / scope / tech / impact, plus its
  `matchedRequirements` and `rationale` from the match.
- `<skill_candidates>` — the vault's skills **plus** every tech named in a selected
  contribution's `techStack`. Nothing else may appear in the skills section.

Produce the tailoring JSON and write it to `<folder>/tailoring.json`. Then:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py assemble \
  --selected <folder>/selected.json --tailoring <folder>/tailoring.json --out <folder>/content.json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render.py <folder>/content.json -o <folder>/resume.html
```

`assemble` is the anti-hallucination gate: one bullet per selected contribution, no extra
ids, no skill that isn't grounded in the vault. If it rejects the tailoring, fix exactly what it
names in `tailoring.json` and re-run — do not loosen the selection to make it pass.

## 4. Hand over

Tell the user the path to `resume.html`, that it opens in any browser, and that
**File → Print → Save as PDF** gives a PDF. Then offer, briefly:

- reword a specific bullet (edit `tailoring.json`, re-run assemble + render — never edit
  `content.json` or the HTML by hand)
- revisit the gaps: which ones an interview could turn into real vault material
  (`/rekall-vault:interview`), and which are genuinely missing

## Rules

- **Language.** Talk to the user in their language. The résumé itself is written in the
  **JD's language** unless the user says otherwise — a Chinese vault + an English JD yields an
  English résumé. Say which language you're generating in before the tailor step so they can
  override in one word.
- Every bullet traces to a contribution the user confirmed. If the JD wants something the
  vault doesn't have, it stays a gap — it does not become a bullet.
- Don't restructure the user's history to fit the JD. Selection is the tailoring lever;
  the facts don't move.
- One JD, one folder, one résumé. A new JD starts at step 0.
