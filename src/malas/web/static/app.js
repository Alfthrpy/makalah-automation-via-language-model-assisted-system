'use strict';

/* MALAS web UI — vanilla JS, tanpa dependensi. Semua teks dari server dirender via textContent. */

const $ = (sel, root = document) => root.querySelector(sel);
const FORM_KEY = 'malas.form.v1';
const JOB_KEY = 'malas.job.v1';
const ACTIVE = new Set(['queued', 'running']);
const BADGE = { queued: 'Antre', running: 'Berjalan', done: 'Selesai', error: 'Gagal', interrupted: 'Terhenti', cancelled: 'Dibatalkan' };
const MAX_PENYUSUN = 10;

let cfg = null;
let currentId = null;
let pollTimer = null;
let tickTimer = null;
let lastJob = null;
let rowSeq = 0;

/* ---------- util ---------- */
function el(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else node.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat()) if (kid != null) node.append(kid);
  return node;
}
function svgIcon(id, cls = 'ic') {
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  s.setAttribute('class', cls);
  s.setAttribute('aria-hidden', 'true');
  const u = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  u.setAttribute('href', '#' + id);
  s.append(u);
  return s;
}
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* mode privat / diblokir */ } },
  del(k) { try { localStorage.removeItem(k); } catch { /* abaikan */ } },
};
async function api(path, opts = {}) {
  const init = { method: opts.method || 'GET', headers: {} };
  if (opts.body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(opts.body);
  }
  const res = await fetch(path, init);
  let data = null;
  try { data = await res.json(); } catch { /* tubuh kosong */ }
  if (!res.ok) throw Object.assign(new Error('HTTP ' + res.status), { status: res.status, data });
  return data;
}
function fmtDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' });
}
function fmtClock(iso) {
  return new Date(iso).toLocaleTimeString('id-ID', { hour12: false });
}
function fmtDur(sec) {
  sec = Math.max(0, Math.round(sec));
  const m = Math.floor(sec / 60), s = sec % 60;
  return m ? `${m} mnt ${String(s).padStart(2, '0')} dtk` : `${s} dtk`;
}
function showBanner(msg, kind = 'warn') {
  const b = $('#banner');
  if (!msg) { b.hidden = true; b.textContent = ''; return; }
  b.textContent = msg;
  b.className = 'banner' + (kind === 'bad' ? ' bad' : '');
  b.hidden = false;
}

/* ---------- penyusun ---------- */
function addPenyusun(nama = '', nim = '') {
  const list = $('#penyusun-list');
  if (list.children.length >= MAX_PENYUSUN) return;
  const n = ++rowSeq;
  const row = el('div', { class: 'pen-row' },
    el('div', { class: 'pen-f-nama' }, el('label', { for: `pen-nama-${n}` }, 'Nama'),
      el('input', { id: `pen-nama-${n}`, class: 'pen-nama', maxlength: '100', value: nama })),
    el('div', { class: 'pen-f-nim' }, el('label', { for: `pen-nim-${n}` }, 'NIM'),
      el('input', { id: `pen-nim-${n}`, class: 'pen-nim-input', maxlength: '30', inputmode: 'numeric', value: nim })),
    el('button', { type: 'button', class: 'btn ghost icon danger pen-del', 'data-remove': '' }, svgIcon('i-trash')),
  );
  list.append(row);
  syncPenyusunControls();
}
function syncPenyusunControls() {
  const rows = [...document.querySelectorAll('.pen-row')];
  rows.forEach((r, i) => {
    const b = $('[data-remove]', r);
    b.setAttribute('aria-label', `Hapus penyusun ${i + 1}`);
    b.disabled = rows.length === 1;
  });
  $('#add-penyusun').disabled = rows.length >= MAX_PENYUSUN;
}
function setPenyusun(list) {
  $('#penyusun-list').replaceChildren();
  (list && list.length ? list : [{}]).forEach((p) => addPenyusun(p.nama || '', p.nim || ''));
}

