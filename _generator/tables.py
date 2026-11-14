# Rebuilds the tables of the question book as HTML tables, from the cell borders the PDF draws.
# Used by parse_questions.py for blocks that would otherwise be pictures. Returns None when a block is not a
# clean table (a cell shape that is not a rectangle, a word beside the table ...), so the caller falls back to
# the picture and no question is ever lost.
import pymupdf

TOL = 3.0


def _cluster(values, tol=TOL):
    out = []
    for v in sorted(values):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(c) / len(c) for c in out]


def _segments(page, top, bottom):
    """Thin horizontal and vertical rectangles inside [top, bottom], keeping only those that touch each other."""
    hs, vs = [], []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] != "re":
                continue
            r = it[1]
            if r.y1 < top - 2 or r.y0 > bottom + 2:
                continue
            if r.height < 3 and r.width > 15:
                hs.append((r.x0, r.x1, (r.y0 + r.y1) / 2))
            elif r.width < 3 and r.height > 5:
                vs.append(((r.x0 + r.x1) / 2, r.y0, r.y1))
    keep_h = [h for h in hs if any(h[0] - TOL <= v[0] <= h[1] + TOL and v[1] - TOL <= h[2] <= v[2] + TOL for v in vs)]
    keep_v = [v for v in vs if any(h[0] - TOL <= v[0] <= h[1] + TOL and v[1] - TOL <= h[2] <= v[2] + TOL for h in hs)]
    return keep_h, keep_v


def _covered(intervals, a, b):
    """True if the intervals together cover [a, b]."""
    pos = a
    for x0, x1 in sorted(intervals):
        if x0 <= pos + TOL:
            pos = max(pos, x1)
    return pos >= b - TOL


