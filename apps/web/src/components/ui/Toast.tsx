import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Icon, type IconName } from "../icons";
import { id as t } from "../../copy/id";

export type ToastKind = "info" | "ok" | "bad";
interface ToastItem { key: number; msg: string; kind: ToastKind }
type Push = (msg: string, kind?: ToastKind) => void;

const Ctx = createContext<Push>(() => {});
export const useToast = () => useContext(Ctx);

const ICON: Record<ToastKind, IconName> = { ok: "check", bad: "alert", info: "info" };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const seq = useRef(0);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((key: number) => {
    setItems((xs) => xs.filter((x) => x.key !== key));
    const tm = timers.current.get(key);
    if (tm) { clearTimeout(tm); timers.current.delete(key); }
  }, []);
  const push = useCallback<Push>((msg, kind = "info") => {
    const key = ++seq.current;
    setItems((xs) => [...xs.slice(-3), { key, msg, kind }]);
    timers.current.set(key, setTimeout(() => dismiss(key), 4200));
  }, [dismiss]);
  useEffect(() => { const m = timers.current; return () => { m.forEach(clearTimeout); m.clear(); }; }, []);

  const value = useMemo(() => push, [push]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="toasts" aria-live="polite" aria-atomic="false">
        {items.map((x) => (
          <div key={x.key} className="toast" data-k={x.kind} role={x.kind === "bad" ? "alert" : "status"}>
            <Icon name={ICON[x.kind]} size="md" />
            <span>{x.msg}</span>
            <button type="button" aria-label={t.common.close} onClick={() => dismiss(x.key)}><Icon name="x" /></button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