/* ---------- form ---------- */
const TEXT_FIELDS = ['judul', 'mata_kuliah', 'dosen_pengampu', 'universitas', 'fakultas', 'jurusan', 'kelas', 'kota', 'tahun'];

function usingOwnKey() {
  const r = document.querySelector('input[name="source"]:checked');
  return cfg && (cfg.hosted || !cfg.server_key_available || (r && r.value === 'own'));
}
function currentProvider() { return (cfg.providers || []).find((p) => p.id === $('#provider').value) || null; }

/* forStorage=true: tanpa API key. Key hanya hidup di kolom input dan dalam satu permintaan POST. */
function collect(forStorage = false) {
  const data = {};
  for (const f of TEXT_FIELDS) data[f] = $('#' + f).value.trim();
  data.penyusun = [...document.querySelectorAll('.pen-row')]
    .map((r) => ({ nama: $('.pen-nama', r).value.trim(), nim: $('.pen-nim-input', r).value.trim() }))
    .filter((p) => p.nama || p.nim);
  data.template = $('#template').value || null;
  data.mock = $('#mock').checked;
  data.source = usingOwnKey() ? 'own' : 'server';
  if (data.source === 'own') {
    data.provider = $('#provider').value;
    data.model_planner = $('#model_planner').value.trim() || null;
    data.model_writer = $('#model_writer').value.trim() || null;
    if (!forStorage && !data.mock) data.api_key = $('#api_key').value.trim();
  }
  return data;
}
function fillForm(data) {
  for (const f of TEXT_FIELDS) if (data[f] != null) $('#' + f).value = data[f];
  setPenyusun(data.penyusun);
  if (data.template && [...$('#template').options].some((o) => o.value === data.template)) $('#template').value = data.template;
  if (typeof data.mock === 'boolean') $('#mock').checked = data.mock;
  const src = document.querySelector(`input[name="source"][value="${data.source === 'server' ? 'server' : 'own'}"]`);
  if (src && !$('#source-wrap').hidden) src.checked = true;
  if (data.provider && [...$('#provider').options].some((o) => o.value === data.provider && !o.disabled)) {
    $('#provider').value = data.provider;
    syncProvider(false);
  }
  if (data.model_planner) $('#model_planner').value = data.model_planner;
  if (data.model_writer) $('#model_writer').value = data.model_writer;
  syncProviderUI();
}
function saveForm() { store.set(FORM_KEY, collect(true)); }

function clearErrors() {
  document.querySelectorAll('.err').forEach((e) => { e.textContent = ''; });
  document.querySelectorAll('[aria-invalid]').forEach((e) => e.removeAttribute('aria-invalid'));
}
function setErr(field, msg, control) {
  const slot = $('#err-' + field);
  if (slot && !slot.textContent) slot.textContent = msg;
  const input = control || $('#' + field);
  if (input) input.setAttribute('aria-invalid', 'true');
}
function validate(d) {
  const errs = [];
  if (d.judul.length < 3) errs.push(['judul', 'Judul wajib diisi (minimal 3 karakter).']);
  if (d.mata_kuliah.length < 2) errs.push(['mata_kuliah', 'Mata kuliah wajib diisi.']);
  if (!/^(19|20)\d{2}$/.test(d.tahun)) errs.push(['tahun', 'Isi tahun 4 digit, mis. 2025.']);
  if (d.source === 'own' && !d.mock) {
    if (!d.api_key || d.api_key.length < 8) errs.push(['api_key', 'Isi API key Anda (minimal 8 karakter).']);
    else if (/\s/.test(d.api_key)) errs.push(['api_key', 'API key tidak boleh mengandung spasi.']);
    const prov = currentProvider();
    if (prov && prov.needs_model) {
      if (!d.model_planner) errs.push(['model_planner', 'Isi id model (lihat daftar model penyedia).']);
      if (!d.model_writer) errs.push(['model_writer', 'Isi id model (lihat daftar model penyedia).']);
    }
  }
  if (!d.penyusun.length) errs.push(['penyusun', 'Isi minimal satu penyusun.', $('.pen-nama')]);
  d.penyusun.forEach((p, i) => {
    if (!p.nama) errs.push(['penyusun', 'Nama penyusun tidak boleh kosong.', document.querySelectorAll('.pen-nama')[i]]);
  });
  return errs;
}
function showErrors(errs) {
  errs.forEach(([field, msg, control]) => setErr(field, msg, control));
  const first = document.querySelector('[aria-invalid="true"]');
  if (first) { first.scrollIntoView({ block: 'center', behavior: 'smooth' }); first.focus({ preventScroll: true }); }
}
function serverMsg(e) {
  const c = e.ctx || {};
  switch (e.type) {
    case 'string_too_short': return `Minimal ${c.min_length} karakter.`;
    case 'string_too_long': return `Maksimal ${c.max_length} karakter.`;
    case 'string_pattern_mismatch': return 'Format tidak valid.';
    case 'too_short': return 'Isi minimal satu penyusun.';
    case 'too_long': return `Maksimal ${MAX_PENYUSUN} penyusun.`;
    case 'missing': return 'Wajib diisi.';
    default: return e.msg || 'Tidak valid.';
  }
}
function showServerErrors(detail) {
  const errs = detail.map((e) => {
    const loc = e.loc || [];
    const field = loc[1];
    let control = null;
    if (field === 'penyusun' && typeof loc[2] === 'number') control = document.querySelectorAll('.pen-row')[loc[2]]?.querySelector(loc[3] === 'nim' ? '.pen-nim-input' : '.pen-nama');
    return [field || 'judul', serverMsg(e), control];
  });
  showErrors(errs);
}

