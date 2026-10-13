#!/bin/bash
# Multi-viewport visual verification for the PSP static site.
#
# The bb browser API has no viewport size control, so this script renders each
# width with the iframe trick: an iframe of width W answers its own CSS media
# queries, and a very tall iframe shows the whole page without scrolling.
# It captures homepage + one campaign page at 412 / 768 / 1440 and crops the
# top band and the footer region of each render into /tmp/psp_visual_check/.
#
# Usage:  tools/visual_check.sh [baseUrl]     (default: the live Pages site)
# Review: read the cropped PNGs after the run; anything that looks broken is a
# finding — do not ship layout changes without a clean pass at all three widths.

set -euo pipefail
BASE="${1:-https://cristoslc.github.io/protect-south-portland-site/}"
OUT=/tmp/psp_visual_check
rm -rf "$OUT" && mkdir -p "$OUT"
IFRAME_H=11000
CAMPAGE="tank-farms.html"

S=$(bb browser-automation open --backend local --headless --machine host_yat733yf8z --json | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
trap 'bb browser-automation close "$S" >/dev/null 2>&1' EXIT

for W in 412 768 1440; do
  for PAGE in "" "$CAMPAGE"; do
    NAME="${PAGE:-index}"; NAME="${NAME%.html}"
    bb browser-automation run "$S" --script \
"const p = await browser.getPage('main');
await p.goto('about:blank');
await p.evaluate(() => { document.body.innerHTML = '<iframe id=f style=\"width:${W}px;height:${IFRAME_H}px;border:0;display:block\" src=\"${BASE}${PAGE}?vc=' + Date.now() + '\"></iframe>'; });
await new Promise(r => setTimeout(r, 3500));
await p.screenshot({path: '$OUT/${W}_${NAME}_full.png', fullPage: true});" \
      --json >/dev/null 2>&1
    python3 - "$OUT/${W}_${NAME}_full.png" "$W" "$NAME" <<'PYEOF'
import sys
from PIL import Image
path, w, name = sys.argv[1], sys.argv[2], sys.argv[3]
im = Image.open(path).convert("RGB")
px = im.load()
def row_dark(y):
    c = 0
    for x in range(20, int(w)-20, 4):
        r, g, b = px[x, y]
        if r+g+b < 700:
            c += 1
            if c > 3:
                return True
    return False
bottom = None
for y in range(im.height-1, 0, -1):
    if row_dark(y):
        bottom = y
        break
top = bottom if bottom else im.height-1
im.crop((0, 0, int(w), min(1400, im.height))).save(path.replace("_full", "_top"))
im.crop((0, top-1500, int(w), top+30)).save(path.replace("_full", "_bottom"))
PYEOF
    echo "captured $W ${NAME}"
  done
done
echo "crops in $OUT (_top.png/_bottom.png per width)"