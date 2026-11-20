import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router";
import { Icon, type IconName } from "../../components/icons";
import { MascotBig } from "../../components/Mascot";
import { LinkButton } from "../../components/ui/primitives";
import { id as t } from "../../copy/id";
import { useAuthState } from "../../lib/auth";
import { MotionButton, MotionProvider, useMotion, useSeenOnce } from "./motion";
import { buildPreview } from "./preview";
import { StepsSection } from "./Steps";
import { LANDING_DESCRIPTION, LANDING_TITLE } from "../../seo/site";
import { useSeo } from "../../seo/useSeo";

const L = t.landing;

/* ---------------- hero: coba ketik judul ---------------- */
function TryTitle() {
  const { motion } = useMotion();
  const samples = L.try.samples;
  const [title, setTitle] = useState(samples[0]!);
  const [touched, setTouched] = useState(false);
  const [demoRun, setDemoRun] = useState(0);
  const [animKey, setAnimKey] = useState(0);
  const [debounced, setDebounced] = useState(title);

  // Tanpa interaksi: memutar contoh 6 putaran lalu diam; berhenti begitu input difokus.
  useEffect(() => {
    if (!motion || touched || demoRun >= 6) return;
    const next = samples[(demoRun + 1) % samples.length]!;
    let n = 0;
    let tm: number;
    const step = () => {
      n += 1;
      setTitle(next.slice(0, n)); setDebounced(next.slice(0, n));
      if (n < next.length) tm = window.setTimeout(step, 45);
      else { setAnimKey((k) => k + 1); tm = window.setTimeout(() => setDemoRun((r) => r + 1), 3200); }
    };
    tm = window.setTimeout(step, demoRun === 0 ? 2100 : 600);
    return () => clearTimeout(tm);
  }, [motion, touched, demoRun, samples]);

  // Dijeda sebelum disentuh: kembali ke contoh pertama (keadaan akhir yang tenang).
  useEffect(() => { if (!motion && !touched) { setTitle(samples[0]!); setDebounced(samples[0]!); } }, [motion, touched, samples]);

  // Pratinjau mengikuti ketikan dengan jeda 280 ms.
  useEffect(() => {
    if (!touched) return;
    const tm = window.setTimeout(() => { setDebounced(title); if (motion) setAnimKey((k) => k + 1); }, 280);
    return () => clearTimeout(tm);
  }, [title, touched, motion]);

  const pv = useMemo(() => buildPreview(debounced, samples[0]!), [debounced, samples]);
  const anim = motion && animKey > 0;
  let i = 0;
  const st = () => ({ ["--i" as string]: i++ }) as React.CSSProperties;
  return (
    <div className="try card" role="region" aria-labelledby="try-h">
      <div className="try-head">
        <h2 className="try-title" id="try-h">{L.try.title}</h2>
        <MotionButton />
      </div>
      <div className="try-row">
        <label className="sr-only" htmlFor="try-input">{L.try.inputLabel}</label>
        <input className="input" id="try-input" maxLength={120} autoComplete="off" spellCheck={false} value={title} aria-describedby="try-note"
          onFocus={(e) => { if (!touched) { setTouched(true); e.currentTarget.select(); } }}
          onChange={(e) => { setTouched(true); setTitle(e.target.value); }} />
      </div>
      <div className={`pp${anim ? " anim" : ""}`} key={anim ? animKey : "static"} aria-label={L.try.previewLabel}>
        <p className="pp-k" style={st()}>{L.try.k}</p>
        <p className="pp-t" style={st()}>{pv.title}</p>
        <p className="pp-b" style={st()}>{L.try.b1}</p>
        <p className="pp-s" style={st()}>{L.try.s1}</p>
        <p className="pp-b" style={st()}>{L.try.b2}</p>
        <ol className="pp-list" style={st()}>{pv.subs.map((s) => <li key={s}>{s}</li>)}</ol>
        <p className="pp-snip" style={st()}>
          Kajian tentang {pv.core} terus berkembang <mark>{L.try.cite1}</mark>
          {pv.b ? `, termasuk dalam konteks ${pv.b}` : ""} <mark>{L.try.cite2}</mark>.
        </p>
        <p className="pp-b" style={st()}>{L.try.b3}</p>
        <p className="pp-s" style={st()}>{L.try.s3}</p>
      </div>
      <p className="small muted try-note" id="try-note"><Icon name="info" /><span>{L.try.note}</span></p>
    </div>
  );
}

