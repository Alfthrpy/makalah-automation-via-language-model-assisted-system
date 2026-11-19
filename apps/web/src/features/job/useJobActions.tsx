import { useCallback } from "react";
import { useNavigate } from "react-router";
import { useConfirm } from "../../components/ui/Dialog";
import { useToast } from "../../components/ui/Toast";
import { id as t } from "../../copy/id";
import { ApiError, downloadJobFile } from "../../lib/api";
import { slug } from "../../lib/format";
import { useDeleteJob } from "../../lib/queries";
import type { JobSummary } from "../../lib/types";

/** Aksi bersama riwayat dan detail: unduh .docx, hapus/batalkan (dengan konfirmasi). */
export function useJobActions() {
  const confirm = useConfirm();
  const toast = useToast();
  const del = useDeleteJob();
  const nav = useNavigate();

  const download = useCallback(async (j: Pick<JobSummary, "id" | "title">) => {
    try { await downloadJobFile(j.id, `makalah-${slug(j.title)}.docx`); }
    catch (e) { toast(e instanceof ApiError && e.status !== 0 && e.message ? e.message : t.job.toast.downloadFail, "bad"); }
  }, [toast]);

  const remove = useCallback(async (j: Pick<JobSummary, "id" | "title" | "status" | "has_file">, opts?: { thenGo?: string }) => {
    const queued = j.status === "queued";
    const D = t.dialog;
    const ok = await confirm({
      title: queued ? D.cancelTitle : D.deleteTitle, icon: queued ? "slash" : "trash", okClass: "danger-solid",
      ok: queued ? D.cancelOk : D.deleteOk, cancel: t.common.back,
      body: <><p><b>{j.title}</b></p><p className="small muted">{queued ? D.cancelText : j.has_file ? D.deleteFileText : D.deleteText}</p></>,
    });
    if (!ok) return false;
    try {
      const r = await del.mutateAsync(j.id);
      toast(r.result === "cancelled" ? t.job.toast.cancelled : t.job.toast.deleted, "ok");
      if (opts?.thenGo) nav(opts.thenGo);
      return true;
    } catch (e) {
      toast(e instanceof ApiError ? e.message : t.states.genericError, "bad");
      return false;
    }
  }, [confirm, del, toast, nav]);

  return { download, remove };
}
