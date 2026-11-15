# Builds index.html and test-01.html ... test-26.html from data/tests.json (made by parse_sources.py).
# Run: python -X utf8 -I _generator/build.py   (paths are relative to this file)
import html
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import inline  # noqa: E402  (puts the answer controls into the questions)

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = json.loads((ROOT / "data" / "tests.json").read_text(encoding="utf-8"))
QUESTIONS = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))  # made by parse_questions.py
RAT7 = json.loads((ROOT / "data" / "rat7.json").read_text(encoding="utf-8"))  # made by parse_rat7.py
RAT7_QUESTIONS = json.loads((ROOT / "data" / "rat7-questions.json").read_text(encoding="utf-8"))  # parse_questions.py --guide
RAT7_INDEX = "recent-actual-test-7.html"
e = html.escape

TOPBAR = """<nav class="topbar" aria-label="IELTS Harper">
  <div class="topbar-inner">
    <a class="brand" href="https://ieltsharper.github.io/portal/"><span class="brand-mark" aria-hidden="true">IH</span>IELTS Harper Portal</a>
    {extra}<a class="topbar-link" href="https://ieltsharper.github.io/portal/">&larr; Back to the portal</a>
  </div>
</nav>"""

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="theme.css">
  <link rel="stylesheet" href="test.css">
</head>
<body>
"""


def question_book(t, rat7=False):
    """The question book as text, one part per section with that section's recording on top and the answer
    controls inside the questions; blocks that cannot be text (maps, diagrams, tables) are pictures with an
    answer row under them."""
    n = t["n"]
    out = []
    what = "Recent Actual Test 7, Listening Test" if rat7 else "Listening Test"
    blocks = (RAT7_QUESTIONS if rat7 else QUESTIONS)[str(n)]
    assert len(t["audio"]) == 4 and sum(b["type"] == "section" for b in blocks) == 4, f"test {n}"
    if not rat7:
        blocks = inline.repair(n, blocks)  # option lists the PDF text broke
    blocks = inline.tidy(blocks)  # instruction pieces back into the instruction; mark the title line
    controls = inline.render(blocks, t["key"])
    for i, b in enumerate(blocks):
        if b["type"] == "section":
            s = b["n"]
            if s > 1:
                out.append("</section>")
            out.append(
                f'<section class="qsec" aria-labelledby="sec-h-{s}">'
                f'<div class="qsec-head"><h3 class="qsection" id="sec-h-{s}">Section {s}'
                f'<span class="qrange">Questions {s * 10 - 9}–{s * 10}</span></h3>'
                f'<span class="sec-score" id="sec-{s - 1}"></span></div>'
                f'<div class="track"><audio controls preload="none" src="{t["audio"][s - 1]["file"]}" '
                f'aria-label="Section {s} recording"></audio></div>'
            )
            continue
        rng = f'Questions {b["from"]}–{b["to"]}' if b["to"] != b["from"] else f'Question {b["from"]}'
        body, strip = controls[i]
        if b["mode"] == "image":
            out.append(
                f'<div class="qblock qblock-img"><a class="paper" href="img/{b["image"]}" target="_blank" rel="noopener">'
                f'<img src="img/{b["image"]}" alt="{rng} of {what} {n}, shown as a picture because it has a map, '
                f'diagram, table or flow chart." loading="lazy"></a>{strip}</div>'
            )
            continue
        sentences = []
        for x in b["inst"]:  # an instruction line that does not end with a full stop continues on the next
            if sentences and not re.search(r"[.?!:]$", sentences[-1]):
                sentences[-1] += " " + x
            elif sentences and re.match(r"^[a-z]", x):
                sentences[-1] += " " + x
            else:
                sentences.append(x)
        inst = "".join(f'<p class="qinst">{e(x)}</p>' for x in sentences)
        out.append(f'<div class="qblock"><h4>{rng}</h4>{inst}<div class="qbody">{body}</div>{strip}</div>')
    out.append("</section>")
    return "\n".join(out)


TAPE_SECTION = """  <section class="card tapescript" id="tape-card" aria-labelledby="t-title" hidden>
    <h2 class="section-title" id="t-title">Tapescript</h2>
    <p id="tape-locked" hidden></p>
    <button type="button" id="btn-tape">Show tapescript</button>
    <div id="tape-body" hidden></div>
  </section>
