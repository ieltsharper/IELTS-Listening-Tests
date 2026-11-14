# Builds index.html and test-01.html ... test-26.html from data/tests.json (made by parse_sources.py).
# Run: python -X utf8 -I _generator/build.py   (paths are relative to this file)
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = json.loads((ROOT / "data" / "tests.json").read_text(encoding="utf-8"))
QUESTIONS = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))  # made by parse_questions.py
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


def question_book(n):
    """The question book as text; blocks that cannot be text (maps, diagrams, tables) are pictures."""
    out = []
    for b in QUESTIONS[str(n)]:
        if b["type"] == "section":
            out.append(f'<h3 class="qsection">Section {b["n"]}</h3>')
            continue
        rng = f'Questions {b["from"]}–{b["to"]}' if b["to"] != b["from"] else f'Question {b["from"]}'
        if b["mode"] == "image":
            out.append(
                f'<div class="qblock qblock-img"><a class="paper" href="img/{b["image"]}" target="_blank" rel="noopener">'
                f'<img src="img/{b["image"]}" alt="{rng} of Listening Test {n}, shown as a picture because it has a map, '
                f'diagram, table or flow chart." loading="lazy"></a></div>'
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
        out.append(f'<div class="qblock"><h4>{rng}</h4>{inst}<div class="qbody">{b["html"]}</div></div>')
    return "\n".join(out)


def page(t):
    n = t["n"]
    blob = json.dumps(
        {"n": n, "key": t["key"], "tapescript": t["tapescript"]}, ensure_ascii=False, separators=(",", ":")
    ).replace("</", "<\\/")
    tracks = "\n".join(
        f'      <div class="track"><span class="track-label">{e(a["label"])}</span>'
        f'<audio controls preload="none" src="{a["file"]}"></audio></div>'
        for a in t["audio"]
    )
    if len(t["audio"]) == 1:
        note = (
            "This is the whole test, in one recording. In the exam you hear it <strong>once</strong>, "
            "so try a first listen without pausing."
        )
    else:
        note = (
            "The recording is split into the four sections. In the exam you hear each one <strong>once</strong>, "
            "so try a first listen without pausing."
        )
    prev_link = f'<a class="topbar-link" href="test-{n - 1:02d}.html">&larr; Test {n - 1}</a>\n    ' if n > 1 else ""
    next_link = f'<a class="topbar-link" href="test-{n + 1:02d}.html">Test {n + 1} &rarr;</a>\n    ' if n < 26 else ""
    extra = '<a class="topbar-link" href="./">All tests</a>\n    ' + prev_link + next_link
    return (
        HEAD.format(title=e(f"Listening Test {n} – IELTS Harper"))
        + TOPBAR.format(extra=extra)
        + f"""
<main class="container">
  <header>
    <h1>IELTS Listening: Test {n}</h1>
    <p class="meta">4 sections &middot; 40 questions</p>
    <div class="instructions">
      Play the audio and read the questions in the question book below (maps, diagrams and tables are pictures). Type your answers on the answer sheet
      (for the lettered questions, choose the letter). Then press <strong>Check answers</strong> to see your
      score and your estimated band, and read the tapescript to see where each answer came from.
    </div>
  </header>

  <section class="card" aria-labelledby="audio-title">
    <h2 class="section-title" id="audio-title">Audio</h2>
    <div>
{tracks}
    </div>
    <p class="plain audio-note">{note}</p>
  </section>

  <section class="card" aria-labelledby="q-title">
    <h2 class="section-title" id="q-title">Question book</h2>
    <div class="qbook">
{question_book(n)}
    </div>
    <details class="original">
      <summary>Show the original book pages (picture)</summary>
      <a class="paper" href="img/{t['image']}" target="_blank" rel="noopener">
        <img src="img/{t['image']}" alt="The question book for Listening Test {n}: Sections 1 to 4, Questions 1 to 40." loading="lazy">
      </a>
      <p class="plain hint">Tap or click the pages to open them full size in a new tab.</p>
    </details>
  </section>

  <section class="card" aria-labelledby="sheet-title">
    <h2 class="section-title" id="sheet-title">Answer sheet</h2>
    <div id="sheet"></div>
    <div class="controls">
      <button type="button" class="btn-check" id="btn-check">Check answers</button>
      <button type="button" id="btn-answers">Show answers</button>
      <button type="button" class="btn-reset" id="btn-reset">Clear all</button>
    </div>
    <div class="result" id="result" aria-live="polite" hidden></div>
    <p class="plain portal-note" id="portal-note" aria-live="polite" hidden></p>
    <p class="plain hint">Marking ignores capital letters and accepts plurals and the usual alternative answers. If your answer is right but not accepted, press <em>My answer is also right</em> under it.</p>
  </section>

  <section class="card tapescript" aria-labelledby="t-title">
    <h2 class="section-title" id="t-title">Tapescript</h2>
    <p class="plain locked" id="tape-locked">Check your answers first, then the tapescript opens here.</p>
    <button type="button" id="btn-tape" hidden>Show tapescript</button>
    <div id="tape-body" hidden></div>
  </section>
</main>

<script id="test" type="application/json">{blob}</script>
<script src="test.js"></script>
</body>
</html>
"""
    )


def index():
    def group(title, rng):
        rows = "\n".join(
            f'    <li><a href="test-{n:02d}.html" data-test="{n:02d}">Test {n}'
            f'<span class="meta-inline">'
            f'{"4 audio sections" if 11 <= n <= 15 else "Full recording"} &middot; 40 questions'
            f'<span class="done" data-result></span></span></a></li>'
            for n in rng
        )
        return f'  <h2 class="group-title">{title}</h2>\n  <ul class="menu-list">\n{rows}\n  </ul>\n'

    script = """
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
    return (
        HEAD.format(title="IELTS Listening – 26 Actual Tests – IELTS Harper")
        + TOPBAR.format(extra="")
        + f"""
<main class="container">
  <header>
    <h1>IELTS Listening: 26 Actual Tests</h1>
    <div class="summary">26 full tests with audio, answer sheet and tapescript</div>
    <div class="instructions">
      Choose a test. Listen, type your answers on the answer sheet, then check them to see your score and your
      estimated band, and read the tapescript. Your answers are kept in this browser.
    </div>
  </header>

{group("Tests 1–10", range(1, 11))}{group("Tests 11–15", range(11, 16))}{group("Tests 16–26", range(16, 27))}</main>
{script}</body>
</html>
"""
    )


def main():
    for t in TESTS:
        (ROOT / f"test-{t['n']:02d}.html").write_text(page(t), encoding="utf-8", newline="\n")
    (ROOT / "index.html").write_text(index(), encoding="utf-8", newline="\n")
    print(f"Built index.html and {len(TESTS)} test pages.")


main()
