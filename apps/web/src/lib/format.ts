const TZ = "Asia/Jakarta";

export const capFirst = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

export function slug(t: string): string {
  return t.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60) || "makalah";
}

/** "hari ini, 09.41" / "kemarin, 14.20" / "17 Nov, 20.05" (zona WIB). */
export function whenLabel(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const ymd = (x: Date) => new Intl.DateTimeFormat("sv-SE", { timeZone: TZ }).format(x);
  const time = new Intl.DateTimeFormat("id-ID", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(d).replace(":", ".");
  const day = ymd(d);
  const today = ymd(now);
  const yest = ymd(new Date(now.getTime() - 86_400_000));
  if (day === today) return `hari ini, ${time}`;
  if (day === yest) return `kemarin, ${time}`;
  const dm = new Intl.DateTimeFormat("id-ID", { timeZone: TZ, day: "numeric", month: "short" }).format(d);
  return `${dm}, ${time}`;
}

export function dateTimeLabel(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const dm = new Intl.DateTimeFormat("id-ID", { timeZone: TZ, day: "numeric", month: "short", year: "numeric" }).format(d);
  const time = new Intl.DateTimeFormat("id-ID", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(d).replace(":", ".");
  return `${dm}, ${time}`;
}

/** Sisa waktu sampai `resetsAt` (ISO); tanpa argumen: sampai 00.00 WIB berikutnya. */
export function resetCountdown(resetsAt?: string | null, now: Date = new Date()): string {
  let left: number;
  if (resetsAt) {
    left = Math.max(0, Math.round((new Date(resetsAt).getTime() - now.getTime()) / 60_000));
  } else {
    const parts = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(now);
    const h = Number(parts.find((p) => p.type === "hour")?.value ?? 0);
    const m = Number(parts.find((p) => p.type === "minute")?.value ?? 0);
    left = 24 * 60 - (h * 60 + m);
  }
  const hh = Math.floor(left / 60);
  const mm = left % 60;
  return hh ? `${hh} jam ${mm} menit` : `${mm} menit`;
}

export function greeting(now: Date = new Date()): string {
  const h = Number(new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", hourCycle: "h23" }).format(now));
  return h < 11 ? "Selamat pagi" : h < 15 ? "Selamat siang" : h < 19 ? "Selamat sore" : "Selamat malam";
}

export function clock(sec: number): string {
  const s = Math.max(0, Math.round(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export const initials = (name: string): string =>
  name.trim().split(/\s+/).slice(0, 2).map((p) => p.charAt(0).toUpperCase()).join("") || "U";

export const nf = new Intl.NumberFormat("id-ID");
