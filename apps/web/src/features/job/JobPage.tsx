import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { Icon } from "../../components/icons";
import { Banner, Button, EmptyState, LinkButton, Skeleton, StatusBadge, Tag } from "../../components/ui/primitives";
import { useToast } from "../../components/ui/Toast";
import { id as t } from "../../copy/id";
import { ApiError } from "../../lib/api";
import { clock, nf, whenLabel } from "../../lib/format";
import { retryDelaySec, useConfig, useJob, useKeys } from "../../lib/queries";
import { store } from "../../lib/storage";
import type { Job, StepInfo } from "../../lib/types";
import { isActive } from "../../lib/types";
import { REFILL_KEY } from "../create/formState";
import { ResumeDialog, ResumeMeter } from "./ResumeDialog";
import { elapsedLabel, errorStepKey, stepLabel, stepSeconds, stepsOf } from "./jobUtils";
import { useJobActions } from "./useJobActions";

const J = t.job;

function Stepper({ job, steps }: { job: Job; steps: StepInfo[] }) {
  return (
    <ol className="stepper">
      {steps.map((s) => {
        const st = job.steps[s.key] ?? { status: "pending" as const, detail: "" };
        const sec = stepSeconds(st);
        return (
          <li key={s.key} className="step" data-s={st.status} aria-current={st.status === "running" ? "step" : undefined}>
            <span className="dot">
              <Icon name="dot" className="d-pending" /><Icon name="spin" className="d-run" /><Icon name="check" className="d-done" /><Icon name="skip" className="d-skip" /><Icon name="x" className="d-err" />
            </span>
            <div className="step-body">
              <span className="step-label">{s.label}<span className="step-state">· {t.stepState[st.status]}</span></span>
              <span className="step-hint">{s.hint}</span>
              <span className="step-detail">{st.detail}</span>
            </div>
            <span className="step-time">{sec != null ? clock(sec) : ""}</span>
          </li>
        );
      })}
    </ol>
  );
}

