#!/usr/bin/env python3
"""Publish the public mirror: tests -> build -> scan -> single-commit push.

One command builds the site into docs/, stages the exact publish tree
(campaign pages + local assets + the standalone map under map/), scans it
for everything private or draft-flavored, force-pushes ONE fresh commit
(no inherited history) to the mirror repo, and makes sure Pages serves the
mirror's main branch root. Tests run via the pytest binary on PATH when it
exists (uv-managed installs often lack it in the executing interpreter),
falling back to python3 -m pytest.

The mirror is the public face, so publication requires the reviewer's
per-page gate report (AGENTS.md "Public website release gate"):

    {"date": "2026-10-13",
     "review_model": "ollama-cloud/glm-5.3",
     "pages": {"index.html": {"rounds": 1, "outcome": "pass"}, ...}}

Every page under site/pages/ must appear with outcome "pass" before
anything is pushed; missing or failing pages abort loudly and the copy
escalates to the operator instead of being published.

Usage:
  python3 tools/publish.py --gate-report ../gate-reports/2026-10-13.json
  python3 tools/publish.py --gate-report ... --mirror-dir /tmp/psp-mirror-check
      (local verification: same staging + scan + commit against a scratch
       git repo; never contacts GitHub)
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import psp_public

ROOT = psp_public.SITE_REPO_ROOT
MIRROR_REPO = "cristoslc/protect-south-portland-published"
MIRROR_URL = f"https://github.com/{MIRROR_REPO}.git"
MIRROR_DIR = os.path.join(os.path.dirname(ROOT), "protect-south-portland-published")
MIRROR_PAGES_BASE = f"https://cristoslc.github.io/protect-south-portland-published"

# Staged for the later DNS flip in the site repo; the mirror keeps its
# default github.io URL until the operator moves the domain over.
# .gitkeep is a repo artifact, not site content.
PUBLISH_EXCLUDES = ("CNAME", ".gitkeep")

# The mirror README is fixed public text, rebuilt fresh on every publish.
MIRROR_README_TEXT = """# Protect South Portland

Public snapshot of the Protect South Portland campaign website, maintained
by volunteers in South Portland, Maine.

- Start at `index.html`.
- The standalone interactive map lives at `map/map.html`; the homepage and
  the tank-farms page embed the chrome-free version at `map/embed.html`.

