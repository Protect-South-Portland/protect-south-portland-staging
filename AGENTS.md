# Protect South Portland static site — agent notes

Static HTML/CSS site for Protect South Portland, generated into `docs/` by `tools/build.py`, published via GitHub Actions to GitHub Pages from `main`.

## Commands

- Build: `python3 tools/build.py`
- Test: `python3 -m pytest tests/` (declare this as the project's test command)

## Hard constraints (tests enforce; never bypass)

1. No links to the tank-farms research surfaces anywhere public: `report.html`, `factcheck.html`, `data.html`, `github.com/cristoslc/south-portland-tank-farms`, or their nav labels ("Research report", "Fact-check log", "Data files", "GitHub repo"). The map is self-hosted: index.html and tank-farms.html iframe the RELATIVE `map/embed.html` copy built into this repo's `docs/` (constraint text revised 2026-10-13 by orchestrator — the absolute github.io embed URL is superseded; the publish scanner also bans that host from the public tree).
2. No mention of the October 15 community assembly (invitation-only; Facebook/poster channels only). Never add any event copy for it.
3. Text copied verbatim from PSP-authored pages is fine. Photography and graphics from the live Wix site ARE copied locally into `site/assets/photos/` (operator directive, 2026-10-13) and served from this repo; never hotlink `static.wixstatic.com`. Keep press-photo credits (Portland Press Herald photographers) in captions.
4. Change requests come from the ledger: `website-change-requests.md` in the PSP project workspace (this repo implements the open rows; row 4 and row 9 are constraints, not content).

## Public website release gate (operator directive, 2026-10-13 — applies before ANY publish or republish)

1. **Scope:** every page whose copy changed (on the first run: all pages). A page is not publishable until it passes a full humanizer + style review.
2. **Reviewer:** the review round runs on a GLM-5.3-class model or higher, and flash variants do NOT qualify (operator clarification 2026-10-13): use `ollama-cloud/glm-5.3` (full GLM-5.3) or anything above it in the model ladder. A model below that class may implement revisions, but never performs the review verdict. Verbatim material copied from the historic Wix site is NOT exempt — it is legacy campaign copy and needs the review most.
3. **Rounds:** revise and re-review up to 3 rounds against the humanizer + style findings. Any page that still fails after 3 rounds is NOT published — escalate to the operator for a rewrite instead.
4. **Draft-artifact scan (part of every review):** no internal-draft language may reach the public surface. Known example (found live on `past-work.html` 2026-10-13): the header `THE #1 GOAL AS NOW WRITTEN IN THE MOST RECENT DRAFT:` — a working-draft label that must never be published. Scan for that pattern class: "as now written", "most recent draft", TODO/FIXME labels, template placeholders, anything that reads like a note to self rather than public copy.
5. **Recording the pass:** note per-page review outcome (round count, pass/fail) in the change log/commit message when publishing through the mirror pipeline.

## Publishing to the public mirror

Publishing is one command: `python3 tools/publish.py --gate-report <path.json>`. The gate report carries the reviewer's per-page outcomes (`{"date", "review_model", "pages": {"<page>.html": {"rounds": N, "outcome": "pass"}}}`); every page in `site/pages/` must be present and passing or nothing is pushed.

What it does, in order, failing loud at every step: runs the test suite → builds `docs/` (including copying the standalone map pages into `docs/map/` from the tank-farms checkout, or `PSP_MAP_DOCS_DIR`) → stages the publish tree (`docs/` minus `CNAME`/`.gitkeep`, plus a fixed README and `.nojekyll`) → scans the whole staged tree for private-surface markers (research links/labels, the private repo name and its github.io host, wixstatic, the Oct 15 assembly, draft artifacts, internal file names — the sets live in `tools/psp_public.py`) → force-pushes a single fresh commit ("Publish <date>", orphan history replaced every time) to `cristoslc/protect-south-portland-published` → enables Pages from `main` root and waits for the URLs to serve. `--mirror-dir <scratch>` runs the same staging + scan + commit against a local git repo without touching GitHub.

Map pages: `docs/map/{embed.html, map.html, styles.css}` are generated from the tank-farms repo (embed verbatim — it is chrome-free by construction; map.html is stripped of the research nav + sidebar links). build.py never deletes an existing `docs/map/`, so a CI checkout with the committed copy keeps serving the relative `map/embed.html` iframes with or without the sibling repo present.

The `CNAME` stays in the site repo, staged for the domain flip; when the operator flips DNS to the mirror, add `CNAME` to the publish tree (drop it from `PUBLISH_EXCLUDES`) and set `protectsouthportland.org` as the custom domain in the MIRROR repo's Pages settings.

## Editing flow

Edit `site/pages/*.html` (each file carries its title/description in the first-line `<!-- meta: ... -->` comment), run `python3 tools/build.py`, run the tests, commit, push. CI rebuilds and deploys. After any layout/nav change, run the multi-viewport pass (`tools/visual_check.sh`) before reporting — 412/768/1440 screenshots of homepage + campaign page (top band + footer region); note the tall-iframe harness may miss late `loading="lazy"` images (capture-timing artifact, not a site bug). Old merged pages (`oil-tank-emissions.html`, `vocs.html`) live on as redirect stubs written by `tools/build.py` REDIRECTS.