function Hero() {
  return (
    <div className="wrap">
      <section className="l-hero" aria-labelledby="hero-h">
        <div className="hero-copy">
          <span className="eyebrow">{L.eyebrow}</span>
          <h1 id="hero-h">{L.heroA}<span className="h-mark">{L.heroMark}</span>{L.heroB}</h1>
          <p className="lead">{L.lead}</p>
          <div className="btn-row">
            <LinkButton variant="primary" lg to="/daftar">{L.ctaPrimary} <Icon name="arrow" size="md" /></LinkButton>
            <LinkButton lg to="/masuk">{L.ctaLogin}</LinkButton>
          </div>
          <ul className="hero-facts" aria-label={L.factsLabel}>
            <li><Icon name="clock" />{L.facts.time}</li>
            <li><Icon name="pen" />{L.facts.draft}</li>
            <li><Icon name="key" />{L.facts.key}</li>
          </ul>
        </div>
        <TryTitle />
      </section>
    </div>
  );
}

/* ---------------- singkatan ---------------- */
function Acronym() {
  const { motion } = useMotion();
  const [pressed, setPressed] = useState<number | null>(null);
  const [ref, seen] = useSeenOnce<HTMLUListElement>(0.5);
  return (
    <section className="section" id="singkatan" aria-labelledby="acro-h">
      <div className="wrap">
        <div className="section-head">
          <span className="eyebrow">{L.acro.eyebrow}</span>
          <h2 id="acro-h">{L.acro.title}</h2>
          <p className="acro-full"><b>M</b>akalah <b>A</b>utomation via <b>L</b>anguage-model <b>A</b>ssisted <b>S</b>ystem.</p>
        </div>
        <ul ref={ref} className={`acro${seen && motion ? " in" : ""}`} aria-label={L.acro.label}>
          {L.acro.items.map((it, i) => (
            <li key={i}>
              <button type="button" className="acro-t" aria-pressed={pressed === i} style={{ ["--i" as string]: i } as React.CSSProperties}
                onClick={() => setPressed((p) => (p === i ? null : i))}>
                <span className="acro-l" aria-hidden="true">{it.l}</span>
                <span className="acro-w">{it.via && <><span className="acro-via">{it.via}</span> </>}{it.w}</span>
                <span className="acro-g">{it.g}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* ---------------- pemilih situasi ---------------- */
type SituKey = keyof typeof L.situ.items;
const SITU_KEYS = Object.keys(L.situ.items) as SituKey[];

function Situation({ onPick, motion }: { onPick: (step: number | null) => void; motion: boolean }) {
  const [key, setKey] = useState<SituKey>("h3");
  return (
    <section className="section" id="situasi" aria-labelledby="situ-h">
      <div className="wrap">
        <div className="section-head">
          <span className="eyebrow">{L.situ.eyebrow}</span>
          <h2 id="situ-h">{L.situ.title}</h2>
          <p>{L.situ.sub}</p>
        </div>
        <div className="situ-chips" role="group" aria-label={L.situ.group}>
          {SITU_KEYS.map((k) => (
            <button key={k} type="button" aria-pressed={k === key} onClick={() => { setKey(k); onPick(L.situ.items[k].step); }}>
              <Icon name="check" />{L.situ.items[k].chip}
            </button>
          ))}
        </div>
        {/* Semua panel ditumpuk di satu sel grid: tinggi kotak = panel terpanjang, jadi ganti chip tidak menggeser section di bawahnya. */}
        <div className="situ-box" aria-live="polite">
          {SITU_KEYS.map((k) => {
            const s = L.situ.items[k];
            const f = L.situ.foot(s.step, s.foot);
            const active = k === key;
            return (
              <div key={k} className={`situ-panel${active ? " on" : ""}`} inert={!active}>
                <div className="situ-time"><span className="eyebrow">{L.situ.left}</span><b>{s.left}</b><div className="bar" aria-hidden="true"><i style={{ width: `${s.pct}%` }} /></div></div>
                <div className="vs">
                  <div className="vs-col no"><span className="eyebrow"><Icon name="x" />{L.situ.no}</span><p>{s.no}</p></div>
                  <div className="vs-col yes"><span className="eyebrow"><Icon name="check" />{L.situ.yes}</span><p>{s.yes}</p></div>
                </div>
                <p className="situ-foot">{f.before}
                  <a href={`#step-${s.step}`} onClick={(e) => { e.preventDefault(); document.getElementById(`step-${s.step}`)?.scrollIntoView({ behavior: motion ? "smooth" : "auto", block: "center" }); }}>{f.link}</a>
                  {f.after}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function IconList({ items, className, yellow }: { items: readonly { icon: string; t: string; p: string }[]; className: string; yellow?: boolean }) {
  return (
    <ul className={className}>
      {items.map((it) => (
        <li key={it.t}>
          <span className={`ico${yellow ? " y" : ""}`}><Icon name={it.icon as IconName} size="md" /></span>
          <div><b>{it.t}</b><p>{it.p}</p></div>
        </li>
      ))}
    </ul>
  );
}

function Honest() {
  return (
    <section className="section" id="jujur" aria-labelledby="jujur-h">
      <div className="wrap">
        <div className="section-head"><span className="eyebrow">{L.honest.eyebrow}</span><h2 id="jujur-h">{L.honest.title}</h2></div>
        <IconList className="honest" items={L.honest.items} yellow />
      </div>
    </section>
  );
}

function PrivacySection() {
  return (
    <section className="section" id="privasi" aria-labelledby="pv-h">
      <div className="wrap priv">
        <div className="section-head" style={{ margin: 0 }}>
          <span className="eyebrow">{L.privacy.eyebrow}</span><h2 id="pv-h">{L.privacy.title}</h2><p>{L.privacy.sub}</p>
        </div>
        <IconList className="priv-list" items={L.privacy.items} />
      </div>
    </section>
  );
}

function Faq() {
  return (
    <section className="section" id="faq" aria-labelledby="faq-h">
      <div className="wrap">
        <div className="section-head"><span className="eyebrow">{L.faq.eyebrow}</span><h2 id="faq-h">{L.faq.title}</h2></div>
        <div className="faq">
          {L.faq.items.map((it) => (
            <details key={it.q}><summary>{it.q}<Icon name="chev" size="md" /></summary><p>{it.a}</p></details>
          ))}
        </div>
      </div>
    </section>
  );
}

function CtaBand() {
  const { motion } = useMotion();
  const [ref, seen] = useSeenOnce<HTMLDivElement>(0.4);
  return (
    <section className="wrap" style={{ paddingBlock: "var(--sp-6)" }}>
      <div className="cta-band" ref={ref}>
        <div className="txt"><h2>{L.cta.title}</h2><p>{L.cta.sub}</p></div>
        <MascotBig play={seen && motion} />
        <div className="btn-row">
          <LinkButton lg to="/daftar">{L.ctaPrimary}</LinkButton>
          <LinkButton lg className="alt" to="/masuk">{L.ctaLogin}</LinkButton>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="foot">
      <div className="wrap foot-in">
        <span className="foot-brand">{L.footer.copy} <b>{t.brand.name}</b> · <span className="muted">{t.brand.full}</span></span>
        <nav aria-label={L.footer.legal}>
          <a href="/panduan">Panduan</a>
          <a href="/ketentuan">{L.footer.terms}</a>
          <a href="/privasi">{L.footer.privacy}</a>
        </nav>
      </div>
    </footer>
  );
}

function LandingBody() {
  const { motion } = useMotion();
  const [hl, setHl] = useState<number | null>(null);
  return (
    <main className={`screen landing ${motion ? "anim-on" : "calm"}`} id="main" style={{ paddingTop: 0 }}>
      <Hero />
      <StepsSection highlight={hl} />
      <Acronym />
      <Situation onPick={setHl} motion={motion} />
      <Honest />
      <PrivacySection />
      <Faq />
      <CtaBand />
      <Footer />
    </main>
  );
}

export default function Landing() {
  const auth = useAuthState();
  const quiet = useCallback(() => {}, []);
  useSeo({ title: LANDING_TITLE, description: LANDING_DESCRIPTION, path: "/" });
  if (auth.ready && auth.signedIn) return <Navigate to="/dasbor" replace />;
  return <MotionProvider onPause={quiet}><LandingBody /></MotionProvider>;
}
