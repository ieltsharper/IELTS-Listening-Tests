# Renders the question pages of the 26 Listening tests from the source PDF into img/tNN-K.webp.
# Each test is cut from its "TEST n" heading to the next heading; the page footer is cropped away.
# Usage: python -X utf8 -I _generator/render_questions.py "<path to IELTS Listening Actual Tests and Answers.pdf>"
import io
import json
import pathlib
import re
import sys

import numpy as np
import pymupdf
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "img"
DPI = 130
SIDE = (36, 576)  # points: crop to the same left/right margins on every slice

doc = pymupdf.open(sys.argv[1])
FOOTER = re.compile(r"^\d+\s*\|\s*P\s*a\s*g\s*e")

heads = {}
solution = None
for pn, page in enumerate(doc, 1):
    if pn < 5:
        continue
    for b in page.get_text("blocks"):
        t = b[4].strip()
        m = re.match(r"^TEST\s*(\d+)$", t)
        if m and int(m.group(1)) not in heads:
            heads[int(m.group(1))] = (pn, b[1])
        if t == "SOLUTION" and solution is None:
            solution = (pn, b[1])
assert sorted(heads) == list(range(1, 27)), heads
heads[27] = solution


def footer_top(page):
    tops = [b[1] for b in page.get_text("blocks") if FOOTER.match(b[4].strip())]
    return min(tops) - 16 if tops else page.rect.height - 40


def trim(img):
    gray = np.asarray(img.convert("L"))
    rows = np.where((gray < 235).any(axis=1))[0]
    if len(rows) == 0:
        return None
    top = max(rows[0] - 6, 0)
    bottom = min(rows[-1] + 6, gray.shape[0])
    return img.crop((0, top, img.width, bottom))


OUT.mkdir(exist_ok=True)
for old in OUT.glob("t*.webp"):
    old.unlink()
manifest = {}
for n in range(1, 27):
    (p0, y0), (p1, y1) = heads[n], heads[n + 1]
    slices = []
    for pn in range(p0, p1 + 1):
        page = doc[pn - 1]
        top = y0 - 4 if pn == p0 else 30
        bottom = footer_top(page)
        if pn == p1:
            bottom = min(bottom, y1 - 4)
        if bottom - top < 12:
            continue
        pix = page.get_pixmap(dpi=DPI, clip=pymupdf.Rect(SIDE[0], top, SIDE[1], bottom))
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        img = trim(img)
        if img is None:
            continue
        slices.append(img)
    # one continuous strip per test, so tables and sections that cross a page break read as one
    strip = Image.new("RGB", (slices[0].width, sum(i.height for i in slices)), "white")
    y = 0
    for i in slices:
        strip.paste(i, (0, y))
        y += i.height
    name = f"t{n:02d}.webp"
    strip.save(OUT / name, "WEBP", quality=82, method=6)
    manifest[n] = [name]
(ROOT / "_generator" / "images.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
total = sum((OUT / f).stat().st_size for fs in manifest.values() for f in fs)
print(sum(len(v) for v in manifest.values()), "images,", round(total / 1048576, 1), "MB")
