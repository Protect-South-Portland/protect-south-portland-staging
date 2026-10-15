"""Tests for tools/staging_audit.py — the non-blocking staging accessibility audit.

The audit runs on a schedule against the staging mirror; these tests pin its
pure logic with zero network:

- the typography floor check over the served stylesheet (root 112.5%, body
  1rem, no fixed-px body override) — golden test against the real stylesheet;
- delta classification between two runs (added / resolved / persisting);
- previous-digest extraction tolerating a missing or garbled block;
- digest body shape, including the machine-readable ```json block that the
  next run reads its delta from;
- the non-blocking exit contract: findings exit 0, infrastructure failure is
  the only non-zero exit, and infrastructure errors propagate (never
  swallowed into findings);
- the public page list, sourced from the repo (build.REDIRECTS + map).
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import build
import staging_audit as sa


def finding(fid, title="detail"):
    return sa.Finding(id=fid, title=title, detail=title)


# ---------- typography floor over the served stylesheet ----------

def test_typography_floor_passes_on_the_real_stylesheet():
    css = open(os.path.join(ROOT, "site", "styles.css"), encoding="utf-8").read()
    assert sa.check_typography_floor(css) == []


def test_typography_floor_flags_missing_root_scale():
    css = "html { scroll-behavior: smooth; }\nbody { font-size: 1rem; }"
    ids = [f.id for f in sa.check_typography_floor(css)]
    assert "typography:root-scale" in ids


def test_typography_floor_flags_missing_body_floor():
    css = "html { font-size: 112.5%; }\nbody { margin: 0; }"
    ids = [f.id for f in sa.check_typography_floor(css)]
    assert "typography:body-floor" in ids


def test_typography_floor_flags_banned_fixed_px_body():
    css = "html { font-size: 112.5%; }\nbody { font-size: 17px; }"
    ids = [f.id for f in sa.check_typography_floor(css)]
    assert "typography:fixed-px-body" in ids


def test_typography_floor_reads_the_block_not_a_stray_comment():
    # inverse guard: "112.5%" appearing only inside a comment (or on the
    # wrong selector) must not satisfy the floor check
    css = "/* legacy was font-size: 112.5% */\nhtml { color: #111; }\nbody { font-size: 1rem; }"
    ids = [f.id for f in sa.check_typography_floor(css)]
    assert "typography:root-scale" in ids


# ---------- delta between two runs ----------

def test_delta_classifies_added_resolved_and_persisting():
    previous = {"lighthouse:index.html": "Lighthouse 0.95",
                "lighthouse:about.html": "Lighthouse 0.92"}
    current = [finding("lighthouse:index.html", "Lighthouse 0.96"),
               finding("lighthouse:404.html", "Lighthouse 1.0")]
    d = sa.delta(previous, current)
    assert d["added"] == ["lighthouse:404.html"]
    assert d["resolved"] == ["lighthouse:about.html"]
    assert d["persisting"] == ["lighthouse:index.html"]


def test_delta_with_no_previous_history_is_none():
    assert sa.delta(None, [finding("http:index.html")]) is None


# ---------- previous-digest extraction ----------

MACHINE_BLOCK = """json
{"version": 1, "date": "2026-10-15 13:15 UTC", "findings":
  [{"id": "typography:root-scale", "title": "root floor missing"},
   {"id": "http:about.html", "title": "HTTP 404"}]}
