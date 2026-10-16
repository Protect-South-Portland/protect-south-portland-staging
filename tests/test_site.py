"""Tests for the generated Protect South Portland site.

Builds site/pages into a temp dir via tools/build.py and pins the hard rules:

- Ledger row 5: the verbatim docx banner sits at the very top of the homepage.
- Ledger row 7 + row 3: the map section is titled "South Portland Tank Farms",
  the interactive map sits top-center, and the website-addition text follows.
- Ledger row 6: the old "Make a difference / act now and donate" hero is gone;
  the tank-farms call to action replaces it and ACT NOW points to act-now.html
  (the email-the-Council landing page).
- Ledger row 1: no private links — research report, fact-check log, data files,
  GitHub repo — anywhere in the generated HTML.
- Ledger row 9 (constraint): no mention of the Oct 15 community assembly,
  ever — REVERSED 2026-10-15 by ledger row 33 (operator/Mindy sanctioned the
  meeting copy; the meeting is tonight): the ban is retired and the
  Action-Oriented meeting bullet ships with the flyer link.
- Site hygiene: internal links resolve, external links use an allowlist, every
  page has a title/description, and every image resolves locally with alt text.
- Photography and graphics are copied from the live Wix site into
  site/assets/photos (operator directive 2026-10-13) and served locally; hotlinking
  static.wixstatic.com is banned by test_no_wix_assets_copied.
"""

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "tools", "build.py")
sys.path.insert(0, os.path.join(ROOT, "tools"))

import psp_public
import publish

# Ledger row 5 banner, single-sourced from tools/psp_public.py so the
# tests and publish.py's domain check pin the same string.
BANNER_TEXT = psp_public.BANNER_TEXT
EMBED_URL = "map/embed.html"

# Ledger row 1: private map-site surface must never leak onto the public site.
# Ledger row 9's Oct-15 event-marker ban is reversed by row 33 (2026-10-15):
# EVENT_MARKERS must be retired-empty in psp_public and only the sanctioned
# meeting copy ships. The marker sets live in tools/psp_public.py — shared
# with build.py and tools/publish.py so every entry point enforces the same
# rules.
PRIVATE_MARKERS = psp_public.PRIVATE_MARKERS
FORBIDDEN_EVENT_MARKERS = psp_public.EVENT_MARKERS
FORBIDDEN_DRAFT_MARKERS = psp_public.DRAFT_MARKERS

EXTERNAL_ALLOWLIST = (
    "southportland.gov",
    "southportland.org",
    "protectsouthportland.com",
    "docs.google.com",
    "drive.google.com",
    "diligentoneplatform.com",
    "smellmycity.org",
    "southportland2040.com",
    "oneclimatefuture.org",
    "gmri.maps.arcgis.com",
    "storymaps.arcgis.com",
    "pressherald.com",
    "insideclimatenews.org",
    "justice.gov",
    "maine.gov",
    "mainelegislature.org",
    "legiscan.com",
    "bostonglobe.com",
    "dropbox.com",
    "nytimes.com",
    "scientificamerican.com",
    "beyondpesticides.org",
    "plantcatalyst.com",
    "paypal.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "themainemonitor.org",
    "cascobayestuary.org",
    "digital.sierramagazine.org",
    "edition.pagesuite.com",
    "mainebeacon.com",
    "portlandphoenix.me",
    "centralmaine.com",
    "wmtw.com",
    "web.archive.org",
    "youtu.be",
    "youtube.com",
)


@pytest.fixture(scope="module")
def docs(tmp_path_factory):
    out = tmp_path_factory.mktemp("site_out")
    subprocess.run([sys.executable, BUILD, str(out)], check=True, capture_output=True)
    return out


def read(docs, name):
    return open(os.path.join(docs, name), encoding="utf-8").read()


def html_files(docs):
    return sorted(n for n in os.listdir(docs) if n.endswith(".html"))


def test_expected_pages_built(docs):
    names = html_files(docs)
    for expected in (
        "index.html", "act-now.html", "about.html", "our-campaigns.html",
        "coastal-flooding.html", "yard-south-proposal.html", "oil-tank-emissions.html",
        "clear-skies.html", "fertilizer-ban.html", "pesticides.html", "vocs.html",
        "newsletter.html", "get-involved.html", "donate.html", "contact.html",
        "404.html", "past-work.html", "tank-farms.html",
    ):
        assert expected in names, expected
    assert "styles.css" in os.listdir(docs)
    assert os.path.exists(os.path.join(docs, "assets", "psp-logo.png"))


# merged campaign pages write tiny meta-refresh stubs instead of full shells;
# shell-level tests skip them.
REDIRECT_PAGES = {"oil-tank-emissions.html", "vocs.html"}


def test_merged_redirects(docs):
    stub = read(docs, "oil-tank-emissions.html")
    assert 'url=tank-farms.html' in stub and "content=\"0; url=" in stub
    stub2 = read(docs, "vocs.html")
    assert "tank-farms.html#health-effects-of-vocs" in stub2
    # stubs must not be full shells
    for name in REDIRECT_PAGES:
        page = read(docs, name)
        assert 'class="masthead"' not in page and len(page) < 800, name


def test_nav_structure_after_split(docs):
    for name in html_files(docs):
        if name in REDIRECT_PAGES:
            continue
        m = re.search(r'<nav class="main-nav".*?</nav>', read(docs, name), re.S)
        nav = m.group(0)
        # row 40 (2026-10-15): one "Our work" header item; the active
        # campaigns are its first children and the past-work pages live in a
        # nested flyout labeled Past work
        assert "Our work" in nav, name
        assert "Active campaigns" not in nav, name
        assert "Past work" in nav, name
        assert 'href="our-campaigns.html"' in nav, name
        assert 'aria-haspopup="true"' in nav, name
        assert "aria-expanded=" in nav, name
        first_child = nav.index(">South Portland Tank Farms<")
        past_label = nav.index(">Past work<")
        all_past = nav.index(">All past work<")
        yard = nav.index(">Yard South Proposal<")
        assert first_child < past_label < all_past < yard, name
        assert "Our Campaigns" not in nav, name
        assert "oil-tank-emissions.html" not in nav, name
        assert "vocs.html" not in nav, name
        assert 'href="tank-farms.html"' in nav, name
    tf = read(docs, "tank-farms.html")
    assert '<h1>South Portland Tank Farms</h1>' in tf
    assert EMBED_URL in tf
    assert 'id="health-effects-of-vocs"' in tf
    assert "assets/files/hem3-report-summary.pdf" in tf


