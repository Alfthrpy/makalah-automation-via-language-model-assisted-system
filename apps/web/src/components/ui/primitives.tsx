import { forwardRef, useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { Link, type LinkProps } from "react-router";
import { Icon, type IconName } from "../icons";
import { id as t } from "../../copy/id";
import type { JobStatus } from "../../lib/types";

type Variant = "default" | "primary" | "ghost" | "danger" | "danger-solid";
const cls = (...xs: (string | false | undefined)[]) => xs.filter(Boolean).join(" ");
const btnClass = (v: Variant, o: { lg?: boolean; block?: boolean; icon?: boolean; className?: string }) =>
  cls("btn", v !== "default" && v, o.lg && "lg", o.block && "block", o.icon && "icon", o.className);

interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant; lg?: boolean; block?: boolean; icon?: boolean;
  /** Nonaktif dengan alasan tertulis: tetap bisa difokus, klik diabaikan, aria-disabled. */
  disabledReason?: boolean;
}
export const Button = forwardRef<HTMLButtonElement, BtnProps>(function Button(
  { variant = "default", lg, block, icon, disabledReason, className, onClick, type = "button", ...rest }, ref) {
  return (
    <button ref={ref} type={type} className={btnClass(variant, { lg, block, icon, className })}
      aria-disabled={disabledReason || undefined}
      onClick={(e) => { if (disabledReason) { e.preventDefault(); return; } onClick?.(e); }} {...rest} />
  );
});

interface LinkBtnProps extends LinkProps { variant?: Variant; lg?: boolean; block?: boolean }
export function LinkButton({ variant = "default", lg, block, className, ...rest }: LinkBtnProps) {
  return <Link className={btnClass(variant, { lg, block, className })} {...rest} />;
}

export function StatusBadge({ status, mock }: { status: JobStatus; mock?: boolean }) {
  const icon: Record<JobStatus, IconName> = { queued: "clock", running: "spin", done: "check", error: "x", interrupted: "pause", cancelled: "slash" };
  return (
    <span className="badge" data-s={status}>
      <Icon name={icon[status]} />{t.status[status]}{mock ? t.status.mockSuffix : ""}
    </span>
  );
}

export function Tag({ children, mark, style }: { children: ReactNode; mark?: boolean; style?: React.CSSProperties }) {
  return <span className={cls("tag", mark && "mark")} style={style}>{children}</span>;
}

export function Banner({ kind, icon, title, children, actions, role }: {
  kind: "info" | "warn" | "bad" | "ok"; icon?: IconName; title?: string; children?: ReactNode; actions?: ReactNode; role?: "alert" | "status"; }) {
  const ic: IconName = icon ?? (kind === "bad" ? "alert" : kind === "warn" ? "alert" : kind === "ok" ? "check" : "info");
  return (
    <div className={`banner ${kind}`} role={role ?? (kind === "bad" || kind === "warn" ? "alert" : "status")}>
      <Icon name={ic} size="md" />
      <div className="b-body">
        {title && <strong>{title}</strong>}
        {children && <span>{children}</span>}
        {actions && <div className="btn-row">{actions}</div>}
      </div>
    </div>
  );
}

export function Card({ children, className, ...rest }: React.HTMLAttributes<HTMLElement> & { as?: "section" | "div" | "aside" }) {
  return <section className={cls("card", className)} {...rest}>{children}</section>;
}

/* ---------- form ---------- */
export function Field({ id, label, required, optional, hint, error, children, className }: {
  id: string; label: ReactNode; required?: boolean; optional?: boolean; hint?: ReactNode; error?: string; children: (a: { id: string; "aria-describedby": string; "aria-invalid"?: true }) => ReactNode; className?: string }) {
  const hid = `hint-${id}`, eid = `err-${id}`;
  return (
    <div className={cls("field", className)}>
      <label htmlFor={id}>{label}{required && <span className="req" aria-hidden="true"> *</span>}{optional && <span className="opt"> {t.common.optional}</span>}</label>
      {children({ id, "aria-describedby": [hint ? hid : "", eid].filter(Boolean).join(" "), ...(error ? { "aria-invalid": true as const } : {}) })}
      {hint && <p className="hint" id={hid}>{hint}</p>}
      <p className="err" id={eid}>{error}</p>
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { mono?: boolean }>(function Input({ mono, className, ...rest }, ref) {
  return <input ref={ref} className={cls("input", mono && "mono", className)} {...rest} />;
});
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={cls("input", className)} {...rest} />;
});
export function Select({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cls("input", className)} {...rest} />;
}

export function CheckCard({ id, checked, onChange, title, hint }: { id: string; checked: boolean; onChange: (v: boolean) => void; title: string; hint: ReactNode }) {
  return (
    <label className="check" htmlFor={id}>
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="t"><strong>{title}</strong><span className="hint">{hint}</span></span>
    </label>
  );
}

export interface ChoiceOption<V extends string> { value: V; title: ReactNode; hint?: ReactNode; extra?: ReactNode }
export function RadioCards<V extends string>({ name, value, onChange, options, className }: { name: string; value: V; onChange: (v: V) => void; options: ChoiceOption<V>[]; className?: string }) {
  return (
    <div className={cls("choice", className)}>
      {options.map((o) => (
        <label key={o.value}>
          <input type="radio" name={name} value={o.value} checked={value === o.value} onChange={() => onChange(o.value)} />
          <b>{o.title}</b>{o.hint && <span>{o.hint}</span>}{o.extra}
        </label>
      ))}
    </div>
  );
}

export function Seg<V extends string>({ label, value, onChange, options }: { label: string; value: V; onChange: (v: V) => void; options: { value: V; label: string }[] }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={value === o.value} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

export function Skeleton({ h, w }: { h: number; w?: string }) {
  return <div className="skel" style={{ height: h, width: w }} />;
}

export function EmptyState({ icon, title, children, action }: { icon?: IconName; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      {icon && <Icon name={icon} size="md" style={{ width: 40, height: 40, color: "var(--muted)" }} />}
      <b>{title}</b>{children && <p>{children}</p>}{action}
    </div>
  );
}

export function useUid(prefix: string) { return `${prefix}-${useId().replace(/:/g, "")}`; }
