#!/usr/bin/env python3
"""
render.py — turn content.json (from `vault.py assemble`) into a single self-contained HTML file.

The model never writes HTML. It writes *content*; this script decides what it looks like.
Open the output in a browser and print to PDF if you need one.

Standard library only.

Usage:
  render.py <content.json> -o <resume.html> [--template classic]
"""

import argparse
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(os.path.dirname(HERE), "templates")


def esc(s):
    return html.escape(str(s), quote=True) if s is not None else ""


def nonempty(x):
    return x is not None and str(x).strip() != ""


def render(content, css):
    out = []
    w = out.append
    h = content.get("header") or {}

    w("<!DOCTYPE html>")
    w('<html lang="en"><head><meta charset="utf-8"/>')
    w(f"<title>{esc(h.get('name') or 'Résumé')}</title>")
    w(f"<style>\n{css}\n</style></head><body><div class=\"page\">")

    # header
    w(f'<div class="name">{esc(h.get("name"))}</div>')
    if nonempty(h.get("contactLine")):
        w(f'<div class="contact">{esc(h["contactLine"])}</div>')
    if nonempty(content.get("objective")):
        w(f'<div class="tagline">{esc(content["objective"])}</div>')

    # summary
    if nonempty(content.get("summary")):
        w('<div class="section"><h2>Summary</h2>')
        w(f"<p>{esc(content['summary'])}</p></div>")

    # experience
    exps = content.get("experiences") or []
    if exps:
        w('<div class="section"><h2>Experience</h2>')
        for e in exps:
            w('<div class="entry">')
            w('<table class="entry-row"><tr>')
            w(f'<td class="left title">{esc(e.get("roleTitle"))}</td>')
            w(f'<td class="right">{esc(e.get("dateRange"))}</td>')
            w("</tr></table>")
            sub = e.get("company") or ""
            if nonempty(e.get("location")):
                sub = f"{sub}, {e['location']}"
            w(f'<div class="sub">{esc(sub)}</div>')
            bullets = e.get("bullets") or []
            if bullets:
                w('<ul class="bullets">')
                for b in bullets:
                    src = b.get("sourceContributionId")
                    attr = f' data-source="{esc(src)}"' if src else ""
                    w(f"<li{attr}>{esc(b.get('text'))}</li>")
                w("</ul>")
            w("</div>")
        w("</div>")

    # education
    edu = content.get("education") or []
    if edu:
        w('<div class="section"><h2>Education</h2>')
        for x in edu:
            title = " ".join(p for p in (x.get("degree"), x.get("field")) if nonempty(p))
            title = f"{title} @ {x.get('school')}" if title else (x.get("school") or "")
            w('<div class="entry"><table class="entry-row"><tr>')
            w(f'<td class="left title">{esc(title)}</td>')
            w(f'<td class="right">{esc(x.get("dateRange"))}</td>')
            w("</tr></table>")
            if nonempty(x.get("details")):
                w(f'<div class="edu-details">{esc(x["details"])}</div>')
            w("</div>")
        w("</div>")

    # skills
    skills = content.get("skills") or []
    if skills:
        w('<div class="section"><h2>Skills</h2><table class="skills">')
        for g in skills:
            w(f'<tr><td class="cat">{esc(g.get("category"))}</td>'
              f'<td class="items">{esc(", ".join(g.get("items") or []))}</td></tr>')
        w("</table></div>")

    # certifications
    certs = content.get("certifications") or []
    if certs:
        w('<div class="section"><h2>Certifications</h2>')
        for c in certs:
            title = c.get("name") or ""
            if nonempty(c.get("issuer")):
                title = f"{title} — {c['issuer']}"
            w('<div class="entry"><table class="entry-row"><tr>')
            w(f'<td class="left title">{esc(title)}</td>')
            w(f'<td class="right">{esc(c.get("date"))}</td>')
            w("</tr></table></div>")
        w("</div>")

    # patents
    pats = content.get("patents") or []
    if pats:
        w('<div class="section"><h2>Patents</h2>')
        for p in pats:
            right = " · ".join(x for x in (p.get("id"), p.get("date")) if nonempty(x))
            w('<div class="entry"><table class="entry-row"><tr>')
            w(f'<td class="left title">{esc(p.get("title"))}</td>')
            w(f'<td class="right">{esc(right)}</td>')
            w("</tr></table></div>")
        w("</div>")

    w("</div></body></html>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("content")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--template", default="classic")
    args = ap.parse_args()

    css_path = os.path.join(TEMPLATES, args.template, "resume.css")
    if not os.path.exists(css_path):
        sys.stderr.write(f"ERROR: template '{args.template}' not found at {css_path}\n")
        sys.exit(1)
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    with open(args.content, encoding="utf-8") as f:
        content = json.load(f)
    if not (content.get("header") or {}).get("name"):
        sys.stderr.write("ERROR: content.header.name is required\n")
        sys.exit(1)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(content, css))
    print(f"résumé written to {args.out}")
    print("open it in a browser; File → Print → Save as PDF if you need a PDF")


if __name__ == "__main__":
    main()
