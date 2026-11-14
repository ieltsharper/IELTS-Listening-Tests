# Turns the question pages of the 26 Listening tests into text blocks (data/questions.json) and cuts
# the blocks that cannot be shown as text (tables, maps, diagrams, flowcharts, anything that fails the
# checks) out of the PDF as images (img/tNN-bK.webp).
# Usage: python -X utf8 -I _generator/parse_questions.py "<IELTS Listening Actual Tests and Answers.pdf>" [test numbers...]
#
# A block is one "Questions a - b" group. It is shown as text only when the text passes the checks:
# every question number of the block is found exactly once (as a gap, a numbered question or a numbered
# item). Anything else falls back to the picture of that block, so no question is ever lost.
import html
import io
import json
import pathlib
import re
import sys

import numpy as np
import pymupdf
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lines as L  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG = ROOT / "img"
DPI = 130
SIDE = (36, 576)
e = html.escape

QHEAD = re.compile(r"^Questions?\s*(\d+)\s*(?:[-–—&]|to|and)?\s*(\d+)?\s*[.:]?\s*$", re.I)
SECTION = re.compile(r"^Section\s*(\d)\s*$", re.I)
SKIP = re.compile(r"^(TEST\s*\d+|Listen to [Aa]udio.*)$")
INSTR = re.compile(r"^(Complete|Choose|Write|Circle|Label|Match|Name|Look|Select|Use|Listen)\b")
INSTR_CONT = re.compile(r"^(below|answer|each answer|TWO|THREE|ONE|NO MORE|A NUMBER|AND/OR|WORDS|for |in each|next to|from the)", re.I)
GRAPHIC = re.compile(r"\b(table|diagrams?|flow\s*-?\s*chart|map|plan|label|chart|figure|graph)\b", re.I)
OPT = re.compile(r"^([A-I])\s*[.)]?\s+\S")
NUMQ = re.compile(r"^\(?(\d{1,2})((?:\s*(?:&|,|and)\s*\d{1,2})*)(?=[\s.)])\s*[.)]?\s*(?=\S)")
MULTI = re.compile(r"(?:Choose|Circle|Which)\s+(TWO|THREE|FOUR|FIVE|SIX)|(?:Choose|Circle)\s+(two|three|four|five|six)\s+(letters|answers)", re.I)
DOTS = r"[.…·_]{2,}\s*(?:\.\s*)*"
# a gap: dots around or beside the question number ("…..7…..", "7 .....", "….. 7", "7……")
GAP = re.compile(rf"(?:{DOTS})?\s*\(?\b(\d{{1,2}})\b\)?\.?\s*(?:{DOTS})|(?:{DOTS})\s*\(?\b(\d{{1,2}})\b\)?")
BLANK = re.compile(DOTS)


def fix_text(s):
    s = s.replace(" ", " ").replace("ﬁ", "fi").replace("ﬂ", "fl")
    return re.sub(r"\s+", " ", s).strip()


def split_blocks(ls):
    """Cut the lines of a test into [(section, heading, lines)]; section headings become their own item."""
    items = []
    cur = None
    for ln in ls:
        t = fix_text(ln["text"])
        if not t or SKIP.match(t):
            continue
        ln["t"] = t
        m = SECTION.match(t)
        if m:
            cur = None
            items.append(("section", int(m.group(1)), ln, []))
            continue
        m = QHEAD.match(t)
        if m:
            a = int(m.group(1))
            b = int(m.group(2)) if m.group(2) else a
            cur = ["block", (a, b), ln, []]
            items.append(cur)
            continue
        if cur is None:
            # text before the first block of a section (rare): attach to a new anonymous block
            cur = ["block", None, ln, [ln]]
            items.append(cur)
            continue
        cur[3].append(ln)
    return items


def merge_wrapped(lines, right_margin):
    """Joins lines that are one wrapped sentence into one paragraph. Returns [[line, ...], ...]."""
    paras = []
    for ln in lines:
        if paras:
            prev = paras[-1][-1]
            gap = ln["y0"] - prev["y0"]
            dots_next = bool(re.match(r"^[.…·_]{2,}", ln["t"])) and bool(re.search(r"\d+\)?\.?$", prev["t"]))
            # a line that starts in lower case continues the sentence above unless that one just ended
            lower_next = (
                bool(re.match(r"^[a-z(]", ln["t"]))
                and not re.search(r"[A-Za-z]{3,}[.?!:]$", prev["t"])
                and ln["page"] == prev["page"]
                and gap < 22
                and not OPT.match(ln["t"])
            )
            wraps = dots_next and ln["page"] == prev["page"] and gap < 22 or lower_next or (
                gap < 17
                and ln["page"] == prev["page"]
                and prev["x1"] > right_margin - 30
                and not OPT.match(ln["t"])
                and not NUMQ.match(ln["t"])
                and not ln["t"].startswith(("- ", "• ", "● "))
            )
            if wraps:
                paras[-1].append(ln)
                continue
        paras.append([ln])
    return paras


