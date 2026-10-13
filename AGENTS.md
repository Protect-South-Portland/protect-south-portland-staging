# Protect South Portland static site — agent notes

Static HTML/CSS site for Protect South Portland, generated into `docs/` by `tools/build.py`, published via GitHub Actions to GitHub Pages from `main`.

## Commands

- Build: `python3 tools/build.py`
- Test: `python3 -m pytest tests/` (declare this as the project's test command)

## Hard constraints (tests enforce; never bypass)

1. No links to the tank-farms research surfaces anywhere public: `report.html`, `factcheck.html`, `data.html`, `github.com/cristoslc/south-portland-tank-farms`, or their nav labels ("Research report", "Fact-check log", "Data files", "GitHub repo"). The homepage iframe must keep pointing at `https://cristoslc.github.io/south-portland-tank-farms/embed.html` only.
2. No mention of the October 15 community assembly (invitation-only; Facebook/poster channels only). Never add any event copy for it.
3. Text copied verbatim from PSP-authored pages is fine. Do NOT copy photos or graphics from the live Wix site; use labeled placeholder blocks instead.
4. Change requests come from the ledger: `website-change-requests.md` in the PSP project workspace (this repo implements the open rows; row 4 and row 9 are constraints, not content).

## Editing flow

Edit `site/pages/*.html` (each file carries its title/description in the first-line `<!-- meta: ... -->` comment), run `python3 tools/build.py`, run the tests, commit, push. CI rebuilds and deploys.