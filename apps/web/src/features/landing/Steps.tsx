import { useEffect, useRef, useState } from "react";
import { Icon } from "../../components/icons";
import { MascotStep } from "../../components/Mascot";
import { LinkButton } from "../../components/ui/primitives";
import { id as t } from "../../copy/id";
import { MotionButton, useMotion, useSeenOnce, useTimers } from "./motion";

const C = t.landing.steps;
interface SceneProps { runId: number; setPlaying: (v: boolean) => void }

/** Teks yang diketik: versi penuh (tak terlihat) ikut menahan tinggi/lebar, jadi mengetik tidak mengubah ukuran kartu. */
function Typed({ full, text, caret }: { full: string; text: string; caret?: boolean }) {
  return (
    <span className="typed">
      <span className="typed-ghost" aria-hidden="true">{full}{caret && <i className="caret" />}</span>
      <span className="typed-live">{text}{caret && <i className="caret" />}</span>
    </span>
  );
}

function Scene1({ runId, setPlaying }: SceneProps) {
  const full = C.s1.title;
  const [text, setText] = useState(full);
  const [pen, setPen] = useState(true);
  const { clear, later } = useTimers();
  useEffect(() => {
    clear();
    if (runId === 0) { setText(full); setPen(true); setPlaying(false); return; }
    setPlaying(true); setText(""); setPen(false);
    [...full].forEach((_, i) => later(300 + i * 55, () => setText(full.slice(0, i + 1))));
    later(300 + full.length * 55 + 300, () => setPen(true));
    later(300 + full.length * 55 + 1800, () => setPlaying(false));
  }, [runId, full, clear, later, setPlaying]);
  return (
    <div className="scene" aria-hidden="true">
      <div className="mini-field"><span className="mini-lbl">{C.s1.field}</span><span className="mini-val"><Typed full={full} text={text} caret /></span></div>
      <div className="mini-field" style={{ visibility: pen ? undefined : "hidden" }}><span className="mini-lbl">{C.s1.pen}</span><span className="mini-val mono">{C.s1.penVal}</span></div>
    </div>
  );
}

function Scene2({ runId, setPlaying }: SceneProps) {
  const full = C.s2.key;
  const [text, setText] = useState(full);
  const [lock, setLock] = useState(true);
  const [note, setNote] = useState(true);
  const { clear, later } = useTimers();
  useEffect(() => {
    clear();
    if (runId === 0) { setText(full); setLock(true); setNote(true); setPlaying(false); return; }
    setPlaying(true); setText(""); setLock(false); setNote(false);
    [...full].forEach((_, i) => later(300 + i * 60, () => setText(full.slice(0, i + 1))));
    later(300 + full.length * 60 + 200, () => setLock(true));
    later(300 + full.length * 60 + 600, () => setNote(true));
    later(300 + full.length * 60 + 900, () => setPlaying(false));
  }, [runId, full, clear, later, setPlaying]);
  return (
    <div className="scene" aria-hidden="true">
      <div className="mini-field"><span className="mini-lbl">{C.s2.field}</span>
        <span className="mini-val mono"><Typed full={full} text={text} /><span style={{ visibility: lock ? undefined : "hidden" }}><Icon name="lock" /></span></span></div>
      <span className="mini-note" style={{ visibility: note ? undefined : "hidden" }}><Icon name="check" />{C.s2.note}</span>
      <div className="btn-row"><span className="tag">{C.s2.or}</span><span className="tag"><Icon name="flask" />{C.s2.mock}</span></div>
    </div>
  );
}