def gaps_in(text):
    """(html, [numbers]) for a paragraph: each gap becomes a numbered box."""
    found = []

    def sub(m):
        n = int(m.group(1) or m.group(2))
        found.append(n)
        return f" \x00{n}\x01 "

    def sub2(m):
        found.append(int(m.group(1)))
        return f"{m.group(2)} \x00{m.group(1)}\x01 "

    t = GAP.sub(sub, text)
    if not found:
        # "3. mj@......": the number, then a bit of fixed text, then the blank
        t = re.sub(r"\b(\d{1,2})\.\s+(\S{1,12}?)" + DOTS, sub2, t)
    t = BLANK.sub(" \x00_\x01 ", t)  # a gap with no number (example, or a typo in the book)
    t = re.sub(r"\s+", " ", t).strip()
    out = e(t)
    out = re.sub(r"\x00(\d+)\x01", r'<span class="gap">\1</span>', out)
    out = out.replace("\x00_\x01", '<span class="gap">&nbsp;</span>')
    return out, found


def block_text(block, right_margin):
    """Returns (kind, inst, html, numbers) for one block of lines, or None if it should be an image."""
    lines = block[3]
    inst = []
    body = []
    state = "pre"
    for ln in lines:
        t = ln["t"]
        if state in ("pre", "inst") and (INSTR.match(t) or (state == "inst" and INSTR_CONT.match(t))):
            inst.append(t)
            state = "inst"
        else:
            state = "body"
            body.append(ln)
    return inst, body


def render_text_block(block, right_margin):
    inst, body = block_text(block, right_margin)
    paras = merge_wrapped(body, right_margin)
    texts = [fix_text(" ".join(l["t"] for l in p)) for p in paras]
    nums = []
    parts = []
    in_opts = False
    for t in texts:
        mo = OPT.match(t)
        mq = NUMQ.match(t)
        if mo and not re.search(DOTS, t) and (in_opts or parts or mo.group(1) == "A"):
            if not in_opts:
                parts.append("<ul class='opts'>")
                in_opts = True
            parts.append(f"<li><b>{mo.group(1)}</b> {e(t[mo.end(1):].lstrip('.) ').strip())}</li>")
            continue
        if in_opts:
            parts.append("</ul>")
            in_opts = False
        if mq and not re.search(DOTS, t[:4]) and 1 <= int(mq.group(1)) <= 40 and not GAP.search(t):
            group = [int(mq.group(1))] + [int(x) for x in re.findall(r"\d+", mq.group(2))]
            nums.extend(group)
            rest = t[mq.end():]
            label = " & ".join(str(x) for x in group)
            parts.append(f"<p class='q'><span class='qn'>{label}</span> {e(rest)}</p>")
            continue
        h, found = gaps_in(t)
        nums.extend(found)
        cls = "bullet" if t.startswith(("- ", "• ", "● ")) else ""
        if cls:
            h = h[2:].lstrip()
        parts.append(f"<p class='{cls}'>{h}</p>" if cls else f"<p>{h}</p>")
    if in_opts:
        parts.append("</ul>")
    return inst, "".join(parts), nums


def has_graphics(doc, block_lines, y_ranges):
    """True if a picture or a drawn diagram sits inside the block's area."""
    for pn, y0, y1 in y_ranges:
        page = doc[pn - 1]
        for im in page.get_image_info():
            r = pymupdf.Rect(im["bbox"])
            if r.width > 40 and r.height > 30 and r.y1 > y0 and r.y0 < y1:
                return True
        boxes = 0
        for d in page.get_drawings():
            r = d["rect"]
            if r.width > 25 and r.height > 14 and r.y1 > y0 and r.y0 < y1 and r.width < 560:
                boxes += 1
        if boxes >= 3:
            return True
    return False


def trim(img):
    gray = np.asarray(img.convert("L"))
    rows = np.where((gray < 235).any(axis=1))[0]
    if len(rows) == 0:
        return None
    return img.crop((0, max(rows[0] - 6, 0), img.width, min(rows[-1] + 6, gray.shape[0])))


