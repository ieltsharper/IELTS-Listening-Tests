# Reads the source PDF into clean text lines with their page and position, per test.
# Shared by parse_questions.py. Usage (debug): python -X utf8 -I _generator/lines.py "<PDF>" <test number>
import pathlib
import re
import sys

import pymupdf

FOOTER = re.compile(r"^\d+\s*\|\s*P\s*a\s*g\s*e")
JUNK = re.compile(r"sachphotos|superingenious|^\s*\d+\s*\|\s*Page", re.I)


def open_pdf(path):
    return pymupdf.open(path)


def find_heads(doc):
    """{test number: (page number, y)} for the 'TEST n' headings (pages 5+) and 27 = SOLUTION."""
    heads = {}
    for pn, page in enumerate(doc, 1):
        if pn < 5:
            continue
        for b in page.get_text("blocks"):
            t = b[4].strip()
            m = re.match(r"^TEST\s*(\d+)$", t)
            if m and int(m.group(1)) not in heads:
                heads[int(m.group(1))] = (pn, b[1])
            if t == "SOLUTION" and 27 not in heads:
                heads[27] = (pn, b[1])
    return heads


def page_lines(page, top, bottom):
    """Lines of one page between top and bottom: [{y0, y1, x0, text, words:[(x0, x1, text)]}]."""
    words = page.get_text("words")  # x0, y0, x1, y1, text, block, line, wordno
    rows = {}
    for w in words:
        if w[1] < top or w[3] > bottom:
            continue
        rows.setdefault((w[5], w[6]), []).append(w)
    out = []
    for ws in rows.values():
        ws.sort(key=lambda w: w[0])
        text = " ".join(w[4] for w in ws)
        out.append(
            {
                "y0": min(w[1] for w in ws),
                "y1": max(w[3] for w in ws),
                "x0": ws[0][0],
                "x1": ws[-1][2],
                "text": text,
                "words": [(w[0], w[2], w[4]) for w in ws],
            }
        )
    out.sort(key=lambda l: (round(l["y0"]), l["x0"]))
    # separate PDF lines on the same row (an option letter and its text, a form label and its value) are one line
    merged = []
    for ln in out:
        if merged and abs(ln["y0"] - merged[-1]["y0"]) < 3 and ln["x0"] >= merged[-1]["x1"] - 1:
            m = merged[-1]
            m["text"] += " " + ln["text"]
            m["x1"] = max(m["x1"], ln["x1"])
            m["y1"] = max(m["y1"], ln["y1"])
            m["words"] += ln["words"]
        else:
            merged.append(ln)
    return merged


def footer_top(page):
    tops = [b[1] for b in page.get_text("blocks") if FOOTER.match(b[4].strip())]
    return min(tops) - 4 if tops else page.rect.height - 30


def test_lines(doc, heads, n):
    """All lines of test n in reading order, each with its page number: [{page, ...}]."""
    (p0, y0), (p1, y1) = heads[n], heads[n + 1]
    res = []
    for pn in range(p0, p1 + 1):
        page = doc[pn - 1]
        top = y0 - 2 if pn == p0 else 20
        bottom = footer_top(page)
        if pn == p1:
            bottom = min(bottom, y1 - 2)
        if bottom - top < 8:
            continue
        for ln in page_lines(page, top, bottom):
            if JUNK.search(ln["text"]):
                continue
            ln["page"] = pn
            res.append(ln)
    return res


if __name__ == "__main__":
    doc = open_pdf(sys.argv[1])
    heads = find_heads(doc)
    for ln in test_lines(doc, heads, int(sys.argv[2])):
        print(f'p{ln["page"]} y{ln["y0"]:6.1f} x{ln["x0"]:5.1f}  {ln["text"]}')
