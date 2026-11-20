/** Pratinjau outline TIRUAN untuk hero landing: dibentuk lokal dari judul, tidak dikirim ke mana pun. */
export interface TopicParts { a: string; b: string; conn: string; core: string }

export function topicParts(raw: string): TopicParts {
  const t = raw.trim().replace(/\s+/g, " ");
  const m = t.match(/^(.+?)\s+(dalam|pada|terhadap|untuk|bagi|di|dengan|melalui|sebagai)\s+(.+)$/i);
  const a = m?.[1] ?? t;
  const b = m?.[3] ?? "";
  const core = a.replace(/^(peran|pengaruh|dampak|analisis|penerapan|strategi|implementasi|tinjauan|studi|efektivitas|hubungan|upaya)\s+/i, "") || a;
  return { a, b, conn: m ? (m[2] ?? "").toLowerCase() : "", core };
}

export interface Preview { title: string; subs: string[]; core: string; b: string }

export function buildPreview(title: string, fallback: string): Preview {
  const t = title.trim().length >= 3 ? title.trim() : fallback;
  const { a, b, conn, core } = topicParts(t);
  const subs = [
    `2.1 Konsep Dasar ${core}`,
    b ? `2.2 Gambaran Umum ${b}` : `2.2 Perkembangan ${core} Saat Ini`,
    b ? `2.3 ${a} ${conn} ${b}` : `2.3 Penerapan ${core}`,
    "2.4 Tantangan dan Peluang",
  ];
  return { title: t, subs, core, b };
}
