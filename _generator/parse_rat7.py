# Recent Actual Tests Vol 7 (6 tests): reads the answer key from the Vietnamese solution guide and copies the
# MP3s, then writes data/rat7.json. The question book comes from parse_questions.py --guide.
# Usage: python -X utf8 -I _generator/parse_rat7.py "<guide .pdf>" "<folder with AUDIO/TEST n/Part k.mp3>"
import json
import pathlib
import re
import shutil
import sys

import pymupdf

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lines as L  # noqa: E402

GUIDE = pathlib.Path(sys.argv[1])
AUDIO = pathlib.Path(sys.argv[2])
KEY_PAGES = range(238, 244)  # ANSWER KEY: one page per test (1-based)

# Typos or extra accepted forms in the guide's key: (test, question) -> replacement key text.
# (test.js splits alternatives at a slash, but not one that follows a digit, and it cannot tell "centre/center"
# from two separate answers, so these are written out in full.)
FIXES = {
    (1, 9): "6 / six",
    (3, 18): "2.30 / 2:30",
    (3, 36): "conference centre / conference center",
    (5, 3): "40 / forty",
    (5, 29): "17 / 17th February",
    (5, 30): "senior adviser / senior advisor",
}


def column_rows(page, x_from, x_to):
    rows = []
    for ln in L.page_lines(page, 90, 700):
        ws = [w for w in ln["words"] if x_from <= w[0] < x_to]
        if ws:
            rows.append(ws)
    return rows


def parse_page(page):
    key = {}
    groups = []
    for x_from, x_to in ((60, 305), (305, 700)):
        pending = None  # a "21&22" line: the second letter is on the next row
        for ws in column_rows(page, x_from, x_to):
            first = ws[0][2]
            m = re.match(r"^(\d{1,2})&(\d{1,2})$", first)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                rest = [w[2] for w in ws[1:]]
                letter = rest[0]
                key[a] = letter
                pending = (a, b)
                continue
            if pending and not re.match(r"^\d{1,2}$", first):
                a, b = pending
                key[b] = ws[0][2]
                groups.append([a, b])
                pending = None
                continue
            if re.match(r"^\d{1,2}$", first):
                key[int(first)] = " ".join(w[2] for w in ws[1:])
    return key, groups


def main():
    doc = pymupdf.open(GUIDE)
    out = []
    for n, pn in enumerate(KEY_PAGES, 1):
        key, groups = parse_page(doc[pn - 1])
        for (t, q), text in FIXES.items():
            if t == n:
                key[q] = text
        assert sorted(key) == list(range(1, 41)), f"test {n}: key incomplete {sorted(set(range(1, 41)) - set(key))}"
        assert all(key[q] for q in key), f"test {n}: empty answer"
        grp = {}
        for g in groups:
            for q in g:
                grp[q] = g[0]
        entries = [dict({"n": q, "ans": key[q]}, **({"grp": grp[q]} if q in grp else {})) for q in range(1, 41)]
        audio = []
        for part in range(1, 5):
            src = AUDIO / "AUDIO" / f"TEST {n}" / f"Part {part}.mp3"
            assert src.exists(), src
            dst = ROOT / "audio" / f"rat7-test-{n}-part-{part}.mp3"
            if not dst.exists():
                shutil.copyfile(src, dst)
            audio.append({"label": f"Section {part}", "file": f"audio/{dst.name}"})
        out.append({"n": n, "id": f"rat7-{n}", "audio": audio, "key": entries})
    (ROOT / "data" / "rat7.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"{len(out)} tests, groups: {[(t['n'], sorted({k['grp'] for k in t['key'] if 'grp' in k})) for t in out if any('grp' in k for k in t['key'])]}")


main()
