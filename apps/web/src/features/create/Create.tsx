import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { Icon } from "../../components/icons";
import { Banner, Button, CheckCard, Field, Input, LinkButton, RadioCards, Textarea } from "../../components/ui/primitives";
import { useToast } from "../../components/ui/Toast";
import { id as t } from "../../copy/id";
import { ApiError } from "../../lib/api";
import { dateTimeLabel, resetCountdown } from "../../lib/format";
import { useConfig, useCreateJob, useJobs, useKeys, useMe } from "../../lib/queries";
import { isActive } from "../../lib/types";
import { MAX_PENYUSUN, buildBody, emptyPenyusun, issuesToErrors, validatePaper, type FieldError, type PaperForm } from "../../lib/validation";
import { clearDraft, defaultForm, isBlank, loadDraft, newRid, providerNeedsModel, sampleForm, saveDraft, takeRefill } from "./formState";

const F = t.form;

type ServerBanner = { kind: "warn" | "info" | "bad"; title: string; text: string; retry?: boolean } | null;

function Section({ n, id, title, hint, children }: { n: number; id: string; title: string; hint: string; children: React.ReactNode }) {
  return (
    <section className="fsec" id={`sec-${id}`} aria-labelledby={`h-${id}`}>
      <div className="fsec-head"><span className="n">{n}</span><h2 id={`h-${id}`}>{title}</h2><p>{hint}</p></div>
      {children}
    </section>
  );
}