def test_row40_flyout_structure_on_built_page(docs):
    # row 40 (2026-10-15): the Past work flyout + its five children render in
    # the built chrome on a page nobody edited for this row (404.html): one
    # nested flyout per nav, every child a real link
    nav = re.search(r'<nav class="main-nav".*?</nav>', read(docs, "404.html"), re.S).group(0)
    assert nav.count('<li class="has-sub has-flyout">') == 1, nav
    assert nav.count('class="submenu flyout"') == 1, nav
    for link in (
        'href="past-work.html">All past work</a>',
        'href="yard-south-proposal.html">Yard South Proposal</a>',
        'href="clear-skies.html">Clear Skies</a>',
        'href="fertilizer-ban.html">Fertilizer Ban</a>',
        'href="pesticides.html">Pesticides</a>',
    ):
        assert link in nav, link


def test_row40_landing_retitle(docs):
    # row 40 landing coherence: the "Our work" nav item lands on a page whose
    # h1 + title carry the dictated label; the archive + the four past-work
    # items are linked from the body (compact section, no prose changes)
    page = read(docs, "our-campaigns.html")
    assert "<h1>Our work</h1>" in page, page[:400]
    assert re.search(r"<title>Our work[^<]*</title>", page), page[:400]
    for href in (
        "past-work.html", "yard-south-proposal.html",
        "clear-skies.html", "fertilizer-ban.html", "pesticides.html",
    ):
        assert f'href="{href}"' in page, href


def test_map_not_the_lead_on_tank_farms_page(docs):
    """Operator directive 2026-10-13: on the dedicated campaign page the map is
    never the lead element — where-things-stand text and the tank narrative
    come first."""
    tf = read(docs, "tank-farms.html")
    iframe = tf.index(EMBED_URL)
    assert tf.index("id=\"where-things-stand\"") < iframe
    assert tf.index("120 large petroleum tanks") < iframe
    # the homepage keeps the ledger-pinned layout: map top-center, text below
    idx = read(docs, "index.html")
    assert idx.index(EMBED_URL) < idx.index("120 large petroleum tanks in South Portland")


def test_row5_banner_verbatim_on_homepage(docs):
    idx = read(docs, "index.html")
    assert BANNER_TEXT in idx
    # banner is the very top of the page body: before the tank-farms section
    assert idx.index(BANNER_TEXT) < idx.index('id="tank-farms"')


def test_row7_section_relabelled(docs):
    idx = read(docs, "index.html")
    assert '<h2>South Portland Tank Farms</h2>' in idx
    assert 'id="tank-farms"' in idx


def test_row3_map_top_center_text_below(docs):
    idx = read(docs, "index.html")
    iframe_pos = idx.index(EMBED_URL)
    assert '<iframe' in idx
    # the verbatim website-addition text sits below the map
    assert idx.index("120 large petroleum tanks in South Portland") > iframe_pos
    # map section is near the top, right after the banner
    assert iframe_pos < idx.index("Now is the time to act")


def test_row7_map_swap_stays_silent(docs):
    """Operator directive 2026-10-14: the 'Final public map graphic: in
    design' notice is killed. The interactive embed is the shipping feature;
    when Nate's final graphic lands it slots in silently via the row-7
    staged swap, so no page announces a future graphic."""
    for name in ("index.html", "tank-farms.html"):
        page = read(docs, name)
        assert "Final public map graphic" not in page, name
        assert "in design" not in page, name
        assert "once design work wraps" not in page, name
        assert "map-placeholder" not in page, name


def test_row6_hero_replaced_and_act_now_landing(docs):
    idx = read(docs, "index.html")
    assert "Now is the time to act" in idx
    assert 'href="act-now.html"' in idx
    all_html = "\n".join(read(docs, n) for n in html_files(docs))
    assert "Make a difference" not in all_html
    act = read(docs, "act-now.html")
    assert "https://southportland.gov/411/City-Council" in act
    assert "pressure the DEP to use the existing licensing process" in act


def test_row33_oct15_meeting_copy_published(docs):
    """Ledger row 33 (2026-10-15, Mindy-sanctioned, operator: publish today):
    the Action-Oriented meeting bullet ships verbatim on the homepage callout
    above the Oct 27 workshop bullet, with the QR-code link to the mirrored
    flyer and the mailto anchor inside the verbatim parenthetical. Row 9's
    scan ban on the event is retired — the marker list must be empty."""
    idx = read(docs, "index.html")
    bullet = ('<li><strong>Join neighbors on Thursday, Oct. 15 for a community meeting to '
              "share ideas, concerns, and stories:</strong> 5:30 p.m. food and "
              "community; 6-7 p.m. discussion. First Congregational Church "
              "UCC, 301 Cottage Road. (RSVPs are great/not required \u2013 use "
              '<a href="assets/files/tank-talk-flyer.pdf">the QR code</a> or '
              '<a href="mailto:protectsouthportland@gmail.com">the email below</a>.) '
              "Kids welcome.</li>")
    assert bullet in idx, "sanctioned meeting bullet must be verbatim (en dash included; links are render-only)"
    assert 'href="assets/files/tank-talk-flyer.pdf"' in idx, "the QR code must link the flyer"
    assert 'href="mailto:protectsouthportland@gmail.com">the email below</a>' in idx
    flyer = os.path.join(ROOT, "docs", "assets", "files", "tank-talk-flyer.pdf")
    assert os.path.exists(flyer), "the Tank Talk flyer must be mirrored into the built tree"
    # meeting bullet sits above the Oct 27 workshop bullet (operator placement)
    callout_pos = idx.index("Now is the time to act")
    assert idx.index("Join neighbors on Thursday, Oct. 15", callout_pos) < \
        idx.index("Make plans to come to the City Council workshop", callout_pos)
    # the scan ban is retired: no event markers remain to reject it
    assert tuple(FORBIDDEN_EVENT_MARKERS) == ()


