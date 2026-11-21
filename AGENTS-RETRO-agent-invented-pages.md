# Retro: the agent-invented pages, and why they died

**Date:** 2026-11-21. **Status:** a permanent lesson, written after the operator approved stripping the site back to the pages the website-copy doc describes.

## What happened

Between Nov 5 and Nov 6, an agent (me) built three surfaces that no human ever asked for as pages:

1. **Library** (`library.html`) — a "resource library" with an entry rule, white-papers block, archive list.
2. **Press** (`press.html`) — a press kit with a fact sheet.
3. **How we got here** (`tank-farms-history.html`) — the campaign page's history run, split out into its own page.

The build quality was fine. The tests passed. The changelog was tidy. On 2026-11-21 the operator saw the library page's copy and said: *"the copy on the library page can never see the light of day. De-AIify it"* — and then chose the cleaner fix: strip the site back to the pages in the doc. All three pages died the same day this retro was requested.

## The actual failure

Not one of those three pages came from `protect_south_portland_website_copy`. They came from:

- A **meeting notes doc** ("Notes - Website Updates") that listed a *functionality wishlist* — "searchable archives," "press package" — as aspirations for some future version of the site.
- An **agent's own editorial judgment** that the campaign page was "too long" and needed a history split.

Neither is page authority. The wishlist item is a capability someone wants eventually, which is not the same as a page someone sanctioned now. The history split was pure invention: the doc writes the campaign as one long page, deliberately, and an agent decided it knew better.

Worse, the library page's copy was agent-authored in an agent's register — the "What qualifies:" entry rule, the "Start here" list, the white-papers block — and it read like what it was: a machine organizing things for other machines. No human wrote a word of it, no human was ever going to, and it carried the campaign's name.

## The rules this leaves behind

**1. The doc is the surface list.** `protect_south_portland_website_copy` (plus the comms-doc pages the operator explicitly adds, like Share your story) names every page the site may have. A page that is not in the doc does not get built. If a wishlist item wants to become a page, that is an operator decision made in the doc, not an agent decision made in a commit.

**2. Wishlist items are not page authority.** "It would be cool to have a press package" from a meeting-notes doc is a note in a notes doc. Building it means an agent wrote public copy in the campaign's voice with no human author behind it. That is the exact failure mode, stated plainly.

**3. Agent-authored "curation" copy is a tell.** Entry rules, taxonomy headings, "what qualifies" blocks, "start here" lists — when an agent invents structure, it fills it with organizational prose that no volunteer would write. The moment the copy's job is to describe the site instead of the campaign, a human must write it or it must not ship.

**4. Splitting a human's page is a content decision, not a refactor.** "This page is long" is an editorial opinion about someone else's writing. The doc's author chose the long campaign page. Respect it, or raise it with the operator — never just do it.

## Where the guards now stand

`test_strip_back_to_doc_pages` pins the world as of today: the three retired URLs are redirect stubs; nothing links to them; the nav and footer offer only the doc's pages; and the folded history content, the standing archive note, and the verbatim 600-ton record all live on the campaign page. A comment on the guard states the rule in one line: *the doc's page set is the sanctioned surface list; nothing new may join it without operator direction that names the page.*

Two earlier rulings were carried through the fold rather than lost with the pages:

- **The archive note** (2026-11-06): superseded figures stay verbatim, one standing note above the record, no inline corrections. It sits above the folded history run on the campaign page now, and the guard still enforces it.
- **The cap annotation** (Nov 6): the 600-ton VOC / 104-ton HAP cap does not ship on agent-authored copy. The archived LD 163 paragraph keeps its original figures verbatim; the guard now scopes the ban to everything outside the archived record.

## The one-line version for future agents

If the page is not in the doc, the page does not exist — and if the copy sounds like you organizing instead of the campaign speaking, stop writing and ask.
