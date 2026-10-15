#!/bin/bash
# Multi-viewport visual verification for the PSP static site.
#
# Renders homepage + one campaign page at 412 / 768 / 1024 / 1100 / 1440 and
# crops the top band and the footer region of each render into
# /tmp/psp_visual_check/. Widths 1024 + 1100 joined 2026-10-15: the
# masthead overlap defect class lived in the 901-1099 band that none of the
# original three widths captured.
# Each width gets a real viewport (dev-browser page.setViewport), so CSS media
# queries answer at W directly; screenshots are full-page. An earlier
# revision used a very tall iframe instead, which silently stopped painting
# content when the old hard-coded capture base went dead and again on the
# current headless backend (2026-10-13/14 reviewer finding).
#
# Capture target: a local python http.server over the freshly built docs/ in
# the site checkout. An explicit baseUrl argument overrides it. Preflight
# requires HTTP 200 from the base and the campaign page and aborts loudly on
# anything else, so a dead or wrong base can never produce "valid-looking"
# output.
#
# Post-capture guards, before any crop ships:
#   1. no screenshot bytes or a failed browser run aborts non-zero;
#   2. per viewport width, the index and tank-farms full-frame checksums must
#      differ (identical renders mean both pages failed to load);
#   3. every crop must be non-uniform: more than $MIN_COLORS distinct colors
#      (a blank or black capture is 1-2 colors).
# A black/blank capture can never exit 0 again.
#
# Usage:  tools/visual_check.sh [baseUrl]     (default: local server on docs/)
# Review: read the cropped PNGs after the run; anything that looks broken is a
# finding — do not ship layout changes without a clean pass at all three widths.

set -euo pipefail

OUT=/tmp/psp_visual_check
CAMPAGE="tank-farms.html"
MIN_COLORS=64
VIEWPORT_H=900
SETTLE_MS=700

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCS="$ROOT/docs"

S=""
SERVER_PID=""
cleanup() {
  if [ -n "$S" ]; then
    bb browser-automation close "$S" >/dev/null 2>&1 || true
  fi
  if [ -n "$SERVER_PID" ]; then
    kill "$SERVER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [ $# -gt 0 ]; then
  BASE="$1"
  case "$BASE" in
    */|*.html) : ;;
    *) BASE="${BASE}/" ;;
  esac
else
  if [ ! -d "$DOCS" ]; then
    echo "visual check: $DOCS does not exist; run tools/build.py first (or pass an explicit baseUrl)." >&2
    exit 1
  fi
  PORT="$(python3 - <<'PY'
import socket
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    print(s.getsockname()[1])
PY
)"
  python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$DOCS" >/dev/null 2>&1 &
  SERVER_PID=$!
  BASE="http://127.0.0.1:${PORT}/"
fi

rm -rf "$OUT" && mkdir -p "$OUT"

# Local server readiness: poll until the base serves 200, abort if it never
# will (port stolen, server crashed). The preflight below re-checks both
# modes, so an explicit override URL is verified the same way.
if [ -n "$SERVER_PID" ]; then
  ok=""
  for _ in $(seq 1 50); do
    code="$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$BASE" || true)"
    if [ "$code" = "200" ]; then ok=1; break; fi
    sleep 0.2
  done
  if [ -z "$ok" ]; then
    echo "visual check: local capture server on $BASE never served HTTP 200; aborting." >&2
    exit 1
  fi
fi

# Preflight: the base and the campaign page must answer 200. This is the
# fail-loud replacement for the old silently-blank-capture path.
echo "capture base: $BASE"
for u in "$BASE" "${BASE}${CAMPAGE}"; do
  code="$(curl -s -o /dev/null -m 20 -w '%{http_code}' "$u" || echo 000)"
  if [ "$code" != "200" ]; then
    echo "visual check: capture target $u returned HTTP ${code:-000}, not 200; aborting (no blank captures)." >&2
    exit 1
  fi
done

S="$(bb browser-automation open --backend local --headless --machine host_yat733yf8z --json | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")"

for W in 412 768 1024 1100 1440; do
  for PAGE in "" "$CAMPAGE"; do
    NAME="${PAGE:-index}"; NAME="${NAME%.html}"
    FULL="$OUT/${W}_${NAME}_full.png"
    if ! bb browser-automation run "$S" --script \
