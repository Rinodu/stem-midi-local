const $ = (id) => document.getElementById(id);
const BASE = 'http://127.0.0.1:8765';
let token = '', connected = false, polling = false;
const audioUrls = new Map();
const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.has('token')) {
  $('token').value = fragment.get('token');
  history.replaceState(null, '', location.pathname + location.search);
}

async function api(path, options = {}) {
  const response = await fetch(BASE + '/api/' + path, {
    ...options, headers: {...options.headers, Authorization: `Bearer ${token}`},
    signal: AbortSignal.timeout(options.body instanceof File ? 300000 : 30000)
  });
  if (!response.ok) {
    let detail;
    try { detail = (await response.json()).detail; } catch { detail = response.statusText; }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return response;
}

function button(label, action, disabled = false) {
  const element = document.createElement('button');
  element.className = 'secondary'; element.textContent = label; element.disabled = disabled;
  element.onclick = async () => {
    element.disabled = true;
    try { await action(); } catch (error) { alert(error.message); }
    finally { if (element.isConnected) element.disabled = disabled; }
  };
  return element;
}

async function download(path, name) {
  const [, jobId, kind, ...parts] = path.split('/');
  const asset = kind === 'archive' ? 'archive' : parts.join('/');
  const ticket = await (await api(`jobs/${jobId}/download?asset=${encodeURIComponent(asset)}`, {method:'POST'})).json();
  // Native downloads stream large WAV/ZIP files without buffering them in browser memory.
  const a = document.createElement('a'); a.href = BASE + ticket.url; a.download = name; a.click();
}

function field(label, input) {
  const wrapper = document.createElement('label'); wrapper.textContent = label;
  wrapper.append(input); return wrapper;
}

function renderJob(job) {
  const card = document.createElement('article'); card.className = 'job';
  card.dataset.id = job.id;
  const busy = ['queued', 'processing'].includes(job.status);
  const heading = document.createElement('h3'); heading.textContent = job.name;
  const status = document.createElement('p'); status.className = 'job-status'; status.textContent = job.stage;
  const meta = document.createElement('p'); meta.className = 'job-meta';
  meta.textContent = `${job.model === 'six' ? 'Demucs 6 stem' : 'Demucs 4 stem FT'} · ${job.device.toUpperCase()} · mulai ${job.start}s${job.duration ? ` · durasi ${job.duration.toFixed(1)}s` : ''}`;
  card.append(heading, status, meta);
  if (job.error) { const p = document.createElement('p'); p.className = 'error'; p.textContent = job.error; card.append(p); }
  for (const [stem, asset] of Object.entries(job.stems)) {
    const row = document.createElement('div'); row.className = 'stem';
    const title = document.createElement('strong'); title.textContent = stem; row.append(title);
    const path = `jobs/${job.id}/files/${asset}`;
    const play = button('▶ Dengarkan', async () => {
      const blob = await (await api(path)).blob();
      const key = `${job.id}/${stem}`;
      if (audioUrls.has(key)) URL.revokeObjectURL(audioUrls.get(key));
      const url = URL.createObjectURL(blob); audioUrls.set(key, url);
      const audio = document.createElement('audio'); audio.controls = true; audio.src = url;
      audio.setAttribute('aria-label', `Preview ${stem}`); play.replaceWith(audio);
      audio.play().catch(() => {});
    });
    row.append(play, button('↓ WAV', () => download(path, `${stem}.wav`)));
    if (stem !== 'drums') {
      const controls = document.createElement('div'); controls.className = 'midi-options';
      const engine = document.createElement('select');
      const choices = stem === 'piano' ? [['transkun', 'Transkun · piano'], ['basic-pitch', 'Basic Pitch']] : [['basic-pitch', 'Basic Pitch']];
      for (const [value, label] of choices) { const o = new Option(label, value); engine.add(o); }
      const onset = document.createElement('input'); onset.type = 'number'; onset.min = '.1'; onset.max = '.9'; onset.step = '.05'; onset.value = job.midi[stem]?.onset ?? '.5';
      const minimum = document.createElement('input'); minimum.type = 'number'; minimum.min = '30'; minimum.max = '1000'; minimum.value = job.midi[stem]?.minimum_ms ?? '100';
      if (job.midi[stem]) engine.value = job.midi[stem].engine;
      const onsetField = field('Onset (Basic Pitch)', onset);
      const sync = () => { onset.disabled = engine.value === 'transkun'; }; engine.onchange = sync; sync();
      controls.append(field('Model MIDI', engine), onsetField, field('Min. not (ms)', minimum), button(job.midi[stem] ? 'Ulangi MIDI' : 'Buat MIDI', async () => {
        if (!onset.checkValidity() || !minimum.reportValidity()) return;
        await api(`jobs/${job.id}/midi`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({stem, engine: engine.value, onset: Number(onset.value), minimum_ms: Number(minimum.value)})});
        await refresh();
      }, busy));
      if (stem === 'other') { const warning = document.createElement('span'); warning.className = 'muted'; warning.textContent = 'Other bisa berisi banyak instrumen; MIDI lebih rentan salah.'; controls.append(warning); }
      row.append(controls);
    }
    if (job.midi[stem]) {
      const item = job.midi[stem];
      row.append(button(`↓ MIDI · ${item.notes} not`, () => download(`jobs/${job.id}/files/${item.file}`, `${stem}.mid`)),
        button('Piano roll', () => showRoll(job, stem, item.file)),
        button('↓ CSV not', () => download(`jobs/${job.id}/files/${item.file.replace(/\.mid$/, '.csv')}`, `${stem}.csv`)));
    }
    card.append(row);
  }
  if (Object.keys(job.stems).length) card.append(button('↓ Semua hasil ZIP', () => download(`jobs/${job.id}/archive`, 'stem-midi-results.zip'), busy));
  return card;
}