"""


def page(t, rat7=False):
    n = t["n"]
    data = {"n": n, "key": t["key"]}
    if rat7:  # no tapescript in this book; the page is told which set it belongs to
        data.update({"id": t["id"], "set": "rat7"})
    else:
        data["tapescript"] = t["tapescript"]
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    last = len(RAT7) if rat7 else 26
    href = (lambda k: f"rat7-test-{k}.html") if rat7 else (lambda k: f"test-{k:02d}.html")
    prev_link = f'<a class="topbar-link" href="{href(n - 1)}">&larr; Test {n - 1}</a>\n    ' if n > 1 else ""
    next_link = f'<a class="topbar-link" href="{href(n + 1)}">Test {n + 1} &rarr;</a>\n    ' if n < last else ""
    extra = (
        f'<a class="topbar-link" href="{RAT7_INDEX}">Recent Actual Test 7</a>\n    '
        if rat7
        else '<a class="topbar-link" href="./">All tests</a>\n    '
    ) + prev_link + next_link
    heading = f"Recent Actual Test 7 &middot; Listening Test {n}" if rat7 else f"IELTS Listening: Test {n}"
    how = (
        "Then press <strong>Check answers</strong> to see your score and your estimated band."
        if rat7
        else "Then press <strong>Check answers</strong> to see your\n      score and your estimated band, and read the tapescript to see where each answer came from."
    )
    return (
        HEAD.format(title=e(f"{'Recent Actual Test 7 · ' if rat7 else ''}Listening Test {n} – IELTS Harper")).replace(
            "</head>", '  <link rel="stylesheet" href="ih-annotate.css">' + chr(10) + "</head>", 1
        )
        + TOPBAR.format(extra=extra)
        + f"""
<main class="container">
  <header>
    <h1>{heading}</h1>
    <p class="meta">4 sections &middot; 40 questions</p>
    <div class="instructions">
      Each section has its own recording at the top. In the exam you hear a section <strong>once</strong>, so try a
      first listen without pausing. Answer in the questions themselves: type in the gaps, choose a letter, or tick the
      boxes. Maps, diagrams and some tables are pictures; their answers go in the <em>Your answers</em> row under them.
      {how}
    </div>
  </header>

  <section class="card" aria-labelledby="q-title">
    <h2 class="section-title" id="q-title">Listening and questions</h2>
    <div class="qbook" id="qbook">
{question_book(t, rat7)}
    </div>
  </section>

  <section class="card" aria-labelledby="sheet-title">
    <h2 class="section-title" id="sheet-title">Check your answers</h2>
    <div class="controls">
      <button type="button" class="btn-check" id="btn-check">Check answers</button>
      <button type="button" id="btn-answers">Show answers</button>
      <button type="button" class="btn-reset" id="btn-reset">Clear all</button>
    </div>
    <div class="result" id="result" aria-live="polite" hidden></div>
    <p class="plain portal-note" id="portal-note" aria-live="polite" hidden></p>
    <p class="plain hint">Marking ignores capital letters and accepts plurals and the usual alternative answers. If your answer is right but not accepted, press <em>My answer is also right</em> under it.</p>
  </section>

{"" if rat7 else TAPE_SECTION}</main>

