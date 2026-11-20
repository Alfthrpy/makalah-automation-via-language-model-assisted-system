/** Maskot "lembar tidur": SVG inline geometris, satu tebal garis, warna dari token. aria-hidden. */
const SHEET = (
  <g className="breathe">
    <path className="sheet o" d="M34 14h46l16 16v62a10 10 0 0 1-10 10H34a10 10 0 0 1-10-10V24a10 10 0 0 1 10-10z" />
    <path className="face o" d="M80 14v10a6 6 0 0 0 6 6h10" />
    <path className="margin" d="M38 18v80" />
    <path className="face o" d="M52 50q5 6 10 0M70 50q5 6 10 0M60 62q6 5 12 0" />
    <ellipse className="cheek" cx="52" cy="62" rx="4" ry="2" />
    <ellipse className="cheek" cx="80" cy="62" rx="4" ry="2" />
    <rect className="hl" x="46" y="76" width="40" height="8" rx="2" />
    <path className="face o" d="M48 92h22" />
  </g>
);
const ZZZ = (
  <g>
    <path className="z z1" d="M102 24h12l-12 12h12" />
    <path className="z z2" d="M116 4h8l-8 8h8" />
  </g>
);

/** Ukuran langkah 3 (~136px): lencana centang muncul saat `done`. */
export function MascotStep({ play, done }: { play: boolean; done: boolean }) {
  return (
    <svg className={`rb rb-c${play ? " play" : ""}${done ? " done" : ""}`} viewBox="0 -2 128 112" aria-hidden="true" focusable="false">
      {SHEET}{ZZZ}
      <g className="cpop"><circle className="badge o" cx="92" cy="94" r="12" /><path className="tick" d="M86 94l4 4 8-8" /></g>
    </svg>
  );
}

/** Ukuran CTA (~200px): bar progres terisi sekali saat terlihat (`play`). */
export function MascotBig({ play }: { play: boolean }) {
  return (
    <svg className={`rb rb-big${play ? " play" : ""}`} viewBox="0 -2 128 132" aria-hidden="true" focusable="false">
      {SHEET}{ZZZ}
      <rect className="track" x="24" y="116" width="72" height="8" rx="4" />
      <rect className="fillbar" x="24" y="116" width="72" height="8" rx="4" />
      <g className="pop"><circle className="badge o" cx="92" cy="94" r="12" /><path className="tick" d="M86 94l4 4 8-8" /></g>
    </svg>
  );
}

export function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <svg viewBox="0 0 34 34" width={size} height={size} aria-hidden="true" focusable="false">
      <rect x="1" y="1" width="32" height="32" rx="9" fill="var(--accent)" />
      <path d="M9 6h11l5 5v17H9z" fill="var(--surface)" />
      <path d="M20 6v5h5" fill="none" stroke="var(--accent)" strokeWidth="1.4" />
      <rect x="11.5" y="16" width="11" height="3.2" rx="1" fill="var(--mark)" />
      <path d="M12 22.5h10M12 13h6" stroke="var(--accent)" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
