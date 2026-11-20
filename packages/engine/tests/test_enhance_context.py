from malas.citations import content_text
from malas.crews.models.TaskOutput import Bab, ContentList, ContentText, Makalah, SubBab
from malas.enhance.context import (
    build_context, facts_of, one_line_refs, render_context, research_questions, scope_text, sentences,
)

STAT = "Hasilnya F(1,67) = 8,52 dengan p = 0,005 pada 70 siswa. Peningkatan terbesar terjadi pada dimensi pencapaian."


def _makalah(done_until: str = "3.1") -> Makalah:
    subs = {
        "I": [SubBab(judul="1.1 Latar Belakang", content=[ContentText(isi="Latar belakang panjang. " + STAT)]),
              SubBab(judul="1.2 Rumusan Masalah", content=[ContentList(items=["Bagaimana peta penerapan?", "Bagaimana pengaruhnya?"])]),
              SubBab(judul="1.3 Tujuan", content=[])],
        "II": [SubBab(judul="2.1 Konsep", content=[ContentText(isi="Konsep dasar gamifikasi dijelaskan. Elemen game dipakai.")]),
               SubBab(judul="2.2 Dampak", content=[ContentText(isi="Dampak diteliti. " + STAT)])],
        "III": [SubBab(judul="3.1 Kesimpulan", content=[])],
    }
    return Makalah(judul="J", bab={k: Bab(judul=k, subbab=v) for k, v in subs.items()})


def test_penulis_2_1_kini_melihat_rumusan_masalah_dan_bab_i():
    """Regresi RC-03: dulu sub-bab pertama Bab II tak melihat apa pun dari Bab I."""
    m = _makalah()
    cur = m.bab["II"].subbab[0]
    pack = build_context(m, cur, "II")
    assert pack.rq == ["Bagaimana peta penerapan?", "Bagaimana pengaruhnya?"]
    txt = render_context(pack)
    assert "Rumusan masalah" in txt and "1.1 Latar Belakang" in txt and "Bagaimana pengaruhnya?" in txt
    assert "2.1 Konsep]" not in txt  # sub-bab yang sedang ditulis tidak masuk ledger


def test_kesimpulan_mendapat_rm_dan_ringkasan_bab_ii():
    """Regresi RC-03: Kesimpulan dulu menulis TANPA konteks (i=0)."""
    m = _makalah()
    pack = build_context(m, m.bab["III"].subbab[0], "III")
    assert pack.rq and len(pack.digest_bab2) == 2
    txt = render_context(pack)
    assert "dasar untuk menjawab TIAP rumusan masalah" in txt and "[2.2 Dampak]" in txt


def test_ledger_menyertakan_angka_sekali_per_sub_bab_dan_lebih_pendek_dari_teks_penuh():
    m = _makalah()
    pack = build_context(m, m.bab["III"].subbab[0], "III")
    assert any("F(1,67) = 8,52" in ln for ln in pack.ledger)
    full = "\n".join(content_text(sb.content) for b in m.bab.values() for sb in b.subbab)
    assert len(render_context(pack)) < len(full) + 600  # sepadan/lebih ringkas pada makalah mini; pada makalah nyata jauh lebih pendek


def test_ledger_dibatasi_walau_banyak_sub_bab():
    subs = [SubBab(judul=f"2.{i} Bagian", content=[ContentText(isi="Kalimat pembuka yang cukup panjang untuk diuji. " * 6)])
            for i in range(1, 9)]
    m = Makalah(bab={"II": Bab(judul="II", subbab=subs + [SubBab(judul="2.9 Baru", content=[])])})
    pack = build_context(m, m.bab["II"].subbab[-1], "II")
    assert sum(len(x) for x in pack.ledger) < 1600


def test_rq_dari_teks_bermarker_dan_fallback_blueprint():
    sb = SubBab(judul="1.2 Rumusan Masalah", content=[ContentText(isi="Pengantar:\n1) Apa A?\n2) Apa B?")])
    m = Makalah(bab={"I": Bab(subbab=[sb])})
    assert research_questions(m) == ["Apa A?", "Apa B?"]
    from malas.enhance.models import Blueprint
    m2 = Makalah(bab={"I": Bab(subbab=[SubBab(judul="1.2 Rumusan Masalah")])}, blueprint=Blueprint(research_questions=["RM?"]))
    assert research_questions(m2) == ["RM?"]


def test_fakta_dan_kalimat():
    assert facts_of(STAT)[:3] == ["F(1,67) = 8,52", "p = 0,005", "70 siswa"]
    assert len(sentences("Satu. Dua! Tiga?")) == 3


def test_scope_text_default_melarang_populasi_liar_dan_memakai_isian_pengguna():
    assert "JANGAN menyebut populasi" in scope_text(Makalah())
    t = scope_text(Makalah(subjek="siswa MTs", jenjang="SMP/MTs"))
    assert "siswa MTs" in t and "SMP/MTs" in t and "kajian pustaka" in t


def test_one_line_refs_tanpa_kutipan():
    out = one_line_refs([{"sitasi": "(A, 2024)", "title": "T", "year": 2024, "excerpt": "Kalimat satu. Kalimat dua.", "kutipan": ["x" * 500]}])
    assert out == [{"sitasi": "(A, 2024)", "title": "T", "year": 2024, "excerpt": "Kalimat satu."}]
