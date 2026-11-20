import { useRef, useState } from "react";
import { Icon } from "./icons";
import { Banner, Button, Skeleton } from "./ui/primitives";
import { useConfirm } from "./ui/Dialog";
import { useToast } from "./ui/Toast";
import { id as t } from "../copy/id";
import { ApiError } from "../lib/api";
import { LOGO_ACCEPT, LogoPrepError, prepareLogo } from "../lib/image";
import { useDeleteLogo, useLogoPreview, useMe, useUploadLogo } from "../lib/queries";

const L = t.logo;

/** Kelola logo kampus/sekolah (satu per akun): pratinjau, unggah/ganti, hapus. `id` membedakan input berkas di halaman. */
export function LogoManager({ id }: { id: string }) {
  const me = useMe();
  const info = me.data?.logo ?? null;
  const preview = useLogoPreview(info?.updated_at, !!info);
  const upload = useUploadLogo();
  const del = useDeleteLogo();
  const confirm = useConfirm();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onPick(file: File | undefined) {
    if (!file) return;
    setError(null);
    setBusy(true);
    try {
      const png = await prepareLogo(file);
      await upload.mutateAsync(png);
      toast(L.uploaded, "ok");
    } catch (e) {
      setError(e instanceof LogoPrepError || e instanceof ApiError ? e.message : t.states.genericError);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = ""; // boleh memilih berkas yang sama lagi
    }
  }

  async function remove() {
    const ok = await confirm({ title: L.deleteTitle, icon: "trash", okClass: "danger-solid", ok: L.remove, cancel: t.common.back, body: <p className="small">{L.deleteBody}</p> });
    if (!ok) return;
    try { await del.mutateAsync(); toast(L.removed, "ok"); }
    catch (e) { toast(e instanceof ApiError ? e.message : t.states.genericError, "bad"); }
  }

  return (
    <div className="logo-box">
      <div className="logo-row">
        <div className="logo-preview" aria-live="polite">
          {me.isPending || (info && preview.isPending) ? <Skeleton h={72} />
            : info && preview.data ? <img src={preview.data} alt={L.alt} width={72} height={72} />
            : <span className="logo-empty" aria-hidden="true"><Icon name="doc" /></span>}
        </div>
        <div className="logo-actions">
          <p className="small muted" style={{ margin: 0 }}>{info ? L.privacy : L.none}</p>
          <div className="btn-row">
            <input ref={input} id={`${id}-file`} type="file" accept={LOGO_ACCEPT} hidden aria-label={L.fileLabel}
              onChange={(e) => void onPick(e.target.files?.[0])} />
            <Button type="button" onClick={() => input.current?.click()} disabled={busy}>
              <Icon name="plus" />{busy ? L.uploading : info ? L.replace : L.upload}
            </Button>
            {info && <Button type="button" variant="danger" onClick={() => void remove()} disabled={busy}><Icon name="trash" />{L.remove}</Button>}
          </div>
        </div>
      </div>
      {error && <Banner kind="bad" role="alert">{error}</Banner>}
    </div>
  );
}
