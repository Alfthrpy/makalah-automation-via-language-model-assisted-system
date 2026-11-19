import { useState } from "react";
import { Link } from "react-router";
import { Icon } from "../../components/icons";
import { QuotaCard } from "../../components/QuotaCard";
import { Banner, Button, LinkButton, StatusBadge, Tag } from "../../components/ui/primitives";
import { id as t } from "../../copy/id";
import { useAuthState } from "../../lib/auth";
import { capFirst, greeting, whenLabel } from "../../lib/format";
import { useConfig, useJobs } from "../../lib/queries";
import { isActive, type JobSummary } from "../../lib/types";
import { ResumeDialog } from "../job/ResumeDialog";
import { stepLabel, stepsOf, summaryPct } from "../job/jobUtils";
import { useJobActions } from "../job/useJobActions";

const D = t.dash;

function ActiveBanner({ job }: { job: JobSummary }) {
  const cfg = useConfig();
  const pct = summaryPct(job);
  const label = stepLabel(stepsOf(cfg.data), job.current_step);
  const detail = job.status === "queued" ? D.queuedDetail(job.queue_position) : [label, job.current_detail].filter(Boolean).join(" · ") || t.status.running;
  const C = 125.6;
  return (
    <section className="active-banner" aria-label={D.activeLabel}>
      <svg className="ring" viewBox="0 0 48 48" aria-hidden="true">
        <circle cx="24" cy="24" r="20" fill="none" stroke="var(--surface-2)" strokeWidth="5" />
        <circle cx="24" cy="24" r="20" fill="none" stroke="var(--accent)" strokeWidth="5" strokeLinecap="round" strokeDasharray={`${((pct / 100) * C).toFixed(1)} ${C}`} transform="rotate(-90 24 24)" />
        <text x="24" y="28" textAnchor="middle" fontSize="11" fontWeight="700" fill="var(--ink)" fontFamily="var(--font-body)">{pct}%</text>
      </svg>
      <div className="t"><StatusBadge status={job.status} mock={job.mock} /><b>{job.title}</b><span className="small muted num">{detail}</span></div>
      <LinkButton variant="primary" to={`/job/${job.id}`}>{D.seeProgress} <Icon name="arrow" /></LinkButton>
    </section>
  );
}

function HistoryItem({ j, onResume, actions }: { j: JobSummary; onResume: (id: string) => void; actions: ReturnType<typeof useJobActions> }) {
  const running = j.status === "running", queued = j.status === "queued";
  const canResume = (j.status === "error" || j.status === "interrupted") && j.resume?.available;
  return (
    <li className="hist-item">
      <div className="hist-main">
        <Link className="hist-title" to={`/job/${j.id}`}>{j.title}</Link>
        <div className="hist-meta">
          <StatusBadge status={j.status} mock={j.mock} />
          {j.mata_kuliah && <span>{j.mata_kuliah}</span>}
          <span>{capFirst(whenLabel(j.created_at))}</span>
          {canResume && j.resume && <Tag>{D.resumeTag(j.resume.done, j.resume.total)}</Tag>}
          {j.mock && <Tag>{D.mockTag}</Tag>}
        </div>
      </div>
      <div className="hist-actions">
        {running && <LinkButton to={`/job/${j.id}`}>{D.seeProgress}</LinkButton>}
        {queued && <><LinkButton to={`/job/${j.id}`}>{D.view}</LinkButton><Button variant="danger" aria-label={D.cancelFor(j.title)} onClick={() => void actions.remove(j)}>{D.cancel}</Button></>}
        {j.status === "done" && j.has_file && <Button onClick={() => void actions.download(j)}><Icon name="download" />{D.download}</Button>}
        {canResume && <Button onClick={() => onResume(j.id)}><Icon name="refresh" />{D.resume}</Button>}
        {!running && !queued && <Button variant="danger" icon aria-label={D.deleteFor(j.title)} onClick={() => void actions.remove(j)}><Icon name="trash" size="md" /></Button>}
      </div>
    </li>
  );
}

function Skeletons() {
  return (
    <div aria-busy="true"><span className="sr-only">{D.loadingHist}</span>
      {[0, 1, 2].map((i) => (
        <div className="skel-row" aria-hidden="true" key={i}>
          <div style={{ display: "grid", gap: 8 }}><div className="skel" style={{ height: 16, width: "80%" }} /><div className="skel" style={{ height: 12, width: "45%" }} /></div>
          <div className="skel" style={{ height: 40 }} />
        </div>
      ))}
    </div>
  );
}

function EmptyHistory() {
  return (
    <div className="empty">
      <svg className="big" viewBox="0 0 120 96" aria-hidden="true"><rect x="22" y="8" width="64" height="80" rx="4" fill="var(--surface)" stroke="var(--line-strong)" strokeWidth="2" /><path d="M34 8v80" stroke="var(--margin-red)" strokeWidth="2" /><path d="M40 28h36M40 40h36M40 52h24" stroke="var(--rule)" strokeWidth="3" strokeLinecap="round" /><rect x="38" y="60" width="30" height="8" rx="2" fill="var(--mark)" /><circle cx="92" cy="70" r="16" fill="var(--accent)" /><path d="M92 63v14M85 70h14" stroke="var(--on-accent)" strokeWidth="3" strokeLinecap="round" /></svg>
      <b>{D.empty.title}</b><p>{D.empty.text}</p>
      <LinkButton variant="primary" to="/buat"><Icon name="plus" size="md" />{D.empty.cta}</LinkButton>
    </div>
  );
}

export default function Dashboard() {
  const auth = useAuthState();
  const jobs = useJobs();
  const actions = useJobActions();
  const [resumeId, setResumeId] = useState<string | null>(null);
  const list = jobs.data ?? [];
  const active = list.find((j) => isActive(j.status));
  const firstName = auth.mode === "clerk" ? (auth.user?.name.split(" ")[0] ?? "") : "";

  return (
    <main className="screen" id="main">
      <div className="wrap">
        <div className="page-head">
          <div><h1>{D.greet(greeting(), firstName)}</h1><p>{D.sub}</p></div>
          <LinkButton variant="primary" lg to="/buat"><Icon name="plus" size="md" />{D.newBtn}</LinkButton>
        </div>
        <div className="dash-grid">
          <div className="stack">
            {active && <ActiveBanner job={active} />}
            <section className="card" aria-labelledby="hist-h">
              <h2 className="card-title" id="hist-h">{D.title}</h2>
              <div aria-live="polite">
                {jobs.isPending ? <Skeletons />
                  : jobs.isError ? <Banner kind="bad" title={D.loadError} actions={<Button onClick={() => void jobs.refetch()}><Icon name="refresh" />{t.common.retry}</Button>}>{jobs.error.message}</Banner>
                  : !list.length ? <EmptyHistory />
                  : <ul className="hist">{list.map((j) => <HistoryItem key={j.id} j={j} onResume={setResumeId} actions={actions} />)}</ul>}
              </div>
            </section>
          </div>
          <aside className="stack">
            <QuotaCard variant="dash" />
            <section className="card" aria-labelledby="tips-h" style={{ display: "grid", gap: 10 }}>
              <h2 className="eyebrow" id="tips-h">{D.tips.title}</h2>
              <p className="small">{D.tips.text}</p>
            </section>
          </aside>
        </div>
      </div>
      <ResumeDialog jobId={resumeId} onClose={() => setResumeId(null)} />
    </main>
  );
}
