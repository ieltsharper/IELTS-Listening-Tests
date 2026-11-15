// Listening test page: the answers are typed or chosen inside the questions (build.py makes the controls);
// this marks them against the key in <script id="test" type="application/json"> (lenient: capitals, plurals,
// optional words, alternatives, "either order" groups), shows the score and an estimated band, opens the
// tapescript and keeps the work in this browser.
(function () {
  const data = JSON.parse(document.getElementById('test').textContent);
  // data.id ("rat7-3") marks a test of another set (Recent Actual Test 7); those have no tapescript
  const storeKey = 'ih-listening-test:' + (data.id || String(data.n).padStart(2, '0'));
  const $ = (id) => document.getElementById(id);
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

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
        .split(/\s+\/\s+|(?<!\d)\/|\/(?!\d)/) // "two/2" is two answers; "1/2" is one
        .flatMap((alt) => expand(alt.replace(/\(any order\)/i, '')))
        .map(norm)
        .filter(Boolean),
    );
  const accepted = {};
  for (const k of data.key) if (!letterQuestion(k)) accepted[k.n] = acceptable(k.ans);

  // ---- The answer controls sit inside the questions (build.py puts them there); this finds them.
  // ctl[n] = { get(): the answer, set(v), fb: where the marking goes, paint(state, keyLetter), reset() }
  //   - a text box or a drop-down:  data-q="n" inside a [data-w="n"] wrapper
  //   - one of several radio buttons: data-q="n" on each, inside a [data-w] wrapper
  //   - a choose-TWO/THREE group of check boxes: <ul data-nums="21,22">. The ticked letters, in alphabetical
  //     order, are the answers of those numbers (marking accepts any order, like the key).
  const book = $('qbook');
  const ctl = {};
  const groups = [];
  const paintEl = (el, state) => {
    el.classList.toggle('correct', state === 'ok');
    el.classList.toggle('incorrect', state === 'bad');
  };
  const addCtl = (n, c) => {
    c.fb.textContent = '';
    c.reset = () => {
      c.paint(null);
      c.fb.textContent = '';
      c.fb.classList.remove('ok', 'bad');
    };
    ctl[n] = c;
  };
  for (const el of book.querySelectorAll('input[type=text][data-q], select[data-q]')) {
    const wrap = el.closest('[data-w]');
    addCtl(+el.dataset.q, {
      fb: wrap.querySelector('.fb'),
      get: () => el.value.trim(),
      set: (v) => {
        el.value = v;
      },
      paint: (state) => paintEl(wrap, state),
    });
  }
  const radios = {};
  for (const el of book.querySelectorAll('input[type=radio][data-q]')) (radios[el.dataset.q] = radios[el.dataset.q] || []).push(el);
  for (const q of Object.keys(radios)) {
    const list = radios[q];
    const wrap = list[0].closest('[data-w]');
    addCtl(+q, {
      fb: wrap.querySelector('.fb'),
      get: () => (list.find((r) => r.checked) || { value: '' }).value,
      set: (v) => list.forEach((r) => (r.checked = r.value === v)),
      paint: (state, keyLetter) => {
        paintEl(wrap, state);
        for (const r of list) {
          const li = r.closest('li');
          paintEl(li, r.checked ? state : null);
          li.classList.toggle('key', Boolean(keyLetter) && state === 'bad' && r.value === keyLetter);
        }
      },
    });
  }
  for (const ul of book.querySelectorAll('ul[data-nums]')) {
    const nums = ul.dataset.nums.split(',').map(Number);
    const wrap = ul.closest('[data-w]');
    const boxes = [...ul.querySelectorAll('input[type=checkbox]')];
    const ticked = () => boxes.filter((b) => b.checked).map((b) => b.value).sort();
    const clearMarks = () => boxes.forEach((b) => paintEl(b.closest('li'), null));
    groups.push({ nums, boxes });
    nums.forEach((n, i) => {
      addCtl(n, {
        fb: wrap.querySelector('[data-fb="' + n + '"]'),
        letter: true,
        get: () => ticked()[i] || '',
        set: () => {}, // the whole group is set below
        paint: (state) => {
          if (state === null) return clearMarks();
          const b = boxes.find((x) => x.checked && x.value === ticked()[i]);
          if (b) paintEl(b.closest('li'), state);
        },
      });
    });
  }
  for (const k of data.key) if (!ctl[k.n]) throw new Error('No answer control for question ' + k.n);
  const field = (n) => ctl[n];

  // ---- Saved work
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(storeKey) || '{}') || {};
  } catch (e) {
    saved = {};
  }
  const savedAnswers = saved.a || {};
  for (const k of data.key) if (savedAnswers[k.n]) field(k.n).set(savedAnswers[k.n]);
  for (const g of groups) {
    const want = new Set(g.nums.map((n) => savedAnswers[n]).filter(Boolean));
    for (const b of g.boxes) b.checked = want.has(b.value);
  }
  let own = new Set(saved.own || []);
  let lastResult = saved.r || null;
  let showKey = false;
  const persist = () => {
    const a = {};
    for (const k of data.key) a[k.n] = field(k.n).get();
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
      const v = field(k.n).get();
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
    if (!data.tapescript) return;
    const card = $('tape-card'); // (a page cached from before the card was hidden has none)
    if (card) card.hidden = false;
  };


  // ---- Saving the result. A signed-in student's result goes into their Listening progress (the portal
  // and these pages share one site, so the portal sign-in is readable here); checking the same test again
  // the same day updates that entry. Anyone else types a name before starting (the same name as on the
  // Reading pages: one name for the whole website) and the result is saved under it for the teacher, who
  // sees it on the portal (Bài tập → Bài nghe). Only the score is sent, never the answers.
  const API_URL = 'https://script.google.com/macros/s/AKfycbwKm1zvqca2-WO20f49M4mNW2qn9Aq4uxJZ3_bnQrErWPL5TN4jHycXZUQBDJ1W7wWg/exec';
  const PORTAL = 'https://ieltsharper.github.io/portal/';
  const NAME_KEY = 'ih-reading:name';
  const note = $('portal-note');
  const portalToken = () => {
    try {
      return localStorage.getItem('portal.session');
    } catch (e) {
      return null;
    }
  };
  const storedName = () => {
    try {
      return localStorage.getItem(NAME_KEY) || '';
    } catch (e) {
      return '';
    }
  };
  const cleanName = (s) => String(s || '').normalize('NFC').replace(/\s+/g, ' ').trim();
  const nameProblem = (n) =>
    n.length < 2 || n.length > 40 || !/\p{L}/u.test(n) || /[<>]/.test(n) ? 'Please type your name (2–40 letters).' : '';
  const say = (html) => {
    note.hidden = !html;
    note.innerHTML = html || '';
  };

  // A visitor's name, under the buttons, with a way to change it
  const whoLine = document.createElement('p');
  whoLine.className = 'plain visitor-name';
  whoLine.hidden = true;
  note.parentNode.insertBefore(whoLine, note);
  const drawWho = () => {
    const n = portalToken() ? '' : storedName();
    whoLine.hidden = !n;
    whoLine.innerHTML = n
      ? 'Your results are saved for your teacher under the name <strong>' + esc(n) + '</strong> ' +
        '<button type="button" class="link-btn" id="change-name">Change</button>'
      : '';
    if (n) $('change-name').addEventListener('click', () => askName(true));
  };

  // The name box: before starting (cannot be closed), or to change the name
  let overlay = null;
  let afterName = null; // a score waiting for the name
  const setInert = (on) =>
    document.querySelectorAll('nav.topbar, main').forEach((el) => (on ? el.setAttribute('inert', '') : el.removeAttribute('inert')));
  const askName = (change, problem) => {
    if (overlay) overlay.remove();
    overlay = document.createElement('div');
    overlay.className = 'name-overlay';
    overlay.innerHTML =
      '<form class="name-box" role="dialog" aria-modal="true" aria-labelledby="name-title" novalidate>' +
      '<h2 id="name-title">' + (change ? 'Change your name' : 'Before you start: what is your name?') + '</h2>' +
      '<p>When you check your answers, your score is saved online under this name so your teacher can see it.</p>' +
      '<p class="name-rule"><strong>Please use only one name on this website</strong>, spelt the same way every time ' +
      '(for example, your full name), the same name as on the Reading pages.</p>' +
      '<label for="name-input">Your name</label>' +
      '<input id="name-input" type="text" autocomplete="name" maxlength="40" spellcheck="false">' +
      '<p class="name-error" id="name-error" role="alert"></p>' +
      '<div class="name-actions"><button type="submit" class="btn-check">' + (change ? 'Save name' : 'Start') + '</button>' +
      (change ? '<button type="button" id="name-cancel">Cancel</button>' : '') + '</div>' +
      '<p class="name-alt">Have an IELTS Harper Portal account? <a href="' + PORTAL + '" target="_blank" rel="noopener">Sign in to the portal</a>, then reload this page.</p>' +
      '</form>';
    document.body.appendChild(overlay);
    setInert(true);
    const input = $('name-input');
    const error = $('name-error');
    if (change) input.value = storedName();
    if (problem) error.textContent = problem;
    input.focus();
    const close = () => {
      overlay.remove();
      overlay = null;
      setInert(false);
    };
    if (change) {
      $('name-cancel').addEventListener('click', close);
      overlay.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') close();
      });
    }
    overlay.querySelector('form').addEventListener('submit', (e) => {
      e.preventDefault();
      const n = cleanName(input.value);
      const bad = nameProblem(n);
      if (bad) {
        error.textContent = bad;
        input.focus();
        return;
      }
      try {
        localStorage.setItem(NAME_KEY, n);
      } catch (err) {}
      close();
      drawWho();
      if (afterName !== null) {
        const s = afterName;
        afterName = null;
        logToPortal(s);
      }
    });
  };

  let sending = false;
  let again = null;
  const logToPortal = (score) => {
    if (sending) {
      again = score;
      return;
    }
    const tok = portalToken();
    const name = tok ? '' : storedName();
    if (!tok && !name) {
      afterName = score;
      askName(false);
      return;
    }
    const payload = data.set ? { test: data.n, set: data.set, correct: score } : { test: data.n, correct: score };
    if (!tok) payload.name = name;
    sending = true;
    say(tok ? 'Saving to your portal…' : 'Saving your result for your teacher…');
    fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: JSON.stringify({ action: tok ? 'listening.result' : 'listening.visitor.result', token: tok, payload }),
      redirect: 'follow',
      credentials: 'omit',
    })
      .then((r) => r.json())
      .then((env) => {
        if (!tok) {
          if (env.ok) say('✓ Result saved for your teacher under the name <strong>' + esc(env.data.name) + '</strong> (' + score + ' / 40).');
          else if (env.error.code === 'invalid' && /name/i.test(env.error.message)) {
            try {
              localStorage.removeItem(NAME_KEY);
            } catch (e) {}
            drawWho();
            say('');
            afterName = score;
            askName(false, env.error.message);
          } else say('Could not save your result: ' + esc(env.error.message));
          return;
        }
        if (env.ok) say('✓ Saved to your portal <a href="' + PORTAL + '" target="_blank" rel="noopener">Listening progress</a> (' + score + ' / 40, 40 minutes; you can change the minutes there).');
        else if (env.error.code === 'forbidden' && env.error.details && env.error.details.reason === 'day_locked') say('');
        else if (env.error.code === 'unauthorized') say('Your portal sign-in has ended. <a href="' + PORTAL + '" target="_blank" rel="noopener">Sign in again</a>, then check your answers again.');
        else if (env.error.code === 'forbidden') say(''); // a teacher account: nothing to log
        else say('Could not save to the portal: ' + esc(env.error.message));
      })
      .catch(() => say(tok ? 'Could not reach the portal, so this result was not saved there. Check your answers again later.' : 'Could not reach the server, so this result was not saved for your teacher. Check your answers again later.'))
      .then(() => {
        sending = false;
        if (again !== null) {
          const s = again;
          again = null;
          logToPortal(s);
        }
      });
  };
  drawWho();
  if (!portalToken() && !storedName()) askName(false);

  const render = () => {
    const ok = mark();
    const perSection = [0, 0, 0, 0];
    let score = 0;
    for (const k of data.key) {
      const c = field(k.n);
      const v = c.get();
      const good = ok[k.n] || own.has(k.n);
      if (good) {
        score++;
        perSection[Math.floor((k.n - 1) / 10)]++;
      }
      c.paint(good ? 'ok' : 'bad', showKey ? k.ans.replace(/\s*\(any order\)/i, '') : null);
      let text = good ? (ok[k.n] ? '✓ Correct' : '✓ Marked as correct by you') : v ? '✗ Not matching the key' : '✗ No answer';
      if (!good && showKey) text += ' · Key: ' + keyText(k);
      if (c.letter && v) text = v + ': ' + text; // a choose-TWO/THREE group: say which letter this is about
      c.fb.textContent = '';
      c.fb.classList.toggle('ok', good);
      c.fb.classList.toggle('bad', !good);
      c.fb.appendChild(document.createTextNode(text));
      if (!ok[k.n] && v) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'own';
        btn.textContent = own.has(k.n) ? 'Undo: my answer is also right' : 'My answer is also right';
        btn.addEventListener('click', () => {
          if (own.has(k.n)) own.delete(k.n);
          else own.add(k.n);
          render();
        });
        c.fb.appendChild(btn);
      }
    }
    perSection.forEach((n, i) => {
      const el = $('sec-' + i);
      if (el) el.textContent = n + ' / 10';
    });
    const band = bandFor(score);
    const box = $('result');
    box.hidden = false;
    box.innerHTML =
      'Score: <strong>' + score + ' / 40</strong> · Estimated band: <strong>' + band + '</strong><br>' +
      'Section 1: ' + perSection[0] + ' · Section 2: ' + perSection[1] + ' · Section 3: ' + perSection[2] + ' · Section 4: ' + perSection[3];
    openTapescript();
    lastResult = { score, band };
    persist();
    if (data.key.some((k) => field(k.n).get())) logToPortal(score);
  };

  $('btn-check').addEventListener('click', render);
  $('btn-answers').addEventListener('click', () => {
    showKey = true;
    render();
  });
  $('btn-reset').addEventListener('click', () => {
    if (!confirm('Clear all your answers for this test?')) return;
    for (const k of data.key) {
      field(k.n).set('');
      field(k.n).reset();
    }
    for (const g of groups) for (const b of g.boxes) b.checked = false;
    own = new Set();
    lastResult = null;
    showKey = false;
    $('result').hidden = true;
    for (let i = 0; i < 4; i++) {
      const el = $('sec-' + i);
      if (el) el.textContent = '';
    }
    try {
      localStorage.removeItem(storeKey);
    } catch (e) {
      /* nothing to remove */
    }
  });
  // Changing an answer clears the marking of that question (of the whole group, for check boxes) and keeps the work.
  book.addEventListener('input', (e) => {
    const t = e.target;
    let nums;
    const group = t.closest('[data-nums]');
    if (group) {
      nums = group.dataset.nums.split(',').map(Number);
      if (group.querySelectorAll('input:checked').length > nums.length) {
        t.checked = false; // choose TWO means two: the extra tick does not stick
        return;
      }
    } else if (t.dataset.q) {
      nums = [+t.dataset.q];
    } else {
      return;
    }
    for (const n of nums) {
      field(n).reset();
      own.delete(n);
    }
    persist();
  });

  // ---- Tapescript
  const tape = $('tape-body');
  if (data.tapescript) {
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
  }

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