function Scene3({ runId, setPlaying }: SceneProps) {
  const [label, setLabel] = useState(C.s3.done);
  const [pct, setPct] = useState(100);
  const [file, setFile] = useState<"hidden" | "shown" | "pop">("shown");
  const [press, setPress] = useState(false);
  const [mascot, setMascot] = useState({ play: false, done: true });
  const { clear, later } = useTimers();
  useEffect(() => {
    clear();
    if (runId === 0) { setLabel(C.s3.done); setPct(100); setFile("shown"); setMascot({ play: false, done: true }); setPlaying(false); return; }
    setPlaying(true); setLabel(C.s3.queued); setPct(0); setFile("hidden"); setMascot({ play: false, done: false });
    later(20, () => setMascot({ play: true, done: false }));
    later(250, () => setPress(true));
    later(450, () => setPress(false));
    C.stages.forEach((s, i) => later(700 + i * 480, () => { setLabel(C.s3.stage(s, i + 1)); setPct(Math.round(((i + 1) / 7) * 100)); }));
    later(700 + 7 * 480 + 200, () => { setLabel(C.s3.done); setFile("pop"); setMascot({ play: true, done: true }); });
    later(700 + 7 * 480 + 800, () => setPlaying(false));
  }, [runId, clear, later, setPlaying]);
  return (
    <div className="scene" aria-hidden="true">
      <span className={`mini-btn${press ? " press" : ""}`}>{C.s3.btn}</span>
      <div className="prog"><span className="mini-lbl num">{label}</span><div className="bar"><i style={{ width: `${pct}%` }} /></div></div>
      <div className="s3-end">
        <MascotStep play={mascot.play} done={mascot.done} />
        <span className={`file-chip${file === "pop" ? " pop" : ""}`} style={{ visibility: file === "hidden" ? "hidden" : undefined }}><Icon name="doc" />{C.s3.file}</span>
      </div>
    </div>
  );
}

const SCENES = [Scene1, Scene2, Scene3] as const;

function StepCard({ n, hl }: { n: 1 | 2 | 3; hl: boolean }) {
  const { motion } = useMotion();
  const item = C.items[n - 1]!;
  const [ref, seen] = useSeenOnce<HTMLLIElement>(0.45);
  const [runId, setRunId] = useState(0);
  const [playing, setPlaying] = useState(false);
  const autoDone = useRef(false);
  const { later, clear } = useTimers();

  // Main SEKALI saat terlihat, bergiliran antar kartu; tidak main bila animasi dijeda.
  useEffect(() => {
    if (!seen || !motion || autoDone.current) return;
    autoDone.current = true;
    later((n - 1) * 650, () => setRunId((r) => r + 1));
  }, [seen, motion, n, later]);
  // Dijeda: langsung ke keadaan akhir.
  useEffect(() => { if (!motion) { clear(); setRunId(0); setPlaying(false); } }, [motion, clear]);

  const Scene = SCENES[n - 1]!;
  return (
    <li ref={ref} className={`l-step${hl ? " hl" : ""}${playing ? " playing" : ""}`} id={`step-${n}`} data-step={n}>
      <div className="l-step-top">
        <span className="l-num" aria-hidden="true">{n}</span>
        <h3><span className="sr-only">Langkah {n}: </span>{item.title}</h3>
        <span className="tag mark hl-tag">{C.hl}</span>
      </div>
      <p>{item.text}</p>
      <Scene runId={runId} setPlaying={setPlaying} />
      <button type="button" className="btn ghost replay" onClick={() => setRunId((r) => r + 1)}><Icon name="refresh" />{C.replay}</button>
    </li>
  );
}

export function StepsSection({ highlight }: { highlight: number | null }) {
  return (
    <section className="section" id="cara-kerja" aria-labelledby="ck-h">
      <div className="wrap">
        <div className="head-row">
          <div className="section-head">
            <span className="eyebrow">{C.eyebrow}</span>
            <h2 id="ck-h">{C.title}</h2>
            <p>{C.sub}</p>
          </div>
          <MotionButton />
        </div>
        <ol className="l-steps">
          {([1, 2, 3] as const).map((n) => <StepCard key={n} n={n} hl={highlight === n} />)}
        </ol>
        <div className="after-steps">
          <LinkButton variant="primary" lg to="/daftar">{t.landing.ctaPrimary}</LinkButton>
          <span className="small muted">{C.after}</span>
        </div>
      </div>
    </section>
  );
}
