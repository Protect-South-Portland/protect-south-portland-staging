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
  python3 tools/publish.py --gate-report ... --repo <owner/name> \
      --domain <hostname>
      (same pipeline against another public repo — orphan commit, gate
       report, marker scan, Pages enable with the custom domain; then
       https://<hostname> is verified over a hostname-valid TLS
       connection and https_enforced is set once the certificate is
       approved (--no-wait-https skips the wait); a target repo that
       already carries a Pages custom domain is refused without --domain
       or an explicit --allow-domain-drop)
"""
import argparse
import datetime
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request

import psp_public

ROOT = psp_public.SITE_REPO_ROOT
MIRROR_REPO = "cristoslc/protect-south-portland-published"
MIRROR_PAGES_BASE = "https://cristoslc.github.io/protect-south-portland-published"
MIRROR_DIR = os.path.join(os.path.dirname(ROOT), "protect-south-portland-published")


def repo_pages_base(repo):
    """GitHub Pages URL root for a repo: https://{owner}.github.io/{name}."""
    owner, _, name = repo.partition("/")
    return f"https://{owner}.github.io/{name}"


def repo_url(repo):
    """HTTPS clone URL for a publishes-to repo."""
    return f"https://github.com/{repo}.git"


def default_mirror_dir(repo):
    """Default checkout for a publish target: a sibling of the site repo.

    The production mirror keeps its fixed path; any other --repo target
    gets a sibling named after the repo.
    """
    if repo == MIRROR_REPO:
        return MIRROR_DIR
    return os.path.join(os.path.dirname(ROOT), repo.partition("/")[2])

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


def stage_publish_tree(staging, cname=None, docs_dir=None):
    """Copy docs/ minus the CNAME/.gitkeep, add the fixed README, scan.

    With --domain the given hostname is staged as the tree's CNAME (the
    site repo's own docs/CNAME — the production flip — stays excluded
    unless the operator publishes with --domain that hostname).
    docs_dir overrides the source build tree (tests use the built fixture;
    production always leaves it None = the repo's docs/).
    """
    docs = docs_dir or os.path.join(ROOT, "docs")
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
    if cname:
        open(os.path.join(staging, "CNAME"), "w", encoding="utf-8").write(cname + "\n")
    psp_public.assert_clean(psp_public.scan_tree(staging), "staged publish tree")
    return sum(len(files) for _, _, files in os.walk(staging))


