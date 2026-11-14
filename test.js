// Listening test page: draws the answer sheet from <script id="test" type="application/json">, marks the
// answers against the key (lenient: capitals, plurals, optional words, alternatives, "either order" groups),
// shows the score and an estimated band, opens the tapescript and keeps the work in this browser.
(function () {
  const data = JSON.parse(document.getElementById('test').textContent);
  const storeKey = 'ih-listening-test:' + String(data.n).padStart(2, '0');
  const $ = (id) => document.getElementById(id);
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
  const LETTERS = 'ABCDEFGHI'.split('');

  // ---- Key -> things to compare with
  const isLetter = (s) => /^[A-I]$/.test(s);
  const groupLetters = {}; // group id -> letters that are right, in any order
  for (const k of data.key) {
    if (k.grp === undefined) continue;
    const set = groupLetters[k.grp] || (groupLetters[k.grp] = new Set());
    const m = k.ans.replace(/\(.*?\)/g, '').match(/\b[A-I]\b/g);
    if (m) m.forEach((l) => set.add(l));
  }
  const letterQuestion = (k) => isLetter(k.ans) || (k.grp !== undefined && groupLetters[k.grp].size > 0);

  const norm = (s) => {
    const t = String(s)
      .toLowerCase()
      .replace(/&/g, ' and ')
      .replace(/[£$€%]/g, '')
      .replace(/(\d),(?=\d{3}\b)/g, '$1')
      .replace(/(\d)\s*(st|nd|rd|th)\b/g, '$1')
      .replace(/[^a-z0-9.:\s]+/g, ' ')
      .replace(/(?<!\d)\.|\.(?!\d)/g, ' ');
    let words = t.split(/\s+/).filter(Boolean);
    words = words.filter((w, i) => !(i === 0 && /^(the|a|an)$/.test(w)));
    words = words.map((w) => (w.length > 3 && w.endsWith('s') ? w.slice(0, -1) : w));
    return words.sort().join(' ');
  };
  const expand = (s) => {
    const m = s.match(/\(([^)]*)\)/);
    if (!m) return [s];
    return [...expand(s.replace(m[0], '')), ...expand(s.replace(m[0], m[1]))];
  };
  const acceptable = (ans) =>
    new Set(
      ans
        .split(/\s+\/\s+|(?<!\d)\/(?!\d)/)
        .flatMap((alt) => expand(alt.replace(/\(any order\)/i, '')))
        .map(norm)
        .filter(Boolean),
    );
  const accepted = {};
  for (const k of data.key) if (!letterQuestion(k)) accepted[k.n] = acceptable(k.ans);

  // ---- Answer sheet
  const sheet = $('sheet');
  const field = (n) => $('a-' + n);
  for (let s = 0; s < 4; s++) {
    const sec = document.createElement('div');
    sec.className = 'sheet-section';
    sec.innerHTML =
      '<h3>Section ' + (s + 1) + ' · Questions ' + (s * 10 + 1) + '–' + (s * 10 + 10) +
      '<span class="section-score" id="sec-' + s + '"></span></h3><ol class="cells"></ol>';
    sheet.appendChild(sec);
    const list = sec.querySelector('ol');
    for (const k of data.key.slice(s * 10, s * 10 + 10)) {
      const li = document.createElement('li');
      li.className = 'cell';
      li.id = 'cell-' + k.n;
      const control = letterQuestion(k)
        ? '<select id="a-' + k.n + '" aria-label="Answer ' + k.n + '"><option value="">–</option>' +
          LETTERS.map((l) => '<option>' + l + '</option>').join('') + '</select>'
        : '<input id="a-' + k.n + '" type="text" autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="Answer ' + k.n + '">';
      li.innerHTML = '<span class="num">' + k.n + '</span>' + control + '<span class="feedback" aria-live="polite"></span>';
      list.appendChild(li);
    }
  }

  // ---- Saved work
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(storeKey) || '{}') || {};
  } catch (e) {
    saved = {};
  }
  const savedAnswers = saved.a || {};
  for (const k of data.key) if (savedAnswers[k.n]) field(k.n).value = savedAnswers[k.n];
  let own = new Set(saved.own || []);
  let lastResult = saved.r || null;
  let showKey = false;
  const persist = () => {
    const a = {};
    for (const k of data.key) a[k.n] = field(k.n).value;
    try {
      localStorage.setItem(storeKey, JSON.stringify({ a, own: [...own], r: lastResult }));
    } catch (e) {
      /* private mode: answers just are not kept */
    }
  };

  // ---- Marking
  const keyText = (k) => k.ans.replace(/\s*\(any order\)/i, '');
  const mark = () => {
    const ok = {};
    const left = {};
    for (const k of data.key) {
      const v = field(k.n).value.trim();
      if (!v) {
        ok[k.n] = false;
      } else if (letterQuestion(k)) {
        if (k.grp !== undefined) {
          const set = left[k.grp] || (left[k.grp] = new Set(groupLetters[k.grp]));
          ok[k.n] = set.has(v);
          if (ok[k.n]) set.delete(v);
        } else {
          ok[k.n] = v === k.ans;
        }
      } else {
        ok[k.n] = accepted[k.n].has(norm(v));
      }
    }
    return ok;
  };
  const BAND = [[39, 9], [37, 8.5], [35, 8], [32, 7.5], [30, 7], [26, 6.5], [23, 6], [18, 5.5], [16, 5], [13, 4.5], [10, 4], [8, 3.5], [6, 3], [4, 2.5]];
  const bandFor = (raw) => (BAND.find(([min]) => raw >= min) || [0, 'below 2.5'])[1];
  const openTapescript = () => {
    $('tape-locked').hidden = true;
    $('btn-tape').hidden = false;
  };

  const render = () => {
    const ok = mark();
    const perSection = [0, 0, 0, 0];
    let score = 0;
    for (const k of data.key) {
      const li = $('cell-' + k.n);
      const v = field(k.n).value.trim();
      const good = ok[k.n] || own.has(k.n);
      if (good) {
        score++;
        perSection[Math.floor((k.n - 1) / 10)]++;
      }
      li.classList.toggle('correct', good);
      li.classList.toggle('incorrect', !good);
      let text = good ? (ok[k.n] ? '✓ Correct' : '✓ Marked as correct by you') : v ? '✗ Not matching the key' : '✗ No answer';
      if (!good && showKey) text += ' · Key: ' + keyText(k);
      li.querySelector('.feedback').textContent = text;
      let btn = li.querySelector('.own');
      if (!ok[k.n] && v) {
        if (!btn) {
          btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'own';
          btn.addEventListener('click', () => {
            if (own.has(k.n)) own.delete(k.n);
            else own.add(k.n);
            render();
          });
          li.appendChild(btn);
        }
        btn.textContent = own.has(k.n) ? 'Undo: my answer is also right' : 'My answer is also right';
      } else if (btn) {
        btn.remove();
      }
    }
    perSection.forEach((n, i) => ($('sec-' + i).textContent = n + ' / 10'));
    const band = bandFor(score);
    const box = $('result');
    box.hidden = false;
    box.innerHTML =
      'Score: <strong>' + score + ' / 40</strong> · Estimated band: <strong>' + band + '</strong><br>' +
      'Section 1: ' + perSection[0] + ' · Section 2: ' + perSection[1] + ' · Section 3: ' + perSection[2] + ' · Section 4: ' + perSection[3];
    openTapescript();
    lastResult = { score, band };
    persist();
  };
  const forget = (li) => {
    li.classList.remove('correct', 'incorrect');
    li.querySelector('.feedback').textContent = '';
    const b = li.querySelector('.own');
    if (b) b.remove();
  };

  $('btn-check').addEventListener('click', render);
  $('btn-answers').addEventListener('click', () => {
    showKey = true;
    render();
  });
  $('btn-reset').addEventListener('click', () => {
    if (!confirm('Clear all your answers for this test?')) return;
    for (const k of data.key) {
      field(k.n).value = '';
      forget($('cell-' + k.n));
    }
    own = new Set();
    lastResult = null;
    showKey = false;
    $('result').hidden = true;
    for (let i = 0; i < 4; i++) $('sec-' + i).textContent = '';
    try {
      localStorage.removeItem(storeKey);
    } catch (e) {
      /* nothing to remove */
    }
  });
  sheet.addEventListener('input', (e) => {
    const li = e.target.closest('.cell');
    if (li) forget(li);
    persist();
  });

  // ---- Tapescript
  const tape = $('tape-body');
  tape.innerHTML = data.tapescript
    .map((p) => {
      const m = p.match(/^([A-Z][A-Za-z.' ]{1,22}):\s+([\s\S]*)$/);
      return m ? '<p><strong>' + esc(m[1]) + ':</strong> ' + esc(m[2]) + '</p>' : '<p>' + esc(p) + '</p>';
    })
    .join('');
  $('btn-tape').addEventListener('click', () => {
    const show = tape.hidden;
    tape.hidden = !show;
    $('btn-tape').textContent = show ? 'Hide tapescript' : 'Show tapescript';
  });

  // A student who already checked this test sees the earlier result straight away.
  if (lastResult) {
    openTapescript();
    const box = $('result');
    box.hidden = false;
    box.innerHTML =
      'Last result: <strong>' + lastResult.score + ' / 40</strong> · Estimated band: <strong>' + lastResult.band +
      '</strong> · press <strong>Check answers</strong> to see the marks again.';
  }
})();