def test_no_draft_language_anywhere(docs):
    """Release-gate rule 4: internal-draft language never reaches the surface."""
    patterns = ("as now written", "most recent draft", "TODO", "FIXME", "[Placeholder")
    for name in html_files(docs):
        page = read(docs, name)
        for p in patterns:
            assert p not in page, f"{name}: draft language leaked: {p}"


def test_row1_no_private_links_anywhere(docs):
    all_html = "\n".join(read(docs, n) for n in html_files(docs))
    for marker in PRIVATE_MARKERS:
        assert marker not in all_html, marker


def test_no_draft_artifacts_anywhere(docs):
    """Release gate rule 4 (AGENTS.md, 2026-10-13): internal working-draft
    language never reaches the public surface. Known live artifact:
    `THE #1 GOAL AS NOW WRITTEN IN THE MOST RECENT DRAFT:` (past-work.html)."""
    violations = []
    for name in html_files(docs):
        violations.extend(psp_public.scan_text(read(docs, name), name, FORBIDDEN_DRAFT_MARKERS))
    assert not violations, "\n" + "\n".join(violations)


@pytest.mark.skipif(
    psp_public.find_map_source_docs() is None,
    reason="standalone map pages not available (no tank-farms checkout)")
def test_map_pages_published_chrome_free(docs):
    """The site build ships the standalone map pages under map/ (published by
    tools/publish.py as the mirror's map subtree, and committed so CI can
    serve the relative iframe). Research chrome must be gone from map.html;
    every map file must be marker-clean."""
    map_dir = os.path.join(docs, "map")
    for name in psp_public.MAP_FILES:
        assert os.path.exists(os.path.join(map_dir, name)), name
    map_html = read(map_dir, "map.html")
    assert "<nav>" not in map_html
    violations = []
    for name in psp_public.MAP_FILES:
        violations.extend(psp_public.scan_file(os.path.join(map_dir, name), f"map/{name}"))
    assert not violations, "\n" + "\n".join(violations)


def test_no_wix_assets_copied(docs):
    """Images from the live site are served locally; never hotlink wixstatic."""
    all_html = "\n".join(read(docs, n) for n in html_files(docs))
    assert "static.wixstatic.com" not in all_html


def test_images_resolve_and_have_alt(docs):
    img_re = re.compile(r"<img\b[^>]*>")
    src_re = re.compile(r'src="([^"]+)"')
    alt_re = re.compile(r'alt="([^"]*)"')
    for name in html_files(docs):
        for tag in img_re.findall(read(docs, name)):
            src_m = src_re.search(tag)
            assert src_m, f"{name}: img without src"
            src = src_m.group(1)
            assert not src.startswith("http"), f"{name}: images must be local, got {src}"
            alt_m = alt_re.search(tag)
            assert alt_m and alt_m.group(1).strip(), f"{name}: img without alt text: {src}"
            assert os.path.exists(os.path.join(docs, src)), f"{name}: missing image file {src}"


def test_favicon_present(docs):
    favicon = os.path.join(docs, "assets", "psp-favicon.png")
    assert os.path.exists(favicon)
    for name in html_files(docs):
        if name in REDIRECT_PAGES:
            continue
        assert 'href="assets/psp-favicon.png"' in read(docs, name), name


def test_cname_ready_for_domain_flip(docs):
    cname = os.path.join(ROOT, "docs", "CNAME")
    assert os.path.exists(cname)
    assert open(cname).read().strip() == "protectsouthportland.org"


def test_every_page_shell_complete(docs):
    # masthead boundary (2026-10-15 readability re-measure): the older-visitor
    # root scale (112.5%) enlarged the rem-based nav row past the masthead's
    # 1060px content cap, so nav links settle at 0.9rem (gaps halved to 2px)
    # and the boundary was re-measured (1021px content + 40 padding + 16
    # scrollbar tax + 30 margin = 1107, rounded to 1120) — numbers recorded in styles.css above the
    # boundary. The served stylesheet carries that boundary and no stale
    # query. The de-duped masthead keeps exactly one brand carrier: the seal,
    # whose alt is the accessible brand name.
    css = open(os.path.join(ROOT, "site", "styles.css"), encoding="utf-8").read()
    assert "@media (max-width: 1120px)" in css, "masthead MENU boundary"
    assert "@media (max-width: 1080px)" not in css and "@media (max-width: 1200px)" not in css, "stale boundary"
    for name in html_files(docs):
        if name in REDIRECT_PAGES:
            continue
        page = read(docs, name)
        assert '<html lang="en">' in page, name
        assert "<title>" in page, name
        assert '<meta name="description"' in page, name
        assert 'name="viewport"' in page, name
        assert 'href="styles.css"' in page, name
        assert 'href="donate.html"' in page, name  # footer donate strip
        assert 'class="masthead"' in page, name
        assert 'class="footer"' in page, name
        # page-structure patch (2026-10-14 review, fixes 4 + 6): every page
        # carries one main landmark between the masthead and the footer, a
        # skip link that targets it without the stuck off-screen wrapper,
        # and a keyboard-focusable nav toggle with no aria-hidden.
        assert page.count('<main id="content">') == 1 and page.count("</main>") == 1, name
        assert page.index('class="masthead"') < page.index('<main id="content">') < page.index('class="footer"'), name
        assert '<a class="skip-link" href="#content">Skip to content</a>' in page, name
        assert 'div class="skip-link"' not in page, name
        assert 'id="nav-toggle"' in page and 'aria-hidden="true"' not in page, name
        # de-dupe (2026-10-15): one brand carrier — the seal alone in the
        # masthead with its alt as the accessible brand name; the text
        # wordmark never renders on any page (the footer's seal keeps its
        # own "... logo" alt, untouched by the de-dupe).
        assert '<img src="assets/psp-logo.png" alt="Protect South Portland">' in page, name
        assert 'wordmark' not in page, name


def test_banner_homepage_only(docs):
    for name in html_files(docs):
        page = read(docs, name)
        has_banner = 'class="banner"' in page
        if name == "index.html":
            assert has_banner, "homepage must carry the banner"
        else:
            assert not has_banner, f"{name} must not carry the homepage banner"


