#!/usr/bin/env python3
"""Assemble the static Protect South Portland website.

site/pages/*.html hold each page's <main> content. The first line of each file
must be an HTML comment carrying the page metadata:

  <!-- meta: title="..." | desc="..." -->

build.py wraps each body in the shared shell — masthead, navigation, footer —
writes the result to docs/, copies site/styles.css and site/assets/, and is
deliberately boring: stdlib only, no dependencies. GitHub Actions runs it on
push, then publishes docs/ with GitHub Pages.
"""
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
PAGES = os.path.join(SITE, "pages")

META_RE = re.compile(r'<!--\s*meta:\s*title="(?P<title>[^"]*)"\s*\|\s*desc="(?P<desc>[^"]*)"\s*-->\s*\n?')

NAV_BODY = """
<div class="skip-link"><a class="skip-link" href="#content">Skip to content</a></div>
<header class="masthead">
  <div class="masthead__inner">
    <a class="logo-link" href="index.html">
      <img src="assets/psp-logo.png" alt="Protect South Portland logo">
      <span class="wordmark">Protect South Portland</span>
    </a>
    <input type="checkbox" id="nav-toggle" class="nav-toggle" aria-hidden="true">
    <label class="nav-toggle-label" for="nav-toggle" aria-label="Toggle navigation">MENU</label>
    <nav class="main-nav" aria-label="Main">
      <ul>
        <li><a href="index.html">Home</a></li>
        <li class="nav-cta"><a href="act-now.html">Act Now</a></li>
        <li><a href="about.html">About</a></li>
        <li class="has-sub">
          <a href="our-campaigns.html">Our Campaigns</a>
          <ul class="submenu">
            <li><a href="index.html#tank-farms">South Portland Tank Farms</a></li>
            <li><a href="coastal-flooding.html">Coastal Flooding</a></li>
            <li><a href="yard-south-proposal.html">Yard South Proposal</a></li>
            <li><a href="oil-tank-emissions.html">Oil Tank Emissions</a></li>
            <li><a href="clear-skies.html">Clear Skies</a></li>
            <li><a href="fertilizer-ban.html">Fertilizer Ban</a></li>
            <li><a href="pesticides.html">Pesticides</a></li>
          </ul>
        </li>
        <li><a href="newsletter.html">Newsletter</a></li>
        <li><a href="get-involved.html">Get Involved</a></li>
        <li><a href="donate.html">Donate</a></li>
        <li><a href="contact.html">Contact</a></li>
      </ul>
    </nav>
  </div>
</header>
"""

FOOTER_BODY = """
<div class="dated-strip" role="note">
  <!-- DATED: remove after 2026-10-27 workshop — delete this div and the .dated-strip block in site/styles.css -->
  <p>Next: City Council workshop - Tuesday, Oct 27, 6:30 p.m., South Portland High School. <a href="act-now.html">Act now.</a></p>
</div>
<footer class="footer">
  <div class="wrap footer__grid">
    <div>
      <img src="assets/psp-logo.png" alt="Protect South Portland logo">
    </div>
    <div class="footer__links">
      <ul>
        <li><a href="index.html">Home</a></li>
        <li><a href="about.html">About</a></li>
        <li><a href="our-campaigns.html">Our campaigns</a></li>
        <li><a href="oil-tank-emissions.html">Oil tank emissions</a></li>
        <li><a href="clear-skies.html">Clear Skies</a></li>
        <li><a href="pesticides.html">Pesticides</a></li>
        <li><a href="coastal-flooding.html">Coastal flooding</a></li>
        <li><a href="yard-south-proposal.html">Yard South Proposal</a></li>
        <li><a href="past-work.html">Past work</a></li>
        <li><a href="newsletter.html">Newsletter</a></li>
        <li><a href="get-involved.html">Get involved</a></li>
        <li><a href="donate.html">Donate</a></li>
        <li><a href="contact.html">Contact</a></li>
      </ul>
    </div>
    <div class="footer__donate">
      <p>Help defend our <strong>COMMUNITY</strong>. Please donate to Protect South Portland.</p>
      <a class="btn btn--cta" href="donate.html">Donate</a>
    </div>
  </div>
  <div class="wrap footer__base">
    <div class="social">
      <a href="https://twitter.com/ProtectSoPo" rel="noopener">Twitter</a>
      <a href="https://www.facebook.com/protectsouthportland/" rel="noopener">Facebook</a>
    </div>
    <p class="credit">A special thank you goes out to Dan Woods and Karen Silverman for their photography donations.</p>
  </div>
</footer>
"""

SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="icon" type="image/png" href="assets/psp-favicon.png">
<link rel="stylesheet" href="styles.css">
</head>
<body>
{nav}
{body}
{footer}
</body>
</html>
"""


def build(out_dir: str) -> list:
    """Assemble every page into out_dir; return the list of pages written."""
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for name in sorted(os.listdir(PAGES)):
        if not name.endswith(".html"):
            continue
        raw = open(os.path.join(PAGES, name), encoding="utf-8").read()
        m = META_RE.match(raw)
        if not m:
            raise ValueError(f"{name}: first line must be the <!-- meta: ... --> comment")
        title = m.group("title")
        desc = m.group("desc")
        body = raw[m.end():].strip()
        html = SHELL.format(title=title, desc=desc, nav=NAV_BODY, body=body, footer=FOOTER_BODY)
        dest = os.path.join(out_dir, name)
        open(dest, "w", encoding="utf-8").write(html)
        written.append(name)
    shutil.copy(os.path.join(SITE, "styles.css"), os.path.join(out_dir, "styles.css"))
    shutil.copytree(os.path.join(SITE, "assets"), os.path.join(out_dir, "assets"), dirs_exist_ok=True)
    print("pages:", ", ".join(written))
    return written


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs")
    build(out)
    print("built into", out)