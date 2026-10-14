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
- Ledger row 9 (constraint): no mention of the Oct 15 community assembly, ever.
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

BANNER_TEXT = "Tell our leaders to stop tank farms from dumping hazardous pollutants in our neighborhoods."
EMBED_URL = "map/embed.html"

# Ledger row 1: private map-site surface must never leak onto the public site.
# The marker sets live in tools/psp_public.py — shared with build.py and
# tools/publish.py so every entry point enforces the same rules.
PRIVATE_MARKERS = psp_public.PRIVATE_MARKERS
FORBIDDEN_EVENT_MARKERS = psp_public.EVENT_MARKERS
FORBIDDEN_DRAFT_MARKERS = psp_public.DRAFT_MARKERS

EXTERNAL_ALLOWLIST = (
    "southportland.gov",
    "southportland.org",
    "protectsouthportland.com",
    "docs.google.com",
    "drive.google.com",
    "go.boarddocs.com",
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
        assert "Active campaigns" in nav, name
        assert "Past work" in nav, name
        assert "Our Campaigns" not in nav, name
        assert "oil-tank-emissions.html" not in nav, name
        assert "vocs.html" not in nav, name
        assert 'href="tank-farms.html"' in nav, name
    tf = read(docs, "tank-farms.html")
    assert '<h1>South Portland Tank Farms</h1>' in tf
    assert EMBED_URL in tf
    assert 'id="health-effects-of-vocs"' in tf
    assert "assets/files/hem3-report-summary.pdf" in tf


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


def test_row7_map_notice_is_public_wording(docs):
    """Row 7 keeps a clearly marked graphic-swap notice, in public copy only:
    no draft language (release-gate rule 4 bans Placeholder/pending labels)."""
    for name in ("index.html", "tank-farms.html"):
        page = read(docs, name)
        assert "Final public map graphic: in design" in page, name
        assert "Explore the interactive map below" in page, name
        assert "Placeholder" not in page and "pending" not in page, name


def test_row6_hero_replaced_and_act_now_landing(docs):
    idx = read(docs, "index.html")
    assert "Now is the time to act" in idx
    assert 'href="act-now.html"' in idx
    all_html = "\n".join(read(docs, n) for n in html_files(docs))
    assert "Make a difference" not in all_html
    act = read(docs, "act-now.html")
    assert "https://southportland.gov/411/City-Council" in act
    assert "pressure the DEP to use the existing licensing process" in act


def test_row9_no_oct15_assembly_anywhere(docs):
    all_html = "\n".join(read(docs, n) for n in html_files(docs)).lower()
    for marker in FORBIDDEN_EVENT_MARKERS:
        assert marker.lower() not in all_html, marker


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


def test_embed_url_is_the_public_embedding(docs):
    """The map is self-hosted: both mapping pages iframe map/embed.html from
    this same published tree — no absolute cristoslc.github.io source."""
    for name in ("index.html", "tank-farms.html"):
        assert 'src="map/embed.html"' in read(docs, name), name


def test_row9_no_oct15_assembly_anywhere(docs):
    """The action dates from the docx must appear (sanity for row 5/6 copy)."""
    idx = read(docs, "index.html")
    assert "Oct. 27" in idx
    assert "637 Highland Ave" in idx


# ---- content-gap rewrite (Oct 13, 2026): homepage cut-down, archive page, ----
# ---- dated footer strip, dead-link sweep                                      ----

DATED_PHRASE = "Next: City Council workshop - Tuesday, Oct. 27, 6:30 p.m., South Portland High School."
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