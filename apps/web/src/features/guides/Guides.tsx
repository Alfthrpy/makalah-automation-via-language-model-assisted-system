import { Link, useParams } from "react-router";
import { LinkButton } from "../../components/ui/primitives";
import { formatDateId, absUrl, type Guide, type GuidesData } from "../../seo/site";
import { useSeo } from "../../seo/useSeo";
import raw from "../../seo/guides.json";
import NotFound from "../states/NotFound";

const DATA = raw as GuidesData;

function Crumbs({ current }: { current?: string }) {
  return (
    <nav aria-label="Jejak halaman" className="crumbs">
      <Link to="/">Beranda</Link> <span aria-hidden="true">›</span>{" "}
      {current ? <><Link to="/panduan">Panduan</Link> <span aria-hidden="true">›</span> <span aria-current="page">{current}</span></> : <span aria-current="page">Panduan</span>}
    </nav>
  );
}

/** Daftar panduan (/panduan). */
export function GuideIndex() {
  const { index, guides } = DATA;
  useSeo({ title: index.title, description: index.description, path: "/panduan" });
  return (
    <main className="screen" id="main">
      <div className="wrap legal">
        <Crumbs />
        <div className="page-head"><div><h1>{index.h1}</h1></div></div>
        <p className="legal-intro">{index.intro}</p>
        <ul className="guide-list">
          {guides.map((g) => (
            <li key={g.slug}>
              <Link to={`/panduan/${g.slug}`}><b>{g.h1}</b></Link>
              <span>{g.description}</span>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}

function Article({ g }: { g: Guide }) {
  useSeo({ title: g.title, description: g.description, path: `/panduan/${g.slug}` });
  const related = g.related.map((s) => DATA.guides.find((x) => x.slug === s)).filter((x): x is Guide => !!x);
  return (
    <main className="screen" id="main">
      <article className="wrap legal">
        <Crumbs current={g.h1} />
        <div className="page-head"><div><h1>{g.h1}</h1><p>Diperbarui {formatDateId(g.updated)} · {g.readingMinutes} menit baca</p></div></div>
        <p className="legal-intro">{g.intro}</p>
        {g.sections.map((s, i) => (
          <section key={i}>
            <h2>{s.h2}</h2>
            {s.paragraphs.map((p, j) => <p key={j}>{p}</p>)}
            {s.bullets && <ul>{s.bullets.map((b, j) => <li key={j}>{b}</li>)}</ul>}
            {s.numbered && <ol>{s.numbered.map((b, j) => <li key={j}>{b}</li>)}</ol>}
            {s.example && <pre className="guide-example">{s.example}</pre>}
          </section>
        ))}
        {g.faq.length > 0 && (
          <section>
            <h2>Pertanyaan yang sering muncul</h2>
            {g.faq.map((f, i) => <div key={i}><h3>{f.q}</h3><p>{f.a}</p></div>)}
          </section>
        )}
        {related.length > 0 && (
          <section>
            <h2>Baca juga</h2>
            <ul>{related.map((r) => <li key={r.slug}><Link to={`/panduan/${r.slug}`}>{r.h1}</Link></li>)}</ul>
          </section>
        )}
        <p className="guide-cta"><LinkButton to="/daftar">Coba gratis</LinkButton> <a href={absUrl("/privasi")}>Kebijakan Privasi</a></p>
      </article>
    </main>
  );
}

/** Satu panduan (/panduan/:slug); slug tidak dikenal -> halaman 404. */
export default function GuidePage() {
  const { slug } = useParams();
  const g = DATA.guides.find((x) => x.slug === slug);
  return g ? <Article g={g} /> : <NotFound />;
}
