#!/usr/bin/env python3
"""
vault.py — deterministic side of the rekall-vault plugin.

Everything that must be *exactly right* lives here rather than in a prompt:
id generation, schema validation, applying confirmed proposals, and the
anti-hallucination check that every résumé bullet points at a real contribution.

Standard library only. Python 3.9+.

Usage:
  vault.py init <extraction.json> [--force]      seed a new vault from a parsed résumé
  vault.py init --empty --name N --email E        start an empty vault
  vault.py view [--ids] [--full]                  readable snapshot (ids for machines, --full adds edu/certs/patents)
  vault.py validate [--assign-ids]                check the vault file; optionally fill in missing ids
  vault.py add-employment --company C [--start YYYY-MM] [--end YYYY-MM]
  vault.py add-role <employmentId> --title T [--level L] [--start YYYY-MM] [--end YYYY-MM]
  vault.py apply <proposals.json>                 file confirmed interview proposals into the vault
  vault.py assemble --selected <ids.json> --tailoring <tailoring.json> --out <content.json>
                                                  validate bullets against the vault and build render input

All commands accept --vault <path>; default is $REKALL_VAULT_HOME/vault.json, or ~/.rekall-vault/vault.json.
Exit code 0 on success, 1 on a validation failure (message on stderr).
"""

import argparse
import json
import os
import secrets
import sys