def test_internal_links_resolve(docs):
    anchor_re = re.compile(r'id="(.*?)"')
    href_re = re.compile(r'href="([^"]*)"')
    ids_by_page = {}
    for name in html_files(docs):
        ids_by_page[name] = set(anchor_re.findall(read(docs, name)))
    for name in html_files(docs):
        for href in href_re.findall(read(docs, name)):
            if href.startswith("mailto:") or href.startswith("#"):
                continue
            if href.startswith("http://") or href.startswith("https://"):
                continue
            target, _, frag = href.partition("#")
            path = os.path.join(docs, target)
            assert os.path.exists(path), f"{name}: broken link {href}"
            if frag:
                frag_ids = ids_by_page.get(target) or set(
                    anchor_re.findall(open(path, encoding="utf-8").read()))
                assert frag in frag_ids, f"{name}: missing anchor {href}"


def test_external_links_allowlisted(docs):
    href_re = re.compile(r'href="(https?://[^"]*)"')
    src_re = re.compile(r'src="(https?://[^"]*)"')
    for name in html_files(docs):
        page = read(docs, name)
        for url in href_re.findall(page) + src_re.findall(page):
            host = re.match(r"https?://([^/?#]*)", url).group(1).lower()
            host = host.removeprefix("www.")
            assert any(host == a or host.endswith("." + a) for a in EXTERNAL_ALLOWLIST), (
                f"{name}: external link not allowlisted: {url}"
            )

def test_donate_page_has_one_paypal_path(docs):
    """Ledger row 25 (live-site parity): donate.html restores the live site's
    PayPal giving path — exactly one PayPal donate link, aimed at PSP's own
    account, opening safely in a new tab. The UAT suite's
    donate-page-has-mechanism expectation now meets its external_link branch;
    the suite file itself was not edited."""
    page = read(docs, "donate.html")
    tags = re.findall(r"<a\s[^>]*paypal\.com[^>]*>", page)
    assert len(tags) == 1, (
        f"donate.html: expected exactly one PayPal link, got {len(tags)}")
    tag = tags[0]
    assert 'target="_blank"' in tag, tag
    assert 'rel="noopener"' in tag, tag
    href = html.unescape(re.search(r'href="([^"]*)"', tag).group(1))
    assert href.startswith("https://www.paypal.com/donate"), href
    assert "business=protectsouthportland%40gmail.com" in href, href
    assert "currency_code=USD" in href, href


def test_sprague_complaint_asset_mirrored(docs):
    """RED-1 (wix-vs-staging-comparison.md): the DOJ complaint document the
    live Wix /global page links ("Read the complaint>>") is mirrored into
    site/assets/files/ and anchored from the Sprague paragraph on
    tank-farms.html, so it survives Wix going dark."""
    tf = read(docs, "tank-farms.html")
    assert "Read the complaint (PDF)" in tf, "anchor text missing"
    hrefs = re.findall(r'href="(assets/files/[^"]*\.pdf)"', tf)
    sprague = [h for h in hrefs if "sprague-doj-complaint" in h]
    assert len(sprague) == 1, f"expected one Sprague complaint link, got {sprague}"
    asset = os.path.join(docs, sprague[0])
    assert os.path.exists(asset), "mirrored Sprague complaint is not reachable"
    with open(asset, "rb") as f:
        assert f.read(5) == b"%PDF-", "mirrored Sprague asset is not a PDF"
    assert tf.index("notice of violation from the EPA on May 29, 2020") < tf.index("Read the complaint (PDF)")


def test_about_links_the_award_video(docs):
    """RED-2 (wix-vs-staging-comparison.md): the Local Hero award video has a
    live public Dropbox copy; about.html links it instead of promising a
    future copy. Operator addendum 2026-10-14: the interim parenthetical is
    stripped too - shipped pages carry the link, not construction notes."""
    page = read(docs, "about.html")
    assert "when a public copy is available" not in page, "false pending claim still present"
    assert 'href="https://www.dropbox.com/s/6kizeqdtod6fr52/ME%20-%20Final.mp4?dl=0"' in page, "Dropbox copy link missing"
    assert "Watch the award video" in page, "video link anchor text missing"
    assert "(temporary link" not in page, "interim parenthetical must be gone"


def test_pages_carry_no_coming_soon_promises(docs):
    """Ledger rows 28/29 (operator addendum): shipped pages do not narrate
    coming mechanics. The subscribe-by-email and email-contact instructions
    ARE the mechanism; the 'coming soon' promises go, sentence-delete only."""
    for name in ("contact.html", "newsletter.html"):
        page = read(docs, name)
        assert "coming soon" not in page, name