function LogPanel({ job }: { job: Job }) {
  const pre = useRef<HTMLPreElement>(null);
  const stick = useRef(true);
  const lines = job.log.slice(-300);
  const time = (iso: string) => new Intl.DateTimeFormat("id-ID", { timeZone: "Asia/Jakarta", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" }).format(new Date(iso)).replace(/:/g, ".");
  const text = lines.map((l) => `[${time(l.t)}] ${l.msg}`).join("\n");
  useEffect(() => { const el = pre.current; if (el && stick.current) el.scrollTop = el.scrollHeight; }, [text]);
  const bad = job.status === "error" || job.status === "interrupted";
  return (
    <details className="log" open={bad || undefined} key={bad ? "open" : "closed"}>
      <summary><Icon name="chev" />{J.log} <span className="muted small">{J.logLines(lines.length)}</span></summary>
      <pre ref={pre} tabIndex={0} aria-label={J.logLabel}
        onScroll={(e) => { const el = e.currentTarget; stick.current = el.scrollTop + el.clientHeight >= el.scrollHeight - 24; }}>{text}</pre>
    </details>
  );
}

function SideCard({ job, onResume }: { job: Job; onResume: () => void }) {
  const actions = useJobActions();
  const nav = useNavigate();
  const toast = useToast();
  const cfg = useConfig();
  const keys = useKeys(job.status === "interrupted");
  const provLabel = cfg.data?.providers.find((p) => p.id === job.provider)?.label ?? job.provider ?? "";
  const S = J.side;
  const [dl, setDl] = useState(false);

  const refill = () => {
    if (job.request) { try { store.set(REFILL_KEY, JSON.stringify({ request: job.request, template: job.template, mock: job.mock, provider: job.provider })); } catch { /* abaikan */ } }
    toast(t.form.toast.refilled);
    nav("/buat");
  };
  const del = <Button variant="danger" onClick={() => void actions.remove(job, { thenGo: "/dasbor" })}><Icon name="trash" />{S.delete}</Button>;
  const r = job.resume;

  switch (job.status) {
    case "queued":
      return (
        <section className="card side-card">
          <h2 className="card-title"><Icon name="clock" size="md" />{S.queuedTitle}</h2>
          <p className="small">{S.queuedText(job.queue_position)}</p>
          <Button variant="danger" block onClick={() => void actions.remove(job, { thenGo: "/dasbor" })}><Icon name="slash" />{S.cancelPaper}</Button>
          <p className="why"><Icon name="info" />{S.cancelWhy}</p>
        </section>
      );
    case "running":
      return (
        <section className="card side-card">
          <h2 className="card-title"><Icon name="spin" size="md" style={{ color: "var(--accent)" }} />{S.runningTitle}</h2>
          <div className="conn"><i aria-hidden="true" /><span>{S.connected}</span></div>
          <p className="small">{S.runningText}</p>
          <span data-tip style={{ display: "grid" }}>
            <Button block disabledReason aria-describedby="why-stop"><Icon name="pause" />{S.stop}</Button>
            <span className="tip" role="tooltip">{S.stopTip}</span>
          </span>
          <p className="why" id="why-stop"><Icon name="info" />{S.stopWhy}</p>
        </section>
      );
    case "done": {
      const st = job.stats ?? {};
      const mock = job.mock;
      const fulltext = st.fulltext_total != null ? `${st.fulltext_ok ?? 0}/${st.fulltext_total}` : "—";
      return (
        <section className="card side-card">
          <h2 className="card-title"><Icon name="check" size="md" style={{ color: "var(--ok)" }} />{S.doneTitle}</h2>
          <div className="stats">
            <div><b>{st.subbab_count ?? "—"}</b><span>{S.stats.subbab}</span></div>
            <div><b>{mock ? "—" : (st.refs_final ?? st.refs_found ?? "—")}</b><span>{S.stats.refs}</span></div>
            <div><b>{mock ? "—" : (st.citations_total ?? "—")}</b><span>{S.stats.cites}</span></div>
            <div><b>{mock ? "—" : fulltext}</b><span>{S.stats.fulltext}</span></div>
            <div style={{ gridColumn: "1/-1" }}><b>{mock || !job.usage ? S.mockLabel : nf.format(job.usage.total)}</b><span>{mock || !job.usage ? S.mockTokens : S.tokens(provLabel)}</span></div>
          </div>
          <Button variant="primary" lg block aria-disabled={dl || undefined} onClick={async () => { setDl(true); await actions.download(job); setDl(false); }}>
            <Icon name="download" size="md" />{dl ? S.downloading : S.download}
          </Button>
          <p className="small muted">{mock ? S.mockNote : S.realNote}</p>
          {!mock && <p className="why"><Icon name="shield" />{job.key_source === "saved" ? S.keyKept : S.keyGone}</p>}
          <div className="btn-row"><Button variant="ghost" onClick={refill}>{S.refill}</Button>{del}</div>
        </section>
      );
    }
    case "error":
    case "interrupted": {
      const err = job.status === "error";
      const canResume = !!r?.available;
      return (
        <section className="card side-card">
          <h2 className="card-title">
            <Icon name={err ? "x" : "pause"} size="md" style={{ color: err ? "var(--bad)" : "var(--warn)" }} />{err ? S.errorTitle : S.interruptedTitle}
          </h2>
          {err ? <Banner kind="bad" role="status">{job.error || S.errorFallback}</Banner>
            : <p className="small">{S.interruptedText(job.key_source === "saved" && keys.data?.keys.some((k) => k.provider === job.provider) !== false)}</p>}
          {r && r.total > 0 && (
            <div style={{ display: "grid", gap: 8 }}>
              <ResumeMeter done={r.done} total={r.total} />
              {(() => { const x = S.resumeDone(r.done, r.total); return <span className="small"><b>{x.bold}</b>{x.rest}</span>; })()}
            </div>
          )}
          {canResume && <><Button variant="primary" lg block onClick={onResume}><Icon name="refresh" size="md" />{S.resumeBtn}</Button><p className="why"><Icon name="info" />{S.resumeFree}</p></>}
          <div className="btn-row"><Button variant="ghost" onClick={refill}>{S.refillForm}</Button>{del}</div>
        </section>
      );
    }
    case "cancelled":
      return (
        <section className="card side-card">
          <h2 className="card-title"><Icon name="slash" size="md" style={{ color: "var(--muted)" }} />{S.cancelledTitle}</h2>
          <p className="small">{S.cancelledText}</p>
          <div className="btn-row"><Button variant="primary" onClick={refill}>{S.refillForm}</Button>{del}</div>
        </section>
      );
  }
}

function ConnBanner({ failures, errorAt, onNow }: { failures: number; errorAt: number; onNow: () => void }) {
  const total = retryDelaySec(failures);
  const [left, setLeft] = useState(total);
  useEffect(() => {
    const tick = () => setLeft(Math.max(0, total - Math.round((Date.now() - errorAt) / 1000)));
    tick();
    const iv = setInterval(tick, 500);
    return () => clearInterval(iv);
  }, [total, errorAt]);
  return (
    <div style={{ marginBottom: "var(--sp-4)" }}>
      <Banner kind="bad" icon="wifi-off" role="status" title={J.conn.title}
        actions={<Button onClick={onNow}><Icon name="refresh" />{J.conn.now}</Button>}>{J.conn.text(left)}</Banner>
    </div>
  );
}

export default function JobPage() {
  const { id } = useParams();
  const q = useJob(id);
  const cfg = useConfig();
  const toast = useToast();
  const [resumeOpen, setResumeOpen] = useState(false);
  const steps = useMemo(() => stepsOf(cfg.data), [cfg.data]);
  const job = q.data;
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { if (job && isActive(job.status)) { const iv = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(iv); } }, [job]);

  // Toast sekali saat job yang sedang dipantau selesai.
  const prev = useRef<string | null>(null);
  useEffect(() => {
    if (!job) return;
    if (prev.current && isActive(prev.current as Job["status"]) && job.status === "done") toast(J.toast.ready, "ok");
    prev.current = job.status;
  }, [job, toast]);

  // Koneksi putus: banner + coba lagi; tetap tampilkan data terakhir.
  const offline = q.isError && q.error instanceof ApiError && q.error.status === 0;
  const notFound = q.isError && q.error instanceof ApiError && q.error.status === 404;

  if (notFound) {
    return (
      <main className="screen" id="main"><div className="wrap">
        <EmptyState icon="doc" title={J.notFound.title} action={<LinkButton to="/dasbor">{J.notFound.cta}</LinkButton>}>{J.notFound.text}</EmptyState>
      </div></main>
    );
  }
  if (!job) {
    return (
      <main className="screen" id="main" aria-busy="true"><div className="wrap" style={{ display: "grid", gap: 12 }}>
        {q.isError && !offline ? <Banner kind="bad" title={t.states.serverDownTitle} actions={<Button onClick={() => void q.refetch()}><Icon name="refresh" />{t.common.retry}</Button>}>{q.error.message}</Banner>
          : offline ? <ConnBanner failures={q.failureCount || 1} errorAt={q.errorUpdatedAt} onNow={() => void q.refetch()} />
          : <><Skeleton h={20} w="20%" /><Skeleton h={36} w="60%" /><Skeleton h={260} /></>}
      </div></main>
    );
  }

  const p = job.provider ? cfg.data?.providers.find((x) => x.id === job.provider) : undefined;
  const provLabel = p?.label ?? job.provider ?? "";
  const resumeTag = (job.status === "error" || job.status === "interrupted") && job.resume?.available && job.resume.total > 0;
  const errKey = errorStepKey(job, steps);
  const running = steps.find((s) => job.steps[s.key]?.status === "running");
  const statusLine = {
    queued: J.statusLine.queued(job.queue_position),
    running: J.statusLine.running(running ? [running.label, job.steps[running.key]?.detail].filter(Boolean).join(" · ") : t.status.running, elapsedLabel(job.started_at ?? job.created_at, null, now)),
    done: J.statusLine.done(elapsedLabel(job.started_at, job.finished_at)),
    error: J.statusLine.error(stepLabel(steps, errKey)),
    interrupted: J.statusLine.interrupted(stepLabel(steps, errKey) || stepLabel(steps, "tulis")),
    cancelled: J.statusLine.cancelled,
  }[job.status];

  return (
    <main className="screen" id="main">
      <div className="wrap">
        <div className="job-head">
          <Link className="back" to="/dasbor"><Icon name="back" />{J.back}</Link>
          <div className="btn-row">
            <StatusBadge status={job.status} mock={job.mock} />
            {resumeTag && job.resume && <Tag>{J.resumeTag(job.resume.done, job.resume.total)}</Tag>}
          </div>
          <h1>{job.title}</h1>
          <div className="meta-row">
            {job.request?.mata_kuliah && <span><Icon name="book" />{job.request.mata_kuliah}</span>}
            {job.template && <span><Icon name="doc" />{J.meta.template(job.template)}</span>}
            {job.mock ? <span><Icon name="flask" />{J.meta.mock}</span>
              : <span><Icon name="key" />{provLabel}{job.models && <> · <code>{job.models.planner}</code> / <code>{job.models.writer}</code></>}</span>}
            {!job.mock && job.key_source && <span><Icon name="lock" />{job.key_source === "saved" ? J.meta.keySaved : J.meta.keySession}</span>}
            <span><Icon name="clock" />{J.meta.created(whenLabel(job.created_at))}</span>
          </div>
        </div>
        {offline && <ConnBanner failures={q.failureCount || 1} errorAt={q.errorUpdatedAt} onNow={() => void q.refetch()} />}
        <div className="job-grid">
          <div className="stack">
            <section className="card" aria-labelledby="prog-h">
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "baseline", marginBottom: "var(--sp-4)" }}>
                <h2 className="card-title" id="prog-h">{J.progress}</h2>
                <span className="status-line num" aria-live="polite">{statusLine}</span>
              </div>
              <Stepper job={job} steps={steps} />
            </section>
            <LogPanel job={job} />
          </div>
          <aside className="stack"><SideCard job={job} onResume={() => setResumeOpen(true)} /></aside>
        </div>
      </div>
      <ResumeDialog jobId={resumeOpen ? job.id : null} onClose={() => setResumeOpen(false)} />
    </main>
  );
}
