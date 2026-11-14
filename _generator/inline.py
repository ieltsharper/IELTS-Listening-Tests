# Puts the answer controls into the question book, so students answer in the exercises themselves:
#   <span class="gap">N</span>                  -> a box to type in (a drop-down of letters when the key is a letter)
#   question + options (one number)             -> radio buttons
#   question + options (two or three numbers)   -> check boxes (choose TWO / THREE, in any order)
#   a question with no options                  -> a box (or a drop-down) after the question
#   a list of options with no question          -> check boxes, when the key says it is a choose-TWO/THREE group
#   numbers with nothing to type in (maps, diagrams, pictures of tables, lists to match) -> a "Your answers"
#                                                  row under the block they belong to
# test.js finds the controls by their data-q / data-nums / data-fb attributes.
import re
from collections import Counter, defaultdict

GAP = re.compile(r'<span class="gap">(\d+)</span>')
QN = re.compile(r"<p class='q'><span class='qn'>([^<]*)</span>(.*?)</p>(<ul class='opts'>(.*?)</ul>)?", re.S)
FREE_UL = re.compile(r"<ul class='opts'>(.*?)</ul>", re.S)
LI = re.compile(r"<li><b>([A-Z])</b>(.*?)</li>", re.S)
SPELL = 'autocomplete="off" autocapitalize="off" spellcheck="false"'


def _is_letter(k):
    return bool(re.fullmatch(r"[A-I]", k["ans"].strip())) or (
        k.get("grp") is not None and bool(re.search(r"\b[A-I]\b", re.sub(r"\(.*?\)", "", k["ans"])))
    )


def _top_letter(b, nums, key):
    """The last letter of the list a drop-down offers: 'A - H' in the instructions, else H; never below the key."""
    text = " ".join(b.get("inst", [])) + " " + re.sub(r"<[^>]+>", " ", b.get("html", ""))
    m = re.search(r"\bA\s*(?:-|–|—|to)\s*([A-I])\b", text)
    top = m.group(1) if m else "H"
    for n in nums:
        for l in re.findall(r"\b[A-I]\b", re.sub(r"\(.*?\)", "", key[n]["ans"])):
            top = max(top, l)
    return top


def gapfield(n, key, top, badge=True):
    """One box for question n (a text box or a drop-down) with its number and a place for the marking."""
    num = f'<span class="gn">{n}</span>' if badge else ""
    if _is_letter(key[n]):
        opts = "".join(f"<option>{chr(c)}</option>" for c in range(ord("A"), ord(top) + 1))
        ctl = f'<select class="gap-sel" data-q="{n}" aria-label="Answer {n}"><option value="">–</option>{opts}</select>'
    else:
        ctl = f'<input type="text" class="gap-in" data-q="{n}" {SPELL} aria-label="Answer {n}">'
    return f'<span class="gapfield" data-w="{n}">{num}{ctl}<span class="fb" data-fb="{n}"></span></span>'


def _options(lis, kind, name, nums=None):
    inputs = {"radio": f'type="radio" name="{name}"', "checkbox": f'type="checkbox" name="{name}"'}[kind]
    q = f' data-q="{nums[0]}"' if kind == "radio" else ""
    return "".join(
        f'<li><label><input {inputs} value="{l}"{q}><b>{l}</b>{txt}</label></li>' for l, txt in lis
    )


def radio_block(n, head, lis):
    return (
        f'<div class="qwrap" data-w="{n}">{head}<ul class="opts">{_options(lis, "radio", f"q{n}", [n])}</ul>'
        f'<span class="fb" data-fb="{n}"></span></div>'
    )


def multi_block(nums, head, lis):
    fbs = "".join(f'<span class="fb" data-fb="{n}"></span>' for n in nums)
    return (
        f'<div class="qwrap" data-w="{nums[0]}">{head}<ul class="opts" data-nums="{",".join(map(str, nums))}">'
        f'{_options(lis, "checkbox", f"g{nums[0]}")}</ul><div class="fbs">{fbs}</div></div>'
    )


def strip(nums, key, b):
    top = _top_letter(b, nums, key) if b["mode"] == "text" else max(
        ["H"] + [l for n in nums for l in re.findall(r"\b[A-I]\b", re.sub(r"\(.*?\)", "", key[n]["ans"]))]
    )
    cells = "".join(gapfield(n, key, top) for n in nums)
    label = "Your answer" if len(nums) == 1 else "Your answers"
    return f'<div class="astrip"><span class="astrip-label">{label}</span>{cells}</div>'