"""


def test_extract_previous_findings_parses_the_machine_block():
    body = "some prose\n```" + MACHINE_BLOCK + "```\nmore prose"
    findings, readable = sa.extract_previous_findings(body)
    assert readable
    assert findings == {"typography:root-scale": "root floor missing",
                        "http:about.html": "HTTP 404"}


def test_extract_previous_findings_tolerates_missing_block():
    findings, readable = sa.extract_previous_findings("no block here")
    assert findings == {}
    assert not readable


def test_extract_previous_findings_tolerates_garbled_block():
    body = "```json\n{not json at all\n```"
    findings, readable = sa.extract_previous_findings(body)
    assert findings == {}
    assert not readable


# ---------- digest body shape ----------

def test_digest_body_carries_a_round_tripping_machine_block():
    current = [finding("typography:root-scale", "root floor missing"),
               finding("http:about.html", "HTTP 404")]
    body = sa.build_digest_body("2026-10-15 13:15 UTC", "https://staging.example.org",
                                {"index.html": {"status": 200, "lighthouse": []}},
                                current, None)
    back, readable = sa.extract_previous_findings(body)
    assert readable
    assert back == {"typography:root-scale": "root floor missing",
                    "http:about.html": "HTTP 404"}


def test_digest_body_contains_headline_sections():
    body = sa.build_digest_body("STAMP", "https://staging.example.org",
                                {"index.html": {"status": 200, "lighthouse": ["color-contrast"]}},
                                [finding("lighthouse:index.html")], None)
    assert "STAMP" in body
    assert "typography floor" in body.lower() or "Typography floor" in body
    assert "lighthouse:index.html" in body


# ---------- the audit run over injected fakes ----------

class FakeFetch:
    def __init__(self, statuses, css_text="ok", fail=False):
        self.statuses = dict(statuses)
        self.css_text = css_text
        self.fail = fail

    def __call__(self, url):
        if self.fail:
            raise sa.AuditInfraError("connection refused")
        path = url.rstrip("/").rsplit("/", 1)[-1]
        if path == "styles.css":
            return 200, self.css_text
        return self.statuses.get(path, 404), "page"


class FakeLighthouse:
    def __init__(self, score=1.0, failed=()):
        self.score = score
        self.failed = list(failed)
        self.calls = []

    def __call__(self, url, form_factor):
        self.calls.append((url, form_factor))
        return self.score, self.failed

PAGES = ["index.html", "about.html"]

CSS = "html { font-size: 112.5%; }\nbody { font-size: 1rem; }"


def test_clean_run_scores_and_floor_only():
    result = sa.run_audit("https://staging.example.org", PAGES,
                          fetch=FakeFetch({"index.html": 200, "about.html": 200}, CSS),
                          lh=FakeLighthouse())
    assert result["findings"] == []
    assert result["page_results"]["index.html"]["status"] == 200
    assert result["page_results"]["index.html"]["lighthouse_score"] == 1.0


def test_audit_runs_desktop_on_every_page_and_mobile_on_index():
    lhs = FakeLighthouse()
    sa.run_audit("https://staging.example.org", PAGES,
                 fetch=FakeFetch({"index.html": 200, "about.html": 200}, CSS), lh=lhs)
    forms = sorted(lhs.calls, key=lambda c: (c[1], c[0]))
    desktops = [c[0] for c in lhs.calls if c[1] == "desktop"]
    mobiles = [c[0] for c in lhs.calls if c[1] == "mobile"]
    assert set(desktops) == {"https://staging.example.org/index.html",
                             "https://staging.example.org/about.html"}
    assert mobiles == ["https://staging.example.org/index.html"]


def test_404_page_becomes_a_finding_not_an_infra_error():
    lhs = FakeLighthouse()
    result = sa.run_audit("https://staging.example.org", PAGES,
                          fetch=FakeFetch({"index.html": 200}, CSS),  # about 404s
                          lh=lhs)
    assert [f.id for f in result["findings"]] == ["http:about.html"]
    # a 404 page gets no Lighthouse run: an audit of an error page is noise
    assert not any(url.endswith("/about.html") for url, _ in lhs.calls)


def test_lighthouse_failures_become_findings():
    result = sa.run_audit("https://staging.example.org", PAGES,
                          fetch=FakeFetch({"index.html": 200, "about.html": 200}, CSS),
                          lh=FakeLighthouse(score=0.92, failed=["color-contrast"]))
    ids = {f.id for f in result["findings"]}
    # desktop runs on both pages; the mobile pass adds the index mobile id
    assert ids == {"lighthouse:index.html", "lighthouse:mobile:index.html",
                   "lighthouse:about.html"}
    detail = [f for f in result["findings"] if f.id == "lighthouse:about.html"][0]
    assert "color-contrast" in detail.detail


def test_typography_floor_failure_becomes_a_finding():
    result = sa.run_audit("https://staging.example.org", PAGES,
                          fetch=FakeFetch({"index.html": 200, "about.html": 200},
                                          "html {}"),
                          lh=FakeLighthouse())
    ids = {f.id for f in result["findings"]}
    assert ids == {"typography:root-scale", "typography:body-floor"}


# ---------- non-blocking exit contract ----------

def test_findings_still_exit_zero():
    assert sa.decide_exit(findings=[finding("http:index.html")], infra=False) == 0


def test_infra_failure_is_the_only_nonzero_exit():
    assert sa.decide_exit(findings=[], infra=True) == 1
    assert sa.decide_exit(findings=[finding("http:index.html")], infra=True) == 1


def test_infra_errors_propagate_fail_loud_never_swallowed():
    with pytest.raises(sa.AuditInfraError):
        sa.run_audit("https://staging.example.org", PAGES,
                     fetch=FakeFetch({}, fail=True), lh=FakeLighthouse())


# ---------- page list ----------

def test_public_page_list_covers_every_source_page_redirects_and_map():
    pages = sa.public_pages()
    for page in sorted(os.listdir(os.path.join(ROOT, "site", "pages"))):
        if page.endswith(".html"):
            assert page in pages, f"missing {page}"
    assert "map/embed.html" in pages
    assert set(build.REDIRECTS) <= set(pages), "redirect stub URLs are public"


# ---------- parse_lighthouse (real runner shape) ----------

def lh_report(audit_overrides=(), category_score=1.0):
    audits = {"color-contrast": {"score": 1.0}, "label": {"score": None}}
    for aid, s in audit_overrides:
        audits.setdefault(aid, {})["score"] = s
    return {"audits": audits,
            "categories": {"accessibility": {
                "score": category_score,
                "auditRefs": [
                    {"id": "color-contrast", "weight": 4},
                    {"id": "label", "weight": 0},          # informative: no weight
                    {"id": "input-image-alt", "weight": 0.1},
                ]}}}


def test_parse_lighthouse_report():
    score, failed = sa.parse_lighthouse(lh_report())
    assert score == 1.0
    assert failed == []


def test_parse_lighthouse_counts_only_weighted_failing_audits():
    report = lh_report(audit_overrides=[("color-contrast", 0.5)], category_score=0.95)
    score, failed = sa.parse_lighthouse(report)
    assert score == 0.95
    # label is scoreless (informative) and input-image-alt still passes:
    # only the weighted failing audit is reported
    assert failed == ["color-contrast"]


def test_parse_lighthouse_malformed_report_is_infrastructure():
    with pytest.raises(sa.AuditInfraError):
        sa.parse_lighthouse({"audits": {}})