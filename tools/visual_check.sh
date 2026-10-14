#!/bin/bash
# Multi-viewport visual verification for the PSP static site.
#
# Renders homepage + one campaign page at 412 / 768 / 1440 and crops the top
# band and the footer region of each render into /tmp/psp_visual_check/.
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

for W in 412 768 1440; do
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

uv run --with pillow python3 - "$OUT" "$MIN_COLORS" <<'PYEOF'
import glob, hashlib, os, sys
from PIL import Image
out, min_colors = sys.argv[1], int(sys.argv[2])
problems = []
for w in ("412", "768", "1440"):
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