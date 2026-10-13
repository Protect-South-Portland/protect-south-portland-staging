# Protect South Portland static site — agent notes

Static HTML/CSS site for Protect South Portland, generated into `docs/` by `tools/build.py`, published via GitHub Actions to GitHub Pages from `main`.

## Commands

- Build: `python3 tools/build.py`
- Test: `python3 -m pytest tests/` (declare this as the project's test command)

## Hard constraints (tests enforce; never bypass)

1. No links to the tank-farms research surfaces anywhere public: `report.html`, `factcheck.html`, `data.html`, `github.com/cristoslc/south-portland-tank-farms`, or their nav labels ("Research report", "Fact-check log", "Data files", "GitHub repo"). The homepage iframe must keep pointing at `https://cristoslc.github.io/south-portland-tank-farms/embed.html` only.
2. No mention of the October 15 community assembly (invitation-only; Facebook/poster channels only). Never add any event copy for it.
3. Text copied verbatim from PSP-authored pages is fine. Photography and graphics from the live Wix site ARE copied locally into `site/assets/photos/` (operator directive, 2026-10-13) and served from this repo; never hotlink `static.wixstatic.com`. Keep press-photo credits (Portland Press Herald photographers) in captions.
4. Change requests come from the ledger: `website-change-requests.md` in the PSP project workspace (this repo implements the open rows; row 4 and row 9 are constraints, not content).

## Editing flow

Edit `site/pages/*.html` (each file carries its title/description in the first-line `<!-- meta: ... -->` comment), run `python3 tools/build.py`, run the tests, commit, push. CI rebuilds and deploys. After any layout/nav change, run the multi-viewport pass (`tools/visual_check.sh`) before reporting — 412/768/1440 screenshots of homepage + campaign page (top band + footer region); note the tall-iframe harness may miss late `loading="lazy"` images (capture-timing artifact, not a site bug). Old merged pages (`oil-tank-emissions.html`, `vocs.html`) live on as redirect stubs written by `tools/build.py` REDIRECTS.