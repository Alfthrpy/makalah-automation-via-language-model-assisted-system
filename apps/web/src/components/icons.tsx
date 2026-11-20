// Dibuat dari sprite prototipe (docs/design/malas-ui.html). Isi SVG statis dan tepercaya.
import type { SVGProps } from "react";

const SYMBOLS = {
  "check": `<path d="M5 10.5l3.2 3.2L15 6.8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>`,
  "x": `<path d="M6 6l8 8M14 6l-8 8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>`,
  "dash": `<path d="M6 10h8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>`,
  "dot": `<circle cx="10" cy="10" r="3" fill="currentColor"/>`,
  "skip": `<path d="M5 6l5 4-5 4M11 6l5 4-5 4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>`,
  "clock": `<circle cx="10" cy="10" r="7.2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M10 6v4.2l2.8 1.8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>`,
  "spin": `<circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" stroke-opacity=".25" stroke-width="2.2"/><path d="M10 3a7 7 0 0 1 7 7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>`,
  "pause": `<circle cx="10" cy="10" r="7.2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8.3 7.2v5.6M11.7 7.2v5.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>`,
  "slash": `<circle cx="10" cy="10" r="7.2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M5 15L15 5" stroke="currentColor" stroke-width="1.8"/>`,
  "alert": `<path d="M10 3.2l7.3 12.8H2.7z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M10 8v3.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="10" cy="13.8" r="1" fill="currentColor"/>`,
  "info": `<circle cx="10" cy="10" r="7.2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M10 9v4.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="10" cy="6.4" r="1" fill="currentColor"/>`,
  "plus": `<path d="M10 4.5v11M4.5 10h11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>`,
  "trash": `<path d="M4.5 6h11M8 6V4.5h4V6m-6 0l.6 9.5h6.8L14 6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>`,
  "download": `<path d="M10 3.5v9m0 0l-3.5-3.5M10 12.5l3.5-3.5M4 16h12" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>`,
  "back": `<path d="M12 5l-5 5 5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`,
  "arrow": `<path d="M4 10h11m-4-4.5L15.5 10 11 14.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`,
  "chev": `<path d="M5.5 8l4.5 4.5L14.5 8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`,
  "key": `<circle cx="7" cy="12.5" r="3.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M9.6 10l6-6M13.2 6.4l2 2M11.6 8l1.6 1.6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>`,
  "lock": `<rect x="4" y="9" width="12" height="8" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M7 9V6.5a3 3 0 0 1 6 0V9" fill="none" stroke="currentColor" stroke-width="1.8"/>`,
  "shield": `<path d="M10 2.8l6 2.4v4.5c0 3.8-2.6 6.4-6 7.5-3.4-1.1-6-3.7-6-7.5V5.2z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M7.4 10l1.8 1.8 3.5-3.6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>`,
  "eye": `<path d="M2.5 10s2.7-5 7.5-5 7.5 5 7.5 5-2.7 5-7.5 5-7.5-5-7.5-5z" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="10" cy="10" r="2.3" fill="none" stroke="currentColor" stroke-width="1.7"/>`,
  "search": `<circle cx="8.8" cy="8.8" r="5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12.6 12.6L16.5 16.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>`,
  "pen": `<path d="M4 16l1-3.8L13.2 4a1.6 1.6 0 0 1 2.3 0l.5.5a1.6 1.6 0 0 1 0 2.3L7.8 15z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>`,
  "quote": `<path d="M4 11.5h4v4.5H4zM4 11.5c0-3.2 1-5 3.6-6M11.5 11.5h4v4.5h-4zM11.5 11.5c0-3.2 1-5 3.6-6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>`,
  "doc": `<path d="M5 2.8h6.5L15 6.3v10.9H5z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M11.3 3v3.4H15M7.5 10h5M7.5 13h5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>`,
  "grid": `<rect x="3.5" y="3.5" width="5.5" height="5.5" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.7"/><rect x="11" y="3.5" width="5.5" height="5.5" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.7"/><rect x="3.5" y="11" width="5.5" height="5.5" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.7"/><rect x="11" y="11" width="5.5" height="5.5" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.7"/>`,
  "gear": `<circle cx="10" cy="10" r="2.6" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M10 2.5v2.2M10 15.3v2.2M2.5 10h2.2M15.3 10h2.2M4.7 4.7l1.6 1.6M13.7 13.7l1.6 1.6M4.7 15.3l1.6-1.6M13.7 6.3l1.6-1.6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>`,
  "sun": `<circle cx="10" cy="10" r="3.4" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M10 2.5v1.8M10 15.7v1.8M2.5 10h1.8M15.7 10h1.8M4.7 4.7l1.3 1.3M14 14l1.3 1.3M4.7 15.3L6 14M14 6l1.3-1.3" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>`,
  "logout": `<path d="M8 4H5v12h3M12 6.5L15.5 10 12 13.5M15.5 10H8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>`,
  "refresh": `<path d="M15.5 8A6 6 0 0 0 4.6 7M4.5 12a6 6 0 0 0 10.9 1M4.3 3.8V7.3h3.5M15.7 16.2v-3.5h-3.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>`,
  "wifi-off": `<path d="M3 7.5a10 10 0 0 1 14 0M5.5 10.3a6.4 6.4 0 0 1 9 0M8 13a2.8 2.8 0 0 1 4 0M3.5 3.5l13 13" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>`,
  "user": `<circle cx="10" cy="7" r="3.3" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M3.8 17c.8-3.2 3.3-5 6.2-5s5.4 1.8 6.2 5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>`,
  "mail": `<rect x="3" y="5" width="14" height="10.5" rx="2" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M3.5 6l6.5 5 6.5-5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>`,
  "flask": `<path d="M8 3h4M8.7 3v4.6L4.4 15a1.4 1.4 0 0 0 1.2 2.1h8.8a1.4 1.4 0 0 0 1.2-2.1l-4.3-7.4V3" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M6.2 12.5h7.6" stroke="currentColor" stroke-width="1.7"/>`,
  "book": `<path d="M10 5.5C8.5 4.3 6.3 3.8 3.5 4v11.5c2.8-.2 5 .3 6.5 1.5 1.5-1.2 3.7-1.7 6.5-1.5V4c-2.8-.2-5 .3-6.5 1.5zM10 5.5V17" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>`,
  "ext": `<path d="M11 4h5v5M16 4l-7 7M14 12v4H4V6h4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>`,
} as const;

export type IconName = keyof typeof SYMBOLS;

/** Sprite tersembunyi; dipasang sekali di akar aplikasi. */
export function IconSprite() {
  const html = (Object.keys(SYMBOLS) as IconName[])
    .map((n) => `<symbol id="i-${n}" viewBox="0 0 20 20">${SYMBOLS[n]}</symbol>`)
    .join("");
  return <svg className="sprite" aria-hidden="true" focusable="false" dangerouslySetInnerHTML={{ __html: html }} />;
}

type Props = { name: IconName; size?: "sm" | "md" } & Omit<SVGProps<SVGSVGElement>, "name">;

/** Ikon dekoratif (aria-hidden). Beri teks di dekatnya; jangan mengandalkan ikon saja. */
export function Icon({ name, size = "sm", className, ...rest }: Props) {
  const cls = [size === "sm" ? "ic-sm" : "ic", name === "spin" ? "spin" : "", className].filter(Boolean).join(" ");
  return (
    <svg className={cls} aria-hidden="true" focusable="false" {...rest}>
      <use href={`#i-${name}`} />
    </svg>
  );
}
