import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Icon, type IconName } from "../icons";
import { id as t } from "../../copy/id";

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  icon?: IconName;
  iconColor?: string;
  children?: ReactNode;
  ok?: string;
  okClass?: "primary" | "danger-solid";
  cancel?: string | null;
  /** Kembalikan false untuk menahan dialog tetap terbuka (mis. validasi gagal). */
  onOk?: () => boolean | void | Promise<boolean | void>;
  busy?: boolean;
}

/** Dialog di atas <dialog> bawaan: fokus terkunci, Esc menutup, backdrop dari token --scrim. */
export function Dialog({ open, onClose, title, icon, iconColor, children, ok = "OK", okClass = "primary", cancel = t.common.cancel, onOk, busy }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const hid = useId();
  const okRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      try { d.showModal(); } catch { d.setAttribute("open", ""); }
      const first = d.querySelector<HTMLElement>("input:not([type=radio]), input:checked") ?? okRef.current;
      setTimeout(() => first?.focus(), 30);
    } else if (!open && d.open) d.close();
  }, [open]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    const r = await onOk?.();
    if (r === false) return;
    onClose();
  }

  return (
    <dialog ref={ref} aria-labelledby={hid} onClose={() => { if (open) onClose(); }}>
      <form className="dlg" onSubmit={submit}>
        <h2 id={hid}>{icon && <Icon name={icon} size="md" style={iconColor ? { color: iconColor } : undefined} />}{title}</h2>
        <div style={{ display: "grid", gap: 12 }}>{children}</div>
        <div className="btn-row">
          {cancel !== null && <button type="button" className="btn" onClick={onClose}>{cancel}</button>}
          <button ref={okRef} type="submit" className={`btn ${okClass}`} aria-disabled={busy || undefined}>{ok}</button>
        </div>
      </form>
    </dialog>
  );
}

/* ---------- konfirmasi berbasis promise ---------- */
export interface ConfirmOptions {
  title: string; icon?: IconName; body?: ReactNode; ok: string; okClass?: "primary" | "danger-solid"; cancel?: string | null;
}
type ConfirmFn = (o: ConfirmOptions) => Promise<boolean>;
const ConfirmCtx = createContext<ConfirmFn>(async () => false);
export const useConfirm = () => useContext(ConfirmCtx);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [opts, setOpts] = useState<ConfirmOptions | null>(null);
  const resolver = useRef<((v: boolean) => void) | null>(null);

  const confirm = useCallback<ConfirmFn>((o) => new Promise<boolean>((res) => { resolver.current?.(false); resolver.current = res; setOpts(o); }), []);
  const finish = (v: boolean) => { resolver.current?.(v); resolver.current = null; setOpts(null); };
  const value = useMemo(() => confirm, [confirm]);

  return (
    <ConfirmCtx.Provider value={value}>
      {children}
      <Dialog open={!!opts} onClose={() => finish(false)} onOk={() => { finish(true); }} title={opts?.title ?? ""} icon={opts?.icon}
        ok={opts?.ok ?? "OK"} okClass={opts?.okClass} cancel={opts?.cancel === undefined ? t.common.back : opts.cancel}>
        {opts?.body}
      </Dialog>
    </ConfirmCtx.Provider>
  );
}
