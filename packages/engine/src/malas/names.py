"""Normalisasi nama penulis: satu sumber kebenaran untuk label sitasi, kunci verifikasi, dan daftar pustaka.

Bentuk kanonik: ``"Family, G. G."`` (nama keluarga dulu, inisial kemudian) atau nama lembaga utuh.
Dipakai di batas provider (`refsearch.orchestrator`) dan sebagai cadangan di `citations`/`docx_converter`
sehingga checkpoint lama yang masih menyimpan ``"Given Family"`` tetap terbaca benar.

Aturan (urut):
  1. Lembaga ("Badan Pusat Statistik", "Wikipedia") ditulis utuh.
  2. Ada koma -> "Family, Given" (bentuk Crossref/APA); bagian setelah koma dijadikan inisial.
  3. Gelar ("Dr.", "M.Pd", "S.Ag.") dibuang dari awal/akhir nama.
  4. Token di BELAKANG yang berupa inisial ("P", "M", "JA", "J.R.") ditandai inisial; nama keluarga =
     token nama terakhir sebelum inisial. Contoh OpenAlex: "Raseena P M" -> "Raseena, P. M.".
  5. Selain itu nama keluarga = token terakhir ("Rizka Utami" -> "Utami, R.").

Keterbatasan (disengaja): urutan nama ber-inisial di belakang bisa ambigu tanpa data keluarga/ORCID;
`is_confident` menandai hasil heuristik. Partikel nama ("van", "de") tidak digabung ke nama keluarga
supaya sama dengan yang dapat dikenali verifier sitasi.
"""
import re

_LEMBAGA = re.compile(
    r"\b(badan|kementerian|kemenkes|kemendikbud|dinas|lembaga|pusat|universitas|institut|politeknik|sekolah tinggi|"
    r"organisasi|asosiasi|komisi|dewan|bank|perusahaan|pemerintah|republik|world|organization|association|ministry|"
    r"institute|university|bureau|agency|commission|council|foundation|department|office)\b", re.IGNORECASE)

_PREFIX_GELAR = re.compile(r"^(?:dr|drs|dra|prof|ir|h|hj|kh|ust|ustadz|ustadzah)\.?$", re.IGNORECASE)
# gelar di belakang: "S.Pd", "M.Pd.I", "S.Ag.", "Lc", "Ph.D", "M.A." (mengandung segmen >1 huruf, atau dikenal)
_SUFFIX_GELAR = re.compile(r"^(?:lc|ma|msc|mba|phd|ph\.d|sh|se|st|mt|mm|mh|dr)\.?$", re.IGNORECASE)
_DOTTED = re.compile(r"^(?:[A-Za-z]{1,4}\.)+[A-Za-z]{0,4}\.?$")


def is_institution(name: str) -> bool:
    """Penulis berupa lembaga ("Badan Pusat Statistik"): ditulis utuh, bukan 'Statistik, B. P.'.

    Nama satu kata ("Wikipedia") selalu dianggap lembaga; nama multi-kata hanya bila memuat kata kunci lembaga.
    """
    parts = name.split()
    return len(parts) == 1 or (len(parts) > 1 and bool(_LEMBAGA.search(name)))


def _is_degree(tok: str) -> bool:
    if _SUFFIX_GELAR.match(tok):
        return True
    if _DOTTED.match(tok):
        segs = [s for s in tok.split(".") if s]
        return any(len(s) > 1 for s in segs)  # "S.Pd" = gelar; "J.R." = inisial
    return False


def _is_initial(tok: str) -> bool:
    t = tok.rstrip(".")
    if len(t) == 1 and t.isalpha():
        return True
    if _DOTTED.match(tok):  # "J.R." / "P.M."
        return all(len(s) == 1 for s in tok.split(".") if s)
    return 2 <= len(t) <= 3 and t.isalpha() and t.isupper()  # "JA", "PM" (gaya Europe PMC/OpenAlex)


def _initials_of(tok: str) -> list:
    if _DOTTED.match(tok) and all(len(s) == 1 for s in tok.split(".") if s):
        return [f"{s.upper()}." for s in tok.split(".") if s]
    t = tok.rstrip(".")
    if t.isupper() and 2 <= len(t) <= 3:  # "JA" -> J. A.
        return [f"{c}." for c in t]
    parts = [p for p in re.split(r"-", t) if p]
    if len(parts) > 1:  # "Jean-Paul" -> "J.-P."
        return ["-".join(f"{p[0].upper()}." for p in parts)]
    return [f"{t[0].upper()}."] if t else []


def _strip_degrees(tokens: list) -> list:
    toks = [t.strip(",") for t in tokens if t.strip(",")]
    while len(toks) > 1 and _PREFIX_GELAR.match(toks[0]):
        toks = toks[1:]
    while len(toks) > 1 and _is_degree(toks[-1]):
        toks = toks[:-1]
    return toks


def split_author(raw: str) -> tuple[str, str, bool]:
    """-> (family, initials "G. G.", confident). Lembaga: (nama utuh, "", True)."""
    raw = " ".join((raw or "").split())
    if not raw:
        return "", "", True
    parts = [p.strip() for p in raw.split(",")]
    while len(parts) > 1 and parts[-1].split() and all(_is_degree(t) for t in parts[-1].split()):
        parts.pop()  # "Siti Nurhaliza, M.Pd., S.Ag." -> gelar di belakang koma dibuang
    raw = ", ".join(p for p in parts if p)
    if "," not in raw and is_institution(raw):
        return raw, "", True
    if "," in raw:
        family, given = (p.strip() for p in raw.split(",", 1))
        toks = _strip_degrees(given.split()) if given else []
        initials = [i for t in toks for i in _initials_of(t)]
        return family, " ".join(initials), True
    toks = _strip_degrees(raw.split())
    if len(toks) == 1:
        return toks[0], "", True
    n = len(toks)
    k = n
    while k > 1 and _is_initial(toks[k - 1]):
        k -= 1
    if k < n:  # ada inisial di belakang: keluarga = token nama terakhir sebelum inisial
        names, trailing = toks[:k], toks[k:]
        family = names[-1]
        initials = [i for t in names[:-1] for i in _initials_of(t)] + [i for t in trailing for i in _initials_of(t)]
        return family, " ".join(initials), False
    family = toks[-1]
    initials = [i for t in toks[:-1] for i in _initials_of(t)]
    return family, " ".join(initials), True


def normalize_author(raw: str) -> str:
    """Bentuk kanonik "Family, G. G." (atau lembaga utuh). String kosong tetap kosong."""
    family, initials, _ = split_author(raw)
    return f"{family}, {initials}" if initials else family


def family_of(raw: str) -> str:
    """Nama keluarga untuk sitasi in-text (lembaga: nama utuh)."""
    return split_author(raw)[0]


def is_confident(raw: str) -> bool:
    """False bila nama keluarga ditebak dari inisial di belakang (tanpa data keluarga/ORCID)."""
    return split_author(raw)[2]