def test_homepage_who_we_are_block(docs):
    """Ledger row 27 (Mindy-sanctioned homepage about-block from Alex's
    homepage pass): the mission line and the About-PSP paragraph sit verbatim
    on the homepage — the mission folds into the banner as its sign-off and
    the About paragraph sits in a compact strip between the hero photo and
    the issue section (2026-10-14 single-hero design pass), with Our Story
    linking about.html and a Get involved link to get-involved.html — after
    the 2026-10-14 design round 2 both read as list items in a two-item link
    row (page-structure patch): prose, not buttons; the banner Act now is the
    only button idiom in the first screen. The
    docx parentheticals are author instructions and must not ship; the
    working-note strings and the fact-flagged grammar quirks stay exactly as
    written (tone check)."""
    idx = read(docs, "index.html")
    assert "We are a community-based, volunteer-run organization working together to protect the environment and the health and well-being of South Portland residents." in idx
    assert "For over a decade, we" in idx
    assert "South Portland&rsquo;s precedent-setting Clear Skies Ordinance" in idx
    assert "a ban on synthetic pesticide" in idx, "grammar quirk must stay verbatim"
    assert "tar sands oils" in idx, "grammar quirk must stay verbatim"
    assert "Read more: Our Story" in idx
    assert 'href="about.html"' in idx, "Our Story must link to about.html"
    assert "Get involved" in idx
    assert 'href="get-involved.html"' in idx, "Get involved must link to get-involved.html"
    # design round 2 + page-structure patch: exactly one button idiom in the
    # first screen — the banner Act now — and the strip's links read as a
    # two-item link row after the paragraph (labels and hrefs char-for-char;
    # the paragraph ends at its own period), not a run-on, not stacked buttons.
    idx_top = idx[idx.index('class="banner"'):idx.index("The issue front and center")]
    assert idx_top.count('class="btn') == 1, "only the banner Act now is a button in the top flow"
    assert "intro-cta" not in idx and "btn--ghost" not in idx_top
    assert "meaningful actions.</p>" in idx and "Our Story</a> <a" not in idx, "strip ends at its own period"
    row_pos = idx.index('<ul class="link-row">')
    row = idx[row_pos:idx.index("</ul>", row_pos)]
    assert row.count('<li><a href="about.html">Read more: Our Story</a></li>') == 1
    assert row.count('<li><a href="get-involved.html">Get involved</a></li>') == 1
    # heading order (fix 3): the banner headline is the page's single h1
    assert idx.count("<h1") == 1 and '<h1 class="banner__headline">' in idx
    assert '<p class="banner__headline">' not in idx
    # final top-of-page order: banner (mission folded in as its sign-off, and
    # now the h1) -> hero photo band -> who-we-are strip -> link row (inside
    # the strip, after the paragraph) -> issue section
    banner_pos = idx.index('class="banner"')
    mission_pos = idx.index("We are a community-based")
    hero_pos = idx.index('class="hero-band')
    strip_pos = idx.index("For over a decade, we")
    issue_pos = idx.index("The issue front and center")
    assert banner_pos < mission_pos < hero_pos < strip_pos < row_pos < issue_pos
    # author working notes are not copy
    for leak in ("Something like this", "Something like that", "link to About Us"):
        assert leak not in idx, leak


def test_embed_url_is_the_public_embedding(docs):
    """The map is self-hosted: both mapping pages iframe map/embed.html from
    this same published tree — no absolute cristoslc.github.io source."""
    for name in ("index.html", "tank-farms.html"):
        assert 'src="map/embed.html"' in read(docs, name), name


def test_docx_action_dates_are_on_the_homepage(docs):
    """The action dates from the docx must appear (sanity for row 5/6 copy)."""
    idx = read(docs, "index.html")
    assert "Oct. 27" in idx
    assert "637 Highland Ave" in idx


# ---- content-gap rewrite (Oct 13, 2026): homepage cut-down, archive page, ----
# ---- dated footer strip, dead-link sweep                                      ----

DATED_PHRASE = "Next: City Council workshop - Tuesday, Oct. 27, 6 p.m., South Portland High School."
# the internal DATED marker lives only in tools/build.py as a Python comment;
# the served HTML must never carry it (release-gate rule 4, reviewer R1)
DATED_COMMENT = "DATED: remove after 2026-10-27 workshop"

PETITION_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSfPIeWgfe7GGgNqhxVatcPAEffmqo5jJJ-iGYcCh4ltcQsZcA/viewform"
)

MIRRORED_PDFS = (
    "hem3-report-summary.pdf",
    "newsletter-2021-01-13.pdf",
    "newsletter-2020-12-13.pdf",
    "fertilizer-ordinance-2020.pdf",
    "maine-dep-report-ld1915.pdf",
    "psp-submission-enr.pdf",
    "falatko-comments.pdf",
    "mikulka-comments.pdf",
    "pesticide-ordinance-ch32.pdf",
    "pesticide-ordinance-faqs.pdf",
    "clear-skies-ordinance-2014.pdf",
)


def test_homepage_cut_down(docs):
    idx = read(docs, "index.html")
    assert "Comprehensive Plan for South Portland is mandated" not in idx
    assert "Yard South development" not in idx
    assert PETITION_URL not in idx
    # the pinned surface survives untouched
    assert BANNER_TEXT in idx and 'id="tank-farms"' in idx


def test_past_work_archives_and_nav_exclusion(docs):
    pw = read(docs, "past-work.html")
    assert pw.count("Historical campaign") >= 2
    assert "Comprehensive Plan advocacy, 2024" in pw
    assert "Yard South proposal, 2023&ndash;2024" in pw
    assert 'href="yard-south-proposal.html"' in pw
    assert "Comprehensive Plan for South Portland is mandated" in pw
    # promoted into the header nav by the pre-workshop restructure (was footer-only)
    page = read(docs, "contact.html")
    m = re.search(r'<nav class="main-nav".*?</nav>', page, re.S)
    assert m and 'href="past-work.html"' in m.group(0)
    # footer carries the archive link
    assert 'href="past-work.html"' in page


def test_act_now_in_header_nav(docs):
    for name in html_files(docs):
        if name in REDIRECT_PAGES:
            continue
        m = re.search(r'<nav class="main-nav".*?</nav>', read(docs, name), re.S)
        assert m and 'href="act-now.html"' in m.group(0), name


def test_dated_footer_strip_every_page(docs):
    for name in html_files(docs):
        if name in REDIRECT_PAGES:
            continue
        page = read(docs, name)
        assert DATED_PHRASE in page, name
        assert DATED_COMMENT not in page, f"{name}: internal DATED comment leaked into served HTML"
        assert 'class="dated-strip"' in page, name
        assert re.search(r'<a href="act-now\.html">Act now\.</a>', page), name


def test_no_public_todo_strings(docs):
    for name in html_files(docs):
        assert "TODO" not in read(docs, name), name


def test_get_involved_current_ask_and_relocation(docs):
    gi = read(docs, "get-involved.html")
    assert "Oct. 27" in gi and "637 Highland Ave" in gi
    assert PETITION_URL in gi
    assert "pressherald.com/contact/" in gi


def test_about_tense_fixes(docs):
    ab = read(docs, "about.html")
    assert "fifth year" not in ab
    assert "docket" not in ab
    assert "12 coordinators" not in ab
    assert "core group of coordinators" in ab
    assert "13th year" in ab
    assert "What we're doing now" in ab


def test_where_things_stand_section(docs):
    ot = read(docs, "tank-farms.html")
    assert "Where things stand &mdash; October 2026" in ot
    assert "southportland.gov/522/Air-Quality-Concerns-Monitoring" in ot
    assert "DocumentCenter/View/5116" in ot
    assert "DocumentCenter/View/4819" in ot
    assert "spo-voc-monitor.html" in ot
    assert "fence-line data" in ot


