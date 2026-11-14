# Reads the teacher's source folder (answer key PDF, tapescript PDFs, MP3s) and writes data/tests.json
# and audio/*.mp3 for the site. Needs poppler's pdftotext on the PATH.
# Usage: python -X utf8 -I _generator/parse_sources.py "<source folder>"
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = pathlib.Path(sys.argv[1])
BOOK = SRC / "IELTS Listening Actual Tests and Answers.pdf"

# Question numbers that are answered together ("Choose TWO/THREE letters"): the letters may be given in any order.
GROUPS = {
    1: [[37, 38], [39, 40]],
    3: [[21, 22]],
    4: [[39, 40]],
    5: [[29, 30]],
    6: [[6, 7, 8], [16, 17, 18], [19, 20]],
    8: [[8, 9, 10], [38, 39, 40]],
    10: [[11, 12]],
    11: [[27, 28], [29, 30], [33, 34]],
    13: [[16, 17], [18, 19]],
    16: [[11, 12, 13], [14, 15], [24, 25]],
    19: [[18, 19, 20]],
    20: [[21, 22, 23], [24, 25]],
    21: [[19, 20]],
    22: [[8, 9, 10], [21, 22], [28, 29, 30]],
    24: [[15, 16]],
    26: [[26, 27], [28, 29, 30]],
}

# Typos or extra accepted forms in the book's key: (test, question) -> replacement key text.
FIXES = {
    (17, 25): "skill(s)",
    (16, 3): "10 thousand / 10,000",
}


def pdf_text(path, layout=False):
    args = ["pdftotext", "-enc", "UTF-8"] + (["-layout"] if layout else []) + [str(path), "-"]
    return subprocess.run(args, check=True, capture_output=True).stdout.decode("utf-8")


def parse_key():
    lines = pdf_text(BOOK, layout=True).split("\n")
    start = next(i for i, l in enumerate(lines) if l.strip() == "SOLUTION" and i > 4000)
    tests, cur, prev = [], None, 0
    for l in lines[start:]:
        l = re.sub(r"\d+\s*\|\s*P\s*a\s*g\s*e", "", l).replace("superingenious.com", "").strip()
        m = re.match(r"^(\d{1,2})\s*\.\s*(?:\1\s*\.\s*)?(.*)$", l)
        if m:
            n, a = int(m.group(1)), m.group(2).strip()
            if n == 1 and (cur is None or prev >= 30):
                cur = {}
                tests.append(cur)
            cur[n] = a
            prev = n
    assert len(tests) == 26 and all(sorted(t) == list(range(1, 41)) for t in tests), "key not complete"
    return tests


def tapescript_path(n):
    folder = SRC / "Tapescripts"
    for f in folder.glob("*.pdf"):
        m = re.search(r"(?:Test|test)\s*(\d+)", f.name)
        if m and int(m.group(1)) == n:
            return f
    raise SystemExit(f"no tapescript for test {n}")


JUNK = re.compile(r"sachphotos|superingenious|tổng hợp tài liệu|^\s*\d+\s*$", re.I)


def tapescript(n):
    text = pdf_text(tapescript_path(n)).replace("\r", "")
    lines = [l.strip() for l in text.split("\n") if l.strip() and not JUNK.search(l)]
    # speaker labels that occur at least twice are used to break text that was run together
    labels = {}
    for l in lines:
        for m in re.finditer(r"(?:^|(?<=[.?!…”’\"')\]]\s))([A-Z][A-Za-z.']{1,14}(?: [A-Z][a-z]+)?):\s", l):
            labels[m.group(1)] = labels.get(m.group(1), 0) + 1
    speakers = [s for s, c in labels.items() if c >= 3 and s not in ("Note", "Section", "Part", "Question", "Questions")]
    paras = []
    for l in lines:
        if len(l) > 300 and speakers:
            pat = r"(?<=[.?!…”’\"')\]])\s+(?=(?:" + "|".join(re.escape(s) for s in speakers) + r"):\s)"
            paras.extend(p.strip() for p in re.split(pat, l) if p.strip())
        else:
            paras.append(l)
    # drop the book's own title text (some PDFs carry the wrong test number in it)
    for i in range(min(2, len(paras))):
        paras[i] = re.sub(r"^(?:Transcript for test \d+|Listening [Tt]est \d+|Test \d+)\s*", "", paras[i]).strip()
    return [p for p in paras if p]


def audio_for(n):
    base = SRC / "Audio"
    out = ROOT / "audio"
    out.mkdir(exist_ok=True)
    tracks = []
    if n <= 10:
        src = base / "Test 1- 10" / ("Test - 3.mp3" if n == 3 else f"Test-{n}.mp3")
        tracks.append(("Whole test", src, f"test-{n:02d}.mp3"))
    elif n <= 15:
        folder = base / "Tests 11-15" / "Tests 11-15" / f"TEST {n}"
        for s in range(1, 5):
            src = folder / f"Section {s}.mp3"
            if not src.exists():
                src = folder / f"Section{s}.mp3"
            tracks.append((f"Section {s}", src, f"test-{n:02d}-s{s}.mp3"))
    else:
        tracks.append(("Whole test", base / "Tests 16-26" / f"Test {n}.mp3", f"test-{n:02d}.mp3"))
    result = []
    for label, src, name in tracks:
        assert src.exists(), src
        dst = out / name
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copyfile(src, dst)
        result.append({"label": label, "file": f"audio/{name}"})
    return result


def main():
    key = parse_key()
    images = json.loads((ROOT / "_generator" / "images.json").read_text(encoding="utf-8"))
    tests = []
    for n in range(1, 27):
        groups = GROUPS.get(n, [])
        in_group = {q: g for g in groups for q in g}
        items = []
        for q in range(1, 41):
            ans = FIXES.get((n, q), key[n - 1][q])
            item = {"n": q, "ans": ans}
            if q in in_group:
                item["grp"] = in_group[q][0]
            items.append(item)
        tests.append(
            {
                "n": n,
                "image": images[str(n)][0],
                "audio": audio_for(n),
                "key": items,
                "tapescript": tapescript(n),
            }
        )
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "tests.json").write_text(json.dumps(tests, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote data/tests.json for", len(tests), "tests")


main()