This repository is a generated snapshot, rebuilt in full on every publish.
"""

# Publish pushes what is committed; build output (docs/) is the only path
# allowed to differ, because publishing regenerates it.
REQUIRED_CLEAN_PATHS = (".github", "AGENTS.md", "README.md", "site", "tests", "tools")


def run(cmd, cwd=ROOT):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}")
    return proc.stdout.strip()


def load_gate_report(path):
    """Validate the gate report and return (review_model, outcomes line)."""
    raw = json.load(open(path, encoding="utf-8"))
    model = raw.get("review_model", "").strip()
    if not model:
        raise SystemExit(f"{path}: missing review_model")
    pages = raw.get("pages")
    if not isinstance(pages, dict) or not pages:
        raise SystemExit(f"{path}: missing per-page outcomes")
    bad = []
    for page in sorted(os.listdir(os.path.join(ROOT, "site", "pages"))):
        if not page.endswith(".html"):
            continue
        entry = pages.get(page)
        if not entry:
            bad.append(f"{page}: NOT REVIEWED — absent from the gate report")
            continue
        outcome = str(entry.get("outcome", "")).strip().lower()
        rounds = entry.get("rounds")
        if outcome != "pass":
            bad.append(f"{page}: outcome {outcome!r} — not published, escalate to the operator")
        elif not isinstance(rounds, int) or not 0 <= rounds <= 3:
            bad.append(f"{page}: rounds {rounds!r} outside 0-3")
    if bad:
        raise SystemExit(
            "gate failures — nothing is published:\n  " + "\n  ".join(bad))
    per_page = ", ".join(
        f"{p} r{pages.get(p, {}).get('rounds', '?')}"
        for p in sorted(k for k in pages if k.endswith(".html")))
    return model, per_page


def require_clean_worktree():
    for path in REQUIRED_CLEAN_PATHS:
        status = run(["git", "status", "--porcelain", "--", path])
        if status:
            raise SystemExit(
                f"{path}: uncommitted changes — the mirror snapshots what is "
                "committed, so commit first:\n" + status)


def build_site():
    pytest_bin = shutil.which("pytest")
    run([pytest_bin, "-q", "tests"] if pytest_bin
        else [sys.executable, "-m", "pytest", "-q", "tests"])
    run([sys.executable, "tools/build.py", "docs"])
    map_out = os.path.join(ROOT, "docs", psp_public.MAP_DIRNAME)
    missing = [name for name in psp_public.MAP_FILES
               if not os.path.exists(os.path.join(map_out, name))]
    if missing:
        raise SystemExit(
            "docs/map/ incomplete (missing: " + ", ".join(missing) + "): the "
            "standalone map pages come from the tank-farms checkout "
            "(../south-portland-tank-farms/docs) or PSP_MAP_DOCS_DIR; the "
            "site repo alone cannot publish the map.")


def stage_publish_tree(staging):
    """Copy docs/ minus the CNAME/.gitkeep, add the fixed README, scan."""
    docs = os.path.join(ROOT, "docs")
    for entry in sorted(os.listdir(docs)):
        if entry in PUBLISH_EXCLUDES:
            continue
        src = os.path.join(docs, entry)
        dst = os.path.join(staging, entry)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    open(os.path.join(staging, "README.md"), "w", encoding="utf-8").write(MIRROR_README_TEXT)
    open(os.path.join(staging, ".nojekyll"), "w").write("")
    psp_public.assert_clean(psp_public.scan_tree(staging), "staged publish tree")
    return sum(len(files) for _, _, files in os.walk(staging))


def ensure_git_repo(mirror_dir, is_remote_target):
    if os.path.isdir(os.path.join(mirror_dir, ".git")):
        origin = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=mirror_dir, capture_output=True, text=True)
        if is_remote_target:
            if origin.returncode != 0 or MIRROR_REPO not in origin.stdout:
                raise SystemExit(
                    f"{mirror_dir}: remote origin is {origin.stdout.strip()!r}, "
                    f"expected the {MIRROR_REPO} clone")
        return
    if is_remote_target:
        view = subprocess.run(
            ["gh", "repo", "view", MIRROR_REPO, "--json", "url"],
            capture_output=True, text=True)
        if view.returncode != 0:
            run(["gh", "repo", "create", MIRROR_REPO, "--public", "--disable-wiki",
                 "--description",
                 "Protect South Portland - published campaign site and map (snapshot)"])
        run(["git", "clone", MIRROR_URL, mirror_dir],
            cwd=os.path.dirname(mirror_dir))
    else:
        run(["git", "init", "-b", "main", mirror_dir])


def sync_tree(staging, mirror_dir):
    """Make the mirror worktree exactly equal the staged tree (except .git)."""
    for dirpath, dirnames, filenames in os.walk(staging):
        dirnames.sort()
        for name in dirnames:
            os.makedirs(os.path.join(mirror_dir, os.path.relpath(dirpath, staging), name),
                        exist_ok=True)
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), staging)
            dst = os.path.join(mirror_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(dirpath, name), dst)
    removed = []
    for dirpath, dirnames, filenames in os.walk(mirror_dir):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), mirror_dir)
            if not os.path.exists(os.path.join(staging, rel)):
                os.remove(os.path.join(dirpath, name))
                removed.append(rel)
    for dirpath, dirnames, filenames in os.walk(mirror_dir, topdown=False):
        if ".git" in dirnames:
            dirnames.remove(".git")
        rel = os.path.relpath(dirpath, mirror_dir)
        if rel == ".git" or rel.startswith(".git" + os.sep):
            continue  # empty-object/refs subdirs of a fresh clone are repo internals
        if dirpath != mirror_dir and not os.listdir(dirpath):
            os.rmdir(dirpath)
    return removed


def source_provenance():
    site_sha = run(["git", "rev-parse", "--short", "HEAD"])
    map_sha = ""
    if os.path.isdir(psp_public.SIBLING_MAP_DOCS):
        map_sha = run(["git", "rev-parse", "--short", "HEAD"],
                      cwd=os.path.dirname(psp_public.SIBLING_MAP_DOCS))
    return site_sha, map_sha


def single_commit(mirror_dir, message):
    """Replace the worktree's commit history with one fresh commit.

    Works on an unborn HEAD (fresh init/clone of an empty repo) and on a
    repo that already has a main: existing refs are only ever replaced,
    never extended, so every publish is exactly one commit.
    """
    unborn = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=mirror_dir, capture_output=True).returncode != 0
    if unborn:
        run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=mirror_dir)
    else:
        run(["git", "checkout", "--orphan", "publish-tmp"], cwd=mirror_dir)
    run(["git", "add", "-A"], cwd=mirror_dir)
    run(["git", "commit", "-m", message], cwd=mirror_dir)
    if not unborn:
        run(["git", "branch", "-M", "publish-tmp", "main"], cwd=mirror_dir)
    return run(["git", "rev-parse", "--short", "HEAD"], cwd=mirror_dir)


def ensure_pages_enabled():
    proc = subprocess.run(
        ["gh", "api", "-X", "POST", f"repos/{MIRROR_REPO}/pages",
         "-f", "build_type=legacy",
         "-f", "source[branch]=main",
         "-f", "source[path]=/"],
        capture_output=True, text=True)
    already = "409" in proc.stderr or "already" in proc.stderr.lower()
    if proc.returncode != 0 and not already:
        raise SystemExit(f"enabling Pages failed:\n{proc.stderr}")


def wait_for_pages(urls, minutes=8):
    pending = list(urls)
    deadline = time.time() + minutes * 60
    while pending and time.time() < deadline:
        time.sleep(15)
        still = []
        for url in pending:
            try:
                with urllib.request.urlopen(url, timeout=20) as resp:
                    if resp.status != 200:
                        still.append(url)
            except Exception:
                still.append(url)
        pending = still
    if pending:
        raise SystemExit("Pages not serving after the wait: " + ", ".join(pending))


def main():
    parser = argparse.ArgumentParser(
        description="Publish the public mirror (gate report mandatory).")
    parser.add_argument("--gate-report", required=True,
                        help="JSON file with the reviewer's per-page outcomes")
    parser.add_argument("--subject", default=None,
                        help="commit subject override (default: 'Publish <today>'; "
                             "a same-day republish keeps the original subject)")
    parser.add_argument("--note", default="",
                        help="extra commit-message body line recording what "
                             "this publish cycle changed")
    parser.add_argument("--mirror-dir", default=MIRROR_DIR,
                        help="mirror checkout (default: the published repo "
                             "clone; any other path = local verification only)")
    args = parser.parse_args()
    is_remote_target = os.path.abspath(
        args.mirror_dir) == os.path.abspath(MIRROR_DIR)

    review_model, per_page = load_gate_report(args.gate_report)
    require_clean_worktree()
    build_site()

    staging = tempfile.mkdtemp(prefix="psp-publish-")
    try:
        file_count = stage_publish_tree(staging)
        ensure_git_repo(args.mirror_dir, is_remote_target)
        removed = sync_tree(staging, args.mirror_dir)
        psp_public.assert_clean(
            psp_public.scan_tree(args.mirror_dir), "mirror worktree")
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    today = datetime.date.today().isoformat()
    site_sha, map_sha = source_provenance()
    snapshot = f"site {site_sha}" + (f", tank-farms map {map_sha}" if map_sha else "")
    subject = args.subject or f"Publish {today}"
    message = (
        f"{subject}\n\n"
        f"Release gate (AGENTS.md): all pages passed the humanizer + style "
        f"review on model {review_model}. Rounds to pass: {per_page}.\n"
        f"Snapshot: {snapshot}."
        + (f"\n{args.note}" if args.note else ""))

    if is_remote_target:
        sha = single_commit(args.mirror_dir, message)
        run(["git", "push", "--force", "origin", "main"], cwd=args.mirror_dir)
        ensure_pages_enabled()
        wait_for_pages([MIRROR_PAGES_BASE + "/",
                        MIRROR_PAGES_BASE + "/map/embed.html",
                        MIRROR_PAGES_BASE + "/map/map.html"])
        print(f"published commit {sha} ({file_count} files) to {MIRROR_REPO}")
        print(f"site: {MIRROR_PAGES_BASE}/")
        print(f"map: {MIRROR_PAGES_BASE}/map/map.html")
    else:
        sha = single_commit(args.mirror_dir, message)
        print(f"LOCAL verification only — nothing pushed ({file_count} files, "
              f"removed stale: {sorted(removed) or 'none'})")
        print(f"commit {sha} in {args.mirror_dir}")
        print(f"gate: {review_model}, pages: {per_page}")
        print(f"snapshot: {snapshot}")


if __name__ == "__main__":
    main()