def crop_image(doc, start, end, name):
    """Cut the area from start=(page, y) to end=(page, y) out of the PDF into one picture."""
    (p0, y0), (p1, y1) = start, end
    slices = []
    for pn in range(p0, p1 + 1):
        page = doc[pn - 1]
        top = y0 - 4 if pn == p0 else 30
        bottom = L.footer_top(page)
        if pn == p1:
            bottom = min(bottom, y1 - 4)
        if bottom - top < 12:
            continue
        pix = page.get_pixmap(dpi=DPI, clip=pymupdf.Rect(SIDE[0], top, SIDE[1], bottom))
        img = trim(Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"))
        if img is not None:
            slices.append(img)
    if not slices:
        return None
    strip = Image.new("RGB", (slices[0].width, sum(i.height for i in slices)), "white")
    y = 0
    for i in slices:
        strip.paste(i, (0, y))
        y += i.height
    strip.save(IMG / name, "WEBP", quality=84, method=6)
    return name


def main():
    doc = L.open_pdf(sys.argv[1])
    heads = L.find_heads(doc)
    only = [int(a) for a in sys.argv[2:]] or list(range(1, 27))
    IMG.mkdir(exist_ok=True)
    right = max(max(w[2] for w in p.get_text("words")) for p in list(doc)[10:20])
    out = {}
    report = []
    for n in only:
        ls = L.test_lines(doc, heads, n)
        items = split_blocks(ls)
        # drop a section-wide "Questions 11 - 20" that is followed at once by another Questions heading
        blocks = []
        for i, it in enumerate(items):
            if it[0] == "block" and it[1] and not it[3]:
                nxt = items[i + 1] if i + 1 < len(items) else None
                inside = nxt is not None and nxt[0] == "block" and nxt[1] and it[1][0] <= nxt[1][0] and nxt[1][1] <= it[1][1] and nxt[1] != it[1]
                if inside:
                    continue
            blocks.append(it)
        result = []
        for bi, it in enumerate(blocks):
            kind, rng, head, lines = it
            if kind == "section":
                result.append({"type": "section", "n": rng})
                continue
            nxt = blocks[bi + 1] if bi + 1 < len(blocks) else None
            end_pos = (nxt[2]["page"], nxt[2]["y0"]) if nxt else heads.get(n + 1, (999, 0))
            if nxt is None:
                end_pos = (heads[n + 1][0], heads[n + 1][1])
            start_pos = (head["page"], head["y0"])
            a, b = rng if rng else (0, 0)
            want = list(range(a, b + 1))
            # areas of the block, per page, to look for pictures
            ranges = []
            for pn in range(start_pos[0], end_pos[0] + 1):
                y0 = start_pos[1] if pn == start_pos[0] else 20
                y1 = end_pos[1] if pn == end_pos[0] else L.footer_top(doc[pn - 1])
                ranges.append((pn, y0, y1))
            inst, body = (None, None)
            info = {"type": "block", "from": a, "to": b}
            use_image = rng is None
            reason = "no question range" if rng is None else ""
            if not use_image:
                inst_l, html_body, nums = render_text_block(it, right)
                joined = " ".join(inst_l)
                if GRAPHIC.search(joined) or GRAPHIC.search(head["t"]):
                    use_image, reason = True, "graphic in instruction"
                elif has_graphics(doc, lines, ranges):
                    use_image, reason = True, "picture or drawing"
                else:
                    if MULTI.search(joined + " " + head["t"] + " " + " ".join(l["t"] for l in lines[:3])) and "<ul class='opts'>" in html_body:
                        # "Choose TWO/THREE letters": one list of options answers all the numbers; the numbers
                        # are on the question line ("37 & 38.") or only in the heading
                        nums = [x for x in nums if a <= x <= b] or want
                        if sorted(set(nums)) != want:
                            nums = want
                    got = sorted(set(nums))
                    if sorted(nums) != sorted(set(nums)) or got != want:
                        # a numbered question and its gap may both appear: accept when the numbers are just all there
                        if not (set(want) <= set(nums) and set(nums) - set(want) == set()):
                            use_image, reason = True, f"numbers {sorted(nums)} != {a}-{b}"
                if not use_image:
                    info.update({"mode": "text", "inst": inst_l, "html": html_body})
            if use_image:
                name = crop_image(doc, start_pos, end_pos, f"t{n:02d}-b{bi}.webp")
                info.update({"mode": "image", "image": name})
                report.append((n, a, b, reason))
            result.append(info)
        out[n] = result
    path = ROOT / "data" / "questions.json"
    prev = json.loads(path.read_text(encoding="utf-8")) if path.exists() and len(only) < 26 else {}
    prev.update({str(k): v for k, v in out.items()})
    path.write_text(json.dumps(prev, ensure_ascii=False, indent=1), encoding="utf-8")
    texts = sum(1 for v in out.values() for b in v if b.get("mode") == "text")
    imgs = sum(1 for v in out.values() for b in v if b.get("mode") == "image")
    print(f"text blocks: {texts}, image blocks: {imgs}")
    for r in report:
        print("IMAGE", r)


main()