/* ---------- konfigurasi ---------- */
function syncProvider(resetModels = true) {
  const prov = currentProvider();
  if (!prov) return;
  $('#models-list').replaceChildren(...prov.models.map((m) => el('option', { value: m })));
  $('#model_planner').placeholder = prov.default_planner || 'mis. ' + (prov.models[0] || 'nama-model');
  $('#model_writer').placeholder = prov.default_writer || 'mis. ' + (prov.models[0] || 'nama-model');
  if (resetModels) { $('#model_planner').value = ''; $('#model_writer').value = ''; }
  const help = $('#key-help');
  help.replaceChildren('Belum punya key? ');
  if (prov.key_url) help.append(el('a', { href: prov.key_url, target: '_blank', rel: 'noopener noreferrer' }, `Buat key di ${prov.label}`), '. ');
  help.append(prov.default_planner ? 'Model dikosongkan = memakai saran (riset: ' + prov.default_planner + ', penulis: ' + prov.default_writer + ').'
    : 'Isi id model sesuai katalog ' + prov.label + '; model berakhiran :free bisa dipakai tanpa biaya.');
}
function syncProviderUI() {
  const own = usingOwnKey() && !$('#mock').checked;
  $('#own-wrap').hidden = !own;
  const insecure = own && location.protocol === 'http:' && !['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
  $('#insecure').hidden = !insecure;
  $('#api_key').disabled = insecure;
}

function renderConfig() {
  const chips = [];
  if (cfg.hosted) {
    chips.push(el('span', { class: 'chip ok' }, 'API key: milik Anda'));
  } else if (cfg.models) {
    const m = cfg.models;
    const uniq = [...new Set(Object.values(m))];
    if (uniq.length === 1) chips.push(el('span', { class: 'chip' }, 'Server: ', el('b', {}, uniq[0])));
    else chips.push(el('span', { class: 'chip' }, 'Penulis ', el('b', {}, m.writer)), el('span', { class: 'chip' }, 'Riset ', el('b', {}, m.planner)));
    chips.push(el('span', { class: 'chip ' + (cfg.api_key_ok ? 'ok' : 'warn') }, cfg.api_key_ok ? 'Key server terdeteksi' : 'Key server belum ada'));
  }
  chips.push(el('span', { class: 'chip' }, 'Full-text ', el('b', {}, cfg.fulltext ? 'aktif' : 'nonaktif')));
  $('#cfg-chips').replaceChildren(...chips);

  const prov = $('#provider');
  prov.replaceChildren(...cfg.providers.map((p) => el('option', { value: p.id, disabled: !p.enabled }, p.label + (p.enabled ? '' : ' (belum tersedia)'))));
  syncProvider(true);
  const showSource = !cfg.hosted && cfg.server_key_available;
  $('#source-wrap').hidden = !showSource;
  if (showSource) document.querySelector('input[name="source"][value="server"]').checked = true;
  syncProviderUI();

  const sel = $('#template');
  sel.replaceChildren(...cfg.templates.map((t) => el('option', { value: t, selected: t === cfg.default_template }, t)));
  if (!cfg.templates.length) { sel.append(el('option', { value: '' }, '(tidak ada template)')); sel.disabled = true; }
  if (cfg.mock_default) $('#mock').checked = true;

  const ol = $('#steps');
  ol.replaceChildren(...cfg.steps.map((s) => el('li', { class: 'step', 'data-step': s.key, 'data-s': 'pending', title: s.hint },
    el('span', { class: 'dot' }, svgIcon('i-check', 's-check'), svgIcon('i-dash', 's-dash'), svgIcon('i-x', 's-x')),
    el('div', {}, el('div', { class: 'step-label' }, s.label), el('div', { class: 'step-detail' })),
  )));
}

/* ---------- job ---------- */
function setCurrent(id) {
  currentId = id;
  lastJob = null;
  if (id) store.set(JOB_KEY, id); else store.del(JOB_KEY);
  clearTimeout(pollTimer);
  if (!id) { $('#job').hidden = true; $('#idle').hidden = false; $('#panel').setAttribute('data-idle', ''); return; }
  poll();
}
async function poll() {
  const id = currentId;
  if (!id) return;
  try {
    const job = await api('/api/jobs/' + id);
    if (id !== currentId) return; // pengguna pindah ke job lain
    renderJob(job);
    if (ACTIVE.has(job.status)) pollTimer = setTimeout(poll, 1500);
    else loadHistory();
  } catch (err) {
    if (id !== currentId) return;
    if (err.status === 404) { setCurrent(null); loadHistory(); return; }
    $('#status-text').textContent = 'Koneksi ke server terputus, mencoba lagi…';
    pollTimer = setTimeout(poll, 3000);
  }
}
function statusLine(job) {
  if (job.status === 'queued') return 'Menunggu job lain selesai…';
  if (job.status === 'running') {
    const running = cfg.steps.find((s) => job.steps[s.key]?.status === 'running');
    const secs = (Date.now() - new Date(job.started_at).getTime()) / 1000;
    return `${running ? running.label : 'Memproses'} · berjalan ${fmtDur(secs)}`;
  }
  if (job.status === 'done') return `Selesai dalam ${fmtDur((new Date(job.finished_at) - new Date(job.started_at)) / 1000)}.`;
  if (job.status === 'cancelled') return 'Dibatalkan sebelum dimulai.';
  return job.error_step ? `Berhenti pada tahap “${cfg.steps.find((s) => s.key === job.error_step)?.label || job.error_step}”.` : 'Berhenti.';
}
function renderJob(job) {
  lastJob = job;
  $('#idle').hidden = true;
  $('#job').hidden = false;
  $('#panel').removeAttribute('data-idle');
  $('#job-title').textContent = job.title;
  const badge = $('#job-badge');
  badge.textContent = (BADGE[job.status] || job.status) + (job.mock ? ' · uji' : '');
  badge.dataset.s = job.status;
  $('#status-text').textContent = statusLine(job);

  document.querySelectorAll('.step').forEach((li) => {
    const st = job.steps[li.dataset.step] || { status: 'pending', detail: '' };
    li.dataset.s = st.status;
    if (st.status === 'running') li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
    $('.step-detail', li).textContent = st.detail || '';
  });

  const log = $('#log');
  const stick = log.scrollTop + log.clientHeight >= log.scrollHeight - 24;
  log.textContent = job.log.map((l) => `[${fmtClock(l.t)}] ${l.msg}`).join('\n');
  if (stick) log.scrollTop = log.scrollHeight;

  renderResult(job);
  clearInterval(tickTimer);
  if (job.status === 'running') {
    tickTimer = setInterval(() => { if (lastJob && lastJob.id === job.id) $('#status-text').textContent = statusLine(lastJob); }, 1000);
  }
}
function renderResult(job) {
  const box = $('#result');
  box.replaceChildren();
  box.className = 'result';
  box.hidden = true;

  if (job.status === 'done') {
    box.hidden = false;
    const s = job.stats || {}, u = job.usage || {};
    const facts = [];
    if (s.subbab_count != null) facts.push(el('li', {}, `${s.subbab_count} sub-bab`));
    if (s.refs_final != null) facts.push(el('li', {}, `${s.refs_final} referensi`));
    if (s.fulltext_total) facts.push(el('li', {}, `full-text ${s.fulltext_ok}/${s.fulltext_total}`));
    if (s.citations_total != null) facts.push(el('li', {}, `${s.citations_total} sitasi`));
    if (s.citations_invalid_after > 0) facts.push(el('li', { class: 'warn' }, `${s.citations_invalid_after} sub-bab masih bersitasi bermasalah`));
    facts.push(el('li', {}, job.mock ? 'mode uji · tanpa token' : u.total ? `${u.total.toLocaleString('id-ID')} token` : 'token tidak tercatat'));
    box.append(
      el('h3', {}, 'Makalah siap'),
      el('ul', { class: 'facts' }, facts),
      el('a', { class: 'btn primary', href: `/api/jobs/${job.id}/download` }, svgIcon('i-download'), 'Unduh .docx'),
      el('p', { class: 'note' }, job.mock
        ? 'Ini hasil mode uji: isinya teks contoh, bukan tulisan sungguhan.'
        : 'Buka di Word dan periksa isi, fakta, serta sitasi sebelum dikumpulkan. Daftar isi/nomor halaman mungkin perlu diperbarui (F9).'),
      job.byok ? el('p', { class: 'note' }, 'API key Anda sudah dibuang dari memori server.') : null,
    );
  } else if (job.status === 'error' || job.status === 'interrupted') {
    box.hidden = false;
    box.classList.add('bad');
    const retry = el('button', { type: 'button', class: 'btn' }, 'Isi ulang formulir dari job ini');
    retry.addEventListener('click', () => { fillForm({ ...job.request, template: job.template, mock: job.mock, source: job.byok ? 'own' : 'server', provider: job.provider, model_planner: job.models && job.models.planner, model_writer: job.models && job.models.writer }); $('#judul').scrollIntoView({ behavior: 'smooth', block: 'center' }); $('#judul').focus({ preventScroll: true }); });
    box.append(el('h3', {}, 'Proses gagal'), el('p', {}, job.error || 'Terjadi kesalahan tak dikenal.'), retry);
  }
}

/* ---------- riwayat ---------- */
async function loadHistory() {
  let items = [];
  try { items = await api('/api/jobs'); } catch { return; }
  const ul = $('#history');
  ul.replaceChildren(...items.map((j) => {
    const actions = el('div', { class: 'h-actions' });
    const view = el('button', { type: 'button', class: 'btn sm' }, 'Lihat');
    view.addEventListener('click', () => { setCurrent(j.id); $('#panel').scrollIntoView({ behavior: 'smooth', block: 'start' }); });
    actions.append(view);
    if (j.has_file) actions.append(el('a', { class: 'btn sm', href: `/api/jobs/${j.id}/download` }, svgIcon('i-download'), 'Unduh'));
    if (j.status !== 'running') {
      const del = el('button', { type: 'button', class: 'btn sm ghost danger', 'aria-label': `${j.status === 'queued' ? 'Batalkan' : 'Hapus'}: ${j.title}` }, j.status === 'queued' ? 'Batalkan' : 'Hapus');
      del.addEventListener('click', () => removeJob(j));
      actions.append(del);
    }
    return el('li', { class: 'h-item' },
      el('div', { class: 'h-main' },
        el('div', { class: 'h-title' }, j.title),
        el('div', { class: 'h-meta' }, el('span', { class: 'badge', 'data-s': j.status }, BADGE[j.status] || j.status), j.mock ? el('span', {}, 'mode uji') : null, el('span', {}, fmtDate(j.created_at)))),
      actions);
  }));
  $('#history-empty').hidden = items.length > 0;
}
async function removeJob(j) {
  const verb = j.status === 'queued' ? 'Batalkan' : 'Hapus';
  if (!window.confirm(`${verb} “${j.title}”?${j.has_file ? ' Berkas hasilnya ikut terhapus.' : ''}`)) return;
  try {
    await api('/api/jobs/' + j.id, { method: 'DELETE' });
    if (currentId === j.id && j.status !== 'queued') setCurrent(null);
    else if (currentId === j.id) poll();
  } catch (err) {
    showBanner(err.data?.detail || 'Gagal menghapus.', 'bad');
  }
  loadHistory();
}

/* ---------- submit ---------- */
async function onSubmit(ev) {
  ev.preventDefault();
  clearErrors();
  showBanner(cfg && !cfg.api_key_ok ? $('#banner').textContent : '');
  const data = collect();
  const errs = validate(data);
  if (errs.length) { showErrors(errs); return; }
  const btn = $('#submit');
  btn.disabled = true;
  try {
    const { source, ...body } = data; // 'source' hanya untuk UI
    const job = await api('/api/jobs', { method: 'POST', body });
    $('#api_key').value = ''; // key sudah di server; jangan biarkan tersisa di halaman
    saveForm();
    setCurrent(job.id);
    loadHistory();
    $('#panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    const d = err.data && err.data.detail;
    if (err.status === 422 && Array.isArray(d)) showServerErrors(d);
    else showBanner(typeof d === 'string' ? d : 'Gagal menghubungi server. Coba lagi.', 'bad');
  } finally {
    btn.disabled = false;
  }
}

/* ---------- init ---------- */
async function init() {
  try {
    cfg = await api('/api/config');
  } catch {
    showBanner('Tidak bisa memuat konfigurasi dari server. Muat ulang halaman.', 'bad');
    return;
  }
  renderConfig();
  $('#panel').setAttribute('data-idle', '');
  const saved = store.get(FORM_KEY);
  setPenyusun(saved && saved.penyusun);
  if (saved) fillForm(saved);
  if (!$('#tahun').value) $('#tahun').value = String(cfg.year);

  $('#add-penyusun').addEventListener('click', () => { addPenyusun(); const rows = document.querySelectorAll('.pen-nama'); rows[rows.length - 1].focus(); });
  $('#penyusun-list').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-remove]');
    if (!btn) return;
    btn.closest('.pen-row').remove();
    syncPenyusunControls();
    saveForm();
  });
  $('#form').addEventListener('submit', onSubmit);
  $('#provider').addEventListener('change', () => syncProvider(true));
  $('#mock').addEventListener('change', syncProviderUI);
  document.querySelectorAll('input[name="source"]').forEach((r) => r.addEventListener('change', syncProviderUI));
  $('#toggle-key').addEventListener('click', () => {
    const k = $('#api_key');
    const show = k.type === 'password';
    k.type = show ? 'text' : 'password';
    $('#toggle-key').textContent = show ? 'Sembunyikan' : 'Tampilkan';
    $('#toggle-key').setAttribute('aria-pressed', String(show));
  });
  // Cegah key tertinggal di halaman yang dipulihkan dari bfcache / tombol Back.
  window.addEventListener('pagehide', () => { $('#api_key').value = ''; });
  $('#form').addEventListener('input', (e) => {
    if (e.target.matches('[aria-invalid]')) { e.target.removeAttribute('aria-invalid'); }
    clearTimeout(init.t); init.t = setTimeout(saveForm, 400);
  });

  loadHistory();
  const resume = cfg.active_job || store.get(JOB_KEY);
  if (resume) setCurrent(resume);
}
document.addEventListener('visibilitychange', () => { if (!document.hidden && currentId && lastJob && ACTIVE.has(lastJob.status)) { clearTimeout(pollTimer); poll(); } });
init();