def test_wix_pdfs_mirrored_locally(docs):
    all_html = "\n".join(read(docs, n) for n in html_files(docs))
    assert "protectsouthportland.com/_files" not in all_html
    for pdf in MIRRORED_PDFS:
        assert os.path.exists(os.path.join(docs, "assets", "files", pdf)), pdf


def test_no_southportland_org_links(docs):
    for name in html_files(docs):
        page = read(docs, name)
        for url in re.findall(r'href="(https?://[^"]*)"', page):
            host = re.match(r"https?://([^/?#]*)", url).group(1).lower().removeprefix("www.")
            assert host != "southportland.org", f"{name}: dead-domain link {url}"


def test_local_pdfs_resolve(docs):
    href_re = re.compile(r'href="(assets/files/[^"]+)"')
    for name in html_files(docs):
        for href in href_re.findall(read(docs, name)):
            assert os.path.exists(os.path.join(docs, href)), f"{name}: missing {href}"


def test_newsletter_archive_demoted(docs):
    nl = read(docs, "newsletter.html")
    assert "Newsletter archive" in nl
    assert "Most recent newsletter" not in nl


# ---- publication-safety helpers (tools/psp_public.py): the mirror tree's ----
# ---- scan rules are unit-pinned here so build/publish/enforcement stay   ----
# ---- in one place.                                                       ----

def test_strip_research_chrome_removes_nav_and_sidebar_links():
    sample = (
        '<header class="site"><div class="wrap"><h1>Protect South Portland</h1><nav>'
        '<a href="index.html">Home</a><a href="report.html">Research Report</a>'
        '<a href="https://github.com/cristoslc/south-portland-tank-farms">GitHub'
        "</a></nav></div></header>\n"
        "<p>Closest pairings stand.</p>\n"
        '<p style="margin-top:8px">\n'
        '  <a class="side-link" href="report.html">Research report</a> &middot;\n'
        '  <a class="side-link" href="data.html">Data files</a>\n'
        "</p>\n"
    )
    stripped = psp_public.strip_research_chrome(sample)
    assert "<nav>" not in stripped
    assert 'href="report.html"' not in stripped
    assert "Research report" not in stripped
    assert "Protect South Portland" in stripped  # brand header stays
    assert "Closest pairings stand." in stripped  # non-link copy stays


def test_public_scan_catches_private_strings(tmp_path):
    page = tmp_path / "page.html"
    page.write_text(
        '<a href="https://github.com/cristoslc/south-portland-tank-farms">GitHub</a>',
        encoding="utf-8",
    )
    violations = psp_public.scan_tree(tmp_path)
    assert any("south-portland-tank-farms" in v for v in violations), violations