"const p = await browser.getPage('main');
await p.setViewport({width: ${W}, height: ${VIEWPORT_H}});
await p.goto('${BASE}${PAGE}?vc=' + Date.now(), {waitUntil: 'load'});
if (typeof p.waitForNetworkIdle === 'function') {
  await Promise.race([
    p.waitForNetworkIdle({idleTime: 500, timeout: 8000}).catch(() => {}),
    new Promise(r => setTimeout(r, 8000))
  ]);
}
if (typeof p.waitForLoadState === 'function') {
  await Promise.race([
    p.waitForLoadState('networkidle').catch(() => {}),
    new Promise(r => setTimeout(r, 8000))
  ]);
}
await new Promise(r => setTimeout(r, ${SETTLE_MS}));
await p.screenshot({path: '${FULL}', fullPage: true});" \
      --timeout-ms 60000 --json >/dev/null 2>&1; then
      echo "visual check: browser run failed for ${W} ${NAME}; aborting." >&2
      exit 1
    fi
    if [ ! -s "$FULL" ]; then
      echo "visual check: no screenshot bytes for ${W} ${NAME}; aborting." >&2
      exit 1
    fi
    uv run --with pillow python3 - "$FULL" "$W" "$MIN_COLORS" <<'PYEOF'
import sys
from PIL import Image
path, w, min_colors = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
im = Image.open(path).convert("RGB")
px = im.load()
def row_dark(y):
    c = 0
    for x in range(20, min(int(w), im.width) - 20, 4):
        r, g, b = px[x, y]
        if r + g + b < 700:
            c += 1
            if c > 3:
                return True
    return False
bottom = None
for y in range(im.height - 1, 0, -1):
    if row_dark(y):
        bottom = y
        break
bottom_y = bottom if bottom else im.height - 1
top_path = path.replace("_full", "_top")
bottom_path = path.replace("_full", "_bottom")
im.crop((0, 0, min(int(w), im.width), min(1400, im.height))).save(top_path)
im.crop((0, max(0, bottom_y - 1500), min(int(w), im.width), min(bottom_y + 30, im.height))).save(bottom_path)
for crop in (top_path, bottom_path):
    n = len(Image.open(crop).convert("RGB").getcolors(maxcolors=10**7) or [])
    if n <= min_colors:
        print(f"visual check: {crop} looks blank ({n} distinct colors <= {min_colors}); capture invalid", file=sys.stderr)
        sys.exit(1)
PYEOF
    echo "captured $W ${NAME}"
  done
done

# ---------- geometric overlap audit: every band composes clean -----------
# Baked 2026-10-15 (round-3 sweep): per width, per page — the brand lockup
# must not be overlapped by any chrome element, its seal must not override
# the wordmark (the 901-band defect mode), no masthead/footer list pair may
# collide, and nothing may overflow the viewport horizontally. Widths: the
# full 700-1440 ladder in 40px steps plus 20px steps across the 1101-1260
# region where the desktop row's fit threshold lives. Any offender aborts
# the pass; screenshots alone can never prove the bands.
echo "geometric audit: begin"
AUDIT_JS="$(cat <<EOFJS
const p = await browser.getPage('main');
const pages = ['index.html', 'tank-farms.html'];
const widths = [700, 740, 780, 820, 860, 900, 940, 980, 1020, 1060, 1100,
  1101, 1121, 1141, 1161, 1181, 1201, 1221, 1241, 1260, 1300, 1340, 1380, 1420, 1440];
