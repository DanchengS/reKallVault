# reKallVault

**Rebuild your career from what actually happened — then generate résumés that can survive an interview.**

A [Claude Code](https://claude.com/claude-code) plugin. It interviews you like a senior hiring
reviewer, keeps what you said as a structured, evidence-backed **vault** on your own machine, and
turns that vault plus a job description into a tailored résumé where every bullet traces back to
something you actually did.

No accounts, no servers, no uploads. One JSON file in your home directory.

---

## Why

Most résumé tools start from your old résumé and make it sound better. That produces bullets you
can't defend in the room.

reKallVault starts from a *conversation*. The interviewer probes the things a hiring manager
would probe — how big, what did *you* own, what changed after, what was the stack — and files only
what you said, with the quote that backs it. When you later generate a résumé for a specific job,
the model is only allowed to polish those facts; it cannot invent a metric, a technology, or a
responsibility. A script checks.

## How it works

```
 /rekall-vault:profile  ─┐
   import your résumé    │      ┌──────────────┐
   (breadth: timeline)   ├────► │  your vault  │ ◄──── /rekall-vault:interview
                         │      │  vault.json  │       a real conversation
                         ┘      └──────┬───────┘       (depth: ownership, numbers, stack)
                                       │
                          paste a JD ──┤
                                       ▼
                          /rekall-vault:resume
                          match → you pick → polish → resume.html
```

Three skills, one shared file:

| Command | What it does |
|---|---|
| `/rekall-vault:profile` | Set up the vault — import an existing résumé (PDF/DOCX/text) or start empty. View and edit it. |
| `/rekall-vault:interview` | A guided conversation about your work. Ends with a review of proposed entries before anything is saved. |
| `/rekall-vault:resume` | Give it a job description. It shows what in your vault matches (and what's missing), you pick, it writes and renders an HTML résumé. |

## Install

Requires [Claude Code](https://claude.com/claude-code) and Python 3.9+ (standard library only —
nothing to `pip install`). No marketplace, no registration: clone and it works.

**Recommended — clone into Claude Code's skills folder.** Every plugin directory under
`~/.claude/skills/` is loaded automatically in every session:

```bash
git clone https://github.com/DanchengS/reKallVault.git ~/.claude/skills/reKallVault
```

Start a new `claude` session anywhere and `/rekall-vault:profile`, `/rekall-vault:interview`,
`/rekall-vault:resume` are available. Update later with `git pull` in that folder; remove by
deleting it.

**Try it once — load for a single session:**

```bash
git clone https://github.com/DanchengS/reKallVault.git
claude --plugin-dir ./reKallVault
```

## Quick start

**1. Seed the vault** (5 minutes)

```
/rekall-vault:profile import ~/Documents/my-resume.pdf
```

Claude reads the PDF, transcribes it into the vault (companies → roles → contributions, plus
skills, education, certifications, patents) and shows you the result. Fix anything it misread.
No résumé? `/rekall-vault:profile` and say you want to start empty.

**2. Add depth** (20–40 minutes, repeatable)

```
/rekall-vault:interview
```

The interviewer opens with whatever looks thinnest in your vault and works upward. Expect
questions like *"Which part of it did you personally build or decide?"* and *"Order of magnitude
is fine — how many events a second?"*. One question at a time. Say "done" whenever you like.

You then review every proposed entry — accept, edit, file under the right role, or drop — before
it's written. Nothing enters the vault unseen.

**3. Generate a résumé** (2 minutes per job)

```
/rekall-vault:resume
```

Paste the job description. You'll see:

- which of your contributions are **STRONG / MODERATE / WEAK** matches and why
- which certifications and patents are worth including
- **gaps** — what the JD asks for that your vault can't show (these are for you; they never get
  papered over)

Adjust the selection, and it renders `resume.html`. Open it in a browser; *File → Print → Save as
PDF* if you need a PDF.

## Where your data lives

```
~/.rekall-vault/
├── vault.json                    your career, structured (the only thing that matters)
├── import-<timestamp>.json       raw extraction from a résumé import
├── sessions/
│   ├── <timestamp>.md            interview transcripts
│   ├── <timestamp>.proposals.json
│   └── <timestamp>.confirmed.json
└── out/<company>-<role>-<date>/
    ├── jd.md · match.json · selected.json · tailoring.json · content.json
    └── resume.html
```

Set `REKALL_VAULT_HOME=/some/dir` to use a different location (or keep several vaults).

Everything is plain text. Back it up, version it, `grep` it, edit `vault.json` by hand — just run
`python3 scripts/vault.py validate` afterwards. **Don't commit it to a public repo**; it's your
personal data.

## The vault, briefly

```
employment (company, dates)
└── role (title, level, dates)
    └── contribution
        ├── name, description        what
        ├── ownership                 who — "Tech lead", "Contributor — owned the ingestion slice"
        ├── scope                     how big — team size, QPS, data volume
        ├── impact                    so what — before/after, numbers
        ├── techStack                 only what you named
        ├── confidence                HIGH / MEDIUM / LOW — richness, not doubt
        └── evidence                  the quote it came from
```

`confidence` measures how résumé-ready an entry is, not whether it's believed. A `LOW` line
means *"thin — one conversation would make this shine"*, and that's where the interviewer starts.

Every item has a short id (`c_7aad`). When a résumé is generated, each bullet carries the id of
the contribution it was written from (`data-source` in the HTML), and `vault.py assemble` refuses
to render a bullet whose id isn't in your selection, or a skill that isn't in your vault.

> 🌐 看到这里已经觉得麻烦了？那别折腾了，直接用网页版 [**Rekall**](https://rekall.up.railway.app/?invite=2B-4W8FCPKT)。
> 同一套东西，功能还多一些（语音访谈、PDF 导出、投递追踪），什么都不用装。
> 链接里的邀请码有次数和有效期限制。先到先得。失效了？[开个 Issue](https://github.com/DanchengS/reKallVault/issues/new?title=Invite%20code%20exhausted) 踢我一下。

## Design principles

- **The model decides what to say; scripts decide what's allowed.** Ids, validation, filing,
  and rendering are deterministic Python. Prompts never emit HTML.
- **Never invent.** Extraction and tailoring are forbidden from adding facts. Gaps stay gaps.
- **Nothing is saved without you seeing it.** Interview output is a proposal until you confirm.
- **Selection is the tailoring lever.** A résumé for a different job picks different facts; the
  facts themselves don't move.

## License

[Apache-2.0](./LICENSE). The classic template is a CSS translation of Trey Hunner's
`resume.cls` (MIT — see `templates/classic/NOTICE.md`).