def _bold_cells(page, rect):
    spans = []
    for blk in page.get_text("dict", clip=rect)["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln["spans"]:
                if sp["text"].strip():
                    spans.append(sp)
    return bool(spans) and all((sp["flags"] & 16) or "bold" in sp["font"].lower() for sp in spans)


def _components(hs, vs):
    """Groups of segments that touch each other, largest first: [(hs, vs)]."""
    segs = [("h", h) for h in hs] + [("v", v) for v in vs]
    parent = list(range(len(segs)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i, (ki, si) in enumerate(segs):
        if ki != "h":
            continue
        for j, (kj, sj) in enumerate(segs):
            if kj == "v" and si[0] - TOL <= sj[0] <= si[1] + TOL and sj[1] - TOL <= si[2] <= sj[2] + TOL:
                parent[find(j)] = find(i)
    for i in range(len(segs)):  # pieces of one line, end to end
        for j in range(i + 1, len(segs)):
            (ki, si), (kj, sj) = segs[i], segs[j]
            if ki != kj:
                continue
            if ki == "v" and abs(si[0] - sj[0]) <= TOL and si[1] - TOL <= sj[2] and sj[1] - TOL <= si[2]:
                parent[find(j)] = find(i)
            if ki == "h" and abs(si[2] - sj[2]) <= TOL and si[0] - TOL <= sj[1] and sj[0] - TOL <= si[1]:
                parent[find(j)] = find(i)
    groups = {}
    for i, (k, sg) in enumerate(segs):
        groups.setdefault(find(i), ([], []))[0 if k == "h" else 1].append(sg)
    return sorted(groups.values(), key=lambda g: -(len(g[0]) + len(g[1])))


def _grid(hs, vs):
    """(xs, ys, cells) for one connected group of segments, or None. cells = [(r0, r1, c0, c1)]."""
    xs = _cluster([v[0] for v in vs])
    ys = _cluster([h[2] for h in hs])
    if len(xs) < 2 or len(ys) < 2:
        return None
    rows, cols = len(ys) - 1, len(xs) - 1

    def hedge(i, c):  # border between row i-1 and row i, across column c
        iv = [(h[0], h[1]) for h in hs if abs(h[2] - ys[i]) <= TOL]
        return _covered(iv, xs[c] + 2, xs[c + 1] - 2)

    def vedge(r, j):
        iv = [(v[1], v[2]) for v in vs if abs(v[0] - xs[j]) <= TOL]
        return _covered(iv, ys[r] + 2, ys[r + 1] - 2)

    parent = {(r, c): (r, c) for r in range(rows) for c in range(cols)}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols and not vedge(r, c + 1):
                parent[find((r, c + 1))] = find((r, c))
            if r + 1 < rows and not hedge(r + 1, c):
                parent[find((r + 1, c))] = find((r, c))
    groups = {}
    for key in parent:
        groups.setdefault(find(key), []).append(key)
    cells = []
    for members in groups.values():
        rs = [m[0] for m in members]
        cs = [m[1] for m in members]
        r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
        if len(members) != (r1 - r0 + 1) * (c1 - c0 + 1):
            return None
        cells.append((r0, r1, c0, c1))
    return xs, ys, sorted(cells)


def find_tables(doc, ranges):
    """The tables in the block's ranges, in reading order: [(page number, page, xs, ys, cells)].
    [] means no table is drawn; None means a drawn grid cannot be read as a table."""
    out = []
    for pn, y0, y1 in ranges:
        page = doc[pn - 1]
        hs, vs = _segments(page, y0, y1)
        if len(vs) < 2 or len(hs) < 2:
            continue
        comps = [c for c in _components(hs, vs) if len(c[0]) >= 3 and len(c[1]) >= 3]
        # pieces of one table that a missing border cut apart (an empty thin row) are joined again
        def box(c):
            xs_ = [v[0] for v in c[1]]
            ys_ = [h[2] for h in c[0]]
            return min(xs_), max(xs_), min(ys_), max(ys_)

        comps.sort(key=lambda c: box(c)[2])
        merged = []
        for c in comps:
            if merged:
                a, b = box(merged[-1]), box(c)
                if abs(a[0] - b[0]) < 6 and abs(a[1] - b[1]) < 6 and b[2] - a[3] <= 25:
                    merged[-1] = (merged[-1][0] + c[0], merged[-1][1] + c[1])
                    continue
            merged.append(c)
        for main in merged:
            g = _grid(*main)
            if g is None:
                return None
            out.append((pn, page) + g)
    return out


def tables_html(doc, ranges, lines, gaps_in, fix_text):
    """[{page, top, bottom, html, nums}] for the tables of a block (lines = its text lines, with words), or None."""
    tabs = find_tables(doc, ranges)
    if tabs is None:
        return None
    res = []
    for pn, page, xs, ys, cells in tabs:
        top, bottom, left, right = ys[0] - 2, ys[-1] + 2, xs[0] - 2, xs[-1] + 2
        owner = {}
        for idx, (r0, r1, c0, c1) in enumerate(cells):
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    owner[(r, c)] = idx
        words = {i: [] for i in range(len(cells))}
        for ln in lines:
            if ln["page"] != pn:
                continue
            yc = (ln["y0"] + ln["y1"]) / 2
            if not top <= yc <= bottom:
                continue
            for x0, x1, txt in ln["words"]:
                xc = (x0 + x1) / 2
                if not left <= xc <= right:
                    return None  # text beside the table
                r = next((i for i in range(len(ys) - 1) if ys[i] - 2 <= yc <= ys[i + 1] + 2), None)
                c = next((i for i in range(len(xs) - 1) if xs[i] - 2 <= xc <= xs[i + 1] + 2), None)
                if r is None or c is None:
                    return None
                words[owner[(r, c)]].append((ln["y0"], x0, txt))
        nums = []
        first = {}
        for idx, (r0, r1, c0, c1) in enumerate(cells):
            text_lines = []
            last_y = None
            for y, x, txt in sorted(words[idx]):
                if last_y is None or abs(y - last_y) > 3:
                    text_lines.append([txt])
                else:
                    text_lines[-1].append(txt)
                last_y = y
            parts = []
            for tl in text_lines:
                s = fix_text(" ".join(tl))
                if parts and not s.startswith(("- ", "• ", "● ")):
                    parts[-1] += " " + s
                else:
                    parts.append(s)
            htmls = []
            for s in parts:
                bullet = s.startswith(("- ", "• ", "● "))
                h, found = gaps_in(s[2:].lstrip() if bullet else s)
                nums.extend(found)
                htmls.append(("• " if bullet else "") + h)
            rect = pymupdf.Rect(xs[c0] + 1, ys[r0] + 1, xs[c1 + 1] - 1, ys[r1 + 1] - 1)
            head = bool(htmls) and not any("class=" in h for h in htmls) and _bold_cells(page, rect)
            tag = "th" if head else "td"
            attrs = ""
            if c1 > c0:
                attrs += f' colspan="{c1 - c0 + 1}"'
            if r1 > r0:
                attrs += f' rowspan="{r1 - r0 + 1}"'
            first[(r0, c0)] = f"<{tag}{attrs}>{'<br>'.join(htmls)}</{tag}>"
        body = []
        for r in range(len(ys) - 1):
            row = "".join(first[(r, c)] for c in range(len(xs) - 1) if (r, c) in first)
            if row.endswith("></td>") and row.count("<td") == 1 and "<th" not in row and "rowspan" not in row:
                continue  # an empty spacer row
            body.append(f"<tr>{row}</tr>")
        html_out = '<div class="tablewrap"><table class="qtable">' + "".join(body) + "</table></div>"
        res.append({"page": pn, "top": top, "bottom": bottom, "html": html_out, "nums": nums})
    return res
