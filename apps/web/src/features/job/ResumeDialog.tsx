import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Dialog } from "../../components/ui/Dialog";
import { Field, Input, RadioCards } from "../../components/ui/primitives";
import { useToast } from "../../components/ui/Toast";
import { id as t } from "../../copy/id";
import { ApiError } from "../../lib/api";
import { dateTimeLabel } from "../../lib/format";
import { useConfig, useCreateJob, useJob, useKeys } from "../../lib/queries";
import type { CreateJobBody } from "../../lib/types";
import { KEY_RE } from "../../lib/validation";

const D = t.dialog.resume;

export function ResumeMeter({ done, total }: { done: number; total: number }) {
  return <div className="resume-meter" aria-hidden="true">{Array.from({ length: total }, (_, i) => <i key={i} className={i < done ? "" : "todo"} />)}</div>;
}

/** Dialog "Lanjutkan dari titik terakhir": pakai key tersimpan, atau masukkan key (hanya di state, dikosongkan saat ditutup). */
export function ResumeDialog({ jobId, onClose }: { jobId: string | null; onClose: () => void }) {
  const open = !!jobId;
  const nav = useNavigate();
  const toast = useToast();
  const job = useJob(jobId ?? undefined);
  const cfg = useConfig();
  const keys = useKeys(open);
  const create = useCreateJob();
  const [src, setSrc] = useState<"saved" | "new">("saved");
  const [key, setKey] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => { if (!open) { setKey(""); setErr(""); setSrc("saved"); } }, [open]);
  useEffect(() => {
    const clear = () => setKey("");
    window.addEventListener("pagehide", clear);
    return () => window.removeEventListener("pagehide", clear);
  }, []);

  const j = job.data;
  const provider = j?.provider ?? "openrouter";
  const info = cfg.data?.providers.find((p) => p.id === provider);
  const label = info?.label ?? provider;
  const saved = keys.data?.keys.find((k) => k.provider === provider);
  const r = j?.resume ?? { available: true, done: 0, total: 0 };
  const useSaved = !!saved && src === "saved";
  const needsKey = !!j && !j.mock && !useSaved;

  async function ok(): Promise<boolean | void> {
    if (!j || !jobId) return false;
    setErr("");
    if (needsKey) {
      const k = key.trim();
      if (k.length < 8 || !KEY_RE.test(k)) { setErr(D.errShort); return false; }
      if (provider === "kenari" && !k.startsWith("kn-")) { setErr(D.errKenari); return false; }
    }
    const body: CreateJobBody = {
      ...(j.request as CreateJobBody),
      template: j.template ?? undefined,
      mock: j.mock,
      resume_from: jobId,
    };
    if (!j.mock) {
      body.provider = provider;
      if (j.models) { body.model_planner = j.models.planner; body.model_writer = j.models.writer; }
      if (useSaved) body.use_saved_key = true; else body.api_key = key.trim();
    }
    try {
      const created = await create.mutateAsync(body);
      setKey("");
      toast(t.job.toast.resumed, "ok");
      nav(`/job/${created.id}`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t.states.genericError);
      return false;
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title={D.title} icon="refresh" ok={D.ok} onOk={ok} busy={create.isPending || !j}>
      {!j ? <p className="small muted">{t.common.loading}</p> : (
        <>
          <p className="small"><b>{j.title}</b></p>
          {r.total > 0 && <ResumeMeter done={r.done} total={r.total} />}
          {r.total > 0 && (() => { const b = D.body(r.done, r.total); return <p className="small">{b.before}<b>{b.bold}</b>{b.after}<b>{b.free}</b></p>; })()}
          {!j.mock && saved && (
            <RadioCards name="rk" value={src} onChange={setSrc} className="one"
              options={[{ value: "saved", title: D.useSaved(label), hint: D.savedAt(dateTimeLabel(saved.saved_at)) }, { value: "new", title: D.other, hint: D.otherHint }]} />
          )}
          {!j.mock && !saved && <p className="small muted">{D.notSaved(label)}</p>}
          {needsKey && (
            <Field id="rk-key" label={D.keyLabel(label)} error={err}>
              {(a) => <Input mono type="password" autoComplete="new-password" autoCapitalize="off" spellCheck={false} maxLength={300} placeholder={provider === "kenari" ? "kn-…" : "sk-or-v1-…"} value={key} onChange={(e) => setKey(e.target.value)} {...a} />}
            </Field>
          )}
          {!needsKey && err && <p className="err" role="alert">{err}</p>}
        </>
      )}
    </Dialog>
  );
}