const EPS = 0.5;
const out = {};
for (const W of widths) {
  await p.setViewport({width: W, height: 900});
  for (const page of pages) {
    await p.goto('${BASE}' + page + '?g=' + Date.now(), {waitUntil: 'load'});
    out[page + '@' + W] = await p.evaluate((EPS) => {
      const intersect = (a, b) => !(
        a.right <= b.left + EPS || a.left >= b.right - EPS ||
        a.bottom <= b.top + EPS || a.top >= b.bottom - EPS);
      const brand = document.querySelector('.logo-link');
      const img = brand && brand.querySelector('img');
      const wordmark = brand && brand.querySelector('.wordmark');
      const brandInternal = !!(img && wordmark &&
        intersect(img.getBoundingClientRect(), wordmark.getBoundingClientRect()));
      const brect = brand ? brand.getBoundingClientRect() : null;
      const brandOverlap = [];
      if (brect) {
        for (const c of document.querySelectorAll('.masthead > *, .footer, .dated-strip')) {
          for (const el of c.querySelectorAll('*')) {
            if (brand.contains(el) || el.closest('.logo-link')) continue;
            const r = el.getBoundingClientRect();
            if (r.width === 0 && r.height === 0) continue;
            if (el.classList.contains('nav-toggle')) continue;
            if (intersect(r, brect)) brandOverlap.push(el.tagName);
          }
        }
      }
      const pairCollisions = [];
      for (const listSel of ['.main-nav > ul', '.footer__links ul']) {
        const lis = [...document.querySelectorAll(listSel + ' > li')];
        for (let i = 0; i < lis.length; i++) {
          for (let j = i + 1; j < lis.length; j++) {
            const a = lis[i].getBoundingClientRect();
            const b2 = lis[j].getBoundingClientRect();
            if ((a.width === 0 && a.height === 0) || (b2.width === 0 && b2.height === 0)) continue;
            if (intersect(a, b2)) pairCollisions.push(listSel + ' ' + i + 'x' + j);
          }
        }
      }
      return {
        brandInternal,
        nOver: brandOverlap.length,
        nPairs: pairCollisions.length,
        docOv: document.documentElement.scrollWidth > document.documentElement.clientWidth + EPS,
        bodyOv: document.body.scrollWidth > document.body.clientWidth + EPS,
      };
    }, EPS);
  }
}
const failures = Object.entries(out).filter(([, v]) =>
  v.brandInternal || v.nOver > 0 || v.nPairs > 0 || v.docOv || v.bodyOv);
return {total: Object.keys(out).length, failures};
EOFJS
)"
AUDIT_OUT="$OUT/audit.json"
if ! bb browser-automation run "$S" --script "$AUDIT_JS" --timeout-ms 110000 --json > "$AUDIT_OUT" 2>&1; then
  echo "visual check: geometric audit run failed; aborting." >&2
  exit 1
fi
AUDIT_STATUS=0
uv run python3 - "$AUDIT_OUT" <<'AUDITPY' || AUDIT_STATUS=1
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception as e:
    print(f"visual check: geometric audit output unreadable: {e}", file=sys.stderr)
    sys.exit(1)
if d.get("ok") is False or d.get("exitCode") != 0:
    print("visual check: geometric audit script error:", (d.get("text") or d.get("error", {}).get("message", "unknown"))[:300], file=sys.stderr)
    sys.exit(1)
try:
    payload = json.loads(d["text"])
except Exception as e:
    print(f"visual check: geometric audit payload unreadable: {e}", file=sys.stderr)
    sys.exit(1)
fails = payload.get("failures", [])
if fails:
    print(f"visual check: geometric audit FAILED — {len(fails)} bad width/page composites:", file=sys.stderr)
    for k, v in fails[:12]:
        print(f"  {k}: brandOverlap={v['nOver']} pairs={v['nPairs']} brandInternal={v['brandInternal']} overflow={v['docOv'] or v['bodyOv']}", file=sys.stderr)
    sys.exit(1)
print(f"geometric audit: OK — {payload['total']} width/page checks clean across 700-1440")
AUDITPY
if [ "$AUDIT_STATUS" -ne 0 ]; then exit 1; fi

uv run --with pillow python3 - "$OUT" "$MIN_COLORS" <<'PYEOF'
import glob, hashlib, os, sys
from PIL import Image
out, min_colors = sys.argv[1], int(sys.argv[2])
problems = []
for w in ("412", "768", "1024", "1100", "1440"):
    idx = os.path.join(out, f"{w}_index_full.png")
    cf = os.path.join(out, f"{w}_tank-farms_full.png")
    ha = hashlib.md5(open(idx, "rb").read()).hexdigest()
    hb = hashlib.md5(open(cf, "rb").read()).hexdigest()
    if ha == hb:
        problems.append(f"{w}: index and tank-farms full frames are checksum-identical ({ha}); captures are not valid renders")
blank = []
for crop in sorted(glob.glob(os.path.join(out, "*_top.png")) + glob.glob(os.path.join(out, "*_bottom.png"))):
    n = len(Image.open(crop).convert("RGB").getcolors(maxcolors=10**7) or [])
    if n <= min_colors:
        blank.append(f"{crop}: uniform ({n} distinct colors <= {min_colors})")
problems.extend(blank)
if problems:
    print("visual check: VALIDITY GUARDS FAILED — no valid pass:", file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)
    sys.exit(1)
crops = glob.glob(os.path.join(out, "*_top.png")) + glob.glob(os.path.join(out, "*_bottom.png"))
print(f"guards: OK — {len(crops)} crops all exceed {min_colors} distinct colors; index/tank-farms checksums differ at every width")
PYEOF

echo "crops in $OUT (_top.png/_bottom.png per width)"