def test_public_scan_catches_draft_and_path_rails(tmp_path):
    (tmp_path / "past-work.html").write_text(
        "<p>THE #1 GOAL AS NOW WRITTEN IN THE MOST RECENT DRAFT:</p>", encoding="utf-8")
    (tmp_path / "gap-analysis.html").write_text("<p>internal</p>", encoding="utf-8")
    (tmp_path / "meeting-notes.md").write_text("internal", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Public snapshot", encoding="utf-8")
    violations = psp_public.scan_tree(tmp_path)
    assert any("most recent draft" in v for v in violations), violations
    assert any("gap-analysis.html" in v for v in violations), violations
    assert any("meeting-notes.md" in v for v in violations), violations
    assert not any(v.startswith("README.md") for v in violations), violations


def test_public_scan_skips_binary_formats(tmp_path):
    bogus = tmp_path / "looks-private.pdf"
    bogus.write_bytes(b"%PDF-1.4 fake payload south-portland-tank-farms")
    assert psp_public.scan_tree(tmp_path) == []


# ---- tools/publish.py --repo/--domain after the 2026-10-14            ----
# ---- staging-first hardening: a bare run targets the staging mirror,  ----
# ---- production is reachable ONLY through an explicit --repo, and a   ----
# ---- publish auto-keeps (never silently clears) a custom domain the   ----
# ---- target already carries.                                          ----

STAGING_PUBLISH_REPO = "cristoslc/protect-south-portland-staging"
STAGING_PUBLISH_DOMAIN = "staging.protectsouthportland.org"


def test_publish_defaults_stay_on_staging():
    """Operator directive 2026-10-14: a bare publish targets the staging
    mirror; production is reachable ONLY through an explicit --repo."""
    args = publish.build_parser().parse_args(["--gate-report", "g.json"])
    assert args.repo == publish.DEFAULT_REPO == publish.STAGING_REPO
    assert args.domain is None
    explicit = publish.build_parser().parse_args(
        ["--gate-report", "g.json", "--repo", publish.PROD_REPO])
    assert explicit.repo == publish.PROD_REPO


def test_publish_flags_select_staging_repo_and_domain():
    args = publish.build_parser().parse_args([
        "--gate-report", "g.json",
        "--repo", STAGING_PUBLISH_REPO, "--domain", STAGING_PUBLISH_DOMAIN])
    assert args.repo == STAGING_PUBLISH_REPO
    assert args.domain == STAGING_PUBLISH_DOMAIN


def test_publish_pages_base_and_default_dir_follow_repo():
    assert publish.repo_pages_base(publish.PROD_REPO) == \
        "https://cristoslc.github.io/protect-south-portland-published"
    assert publish.repo_pages_base(STAGING_PUBLISH_REPO) == \
        "https://cristoslc.github.io/protect-south-portland-staging"
    assert publish.default_mirror_dir(publish.PROD_REPO) == os.path.join(
        os.path.dirname(psp_public.SITE_REPO_ROOT),
        "protect-south-portland-published")
    assert publish.default_mirror_dir(STAGING_PUBLISH_REPO) == os.path.join(
        os.path.dirname(psp_public.SITE_REPO_ROOT),
        "protect-south-portland-staging")


def test_publish_stages_cname_only_when_domain_given(docs, tmp_path):
    """No --domain: the tree carries no CNAME (today's mirror behavior).
    With --domain: exactly that hostname is staged and passes the scan."""
    # Production hands stage_publish_tree an mkdtemp'd (existing) dir.
    default_stage = tmp_path / "default"
    default_stage.mkdir()
    publish.stage_publish_tree(str(default_stage), docs_dir=str(docs))
    assert not os.path.exists(str(default_stage / "CNAME"))

    staged = tmp_path / "staged"
    staged.mkdir()
    publish.stage_publish_tree(str(staged), cname=STAGING_PUBLISH_DOMAIN,
                               docs_dir=str(docs))
    staged_cname = open(str(staged / "CNAME"), encoding="utf-8").read().strip()
    assert staged_cname == STAGING_PUBLISH_DOMAIN, staged_cname
    # The staging hostname must survive the publication scan: no private
    # marker, no draft marker, no event marker.
    assert psp_public.scan_tree(str(staged)) == []

# ---- publish-tool hardening from domain-flip-readiness.md gaps 2-4: the ----
# ---- post-push verification must not follow redirects outside the      ----
# ---- allowed hosts, must wait for the TLS certificate and enforce      ----
# ---- HTTPS, and a default (no --domain) publish must never clear a     ----
# ---- custom domain the target repo already carries.                    ----


def _fake_urlopen(final_url, status=200):
    """Stub for publish.urllib.request.urlopen: 200 at `final_url`."""

    class FakeResp:
        def __init__(self):
            self.status = status

        def read(self):
            return b""

        def geturl(self):
            return final_url

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    return lambda url, timeout=20: FakeResp()


def test_banner_text_single_source():
    assert BANNER_TEXT == ("Tell our leaders to stop tank farms from dumping "
                           "hazardous pollutants in our neighborhoods.")


def test_publish_wait_fails_loud_when_redirect_leaves_github_io(monkeypatch):
    monkeypatch.setattr(
        publish.urllib.request, "urlopen",
        _fake_urlopen("https://www.protectsouthportland.com/map/embed.html"))
    with pytest.raises(SystemExit, match="custom DNS already live"):
        publish.wait_for_pages(
            ["https://cristoslc.github.io/protect-south-portland-published/"
             "map/embed.html"], minutes=0.02)


def test_publish_wait_accepts_the_explicit_custom_domain(monkeypatch):
    monkeypatch.setattr(
        publish.urllib.request, "urlopen",
        _fake_urlopen(f"https://{STAGING_PUBLISH_DOMAIN}/"))
    monkeypatch.setattr(publish.time, "sleep", lambda s: None)
    publish.wait_for_pages([f"https://{STAGING_PUBLISH_DOMAIN}/"],
                           minutes=0.02,
                           allowed_domains=(STAGING_PUBLISH_DOMAIN,))


def test_publish_wait_timeout_names_the_domain_provisioning_hint(monkeypatch):
    def broken(url, timeout=20):
        raise OSError("connection failed")

    monkeypatch.setattr(publish.urllib.request, "urlopen", broken)
    monkeypatch.setattr(publish.time, "sleep", lambda s: None)
    with pytest.raises(SystemExit, match="certificate"):
        publish.wait_for_pages([f"https://{STAGING_PUBLISH_DOMAIN}/"],
                               minutes=0.01,
                               allowed_domains=(STAGING_PUBLISH_DOMAIN,))


def test_publish_wait_timeout_github_io_default_message(monkeypatch):
    def broken(url, timeout=20):
        raise OSError("connection failed")

    monkeypatch.setattr(publish.urllib.request, "urlopen", broken)
    monkeypatch.setattr(publish.time, "sleep", lambda s: None)
    with pytest.raises(SystemExit, match="Pages not serving after the wait"):
        publish.wait_for_pages(
            ["https://cristoslc.github.io/protect-south-portland-published/"],
            minutes=0.01)


def test_publish_stickiness_default_keeps_the_existing_domain():
    """Auto-keep (2026-10-14): without --domain a publish re-stages and
    re-verifies the custom domain the target already carries; it never
    silently drops one. An empty/absent Pages state keeps nothing."""
    state = {"cname": STAGING_PUBLISH_DOMAIN,
             "protected_domain_state": "verified"}
    assert publish.domain_stickiness_violation(state, None, False) is None
    assert publish.domain_stickiness_violation({}, None, False) is None
    assert publish.domain_stickiness_violation(
        {"protected_domain_state": "unverified"}, None, False) is None
    assert publish.resolve_publish_domain(state, None, False) == \
        (STAGING_PUBLISH_DOMAIN, None)
    assert publish.resolve_publish_domain({}, None, False) == (None, None)
    # A verified custom domain with no cname value to read still refuses
    # a domainless run: nothing to keep, staging blind would be worse.
    no_cname = {"protected_domain_state": "verified"}
    resolved = publish.resolve_publish_domain(no_cname, None, False)
    assert resolved[0] is None and resolved[1]
    assert "--domain" in resolved[1] and "--allow-domain-drop" in resolved[1]


def test_publish_stickiness_guard_escape_hatches():
    state = {"cname": STAGING_PUBLISH_DOMAIN}
    assert publish.domain_stickiness_violation(
        state, STAGING_PUBLISH_DOMAIN, False) is None
    assert publish.domain_stickiness_violation(state, None, True) is None
    conflict = publish.domain_stickiness_violation(
        state, STAGING_PUBLISH_DOMAIN, True)
    assert conflict and "conflicts" in conflict
    # --domain replaces what the target carries; --allow-domain-drop
    # clears it; the bare default keeps it (auto-keep).
    assert publish.resolve_publish_domain(
        state, "other.example.org", False) == ("other.example.org", None)
    assert publish.resolve_publish_domain(state, None, True) == (None, None)
    assert publish.resolve_publish_domain(state, None, False) == \
        (STAGING_PUBLISH_DOMAIN, None)


def test_publish_check_domain_stickiness_resolves_and_aborts(monkeypatch):
    monkeypatch.setattr(
        publish, "pages_api",
        lambda repo: {"cname": STAGING_PUBLISH_DOMAIN})
    assert publish.check_domain_stickiness(
        "cristoslc/protect-south-portland-staging", None, False) == \
        STAGING_PUBLISH_DOMAIN
    with pytest.raises(SystemExit, match="conflicts"):
        publish.check_domain_stickiness(
            "cristoslc/protect-south-portland-staging",
            STAGING_PUBLISH_DOMAIN, True)
    monkeypatch.setattr(publish, "pages_api", lambda repo: None)
    assert publish.check_domain_stickiness(
        "cristoslc/protect-south-portland-staging", None, False) is None


def test_publish_index_matches_built(tmp_path):
    index = tmp_path / "index.html"
    index.write_text(f"<p>{BANNER_TEXT}</p>", encoding="utf-8")
    assert publish.index_matches_built(f"<p>{BANNER_TEXT}</p>", str(index))
    assert publish.index_matches_built(f"prose {BANNER_TEXT} prose", str(index))
    # The banner fallback: the served page carries the banner even where the
    # local file read differs.
    index.write_text("<p>unrelated</p>", encoding="utf-8")
    assert publish.index_matches_built(BANNER_TEXT, str(index))
    # Neither branch: a text with no banner, against a differing local file.
    assert not publish.index_matches_built("<p>different text only</p>",
                                           str(index))
    assert not publish.index_matches_built(BANNER_TEXT, str(index) + "-gone")


def test_publish_enforce_https_polls_then_enforces(monkeypatch):
    sequence = iter([
        {"https_enforced": False, "https_certificate":
            {"state": "pending_issuance"}},
        {"https_enforced": False, "https_certificate": {"state": "approved"}},
        {"https_enforced": False, "https_certificate": {"state": "approved"}},
        {"https_enforced": True},
    ])
    monkeypatch.setattr(publish, "pages_api", lambda repo: next(sequence))
    puts = []
    monkeypatch.setattr(publish, "put_https_enforced",
                        lambda repo: puts.append(repo))
    monkeypatch.setattr(publish.time, "sleep", lambda s: None)
    assert publish.enforce_https("cristoslc/protect-south-portland-staging",
                                 clock=lambda: 0)["https_enforced"] is True
    assert puts == ["cristoslc/protect-south-portland-staging"]


def test_publish_enforce_https_timeout_names_the_manual_step(monkeypatch):
    monkeypatch.setattr(
        publish, "pages_api",
        lambda repo: {"https_enforced": False, "https_certificate": None})
    monkeypatch.setattr(publish, "put_https_enforced", lambda repo: None)
    ticks = iter(range(0, 1000, 30))
    with pytest.raises(SystemExit, match="Enforce HTTPS"):
        publish.enforce_https("cristoslc/protect-south-portland-staging",
                              minutes=1,
                              clock=lambda: next(ticks), pause=lambda s: None)


def test_publish_wait_flags_reject_a_domainless_run():
    with pytest.raises(SystemExit, match="custom-domain"):
        publish.assert_flag_agreement(None, True)
    with pytest.raises(SystemExit, match="custom-domain"):
        publish.assert_flag_agreement(None, False)
    publish.assert_flag_agreement(STAGING_PUBLISH_DOMAIN, None)
    publish.assert_flag_agreement(STAGING_PUBLISH_DOMAIN, True)


def test_publish_parser_hardening_flags():
    parser = publish.build_parser()
    args = parser.parse_args(["--gate-report", "g"])
    assert args.allow_domain_drop is False
    assert args.wait_https is None
    args = parser.parse_args(
        ["--gate-report", "g", "--allow-domain-drop", "--wait-https"])
    assert args.allow_domain_drop is True
    assert args.wait_https is True
    args = parser.parse_args(["--gate-report", "g", "--no-wait-https"])
    assert args.wait_https is False


def test_typography_older_visitor_floor():
    # Older-visitor readability pass (2026-10-15): the root scale rides the
    # visitor's own browser font setting (112.5% of it = 18px at defaults),
    # and body reading copy sits at exactly 1rem so every paragraph that
    # inherits the body (prose, cards, placeholder notes — whose own
    # font-size lines were dropped for that) lands on 18px and scales
    # together with every rem-based secondary size. The old fixed 17px body
    # broke that chain, and a fixed body floor is exactly what made the site
    # read small to older visitors. The staging audit
    # (tools/staging_audit.py) re-checks this against whatever the mirror
    # actually serves.
    css = open(os.path.join(ROOT, "site", "styles.css"), encoding="utf-8").read()
    assert "font-size: 112.5%" in css, "accessibility root scale (html)"
    assert "\n  font-size: 1rem;\n" in css, "body floor follows the root in rem"
    assert "font-size: 17px" not in css, "fixed px body defeats user scaling"


def test_footer_cta_contrast_wins_over_footer_link_color():
    # Lighthouse color-contrast, 2026-10-15 staging audit: `.footer a`
    # (0,1,1) out-specifies `.btn--cta` (0,1,0), so the footer DONATE
    # button rendered #bfeaf4 on --orange-dark (4.30:1, below AA for its
    # 17px bold) instead of white (5.55:1). The CTA keeps its own white
    # on the orange fill; the hover path goes darker (white on
    # #9c3615, 7.11:1).
    css = open(os.path.join(ROOT, "site", "styles.css"), encoding="utf-8").read()
    assert re.search(r"\.footer \.btn--cta\s*\{[^}]*color:\s*#fff", css), \
        "footer .btn--cta must re-pin white text on the orange fill"


def test_heading_order_is_sequential(docs):
    # Staging audit digest #4 (2026-10-15): tank-farms.html and
    # our-campaigns.html opened their outline with an h3 directly under the
    # h1. Structure pin only — heading TEXT is unchanged; a retagged heading
    # keeps its visual h3 look via the .h3-look class in styles.css.
    for name in html_files(docs):
        if name in REDIRECT_PAGES:
            continue  # stubs have no headings; Lighthouse audits their target
        levels = [int(m.group(1)) for m in re.finditer(r"<h([1-6])\b", read(docs, name))]
        assert levels, f"{name}: no headings"
        assert levels[0] == 1, f"{name}: outline must open at h1, opens at h{levels[0]}"
        for prev, cur in zip(levels, levels[1:]):
            assert cur <= prev + 1, (
                f"{name}: heading level jumps h{prev} -> h{cur}; outline not sequential")
