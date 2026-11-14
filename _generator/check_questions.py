# Checks data/questions.json against the source PDF: every word of every text block's source lines is in the
# rendered text, every test's 40 question numbers are covered, and every image block's file exists.
# Also deletes img/tNN-bK.webp files that no block uses any more.
# Usage: python -X utf8 -I _generator/check_questions.py "<IELTS Listening Actual Tests and Answers.pdf>"
import collections
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.argv_pdf = sys.argv[1]
src = (ROOT / "_generator" / "parse_questions.py").read_text(encoding="utf-8").replace("\nmain()\n", "\n")
g = {"__file__": str(ROOT / "_generator" / "parse_questions.py"), "__name__": "pq"}
exec(compile(src, "pq", "exec"), g)
L = g["L"]

doc = L.open_pdf(sys.argv_pdf)
heads = L.find_heads(doc)
Q = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))
tok = lambda s: collections.Counter(re.findall(r"[A-Za-z]{2,}|\d+", s))  # noqa: E731
problems = 0
checked = 0
for n in range(1, 27):
    items = g["split_blocks"](L.test_lines(doc, heads, n))
    blocks = [it for it in items if it[0] == "block"]
    cov = []
    for b in Q[str(n)]:
        if b["type"] != "block":
            continue
        cov += range(b["from"], b["to"] + 1)
        if b["mode"] == "image":
            if not (ROOT / "img" / b["image"]).exists():
                print("missing image", n, b["image"])
                problems += 1
            continue
        cand = [it for it in blocks if it[1] == (b["from"], b["to"])]
        if not cand:
            print("no source block", n, b["from"], b["to"])
            problems += 1
            continue
        lost = tok(" ".join(l["t"] for l in cand[0][3])) - tok(
            " ".join(b["inst"]) + " " + re.sub(r"<[^>]+>", " ", html.unescape(b["html"]))
        )
        checked += 1
        if lost:
            print("words lost", n, (b["from"], b["to"]), dict(lost))
            problems += 1
    missing = sorted(set(range(1, 41)) - set(cov))
    if missing:
        print("test", n, "numbers in no block (check they are inside an image):", missing)
used = {b["image"] for bl in Q.values() for b in bl if b.get("mode") == "image"}
gone = [f for f in (ROOT / "img").glob("t??-b*.webp") if f.name not in used]
for f in gone:
    f.unlink()
print(f"text blocks checked: {checked}, problems: {problems}, unused block images deleted: {len(gone)}")
