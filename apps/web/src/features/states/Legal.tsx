import { useEffect } from "react";
import { LEGAL_UPDATED, PRIVACY, TERMS, type Block, type LegalDoc } from "../legal/content";

const DOCS: Record<"terms" | "privacy", LegalDoc> = { terms: TERMS, privacy: PRIVACY };

const URL_RE = /(https?:\/\/[^\s]+?)(?=[.,;:)]?(?:\s|$))/g;

/** Paragraf dengan tautan otomatis untuk URL polos. */
function Text({ children }: { children: string }) {
  const parts = children.split(URL_RE);
  return (
    <>
      {parts.map((p, i) =>
        i % 2 === 1 ? <a key={i} href={p} target="_blank" rel="noopener noreferrer">{p}</a> : <span key={i}>{p}</span>,
      )}
    </>
  );
}

function BlockView({ block }: { block: Block }) {
  if (Array.isArray(block)) return <ul>{block.map((b, i) => <li key={i}><Text>{b}</Text></li>)}</ul>;
  return <p><Text>{block}</Text></p>;
}

/** Ketentuan Layanan / Kebijakan Privasi. Teksnya di ../legal/content.ts (harus sejalan dengan perilaku sistem). */
export default function Legal({ doc }: { doc: "terms" | "privacy" }) {
  const d = DOCS[doc];
  useEffect(() => { document.title = `${d.title} · MALAS`; return () => { document.title = "MALAS"; }; }, [d.title]);
  return (
    <main className="screen" id="main">
      <div className="wrap legal">
        <div className="page-head"><div><h1>{d.title}</h1><p>Terakhir diperbarui {LEGAL_UPDATED}</p></div></div>
        <p className="legal-intro">{d.intro}</p>
        <nav aria-label="Isi halaman" className="legal-toc">
          <ol>{d.sections.map((s) => <li key={s.id}><a href={`#${s.id}`}>{s.title}</a></li>)}</ol>
        </nav>
        {d.sections.map((s) => (
          <section key={s.id} id={s.id} aria-labelledby={`${s.id}-h`}>
            <h2 id={`${s.id}-h`}>{s.title}</h2>
            {s.blocks.map((b, i) => <BlockView key={i} block={b} />)}
          </section>
        ))}
      </div>
    </main>
  );
}