def _inline_text(b, key, placed):
    """The html of a text block with the controls in it; adds the numbers it handled to `placed`."""
    h = b["html"]
    nums_in_block = range(b["from"], b["to"] + 1)
    top = _top_letter(b, [n for n in nums_in_block if n in key], key)

    # 1. gaps (a number that appears twice as a gap, like "Flat 4 ... Booking reference 4", is a gap only the last time)
    counts = Counter(int(x) for x in GAP.findall(h))
    seen = Counter()

    def gap(m):
        n = int(m.group(1))
        seen[n] += 1
        if n not in key or n in placed:
            return m.group(0)
        if seen[n] < counts[n]:
            return m.group(1)
        placed.add(n)
        return gapfield(n, key, top)

    h = GAP.sub(gap, h)

    # 2. questions with their options, and questions without options
    def question(m):
        label, text, ul_whole, ul_inner = m.groups()
        nums = [int(x) for x in re.findall(r"\d+", label) if int(x) in key]
        fresh = [n for n in nums if n not in placed]
        if not nums or len(fresh) != len(nums):
            if not ul_whole and re.fullmatch(r"[\s.]*", text):
                return ""  # a stray "." after a question number that is a gap elsewhere
            return m.group(0)
        head = f"<p class='q'><span class='qn'>{label}</span>{text}</p>"
        if ul_whole:
            lis = LI.findall(ul_inner)
            if len(nums) == 1:
                placed.add(nums[0])
                return radio_block(nums[0], head, lis)
            if all(key[n].get("grp") is not None for n in nums):
                placed.update(nums)
                return multi_block(nums, head, lis)
            return m.group(0)
        if len(nums) == 1:
            placed.add(nums[0])
            return f"<p class='q'><span class='qn'>{label}</span>{text} {gapfield(nums[0], key, top, badge=False)}</p>"
        return m.group(0)

    h = QN.sub(question, h)

    # 3. a list of options with no question: check boxes if the key has a choose-TWO/THREE group for this block
    groups = defaultdict(list)
    for n in nums_in_block:
        k = key.get(n)
        if k and n not in placed and k.get("grp") is not None and _is_letter(k):
            groups[k["grp"]].append(n)
    todo = [groups[g] for g in sorted(groups)]

    def free_ul(m):
        if not todo or len(todo[0]) < 2:
            return m.group(0)
        nums = todo.pop(0)
        placed.update(nums)
        return multi_block(nums, "", LI.findall(m.group(1)))

    return FREE_UL.sub(free_ul, h)


def render(blocks, key_list):
    """{block index: (new html for a text block or None, strip html or '')}: the controls of one test's question book."""
    key = {k["n"]: k for k in key_list}
    placed = set()
    out = {}
    for i, b in enumerate(blocks):
        if b["type"] == "block":
            out[i] = [_inline_text(b, key, placed) if b["mode"] == "text" else None, []]
    # numbers still without a control: under the block whose range holds them, else under the one before them
    real = [i for i, b in enumerate(blocks) if b["type"] == "block"]
    for n in sorted(set(key) - placed):
        target = next((i for i in real if blocks[i]["from"] <= n <= blocks[i]["to"]), None)
        if target is None:
            before = [i for i in real if blocks[i]["from"] <= n]
            target = before[-1] if before else real[0]
        out[target][1].append(n)
    return {i: (h, strip(nums, key, blocks[i]) if nums else "") for i, (h, nums) in out.items()}


# ---- Repairs of option lists that the PDF text broke (an option glued to the one before it, or left outside the list)
GLUED = re.compile(r"^(.*?)\s+([B-I])\.?\s+(.+)$", re.S)

# test number -> [(old html, new html)] for the cases a rule cannot cover
HAND = {
    11: [
        (
            '<p>A <span class="gap">&nbsp;</span> Specialising in one product</p><ul class=\'opts\'><li><b>B</b>',
            "<ul class='opts'><li><b>A</b> Specialising in one product</li><li><b>B</b>",
        ),
    ],
    13: [
        (
            "<li><b>D</b> washing-up liquid</li></ul><p>E.oven cleaner F sink cleaner</p>",
            "<li><b>D</b> washing-up liquid</li><li><b>E</b> oven cleaner</li><li><b>F</b> sink cleaner</li></ul>",
        ),
    ],
    14: [
        (
            '</li></ul><p>B. It was formed a long time ago <span class="gap">&nbsp;</span></p><ul class=\'opts\'><li><b>C</b>',
            "</li><li><b>B</b> It was formed a long time ago</li><li><b>C</b>",
        ),
    ],
}


def _split_glued(m):
    """<li><b>B</b> text C. more text</li> -> two items, when the next letter in order is glued to the text."""
    letter, text = m.group(1), m.group(2)
    want = chr(ord(letter) + 1)
    parts = re.split(rf"\s+{want}\.\s+(?=[A-Za-z])", text, maxsplit=1)
    if len(parts) == 2:
        rest = f"<li><b>{want}</b> {parts[1]}</li>"
        return f"<li><b>{letter}</b> {parts[0]}</li>" + _split_glued(re.match(r"<li><b>(.)</b>(.*)</li>$", rest, re.S))
    return m.group(0)


def repair(n, blocks):
    """Copies of the blocks with broken option lists put right (test n of the main set)."""
    out = []
    for b in blocks:
        if b["type"] == "block" and b["mode"] == "text":
            h = b["html"]
            for old, new in HAND.get(n, []):
                h = h.replace(old, new)
            h = re.sub(r"<li><b>([A-I])</b>(.*?)</li>", _split_glued, h, flags=re.S)
            b = dict(b, html=h)
        out.append(b)
    return out
