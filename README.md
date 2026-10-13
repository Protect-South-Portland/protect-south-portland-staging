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

All appear as dashed orange `.todo` blocks on the live-looking pages:

1. **Donate (donate.html)** — the Wix-hosted PayPal button has no static equivalent. Set up PSP's PayPal giving button or another hosted processor.
2. **Newsletter (newsletter.html)** — subscribe form needs a form service (or mailto bridge already shown); archive PDFs still live on Wix and should be mirrored into this repo.
3. **Contact (contact.html)** — Wix contact form replaced with the email address; embed a form when a hosted service exists.
4. **Final public map graphic (homepage)** — swap the placeholder box for the graphic Mindy and Nate finalize.
5. **Photos/graphics** — none of the original Wix photography is copied (photography credits remain in the footer). Dashed "Photo placeholder" blocks mark where licensed images can be added.
6. **Local Hero Award video (about.html)** — original plays inside Wix; link/embed a hosted copy when available.

## What cannot be static

Contact, newsletter-subscribe, and donation flows need a hosted component eventually (form service now, or the planned self-hosted box). No other feature here requires it; everything else is flat HTML.

## Build & test

```sh
python3 tools/build.py            # assemble docs/ from site/pages
python3 -m pytest tests/          # test suite (pip install pytest)
```

The test suite builds the site into a temp dir and enforces the ledger constraints above (banner verbatim + placement, map ordering, hero replacement, private-link ban, Oct 15 ban, link integrity, external-domain allowlist).

## Repo structure

```
site/pages/*.html   page bodies (metadata in first-line comment)
site/styles.css     the stylesheet
site/assets/        PSP logo (org's own branding)
tools/build.py      assembler (stdlib)
tests/test_site.py  constraint and integrity tests
docs/               generated output, published by Pages
docs/CNAME          protectsouthportland.org (ready for DNS flip)
```