VAULT_HOME = os.environ.get("REKALL_VAULT_HOME") or os.path.expanduser("~/.rekall-vault")
DEFAULT_VAULT = os.path.join(VAULT_HOME, "vault.json")
CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "NA"}
PREFIX = {"employment": "e", "role": "r", "contribution": "c",
          "education": "ed", "certification": "ct", "patent": "p"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def fail(msg):
    sys.stderr.write("ERROR: " + msg + "\n")
    sys.exit(1)


def new_id(kind, taken):
    while True:
        cand = PREFIX[kind] + "_" + secrets.token_hex(2)
        if cand not in taken:
            taken.add(cand)
            return cand


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        fail(f"file not found: {path}")
    except json.JSONDecodeError as e:
        fail(f"{path} is not valid JSON: {e}")


def save_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_vault(path):
    if not os.path.exists(path):
        fail(f"no vault at {path} — run `vault.py init` first")
    v = load_json(path)
    errs = validate_vault(v)
    if errs:
        fail("vault is invalid:\n  " + "\n  ".join(errs) + "\n(run `vault.py validate --assign-ids` if ids are missing)")
    return v


def empty_vault(name=None, email=None):
    return {
        "version": 1,
        "header": {"name": name, "email": email, "phone": None, "location": None, "links": []},
        "careerSummary": None,
        "skills": [],
        "employments": [],
        "educations": [],
        "certifications": [],
        "patents": [],
    }


def fmt_month(s):
    """'2019-03' / '2019-03-15' / '2019' -> 'Mar 2019'; None -> 'Present'."""
    if not s:
        return "Present"
    parts = str(s).split("-")
    try:
        y = int(parts[0])
        if len(parts) >= 2:
            return f"{MONTHS[int(parts[1]) - 1]} {y}"
        return str(y)
    except (ValueError, IndexError):
        return str(s)


def date_range(start, end):
    if not start and not end:
        return ""
    return f"{fmt_month(start)} – {fmt_month(end)}"


def sort_key_desc(start):
    # newest first; unknown start sinks to the bottom
    return start or "0000"


def all_ids(v):
    ids = set()
    for e in v.get("employments", []):
        ids.add(e.get("id"))
        for r in e.get("roles", []):
            ids.add(r.get("id"))
            for c in r.get("contributions", []):
                ids.add(c.get("id"))
    for k in ("educations", "certifications", "patents"):
        for x in v.get(k, []):
            ids.add(x.get("id"))
    ids.discard(None)
    return ids


# ----------------------------------------------------------------------------
# validation
# ----------------------------------------------------------------------------

def validate_vault(v, assign_ids=False):
    """Return a list of error strings. With assign_ids=True, fill in missing ids in place."""
    errs = []
    if not isinstance(v, dict):
        return ["vault root must be an object"]
    for key in ("header", "skills", "employments", "educations", "certifications", "patents"):
        if key not in v:
            errs.append(f"missing top-level key '{key}'")
    if errs:
        return errs

    taken = all_ids(v)
    seen = set()

    def check_id(obj, kind, where):
        cid = obj.get("id")
        if not cid:
            if assign_ids:
                obj["id"] = new_id(kind, taken)
                return
            errs.append(f"{where}: missing id")
            return
        if cid in seen:
            errs.append(f"{where}: duplicate id {cid}")
        seen.add(cid)

    if not isinstance(v["header"], dict) or not v["header"].get("name"):
        errs.append("header.name is required")

    for i, s in enumerate(v["skills"]):
        if not isinstance(s, dict) or not s.get("name"):
            errs.append(f"skills[{i}]: needs a name")

    for i, e in enumerate(v["employments"]):
        where = f"employments[{i}]"
        if not e.get("company"):
            errs.append(f"{where}: company is required")
        check_id(e, "employment", where)
        e.setdefault("roles", [])
        for j, r in enumerate(e["roles"]):
            rw = f"{where}.roles[{j}]"
            if not r.get("title"):
                errs.append(f"{rw}: title is required")
            check_id(r, "role", rw)
            r.setdefault("contributions", [])
            for k, c in enumerate(r["contributions"]):
                cw = f"{rw}.contributions[{k}]"
                if not c.get("name"):
                    errs.append(f"{cw}: name is required")
                check_id(c, "contribution", cw)
                conf = c.get("confidence") or "NA"
                if conf not in CONFIDENCE:
                    errs.append(f"{cw}: confidence must be one of {sorted(CONFIDENCE)}")
                c["confidence"] = conf
                c.setdefault("techStack", [])
                if not isinstance(c["techStack"], list):
                    errs.append(f"{cw}: techStack must be a list")

    for i, x in enumerate(v["educations"]):
        if not x.get("school"):
            errs.append(f"educations[{i}]: school is required")
        check_id(x, "education", f"educations[{i}]")
    for i, x in enumerate(v["certifications"]):
        if not x.get("name"):
            errs.append(f"certifications[{i}]: name is required")
        check_id(x, "certification", f"certifications[{i}]")
    for i, x in enumerate(v["patents"]):
        if not x.get("title"):
            errs.append(f"patents[{i}]: title is required")
        check_id(x, "patent", f"patents[{i}]")
    return errs


# ----------------------------------------------------------------------------
# view
# ----------------------------------------------------------------------------

def render_view(v, ids=False, full=False):
    out = []
    h = v["header"]
    contact = ", ".join(x for x in (h.get("email"), h.get("phone"), h.get("location")) if x)
    out.append(f"Name: {h.get('name')}" + (f"  ({contact})" if contact else ""))
    if v.get("careerSummary"):
        out.append("")
        out.append("Career summary: " + v["careerSummary"].strip())
    if v["skills"]:
        out.append("")
        out.append("Skills: " + ", ".join(
            f"{s['name']} ({s['proficiency']})" if s.get("proficiency") else s["name"]
            for s in v["skills"]))

    emps = sorted(v["employments"], key=lambda e: sort_key_desc(e.get("start")), reverse=True)
    for e in emps:
        out.append("")
        line = f"Company: {e['company']} ({date_range(e.get('start'), e.get('end'))})"
        if ids:
            line += f"  [employmentId: {e['id']}]"
        out.append(line)
        roles = sorted(e["roles"], key=lambda r: sort_key_desc(r.get("start")), reverse=True)
        for r in roles:
            line = f"  Role: {r['title']}"
            if r.get("level"):
                line += f" · {r['level']}"
            if r.get("start") or r.get("end"):
                line += f" ({date_range(r.get('start'), r.get('end'))})"
            if ids:
                line += f"  [roleId: {r['id']}]"
            out.append(line)
            if not r["contributions"]:
                out.append("    (no contributions on record yet)")
            for c in r["contributions"]:
                tag = f"[{c.get('confidence', 'NA')}]"
                line = f"    - {tag} {c['name']}"
                if ids:
                    line += f"  [contributionId: {c['id']}]"
                out.append(line)
                for label, key in (("what", "description"), ("ownership", "ownership"),
                                   ("scope", "scope"), ("impact", "impact")):
                    if c.get(key):
                        out.append(f"        {label}: {c[key]}")
                if c.get("techStack"):
                    out.append(f"        tech: {', '.join(c['techStack'])}")

    if full:
        if v["educations"]:
            out.append("")
            out.append("Education:")
            for x in v["educations"]:
                bits = " ".join(b for b in (x.get("degree"), x.get("field")) if b)
                line = f"  - {bits + ' @ ' if bits else ''}{x['school']} ({date_range(x.get('start'), x.get('end'))})"
                if ids:
                    line += f"  [educationId: {x['id']}]"
                out.append(line)
        if v["certifications"]:
            out.append("")
            out.append("Certifications:")
            for x in v["certifications"]:
                line = f"  - {x['name']}"
                if x.get("issuer"):
                    line += f" — {x['issuer']}"
                if x.get("date"):
                    line += f" ({fmt_month(x['date'])}"
                    line += f", expires {fmt_month(x['expires'])})" if x.get("expires") else ")"
                if ids:
                    line += f"  [certificationId: {x['id']}]"
                out.append(line)
        if v["patents"]:
            out.append("")
            out.append("Patents:")
            for x in v["patents"]:
                line = f"  - {x['title']}"
                if x.get("number"):
                    line += f" ({x['number']})"
                if x.get("date"):
                    line += f" {fmt_month(x['date'])}"
                if ids:
                    line += f"  [patentId: {x['id']}]"
                out.append(line)
    if not emps and not v["skills"] and not v.get("careerSummary"):
        out.append("")
        out.append("(vault is empty — nothing on record yet)")
    return "\n".join(out)


# ----------------------------------------------------------------------------
# init
# ----------------------------------------------------------------------------

def cmd_init(args):
    if os.path.exists(args.vault) and not args.force:
        fail(f"{args.vault} already exists — pass --force to overwrite it")
    if args.empty:
        if not args.name:
            fail("--empty needs --name")
        v = empty_vault(args.name, args.email)
    else:
        if not args.source:
            fail("init needs an extraction JSON path, or --empty")
        src = load_json(args.source)
        v = empty_vault()
        hdr = src.get("header") or {}
        v["header"] = {
            "name": hdr.get("name") or args.name,
            "email": hdr.get("email") or args.email,
            "phone": hdr.get("phone"),
            "location": hdr.get("location"),
            "links": hdr.get("links") or [],
        }
        v["careerSummary"] = src.get("careerSummary")
        v["skills"] = [{"name": s["name"], "category": s.get("category"), "proficiency": s.get("proficiency")}
                       for s in src.get("skills", []) if s.get("name")]
        for e in src.get("employments", []):
            emp = {"id": None, "company": e.get("company"), "location": e.get("location"),
                   "start": e.get("start"), "end": e.get("end"), "roles": []}
            for r in e.get("roles", []):
                role = {"id": None, "title": r.get("title"), "level": r.get("level"),
                        "start": r.get("start"), "end": r.get("end"), "contributions": []}
                for c in r.get("contributions", []):
                    role["contributions"].append(_contribution(c))
                emp["roles"].append(role)
            v["employments"].append(emp)
        for x in src.get("educations", []):
            v["educations"].append({"id": None, "school": x.get("school"), "degree": x.get("degree"),
                                    "field": x.get("field"), "start": x.get("start"), "end": x.get("end"),
                                    "details": x.get("details")})
        for x in src.get("certifications", []):
            v["certifications"].append({"id": None, "name": x.get("name"), "issuer": x.get("issuer"),
                                        "date": x.get("date"), "expires": x.get("expires")})
        for x in src.get("patents", []):
            v["patents"].append({"id": None, "title": x.get("title"), "number": x.get("number"),
                                 "date": x.get("date"), "description": x.get("description")})
    errs = validate_vault(v, assign_ids=True)
    if errs:
        fail("extraction could not be turned into a valid vault:\n  " + "\n  ".join(errs))
    save_json(args.vault, v)
    print(f"vault written to {args.vault}")
    print(render_view(v, full=True))


def _contribution(c, cid=None):
    return {
        "id": cid,
        "name": c.get("name"),
        "description": c.get("description"),
        "ownership": c.get("ownership"),
        "scope": c.get("scope"),
        "techStack": list(c.get("techStack") or []),
        "impact": c.get("impact"),
        "confidence": c.get("confidence") or "NA",
        "evidence": c.get("evidence"),
    }


# ----------------------------------------------------------------------------
# structure edits
# ----------------------------------------------------------------------------

def cmd_add_employment(args):
    v = load_vault(args.vault)
    emp = {"id": new_id("employment", all_ids(v)), "company": args.company, "location": args.location,
           "start": args.start, "end": args.end, "roles": []}
    v["employments"].append(emp)
    save_json(args.vault, v)
    print(emp["id"])


def cmd_add_role(args):
    v = load_vault(args.vault)
    for e in v["employments"]:
        if e["id"] == args.employment_id:
            role = {"id": new_id("role", all_ids(v)), "title": args.title, "level": args.level,
                    "start": args.start, "end": args.end, "contributions": []}
            e["roles"].append(role)
            save_json(args.vault, v)
            print(role["id"])
            return
    fail(f"no employment with id {args.employment_id}")


# ----------------------------------------------------------------------------
# apply proposals
# ----------------------------------------------------------------------------

def cmd_apply(args):
    """
    proposals.json shape (only *confirmed* proposals belong here):
    {
      "contributions": [
        { ...contribution fields..., "targetRoleId": "r_xxxx",
          "replacesContributionId": "c_xxxx" | null }
      ],
      "educations": [...], "certifications": [...], "patents": [...]   # optional, volunteered facts
    }
    """
    v = load_vault(args.vault)
    p = load_json(args.source)
    roles = {}
    contribs = {}
    for e in v["employments"]:
        for r in e["roles"]:
            roles[r["id"]] = r
            for c in r["contributions"]:
                contribs[c["id"]] = (r, c)

    errs = []
    for i, c in enumerate(p.get("contributions", [])):
        if not c.get("name"):
            errs.append(f"contributions[{i}]: name is required")
        if not c.get("targetRoleId"):
            errs.append(f"contributions[{i}] ({c.get('name')}): targetRoleId is required — unassigned proposals must be filed before apply")
        elif c["targetRoleId"] not in roles:
            errs.append(f"contributions[{i}] ({c.get('name')}): targetRoleId {c['targetRoleId']} does not exist")
        rep = c.get("replacesContributionId")
        if rep and rep not in contribs:
            errs.append(f"contributions[{i}] ({c.get('name')}): replacesContributionId {rep} does not exist")
        if (c.get("confidence") or "NA") not in CONFIDENCE:
            errs.append(f"contributions[{i}]: bad confidence {c.get('confidence')}")
    if errs:
        fail("proposals rejected:\n  " + "\n  ".join(errs))

    added = replaced = 0
    taken = all_ids(v)
    for c in p.get("contributions", []):
        rep = c.get("replacesContributionId")
        if rep:
            old_role, old = contribs[rep]
            new = _contribution(c, cid=rep)
            idx = old_role["contributions"].index(old)
            if old_role["id"] == c["targetRoleId"]:
                old_role["contributions"][idx] = new
            else:
                old_role["contributions"].pop(idx)
                roles[c["targetRoleId"]]["contributions"].append(new)
            replaced += 1
        else:
            roles[c["targetRoleId"]]["contributions"].append(_contribution(c, cid=new_id("contribution", taken)))
            added += 1

    facts = 0
    for x in p.get("educations", []):
        v["educations"].append({"id": new_id("education", taken), "school": x.get("school"), "degree": x.get("degree"),
                                "field": x.get("field"), "start": x.get("start"), "end": x.get("end"),
                                "details": x.get("details")})
        facts += 1
    for x in p.get("certifications", []):
        v["certifications"].append({"id": new_id("certification", taken), "name": x.get("name"), "issuer": x.get("issuer"),
                                    "date": x.get("date"), "expires": x.get("expires")})
        facts += 1
    for x in p.get("patents", []):
        v["patents"].append({"id": new_id("patent", taken), "title": x.get("title"), "number": x.get("number"),
                             "date": x.get("date"), "description": x.get("description")})
        facts += 1

    # skills grow with what the user named: any tech in an applied contribution that the
    # skills list doesn't have yet is appended (technical, no proficiency claimed)
    have = {sk["name"].lower() for sk in v["skills"]}
    new_skills = 0
    for c in p.get("contributions", []):
        for tech in c.get("techStack") or []:
            if tech and tech.lower() not in have:
                v["skills"].append({"name": tech, "category": "technical", "proficiency": None})
                have.add(tech.lower())
                new_skills += 1

    errs = validate_vault(v)
    if errs:
        fail("apply produced an invalid vault (not saved):\n  " + "\n  ".join(errs))
    save_json(args.vault, v)
    print(f"applied: {added} new contribution(s), {replaced} replaced, {facts} factual record(s), "
          f"{new_skills} skill(s) added from tech stacks")


# ----------------------------------------------------------------------------
# assemble (check bullets + build render input)
# ----------------------------------------------------------------------------

def cmd_assemble(args):
    """
    selected.json : {"ids": ["c_..", "ed_..", "ct_..", "p_.."]}  (or a bare list)
    tailoring.json: {"summary": str|null, "skills": [{"category", "items": []}],
                     "bullets": [{"contributionId", "text"}]}
    Writes content.json for render.py. Fails loudly on any bullet/skill that isn't grounded.
    """
    v = load_vault(args.vault)
    sel = load_json(args.selected)
    sel_ids = sel["ids"] if isinstance(sel, dict) else sel
    if not isinstance(sel_ids, list) or not sel_ids:
        fail("selected.json must contain a non-empty list of ids")
    t = load_json(args.tailoring)

    # partition the selected ids by type
    known = all_ids(v)
    unknown = [i for i in sel_ids if i not in known]
    if unknown:
        fail("selected ids not in vault: " + ", ".join(unknown))
    sel_set = set(sel_ids)

    # experiences: employment -> role -> selected contributions, newest first
    experiences = []
    selected_contribs = {}
    for e in sorted(v["employments"], key=lambda e: sort_key_desc(e.get("start")), reverse=True):
        for r in sorted(e["roles"], key=lambda r: sort_key_desc(r.get("start")), reverse=True):
            picked = [c for c in r["contributions"] if c["id"] in sel_set]
            if not picked:
                continue
            for c in picked:
                selected_contribs[c["id"]] = c
            experiences.append({
                "company": e["company"],
                "roleTitle": r["title"],
                "location": e.get("location"),
                "dateRange": date_range(r.get("start") or e.get("start"), r.get("end") if r.get("start") else e.get("end")),
                "_ids": [c["id"] for c in picked],
            })

    # bullets: exactly one per selected contribution, none extra
    bullets = t.get("bullets") or []
    errs = []
    by_id = {}
    for b in bullets:
        cid = b.get("contributionId")
        if cid not in selected_contribs:
            errs.append(f"bullet references {cid!r}, which is not a selected contribution")
        elif cid in by_id:
            errs.append(f"more than one bullet for {cid}")
        elif not (b.get("text") or "").strip():
            errs.append(f"bullet for {cid} is empty")
        else:
            by_id[cid] = b["text"].strip()
    for cid in selected_contribs:
        if cid not in by_id:
            errs.append(f"no bullet for selected contribution {cid} ({selected_contribs[cid]['name']})")

    # skills: only names that exist in the vault (skills list or a selected contribution's techStack)
    candidates = {s["name"].lower(): s["name"] for s in v["skills"]}
    for c in selected_contribs.values():
        for tech in c.get("techStack") or []:
            candidates.setdefault(tech.lower(), tech)
    skills_out = []
    for g in t.get("skills") or []:
        items = []
        for item in g.get("items") or []:
            canon = candidates.get(str(item).lower())
            if canon is None:
                errs.append(f"skill {item!r} is not in the vault's skill list or any selected contribution's tech stack")
            else:
                items.append(canon)
        if items:
            skills_out.append({"category": g.get("category") or "Skills", "items": items})
    if errs:
        fail("tailoring rejected — fix and re-run:\n  " + "\n  ".join(errs))

    for exp in experiences:
        exp["bullets"] = [{"text": by_id[cid], "sourceContributionId": cid} for cid in exp.pop("_ids")]

    h = v["header"]
    contact_bits = [h.get("phone"), h.get("email"), h.get("location")] + list(h.get("links") or [])
    content = {
        "header": {"name": h["name"], "contactLine": " ⋄ ".join(b for b in contact_bits if b)},
        "summary": (t.get("summary") or None),
        "objective": None,
        "skills": skills_out,
        "experiences": experiences,
        "education": [{"school": x["school"], "degree": x.get("degree"), "field": x.get("field"),
                       "dateRange": date_range(x.get("start"), x.get("end")), "details": x.get("details")}
                      for x in v["educations"] if x["id"] in sel_set],
        "certifications": [{"name": x["name"], "issuer": x.get("issuer"),
                            "date": fmt_month(x["date"]) if x.get("date") else None}
                           for x in v["certifications"] if x["id"] in sel_set],
        "patents": [{"title": x["title"], "id": x.get("number"),
                     "date": fmt_month(x["date"]) if x.get("date") else None}
                    for x in v["patents"] if x["id"] in sel_set],
    }
    save_json(args.out, content)
    print(f"content written to {args.out} — {len(by_id)} bullet(s) across {len(experiences)} role(s), "
          f"{len(content['education'])} education, {len(content['certifications'])} certification(s), "
          f"{len(content['patents'])} patent(s)")


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", default=DEFAULT_VAULT, help="path to vault.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("source", nargs="?")
    p.add_argument("--empty", action="store_true")
    p.add_argument("--name")
    p.add_argument("--email")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("view")
    p.add_argument("--ids", action="store_true")
    p.add_argument("--full", action="store_true")
    p.set_defaults(fn=lambda a: print(render_view(load_vault(a.vault), ids=a.ids, full=a.full)))

    p = sub.add_parser("validate")
    p.add_argument("--assign-ids", action="store_true")
    def _validate(a):
        if not os.path.exists(a.vault):
            fail(f"no vault at {a.vault}")
        v = load_json(a.vault)
        errs = validate_vault(v, assign_ids=a.assign_ids)
        if errs:
            fail("\n  ".join(["vault is invalid:"] + errs))
        if a.assign_ids:
            save_json(a.vault, v)
        print("vault OK")
    p.set_defaults(fn=_validate)

    p = sub.add_parser("add-employment")
    p.add_argument("--company", required=True)
    p.add_argument("--location")
    p.add_argument("--start")
    p.add_argument("--end")
    p.set_defaults(fn=cmd_add_employment)

    p = sub.add_parser("add-role")
    p.add_argument("employment_id")
    p.add_argument("--title", required=True)
    p.add_argument("--level")
    p.add_argument("--start")
    p.add_argument("--end")
    p.set_defaults(fn=cmd_add_role)

    p = sub.add_parser("apply")
    p.add_argument("source")
    p.set_defaults(fn=cmd_apply)

    p = sub.add_parser("assemble")
    p.add_argument("--selected", required=True)
    p.add_argument("--tailoring", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_assemble)

    p = sub.add_parser("home", help="print the data directory in use")
    p.set_defaults(fn=lambda a: print(VAULT_HOME))

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