<script id="test" type="application/json">{blob}</script>
<script src="test.js"></script>
<script src="ih-annotate.js" data-roots=".qblock, #tape-body" data-skip=".fb, .fbs, .gn, .sec-score"></script>
</body>
</html>
"""
    )


INDEX_SCRIPT = """
<script>
// Shows the result each student saved in this browser next to the test.
for (const a of document.querySelectorAll('a[data-test]')) {
  try {
    const saved = JSON.parse(localStorage.getItem('ih-listening-test:' + a.dataset.test) || 'null');
    if (saved && saved.r) a.querySelector('[data-result]').textContent = ' · ' + saved.r.score + ' / 40, band ' + saved.r.band;
  } catch (e) {
    /* no saved result */
  }
}
</script>
"""


def index():
    def group(title, rng):
        rows = "\n".join(
            f'    <li><a href="test-{n:02d}.html" data-test="{n:02d}">Test {n}'
            f'<span class="meta-inline">'
            f'4 audio sections &middot; 40 questions'
            f'<span class="done" data-result></span></span></a></li>'
            for n in rng
        )
        return f'  <h2 class="group-title">{title}</h2>\n  <ul class="menu-list">\n{rows}\n  </ul>\n'

    script = INDEX_SCRIPT
    return (
        HEAD.format(title="IELTS Listening – 26 Actual Tests – IELTS Harper")
        + TOPBAR.format(extra="")
        + f"""
<main class="container">
  <header>
    <h1>IELTS Listening: 26 Actual Tests</h1>
    <div class="summary">26 full tests with a recording for each section, self-marking questions and tapescript</div>
    <div class="instructions">
      Choose a test. Listen to each section and answer in the questions, then check your answers to see your score
      and your estimated band, and read the tapescript. Your answers are kept in this browser.
    </div>
  </header>

{group("Tests 1–10", range(1, 11))}{group("Tests 11–15", range(11, 16))}{group("Tests 16–26", range(16, 27))}  <h2 class="group-title">Recent Actual Test 7</h2>
  <ul class="menu-list">
    <li><a href="{RAT7_INDEX}">Recent Actual Tests Vol 7 (Tests 1–6)<span class="meta-inline">6 full tests with audio &middot; 40 questions each</span></a></li>
  </ul>
</main>
{script}</body>
</html>
"""
    )


def rat7_index():
    rows = "\n".join(
        f'    <li><a href="rat7-test-{t["n"]}.html" data-test="{t["id"]}">Test {t["n"]}'
        f'<span class="meta-inline">4 audio sections &middot; 40 questions'
        f'<span class="done" data-result></span></span></a></li>'
        for t in RAT7
    )
    return (
        HEAD.format(title="Recent Actual Test 7 – IELTS Listening – IELTS Harper")
        + TOPBAR.format(extra='<a class="topbar-link" href="./">All Listening tests</a>\n    ')
        + f"""
<main class="container">
  <header>
    <h1>Recent Actual Test 7: Listening</h1>
    <div class="summary">6 full tests (IELTS Recent Actual Tests Vol 7) with a recording for each section and self-marking questions</div>
    <div class="instructions">
      Choose a test. Listen to the four sections and answer in the questions, then check your answers to see your
      score and your estimated band. Your answers are kept in this browser.
    </div>
  </header>

  <ul class="menu-list">
{rows}
  </ul>
</main>
{INDEX_SCRIPT}</body>
</html>
"""
    )


def main():
    for t in TESTS:
        (ROOT / f"test-{t['n']:02d}.html").write_text(page(t), encoding="utf-8", newline="\n")
    for t in RAT7:
        (ROOT / f"rat7-test-{t['n']}.html").write_text(page(t, rat7=True), encoding="utf-8", newline="\n")
    (ROOT / RAT7_INDEX).write_text(rat7_index(), encoding="utf-8", newline="\n")
    (ROOT / "index.html").write_text(index(), encoding="utf-8", newline="\n")
    print(f"Built index.html, {len(TESTS)} test pages, {len(RAT7)} Recent Actual Test 7 pages and {RAT7_INDEX}.")


main()