export default function Create() {
  const nav = useNavigate();
  const toast = useToast();
  const cfg = useConfig();
  const me = useMe();
  const jobs = useJobs();
  const keys = useKeys();
  const create = useCreateJob();

  const providers = useMemo(() => (cfg.data?.providers ?? []).filter((p) => p.enabled), [cfg.data]);
  const [form, setForm] = useState<PaperForm>(() => defaultForm());
  const [restored, setRestored] = useState(false);
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [server, setServer] = useState<ServerBanner>(null);
  const [showKey, setShowKey] = useState(false);
  const init = useRef(false);
  const formRef = useRef<HTMLFormElement>(null);

  // Nilai awal dari server (template bawaan, tahun, penyedia), lalu isi-ulang/draf. Sekali saja.
  useEffect(() => {
    if (init.current || !cfg.data) return;
    init.current = true;
    const base = defaultForm({ year: cfg.data.year, template: cfg.data.default_template || cfg.data.templates[0], provider: providers[0]?.id });
    const refill = takeRefill(base);
    const draft = refill ? null : loadDraft(base);
    const start = refill ?? draft ?? base;
    setForm(start);
    if (draft && !isBlank(draft)) setRestored(true);
  }, [cfg.data, providers]);

  // Simpan draf (TANPA key) dengan jeda; kosongkan key saat halaman ditutup/berpindah.
  useEffect(() => {
    if (!init.current) return;
    const tm = setTimeout(() => saveDraft(form), 400);
    return () => clearTimeout(tm);
  }, [form]);
  useEffect(() => {
    const clear = () => setForm((f) => (f.api_key ? { ...f, api_key: "" } : f));
    window.addEventListener("pagehide", clear);
    return () => { window.removeEventListener("pagehide", clear); clear(); };
  }, []);

  const set = <K extends keyof PaperForm>(k: K, v: PaperForm[K]) => {
    setForm((f) => ({ ...f, [k]: v }));
    if (errors.length) setErrors((es) => es.filter((e) => e.field !== (k as string)));
  };

  const prov = providers.find((p) => p.id === form.provider);
  const label = prov?.label ?? form.provider;
  const needModel = providerNeedsModel(prov, form.provider);
  const savedKey = keys.data?.keys.find((k) => k.provider === form.provider);
  const keySource = savedKey ? form.keySource : "new";
  const ctx = { provider: prov, hasSavedKey: !!savedKey && keySource === "saved" };
  const quota = me.data?.quota;
  const active = jobs.data?.find((j) => isActive(j.status));
  const rem = quota?.remaining ?? null;
  const left = resetCountdown(quota?.resets_at);

  let why = "";
  if (active) why = F.banner.activeWhy;
  else if (quota && quota.remaining <= 0 && !form.mock) why = F.banner.quotaWhy;

  const err = (k: string) => errors.find((e) => e.field === k)?.message;
  const errPen = errors.filter((e) => e.field === "penyusun");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setServer(null);
    if (why) { toast(why, "bad"); return; }
    const errs = validatePaper(form, ctx);
    setErrors(errs);
    if (errs.length) {
      const first = errs[0]!;
      const el = document.getElementById(first.anchor);
      el?.scrollIntoView({ block: "center", behavior: "smooth" });
      el?.focus({ preventScroll: true });
      return;
    }
    try {
      const job = await create.mutateAsync(buildBody(form, ctx));
      setForm((f) => ({ ...f, api_key: "", save_key: false })); // key tidak dibiarkan di halaman
      clearDraft();
      init.current = false; // draf kosong saat kembali
      toast(form.mock ? F.toast.queuedMock : F.toast.queued, "ok");
      nav(`/job/${job.id}`);
    } catch (ex) {
      if (!(ex instanceof ApiError)) { setServer({ kind: "bad", title: t.states.genericError, text: "" }); return; }
      if (ex.status === 422 && ex.issues.length) {
        const es = issuesToErrors(ex.issues, form);
        setErrors(es);
        document.getElementById(es[0]?.anchor ?? "judul")?.focus();
      } else if (ex.status === 429) {
        const m = ex.message;
        if (/kuota/i.test(m)) void me.refetch();
        if (/antrean penuh/i.test(m)) setServer({ kind: "warn", title: F.banner.queueFullTitle, text: F.banner.queueFullText, retry: true });
        else if (/kuota/i.test(m)) setServer({ kind: "warn", title: F.banner.quotaTitle, text: m });
        else setServer({ kind: "info", title: F.banner.activeTitle, text: m });
        void jobs.refetch();
      } else if (ex.status === 0) {
        setServer({ kind: "bad", title: t.states.serverDownTitle, text: t.states.serverDownText, retry: true });
      } else {
        setServer({ kind: "bad", title: F.banner.serverMsg, text: ex.message });
      }
    }
  }

  const setPen = (rid: string, k: "nama" | "nim", v: string) => {
    setForm((f) => ({ ...f, penyusun: f.penyusun.map((p) => (p.rid === rid ? { ...p, [k]: v } : p)) }));
    setErrors((es) => es.filter((e) => e.field !== "penyusun"));
  };
  const addPen = () => {
    if (form.penyusun.length >= MAX_PENYUSUN) return;
    const rid = newRid();
    setForm((f) => ({ ...f, penyusun: [...f.penyusun, emptyPenyusun(rid)] }));
    setTimeout(() => document.getElementById(`pn-${rid}`)?.focus(), 30);
  };
  const removePen = (rid: string) => {
    if (form.penyusun.length <= 1) return;
    const i = form.penyusun.findIndex((p) => p.rid === rid);
    const nextRid = (form.penyusun[i - 1] ?? form.penyusun[i + 1])?.rid;
    setForm((f) => ({ ...f, penyusun: f.penyusun.filter((p) => p.rid !== rid) }));
    setTimeout(() => document.getElementById(`pn-${nextRid}`)?.focus(), 30);
  };

  const base = () => defaultForm({ year: cfg.data?.year, template: form.template, provider: form.provider });
  const fillSample = () => { setForm((f) => ({ ...sampleForm(base()), template: f.template, provider: f.provider, mock: f.mock, keySource: f.keySource, api_key: f.api_key })); setErrors([]); };
  const clearForm = () => { setForm((f) => ({ ...base(), mock: f.mock })); setErrors([]); setServer(null); };

  const setProvider = (id: string) => {
    setForm((f) => ({ ...f, provider: id, model_planner: "", model_writer: "", api_key: "", keySource: "saved" }));
    setErrors((es) => es.filter((e) => !["api_key", "model_planner", "model_writer"].includes(e.field)));
  };

  // Status per bagian untuk daftar isi.
  const toc = {
    topik: form.judul.trim().length >= 3 && form.mata_kuliah.trim().length >= 2,
    penyusun: form.penyusun.some((p) => p.nama.trim()),
    institusi: /^(19|20)\d{2}$/.test(form.tahun.trim()),
    opsi: true,
    key: form.mock || ((keySource === "saved" || form.api_key.trim().length >= 8) && (!needModel || (!!form.model_planner.trim() && !!form.model_writer.trim()))),
  };

  const costLine = form.mock
    ? { q: F.summary.mockQuota, qs: F.summary.mockQuotaSub(rem), c: F.summary.mockCost, cs: F.summary.mockCostSub }
    : {
        q: quota ? (quota.remaining > 0 ? F.summary.quotaUse(quota.remaining) : F.summary.quotaOut) : F.summary.noQuota,
        qs: quota ? (quota.remaining > 0 ? F.summary.quotaUseSub(quota.remaining) : F.summary.quotaOutSub(left)) : F.summary.noQuotaSub,
        c: F.summary.costOf(label, keySource === "saved"), cs: F.summary.costSub(label, form.provider === "kenari"),
      };
  const shortCost = why || (form.mock ? F.summary.mobileMock : quota ? F.summary.mobileCost(label) : F.summary.mobileNoQuota(label));
  const submitDisabled = !!why;
  const submitText = create.isPending ? F.summary.submitting : F.summary.submit;
  const models = prov?.models ?? [];
  const f = F.f;

  return (
    <main className="screen" id="main">
      <div className="wrap">
        <div className="page-head">
          <div><h1>{F.title}</h1><p>{F.sub[0]}<span className="req">*</span>{F.sub[1]}</p></div>
          <div className="btn-row"><Button variant="ghost" onClick={fillSample}>{F.fillSample}</Button><Button variant="ghost" onClick={clearForm}>{F.clear}</Button></div>
        </div>

        <div className="stack" style={{ marginBottom: "var(--sp-4)" }}>
          {active && (
            <Banner kind="info" role="status" title={F.banner.activeTitle} actions={<LinkButton to={`/job/${active.id}`}>{t.dash.seeProgress}</LinkButton>}>{F.banner.activeText(active.title)}</Banner>
          )}
          {!active && quota && quota.remaining <= 0 && !form.mock && (
            <Banner kind="warn" title={F.banner.quotaTitle} actions={<Button onClick={() => set("mock", true)}>{F.banner.useMock}</Button>}>{F.banner.quotaText(quota.limit, left)}</Banner>
          )}
          {server && (
            <Banner kind={server.kind} title={server.title} actions={server.retry ? <Button onClick={() => formRef.current?.requestSubmit()}><Icon name="refresh" />{F.banner.retrySend}</Button> : undefined}>{server.text}</Banner>
          )}
          {restored && <Banner kind="info" role="status">{F.banner.draftRestored}</Banner>}
          {cfg.data && !cfg.data.key_storage && !form.mock && <Banner kind="info" role="status">{F.banner.keysUnavailable}</Banner>}
        </div>

        <div className="form-grid">
          <form ref={formRef} className="card" id="paper-form" noValidate autoComplete="off" aria-labelledby="scr-buat-h" onSubmit={onSubmit}>
            <span className="sr-only" id="scr-buat-h">{F.formLabel}</span>
            {errors.length > 0 && (
              <div className="banner bad err-summary" role="alert" style={{ marginBottom: "var(--sp-5)" }}>
                <Icon name="alert" size="md" />
                <div className="b-body">
                  <strong>{F.err.summary(new Set(errors.map((e) => e.field)).size)}</strong>
                  <ul style={{ display: "grid", gap: 4 }}>
                    {errors.filter((e, i, a) => a.findIndex((x) => x.field === e.field) === i).map((e) => (
                      <li key={e.field}><a href={`#${e.anchor}`} onClick={(ev) => { ev.preventDefault(); const el = document.getElementById(e.anchor); el?.scrollIntoView({ block: "center", behavior: "smooth" }); el?.focus({ preventScroll: true }); }}>
                        {F.err.names[e.field]}: {e.message}</a></li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            <Section n={1} id="topik" title={F.sec.topik} hint={F.secHint.topik}>
              <Field id="judul" label={f.judul} required hint={f.judulHint} error={err("judul")}>
                {(a) => <Textarea rows={2} maxLength={200} required value={form.judul} onChange={(e) => set("judul", e.target.value)} {...a} />}
              </Field>
              <div className="grid2">
                <Field id="mata_kuliah" label={f.mataKuliah} required error={err("mata_kuliah")}>
                  {(a) => <Input maxLength={120} required value={form.mata_kuliah} onChange={(e) => set("mata_kuliah", e.target.value)} {...a} />}
                </Field>
                <Field id="dosen_pengampu" label={f.dosen} optional>
                  {(a) => <Input maxLength={120} value={form.dosen_pengampu} onChange={(e) => set("dosen_pengampu", e.target.value)} {...a} />}
                </Field>
              </div>
            </Section>

            <Section n={2} id="penyusun" title={F.sec.penyusun} hint={F.secHint.penyusun}>
              <div className="pen-list">
                {form.penyusun.map((p, i) => (
                  <div className="pen-row" key={p.rid}>
                    <span className="no" aria-hidden="true">{i + 1}.</span>
                    <div className="field f-nama"><label htmlFor={`pn-${p.rid}`}>{f.nama}</label>
                      <input className="input" id={`pn-${p.rid}`} maxLength={100} autoComplete="off" value={p.nama} aria-invalid={errPen.length && !p.nama.trim() && (i === 0 || p.nim.trim()) ? true : undefined}
                        aria-describedby="err-penyusun" onChange={(e) => setPen(p.rid, "nama", e.target.value)} /></div>
                    <div className="field f-nim"><label htmlFor={`pm-${p.rid}`}>{f.nim} <span className="opt">{t.common.optional}</span></label>
                      <input className="input input-nim" id={`pm-${p.rid}`} maxLength={30} inputMode="numeric" value={p.nim} onChange={(e) => setPen(p.rid, "nim", e.target.value)} /></div>
                    <Button variant="danger" icon className="del" aria-label={f.removePen(i + 1)} disabledReason={form.penyusun.length === 1} onClick={() => removePen(p.rid)}><Icon name="trash" size="md" /></Button>
                  </div>
                ))}
              </div>
              <p className="err" id="err-penyusun">{errPen[0]?.message}</p>
              <div>
                <Button disabledReason={form.penyusun.length >= MAX_PENYUSUN} onClick={addPen}><Icon name="plus" size="md" />{f.addPen}</Button>{" "}
                <span className="small muted">{f.penCount(form.penyusun.length, form.penyusun.length >= MAX_PENYUSUN)}</span>
              </div>
            </Section>

            <Section n={3} id="institusi" title={F.sec.institusi} hint={F.secHint.institusi}>
              <Field id="universitas" label={f.universitas} hint={f.univHint}>
                {(a) => <Input maxLength={150} value={form.universitas} onChange={(e) => set("universitas", e.target.value)} {...a} />}
              </Field>
              <div className="grid2">
                <Field id="fakultas" label={f.fakultas}>{(a) => <Input maxLength={150} value={form.fakultas} onChange={(e) => set("fakultas", e.target.value)} {...a} />}</Field>
                <Field id="jurusan" label={f.jurusan}>{(a) => <Input maxLength={150} value={form.jurusan} onChange={(e) => set("jurusan", e.target.value)} {...a} />}</Field>
              </div>
              <div className="grid3">
                <Field id="kota" label={f.kota}>{(a) => <Input maxLength={80} value={form.kota} onChange={(e) => set("kota", e.target.value)} {...a} />}</Field>
                <Field id="kelas" label={f.kelas}>{(a) => <Input maxLength={30} value={form.kelas} onChange={(e) => set("kelas", e.target.value)} {...a} />}</Field>
                <Field id="tahun" label={f.tahun} required error={err("tahun")}>
                  {(a) => <Input mono inputMode="numeric" maxLength={4} value={form.tahun} onChange={(e) => set("tahun", e.target.value)} {...a} />}
                </Field>
              </div>
            </Section>

            <Section n={4} id="opsi" title={F.sec.opsi} hint={F.secHint.opsi}>
              <fieldset style={{ border: 0, padding: 0, margin: 0, display: "grid", gap: 8 }}>
                <legend className="lbl" style={{ marginBottom: 8 }}>{f.template}</legend>
                <RadioCards name="template" className="tpl" value={form.template} onChange={(v) => set("template", v)}
                  options={(cfg.data?.templates ?? []).map((name) => ({
                    value: name, title: name, hint: F.templateHint(name, name === cfg.data?.default_template),
                    extra: <span className="tpl-thumb" aria-hidden="true"><i /><i /><i /><i /></span>,
                  }))} />
              </fieldset>
              <CheckCard id="mock" checked={form.mock} onChange={(v) => set("mock", v)} title={f.mock} hint={f.mockHint} />
            </Section>

            <Section n={5} id="key" title={F.sec.key} hint={F.secHint.key(label)}>
              {form.mock ? (
                <Banner kind="info" icon="flask" role="status" title={f.mockNoteTitle}>{f.mockNote}</Banner>
              ) : (
                <div className="fsec" style={{ gap: "var(--sp-4)" }}>
                  <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
                    <legend className="lbl" style={{ marginBottom: 8 }}>{f.provider}</legend>
                    <RadioCards name="provider" value={form.provider} onChange={setProvider}
                      options={providers.map((p) => ({ value: p.id, title: p.label, hint: F.providerHint[p.id] ?? "" }))} />
                  </fieldset>

                  {savedKey && (
                    <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
                      <legend className="lbl" style={{ marginBottom: 8 }}>{f.apiKey}</legend>
                      <RadioCards name="keysrc" value={keySource} onChange={(v) => set("keySource", v)}
                        options={[{ value: "saved", title: f.keySaved, hint: f.keySavedHint(dateTimeLabel(savedKey.saved_at)) }, { value: "new", title: f.keyNew, hint: f.keyNewHint }]} />
                    </fieldset>
                  )}

                  {keySource === "new" && (
                    <div className="fsec" style={{ gap: "var(--sp-3)" }}>
                      <Field id="api_key" label={f.keyOf(label)} required error={err("api_key")}
                        hint={<>{f.noKey} {prov && <a href={prov.key_url} target="_blank" rel="noopener noreferrer">{f.makeKey(label)} <Icon name="ext" style={{ verticalAlign: -3 }} /></a>}{form.provider === "kenari" ? ` · ${f.kenariPrefix}` : ""}</>}>
                        {(a) => (
                          <div className="keyrow">
                            <Input mono type={showKey ? "text" : "password"} autoComplete="new-password" autoCapitalize="off" spellCheck={false} maxLength={300}
                              placeholder={form.provider === "kenari" ? "kn-…" : "sk-or-v1-…"} value={form.api_key} onChange={(e) => set("api_key", e.target.value)} {...a} />
                            <button type="button" className="btn" aria-pressed={showKey} aria-controls="api_key" onClick={() => setShowKey((s) => !s)}>
                              <Icon name="eye" /><span>{showKey ? f.hide : f.show}</span>
                            </button>
                          </div>
                        )}
                      </Field>
                      {cfg.data?.key_storage && <CheckCard id="save_key" checked={form.save_key} onChange={(v) => set("save_key", v)} title={f.saveKey} hint={f.saveKeyHint} />}
                    </div>
                  )}

                  <div className="grid2">
                    <Field id="model_planner" label={<>{f.modelPlanner}</>} required={needModel} optional={!needModel} error={err("model_planner")}
                      hint={needModel ? f.plannerHintNeed : f.plannerHintDefault(prov?.default_planner ?? "")}>
                      {(a) => <Input mono list="models-list" maxLength={100} spellCheck={false} placeholder={prov?.default_planner || f.modelPh} value={form.model_planner} onChange={(e) => set("model_planner", e.target.value)} {...a} />}
                    </Field>
                    <Field id="model_writer" label={<>{f.modelWriter}</>} required={needModel} optional={!needModel} error={err("model_writer")}
                      hint={needModel ? f.writerHintNeed : f.writerHintDefault(prov?.default_writer ?? "")}>
                      {(a) => <Input mono list="models-list" maxLength={100} spellCheck={false} placeholder={prov?.default_writer || f.modelPh} value={form.model_writer} onChange={(e) => set("model_writer", e.target.value)} {...a} />}
                    </Field>
                  </div>
                  <datalist id="models-list">{models.map((m) => <option key={m} value={m} />)}</datalist>
                  {models.length > 0 && (
                    <div className="models-chips" aria-label={f.suggestions}>
                      <span className="small muted" style={{ alignSelf: "center" }}>{f.suggestions}</span>
                      {models.map((m) => (
                        <button key={m} type="button" className="chipbtn" aria-label={f.useModel(m)} onClick={() => setForm((x) => ({ ...x, model_planner: m, model_writer: m }))}>{m}</button>
                      ))}
                    </div>
                  )}
                  <div className="privacy-box" role="note">
                    <b>{F.privacy.title}</b>
                    <ul>{F.privacy.items.map((x) => <li key={x}><Icon name="check" /><span>{x}</span></li>)}</ul>
                  </div>
                </div>
              )}
            </Section>

            <div className="mobile-submit">
              <Button type="submit" variant="primary" lg block disabledReason={submitDisabled || create.isPending} aria-describedby={why ? "submit-why" : undefined}>{submitText}</Button>
              <span className="small muted">{shortCost}</span>
            </div>
          </form>

          <aside className="summary">
            <section className="card side-card" aria-labelledby="sum-h">
              <h2 className="card-title" id="sum-h">{F.summary.title}</h2>
              <div className="sum-list">
                <div><Icon name="doc" /><span><b>{costLine.q}</b><span className="muted">{costLine.qs}</span></span></div>
                <div><Icon name="key" /><span><b>{costLine.c}</b><span className="muted">{costLine.cs}</span></span></div>
                <div><Icon name="clock" /><span><b>{F.summary.time}</b><span className="muted">{F.summary.timeSub}</span></span></div>
              </div>
              <div className="desk-submit">
                <Button type="submit" form="paper-form" variant="primary" lg block disabledReason={submitDisabled || create.isPending} aria-describedby={why ? "submit-why" : undefined}>{submitText}</Button>
                {why && <p className="small muted" id="submit-why">{why}</p>}
              </div>
            </section>
            <nav className="card toc-card" aria-label={F.toc.label}>
              <div className="toc">
                {([["topik", F.sec.topik], ["penyusun", F.sec.penyusun], ["institusi", F.sec.institusi], ["opsi", F.sec.opsi], ["key", F.sec.key]] as const).map(([k, name], i) => (
                  <a key={k} href={`#sec-${k}`} onClick={(e) => { e.preventDefault(); document.getElementById(`sec-${k}`)?.scrollIntoView({ behavior: "smooth" }); }}>
                    {i + 1} · {name}
                    <span className="st">{toc[k]
                      ? <span className="tag" style={{ background: "var(--ok-soft)", color: "var(--ok)" }}><Icon name="check" /><span className="sr-only">{F.toc.done}</span></span>
                      : <span className="tag">{F.toc.todo}</span>}</span>
                  </a>
                ))}
              </div>
            </nav>
          </aside>
        </div>
      </div>
    </main>
  );
}
