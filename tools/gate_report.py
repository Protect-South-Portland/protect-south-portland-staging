#!/usr/bin/env python3
"""Write a content-addressed release-gate report (2026-11-04 hardening).

The publisher refuses a report whose page hashes do not match the source
files, and refuses a report that does not state a full-class reviewer. This
tool makes producing such a report the easy path: it takes the reviewer's
verdicts, stamps each page's built sha256 (docs/<page>.html, the content the
mirror ships), and validates exactly what publish.py will validate.

Usage:
  python3 tools/gate_report.py \
      --date 2026-11-04-1 \
      --review-model synthetic/hf:zai-org/GLM-5.3 \
      --review-class full \
      --verdicts /tmp/verdicts.json \
      --scope-note "Row 57: ... which commit the review saw ..." \
      --out ../gate-reports/2026-11-04-1.json

The verdicts file is a JSON object of page name -> {"rounds": N,
"outcome": "pass"}. Every file in site/pages/ must be present. Entries for
generated pages outside site/pages/ (the redirect stubs) are carried through
without a hash; the publisher ignores them.

Refuses to overwrite an existing report unless --force is passed: gate
reports are evidence, not scratch files.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import publish


def source_pages():
    pages_dir = os.path.join(publish.ROOT, "site", "pages")
    return sorted(n for n in os.listdir(pages_dir) if n.endswith(".html"))


def build_parser():
    parser = argparse.ArgumentParser(
        description="Write a content-addressed release-gate report.")
    parser.add_argument("--date", required=True,
                        help="report label, normally YYYY-MM-DD-<n>")
    parser.add_argument("--review-model", required=True,
                        help="model that issued the verdicts")
    parser.add_argument("--review-class", required=True,
                        help='reviewer class, "full" for the release gate')
    parser.add_argument("--verdicts", required=True,
                        help="JSON: {page: {rounds, outcome}} from the reviewer")
    parser.add_argument("--scope-note", required=True,
                        help="what the review covered and which commit it saw; "
                             "this is the provenance record, not decoration")
    parser.add_argument("--out", required=True,
                        help="report path, normally ../gate-reports/<date>.json")
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing report file")
    return parser


def main():
    args = build_parser().parse_args()

    if os.path.exists(args.out) and not args.force:
        raise SystemExit(
            f"{args.out}: already exists — gate reports are evidence; pass "
            "--force only to replace a report you wrote yourself")

    review_class = args.review_class.strip().lower()
    if review_class not in publish.REVIEW_CLASSES:
        raise SystemExit(
            f"--review-class {args.review_class!r} is not full — the release "
            f"gate accepts only {', '.join(publish.REVIEW_CLASSES)} "
            "(AGENTS.md \"Public website release gate\")")
    for marker in publish.FLASH_MARKERS:
        if marker in args.review_model.casefold():
            raise SystemExit(
                f"--review-model {args.review_model!r} carries the flash marker "
                f"{marker!r} — flash variants never issue the verdict")

    verdicts = json.load(open(args.verdicts, encoding="utf-8"))
    if not isinstance(verdicts, dict) or not verdicts:
        raise SystemExit(f"{args.verdicts}: expected a JSON object of page -> verdict")

    pages = source_pages()
    problems = []
    for page in pages:
        entry = verdicts.get(page)
        if not entry:
            problems.append(f"{page}: NOT REVIEWED — absent from the verdicts")
            continue
        outcome = str(entry.get("outcome", "")).strip().lower()
        rounds = entry.get("rounds")
        if outcome != "pass":
            problems.append(f"{page}: outcome {outcome!r} — not publishable")
        elif not isinstance(rounds, int) or not 0 <= rounds <= 3:
            problems.append(f"{page}: rounds {rounds!r} outside 0-3")
    if problems:
        raise SystemExit(
            "cannot write the report:\n  " + "\n  ".join(problems))

    report_pages = {}
    for name in sorted(verdicts):
        entry = verdicts[name]
        outcome = str(entry.get("outcome", "")).strip().lower()
        rounds = entry.get("rounds")
        stamped = {"rounds": rounds, "outcome": outcome}
        if name in pages:
            stamped["sha256"] = publish.page_sha256(name)
        report_pages[name] = stamped

    report = {
        "date": args.date,
        "review_model": args.review_model,
        "review_class": review_class,
        "pages": report_pages,
        "scope_note": args.scope_note,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    hashed = sum(1 for entry in report_pages.values() if "sha256" in entry)
    print(f"wrote {args.out}: {hashed}/{len(pages)} source pages hashed, "
          f"{len(report_pages)} entries, model {args.review_model} "
          f"({review_class})")


if __name__ == "__main__":
    main()
