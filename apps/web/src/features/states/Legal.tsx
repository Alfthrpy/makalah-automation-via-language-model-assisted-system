import { Banner } from "../../components/ui/primitives";

/** Placeholder: teks resmi (Ketentuan Layanan / Kebijakan Privasi) menunggu pemilik (Fase 6). */
export default function Legal({ title }: { title: string }) {
  return (
    <main className="screen" id="main"><div className="wrap" style={{ maxWidth: 720 }}>
      <div className="page-head"><div><h1>{title}</h1></div></div>
      <Banner kind="info" role="status" title="Teks resmi belum tersedia">Halaman ini masih placeholder. Isinya akan ditulis pemilik layanan sebelum peluncuran.</Banner>
    </div></main>
  );
}
