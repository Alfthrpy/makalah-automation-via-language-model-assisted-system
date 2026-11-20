import { id as t } from "../copy/id";
import { resetCountdown } from "../lib/format";
import { useMe } from "../lib/queries";

/** Kartu kuota (dasbor: eyebrow; pengaturan: judul kartu). */
export function QuotaCard({ variant }: { variant: "dash" | "settings" }) {
  const { data } = useMe();
  const q = data?.quota;
  const left = resetCountdown(q?.resets_at);
  const label = variant === "dash" ? t.quota.title : t.quota.titleSettings;
  return (
    <section className="card quota-card" aria-labelledby={`q-${variant}`}>
      {variant === "dash" ? <h2 className="eyebrow" id={`q-${variant}`}>{label}</h2> : <h2 className="card-title" id={`q-${variant}`}>{label}</h2>}
      {!q ? (
        <p className="small muted">{t.quota.unlimited}</p>
      ) : (
        <>
          <div className="quota-big"><b className="num">{q.remaining}</b><span className="muted">{variant === "dash" ? t.quota.ofRemaining(q.limit) : t.quota.ofRemainingToday(q.limit)}</span></div>
          <div className="meter" aria-hidden="true">{Array.from({ length: q.limit }, (_, i) => <i key={i} className={i < q.remaining ? "" : "used"} />)}</div>
          <p className="small muted">{variant === "dash" ? t.quota.resetDash(left) : t.quota.resetSettings(left)}</p>
        </>
      )}
    </section>
  );
}