def ensure_git_repo(mirror_dir, is_remote_target, repo):
    if os.path.isdir(os.path.join(mirror_dir, ".git")):
        origin = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=mirror_dir, capture_output=True, text=True)
        if is_remote_target:
            if origin.returncode != 0 or repo not in origin.stdout:
                raise SystemExit(
                    f"{mirror_dir}: remote origin is {origin.stdout.strip()!r}, "
                    f"expected the {repo} clone")
        return
    if is_remote_target:
        view = subprocess.run(
            ["gh", "repo", "view", repo, "--json", "url"],
            capture_output=True, text=True)
        if view.returncode != 0:
            run(["gh", "repo", "create", repo, "--public", "--disable-wiki",
                 "--description",
                 "Protect South Portland - published campaign site and map (snapshot)"])
        run(["git", "clone", repo_url(repo), mirror_dir],
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


def ensure_pages_enabled(repo, cname=None):
    proc = subprocess.run(
        ["gh", "api", "-X", "POST", f"repos/{repo}/pages",
         "-f", "build_type=legacy",
         "-f", "source[branch]=main",
         "-f", "source[path]=/"],
        capture_output=True, text=True)
    already = "409" in proc.stderr or "already" in proc.stderr.lower()
    if proc.returncode != 0 and not already:
        raise SystemExit(f"enabling Pages failed:\n{proc.stderr}")
    if cname:
        proc = subprocess.run(
            ["gh", "api", "-X", "PUT", f"repos/{repo}/pages",
             "-f", f"cname={cname}"],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(
                f"setting the Pages custom domain {cname} failed:\n{proc.stderr}")
        check = subprocess.run(
            ["gh", "api", f"repos/{repo}/pages"],
            capture_output=True, text=True)
        if check.returncode != 0:
            raise SystemExit(f"reading back Pages settings failed:\n{check.stderr}")
        state = json.loads(check.stdout)
        if state.get("cname") != cname:
            raise SystemExit(
                f"Pages custom domain is {state.get('cname')!r}, "
                f"expected {cname!r}")


def wait_for_pages(urls, minutes=8, allowed_domains=None):
    """Wait for the URLs to serve 200, asserting the redirect chain stays
    under the allowed set.

    allowed_domains=None (the github.io verification pass) requires the
    FINAL URL to stay under *.github.io: when it lands elsewhere (the
    custom domain after the flip, or NetSol's forward to Wix), fail loud
    immediately instead of timing out or worse, "verifying" over the
    wrong site's bytes. With --domain the allowed set is exactly that
    hostname.
    """
    pending = list(urls)
    deadline = time.time() + minutes * 60
    while pending and time.time() < deadline:
        still = []
        for url in pending:
            try:
                with urllib.request.urlopen(url, timeout=20) as resp:
                    status, final_url = resp.status, resp.geturl()
            except Exception:
                still.append(url)
                continue
            host = urllib.request.urlsplit(final_url).hostname or ""
            ok = (host in allowed_domains if allowed_domains
                  else host.endswith(".github.io"))
            if not ok:
                raise SystemExit(
                    f"{url}\n  final URL is {final_url!r} (host {host!r})\n"
                    "  custom DNS already live — verify the custom domain "
                    "instead, or DNS not yet moved")
            if status != 200:
                still.append(url)
        pending = still
        if pending:
            time.sleep(15)
    if pending:
        raise SystemExit(
            "Pages not serving after the wait: " + ", ".join(pending) +
            ("\n  (DNS record or TLS certificate for the custom domain may "
             "still be provisioning — cert issuance can take up to 24 hours)"
             if allowed_domains else ""))


def pages_api(repo):
    """GET the repo's Pages settings, or None when Pages is not enabled."""
    proc = subprocess.run(
        ["gh", "api", f"repos/{repo}/pages"], capture_output=True, text=True)
    if proc.returncode == 0:
        return json.loads(proc.stdout)
    if "404" in proc.stderr or "Not Found" in proc.stderr:
        return None
    raise SystemExit(f"reading Pages settings failed:\n{proc.stderr}")


def cert_state(pages_state):
    """The HTTP-certificate status from a Pages API body, whatever shape
    the API shows today (none so far / dict with .state / plain string)."""
    cert = (pages_state or {}).get("https_certificate")
    if isinstance(cert, dict):
        return cert.get("state")
    return cert


def domain_stickiness_violation(state, requested_cname, allow_drop):
    """Abort reason when a CNAME-less tree would clear the target repo's
    custom domain (legacy "branch" builds read the domain from the
    CNAME file), or None when the publish may proceed."""
    current = (state or {}).get("cname")
    protected = (state or {}).get("protected_domain_state") == "verified"
    if not current and not protected:
        return None
    if allow_drop and requested_cname:
        return "--allow-domain-drop conflicts with --domain: pass one or " \
               "the other, never both"
    if allow_drop or requested_cname:
        return None
    return (
        f"this repo already carries the Pages custom domain {current!r}; a "
        "tree staged without --domain would clear it on the next Pages "
        "build. Re-run with --domain " + (current or "<current domain>") +
        " to keep publishing against it, or pass --allow-domain-drop "
        "explicitly to drop the custom domain.")


def check_domain_stickiness(repo, requested_cname, allow_drop):
    violation = domain_stickiness_violation(
        pages_api(repo), requested_cname, allow_drop)
    if violation:
        raise SystemExit(violation)


def tls_cert_subject(host, timeout=20):
    """Peer certificate from a hostname-verified (SNI + SAN matched) TLS
    handshake; a name mismatch or invalid chain raises."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            cert = tls.getpeercert()
    common = next(
        (value for rdn in cert.get("subject", ()) for key, value in rdn
         if key == "commonName"), None)
    return common, cert.get("notAfter")


def index_matches_built(text, index_path):
    """The served index equals the freshly built one, or at least carries
    the verbatim banner line (ledger row 5)."""
    if not os.path.exists(index_path):
        return False
    return (text == open(index_path, encoding="utf-8").read()
            or psp_public.BANNER_TEXT in text)


def verify_custom_domain(domain, index_path, minutes=8):
    """Blocking gate: the custom domain must serve the staged tree over a
    hostname-valid TLS connection before the publish claims success."""
    wait_for_pages([f"https://{domain}/",
                    f"https://{domain}/map/embed.html",
                    f"https://{domain}/map/map.html"],
                   minutes=minutes, allowed_domains=(domain,))
    common, not_after = tls_cert_subject(domain)
    with urllib.request.urlopen(f"https://{domain}/", timeout=20) as resp:
        if resp.status != 200:
            raise SystemExit(f"https://{domain}/ returned {resp.status}")
        text = resp.read().decode("utf-8", errors="replace")
    if not index_matches_built(text, index_path):
        raise SystemExit(
            f"https://{domain}/: the served index matches neither the "
            f"built index ({index_path}) nor the banner line")
    return f"TLS commonName {common!r} (notAfter {not_after})"


def put_https_enforced(repo):
    proc = subprocess.run(
        ["gh", "api", "-X", "PUT", f"repos/{repo}/pages",
         "-F", "https_enforced=true"],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"PUT https_enforced=true failed:\n{proc.stderr}")


def assert_flag_agreement(domain, wait_https):
    """--wait-https/--no-wait-https have no meaning without a custom domain."""
    if wait_https is not None and not domain:
        raise SystemExit(
            "--wait-https/--no-wait-https apply only to custom-domain "
            "publishes: pass --domain as well")


def enforce_https(repo, minutes=60, clock=time.time, pause=time.sleep):
    """Poll the Pages API until the HTTPS certificate is approved, then
    set https_enforced=true. On timeout, fail loud with the manual step —
    never silently continue without encryption."""
    MANUAL = (f"{repo}: HTTPS certificate not approved after {minutes} "
              "minutes. Manual step: repo Pages settings → Enforce HTTPS "
              "once the certificate shows available, then re-run the "
              "verification.")
    deadline = clock() + minutes * 60
    while True:
        state = pages_api(repo) or {}
        if state.get("https_enforced"):
            return state
        if cert_state(state) == "approved":
            put_https_enforced(repo)
            if (pages_api(repo) or {}).get("https_enforced"):
                return pages_api(repo)
        if clock() >= deadline:
            raise SystemExit(MANUAL)
        pause(30)


def build_parser():
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
    parser.add_argument("--repo", default=MIRROR_REPO,
                        help="push target as owner/name (default: the production "
                             "mirror; any other public repo gets the identical "
                             "pipeline, e.g. the staging rehearsal)")
    parser.add_argument("--domain", default=None,
                        help="custom hostname: staged as the tree's CNAME and set "
                             "as the target repo's Pages custom domain (default: "
                             "none — the mirror keeps its github.io URL until the "
                             "operator flips DNS)")
    parser.add_argument("--allow-domain-drop", action="store_true",
                        help="explicit override letting a publish proceed without "
                             "--domain even though the target repo carries a Pages "
                             "custom domain (which the staged CNAME-less tree then "
                             "clears on the next build)")
    wait = parser.add_mutually_exclusive_group()
    wait.add_argument("--wait-https", dest="wait_https",
                      action="store_true", default=None,
                      help="wait for the HTTPS certificate and set https_enforced "
                           "(default behavior for --domain publishes)")
    wait.add_argument("--no-wait-https", dest="wait_https",
                      action="store_false", default=None,
                      help="skip the HTTPS wait/enforcement step (leave it manual)")
    parser.add_argument("--mirror-dir", default=None,
                        help="target checkout (default: the clone of --repo; "
                             "any other path = local verification only)")
    return parser


def main():
    args = build_parser().parse_args()
    mirror_dir = args.mirror_dir or default_mirror_dir(args.repo)
    is_remote_target = os.path.abspath(
        mirror_dir) == os.path.abspath(default_mirror_dir(args.repo))
    pages_base = repo_pages_base(args.repo)
    assert_flag_agreement(args.domain, args.wait_https)

    review_model, per_page = load_gate_report(args.gate_report)
    require_clean_worktree()
    if is_remote_target:
        # Before anything is pushed or built: a default publish must not
        # silently clear a custom domain the target repo already carries.
        check_domain_stickiness(args.repo, args.domain, args.allow_domain_drop)
    build_site()

    staging = tempfile.mkdtemp(prefix="psp-publish-")
    try:
        file_count = stage_publish_tree(staging, cname=args.domain)
        ensure_git_repo(mirror_dir, is_remote_target, args.repo)
        removed = sync_tree(staging, mirror_dir)
        psp_public.assert_clean(
            psp_public.scan_tree(mirror_dir), "mirror worktree")
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
        sha = single_commit(mirror_dir, message)
        run(["git", "push", "--force", "origin", "main"], cwd=mirror_dir)
        ensure_pages_enabled(args.repo, cname=args.domain)
        if args.domain:
            cert_note = verify_custom_domain(
                args.domain, os.path.join(ROOT, "docs", "index.html"))
            wait_https = args.wait_https if args.wait_https is not None else True
            if wait_https:
                final_state = enforce_https(args.repo)
            print(f"published commit {sha} ({file_count} files) to {args.repo}")
            print(f"site: https://{args.domain}/")
            print(f"map: https://{args.domain}/map/map.html")
            print(f"tls: {cert_note}")
            print("index: the served index matches the built index "
                  "(or carries the banner line)")
            if wait_https:
                print("https: enforced — polled the Pages API for the "
                      "certificate, then set https_enforced=true")
        else:
            wait_for_pages([pages_base + "/",
                            pages_base + "/map/embed.html",
                            pages_base + "/map/map.html"])
            print(f"published commit {sha} ({file_count} files) to {args.repo}")
            print(f"site: {pages_base}/")
            print(f"map: {pages_base}/map/map.html")
        state = pages_api(args.repo) or {}
        print(f"pages: status {state.get('status')}, "
              f"cname {state.get('cname')!r}, "
              f"cert {cert_state(state)!r}, "
              f"protected {state.get('protected_domain_state')!r}, "
              f"https_enforced {state.get('https_enforced')}")
        if args.domain and args.wait_https is False:
            print("HTTPS enforcement left off (--no-wait-https): manual "
                  "step — repo Pages settings → Enforce HTTPS once the "
                  "certificate shows available")
    else:
        sha = single_commit(mirror_dir, message)
        print(f"LOCAL verification only — nothing pushed ({file_count} files, "
              f"removed stale: {sorted(removed) or 'none'})")
        print(f"commit {sha} in {mirror_dir}")
        print(f"gate: {review_model}, pages: {per_page}")
        print(f"snapshot: {snapshot}")


if __name__ == "__main__":
    main()