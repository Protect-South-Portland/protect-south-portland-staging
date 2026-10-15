---
title: Protect South Portland — static replacement website
description: Standalone HTML/CSS mirror of protectsouthportland.com with the open website change requests already implemented, served by GitHub Pages.
---

# Protect South Portland — static replacement website

A plain HTML/CSS rebuild of the PSP website, mirroring the structure and content of the live Wix site (https://www.protectsouthportland.com/) with every open change request from the ledger (`website-change-requests.md` in the PSP project workspace) already implemented. No framework, no dependencies — `tools/build.py` (stdlib only) assembles `site/pages/*.html` into `docs/`, and GitHub Actions publishes `docs/` with GitHub Pages on every push to `main`.

## Live URLs

| What | URL |
|---|---|
| Repository | https://github.com/cristoslc/protect-south-portland-site |
| Pages site | https://cristoslc.github.io/protect-south-portland-site/ |
| Interactive map embed (hosted on the tank-farms site) | https://cristoslc.github.io/south-portland-tank-farms/embed.html |

## Custom domain — expect a 404 until DNS is flipped

`docs/CNAME` is pre-placed with `protectsouthportland.org` (per ledger row 4, `.org` is intended to be the primary domain). Until the DNS records at Network Solutions point at this site (A/ALIAS to `cristoslc.github.io` and CNAME `www` accordingly) and the custom domain is entered under the repo's **Settings → Pages**, `https://protectsouthportland.org` **will 404 or serve a GitHub Pages 404 — that is expected and is not a broken deploy.** The Pages URL above works meanwhile. When the operator points the domains, also set a redirect from `.com` at that time.

## Ledger mapping

| Ledger row | Status here |
|---|---|
| 1 — Interactive map on PSP site, private links removed | Implemented. Nav-free `embed.html` (from the tank-farms repo, `884cb99`) is iframed on the homepage; site-wide tests forbid report/fact-check/data/GitHub links. |
| 2 — "Buckeye / South Portland Terminal" label | Already live on the tank-farms map (data-side); nothing further needed here. |
| 3 — Map top-center, website-addition text below it | Implemented on the homepage. |
| 4 — `.org` primary domain flip | DNS task, not site content. `docs/CNAME` staged; waiting on Network Solutions credentials/operator. |
| 5 — Banner at the very top of the homepage | Implemented, verbatim docx copy. |
| 6 — Replace "Make a difference" hero with tank-farms CTA; Act now → council-email landing | Implemented. `act-now.html` carries the docx ask plus the official council email list. |
| 7 — Section relabelled "South Portland Tank Farms", final map pending Nate | Implemented (text). Clear placeholder box for the final public map graphic. |
| 8 — Standing piecemeal mandate | Ongoing; edit `site/pages/*.html`, rebuild, push. |
| 9 — Oct 15 community assembly must appear nowhere (constraint) | Enforced by tests (`FORBIDDEN_EVENT_MARKERS`). |

## Placeholders needing operator decisions

Tracked in the ledger, not on the pages (pages carry visitor-friendly wording):

1. **Donate (donate.html)** — page says "Online giving is coming soon" with the P.O. box; the operator still needs PSP's PayPal (or another hosted) button.
2. **Newsletter (newsletter.html)** — subscribe-by-email shown, form "coming soon"; both archive PDFs are now mirrored locally (2021-01-13, 2020-12-13); a current issue is wanted (the 2021 items are presented as an archive).
3. **Contact (contact.html)** — email-first with "contact form is coming soon"; embed a form when a hosted service exists.
4. **Final public map graphic (homepage)** — swap the placeholder box for the graphic Mindy and Nate finalize.
5. **DEP/CDC fence-line analysis** — the `Where things stand — October 2026` section on oil-tank-emissions.html has a one-line placeholder: link + summarize the analysis when it publishes (verified raw summaries from Sept 8 and Oct 6, 2026 are already linked).
6. **Local Hero Award video (about.html)** — the still frame is shown; the video copy still needs a hosted home.
7. **Grow Healthy South Portland page** — no verified .gov home exists yet; the pesticides.html mention is plain text (link only when verified).

**Dated strip:** every page's footer carries `Next: City Council workshop - Tuesday, Oct 27 ...` marked `<!-- DATED: remove after 2026-10-27 workshop -->` in tools/build.py — delete the strip div in build.py and the `.dated-strip` block in site/styles.css after the workshop.

## What cannot be static

Contact, newsletter-subscribe, and donation flows need a hosted component eventually (form service now, or the planned self-hosted box). No other feature here requires it; everything else is flat HTML.

## Build & test

```sh
python3 tools/build.py            # assemble docs/ from site/pages
python3 -m pytest tests/          # test suite (pip install pytest)
```

The test suite builds the site into a temp dir and enforces the ledger constraints above (banner verbatim + placement, map ordering, hero replacement, private-link ban, Oct 15 ban, homepage cut-down + past-work archive, dated footer strip, nav Act Now, Wix PDF mirroring, dead-domain ban, link integrity, external-domain allowlist) plus the release-gate rules in AGENTS.md (draft-artifact ban, self-hosted map).

## Publish (public mirror)

The public site lives in a separate mirror repo — `cristoslc/protect-south-portland-published` — that carries exactly the campaign pages, local assets, and the standalone map (`map/embed.html`, `map/map.html`). Publish is one command, gate report in hand:

```sh
python3 tools/publish.py --gate-report ../gate-reports/<date>.json
```

Details (staging, marker scans, single-commit force-push, DNS-flip step): AGENTS.md, "Publishing to the public mirror".

### Staging rehearsal (`--repo` / `--domain`)

The identical pipeline can target a different public repo — used to rehearse the DNS flip on a staging mirror before touching production:

```sh
python3 tools/publish.py --gate-report ../gate-reports/<date>.json \
    --repo cristoslc/protect-south-portland-staging \
    --domain staging-b1fa9840.protectsouthportland.org
```

`--repo` swaps the push target (owner/name; default stays the production mirror), and `--domain` stages the hostname as the tree's `CNAME` and sets it as that repo's Pages custom domain. Omitted flags freeze production behavior: the production mirror repo, no staged CNAME (the site repo's `docs/CNAME` for the real flip stays out of the tree). A `--mirror-dir` that is not the target's default checkout remains local verification only.

Post-publish verification is hard against the two DNS-flip traps: the github.io check refuses to follow redirects off `*.github.io` (aborting with "custom DNS already live" instead of passing over a NetSol/Wix forward), and a `--domain` publish is only "done" when `https://<hostname>` serves the built index over a hostname-valid TLS certificate, after which the tool polls the Pages API and sets `https_enforced=true` (`--no-wait-https` leaves it manual; on timeout it fails loud with the Enforce HTTPS manual step). A publish with no `--domain` against a repo that already carries a custom domain is refused (`--allow-domain-drop` overrides explicitly) — a default run can never silently clear the CNAME.

## Repo structure

```
site/pages/*.html   page bodies (metadata in first-line comment)
site/styles.css     the stylesheet
site/assets/        PSP logo + psp-favicon.png (org's own branding)
site/assets/photos/ photography + graphics copied from the live Wix site
tools/build.py      assembler (stdlib)
tests/test_site.py  constraint and integrity tests
docs/               generated output, published by Pages
docs/CNAME          protectsouthportland.org (ready for DNS flip)
```