async function refresh() {
  if (!connected || polling) return;
  polling = true;
  try {
    const jobs = await (await api('jobs')).json();
    if (!jobs.length) { $('jobs').textContent = 'Belum ada hasil. Upload cuplikan pertama lu.'; return; }
    if (!$('jobs').querySelector('.job')) $('jobs').replaceChildren();
    // Keep an unchanged card intact so polling does not stop audio or reset inputs.
    const previous = new Map([...$('jobs').querySelectorAll('.job')].map(el => [el.dataset.id, el]));
    const cards = jobs.map(job => {
      const signature = JSON.stringify(job), old = previous.get(job.id);
      if (old?.dataset.signature === signature) return old;
      const card = renderJob(job); card.dataset.signature = signature; return card;
    });
    // Moving DOM nodes with replaceChildren interrupts native audio on some browsers.
    for (let i = 0; i < cards.length; i++) if ($('jobs').children[i] !== cards[i]) $('jobs').insertBefore(cards[i], $('jobs').children[i] ?? null);
    for (const child of [...$('jobs').children]) if (!cards.includes(child)) child.remove();
  } finally { polling = false; }
}

$('pair').onsubmit = async (event) => {
  event.preventDefault(); token = $('token').value.trim();
  try {
    const health = await (await api('health')).json(); connected = true;
    $('connection').textContent = '● ' + (health.gpu || 'CPU') + ' terhubung';
    $('connection').style.color = 'var(--accent)';
    $('pair-message').textContent = 'Terhubung. Audio diproses dan disimpan di PC ini.';
    $('process').disabled = false; $('refresh').disabled = false;
    if (!health.cuda) $('device').value = 'cpu';
    await refresh();
  } catch (error) {
    connected = false; $('process').disabled = true; $('refresh').disabled = true;
    $('connection').textContent = '● Backend belum terhubung';
    $('pair-message').textContent = `Belum terhubung: ${error.message}. Pastikan Start.bat aktif, token benar, dan akses jaringan lokal diizinkan. Coba versi lokal dari launcher jika browser memblokir koneksi.`;
  }
};

$('audio').onchange = () => { $('chosen').textContent = $('audio').files[0]?.name || 'Belum ada file dipilih'; };
for (const event of ['dragover', 'dragleave', 'drop']) $('drop').addEventListener(event, (e) => {
  e.preventDefault(); $('drop').classList.toggle('drag', event === 'dragover');
  if (event === 'drop' && e.dataTransfer.files.length) { $('audio').files = e.dataTransfer.files; $('audio').dispatchEvent(new Event('change')); }
});
$('upload').onsubmit = async (event) => {
  event.preventDefault();
  const file = $('audio').files[0];
  if (!file || !connected) return;
  if (file.size > 300 * 1024 * 1024) { $('upload-message').textContent = 'File terlalu besar. Maksimum 300 MiB.'; return; }
  $('process').disabled = true; $('upload-message').textContent = 'Mengirim audio ke backend lokal…';
  try {
    const query = new URLSearchParams({filename: file.name, model: $('model').value, device: $('device').value, quality: $('quality').value, start: $('start').value, seconds: $('seconds').value});
    await api('jobs?' + query, {method: 'POST', headers: {'Content-Type': 'application/octet-stream'}, body: file});
    $('upload-message').textContent = 'Masuk antrean. Progres ada di bagian hasil.'; await refresh();
  } catch (error) { $('upload-message').textContent = error.message; }
  finally { $('process').disabled = !connected; }
};
$('refresh').onclick = () => refresh().catch(error => { $('pair-message').textContent = error.message; });
setInterval(() => refresh().catch(error => { $('pair-message').textContent = `Koneksi terganggu: ${error.message}. Backend mungkin berhenti.`; }), 2500);

async function showRoll(job, stem, asset) {
  const notes = await (await api(`jobs/${job.id}/files/${asset.replace(/\.mid$/, '.json')}`)).json();
  $('roll-title').textContent = `Piano roll · ${stem}`;
  $('roll-description').textContent = `${notes.length} not · ${job.name}`;
  const canvas = $('roll'), ctx = canvas.getContext('2d');
  const duration = Math.max(1, ...notes.map(n => n.end));
  const minPitch = notes.length ? Math.max(0, Math.min(...notes.map(n => n.pitch)) - 2) : 48;
  const maxPitch = notes.length ? Math.min(127, Math.max(...notes.map(n => n.pitch)) + 2) : 72;
  canvas.width = Math.min(12000, Math.max(850, duration * 35)); canvas.height = (maxPitch - minPitch + 1) * 14 + 30;
  ctx.fillStyle = '#111710'; ctx.fillRect(0, 0, canvas.width, canvas.height);
  const scale = (canvas.width - 55) / duration;
  ctx.font = '10px system-ui';
  for (let pitch = minPitch; pitch <= maxPitch; pitch++) {
    const y = 25 + (maxPitch - pitch) * 14;
    ctx.strokeStyle = '#273223'; ctx.beginPath(); ctx.moveTo(45, y); ctx.lineTo(canvas.width, y); ctx.stroke();
    ctx.fillStyle = '#a6b09e'; ctx.fillText(String(pitch), 8, y + 10);
  }
  const interval = Math.max(1, Math.ceil(duration / 40));
  for (let t = 0; t <= duration; t += interval) {
    const x = 45 + t * scale; ctx.fillStyle = '#a6b09e'; ctx.fillText(`${t}s`, x, 12);
    ctx.strokeStyle = '#273223'; ctx.beginPath(); ctx.moveTo(x, 20); ctx.lineTo(x, canvas.height); ctx.stroke();
  }
  for (const n of notes) { ctx.fillStyle = `rgba(210,237,133,${.3 + n.velocity / 182})`; ctx.fillRect(45 + n.start * scale, 26 + (maxPitch - n.pitch) * 14, Math.max(2, (n.end - n.start) * scale), 11); }
  $('roll-dialog').showModal();
}
$('close-roll').onclick = () => $('roll-dialog').close();
if ($('token').value) $('pair').requestSubmit();
