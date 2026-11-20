import pytest
from malas.crews.models.TaskOutput import Bab, ContentList, ContentText, Makalah, ReferenceItem, SubBab
from malas.enhance.autofix import apply_auto_fixes
from malas.enhance.lint import RULES, LintContext, lint_report_stats, rules_catalog, run_lints
from malas.enhance.lint._util import ref_key
from malas.enhance.models import Blueprint, EvidenceCard, score_findings

STAT = "Hasilnya F(1,67) = 8,52 dengan p = 0,005 pada 70 siswa (Smith, 2024)."
REFS = [ReferenceItem(title="Gamification effects on motivation", authors=["John Smith"], year=2024, venue="Jurnal A",
                      volume="1", issue="2", pages="1–9", doi="10.1/a", link="https://doi.org/10.1/a"),
        ReferenceItem(title="Arabic learning motivation review", authors=["Ana Lee"], year=2023, venue="Jurnal B",
                      volume="3", pages="10–20", doi="10.1/b", link="https://doi.org/10.1/b")]


def _sb(judul, *paras, kind="narasi"):
    return SubBab(judul=judul, kind=kind, content=[ContentText(isi=p) for p in paras])


def _bersih() -> Makalah:
    lb = ("Gamifikasi dipakai dalam pembelajaran bahasa Arab (Smith, 2024). Namun bukti masih terbatas pada sampel kecil, "
          "sehingga hasilnya perlu dibaca hati-hati (Lee, 2023).")
    return Makalah(
        judul="Gamifikasi Bahasa Arab", daftar_pustaka=list(REFS),
        bab={
            "I": Bab(judul="Pendahuluan", subbab=[
                _sb("1.1 Latar Belakang", lb),
                SubBab(judul="1.2 Rumusan Masalah", kind="daftar", content=[ContentList(items=[
                    "Bagaimana peta penerapan gamifikasi?", "Bagaimana pengaruhnya terhadap motivasi?"])]),
                SubBab(judul="1.3 Tujuan", kind="daftar", content=[ContentList(items=[
                    "Memetakan penerapan gamifikasi.", "Menganalisis pengaruh gamifikasi terhadap motivasi."])]),
                SubBab(judul="1.4 Manfaat", kind="daftar", content=[ContentList(items=["Manfaat teoretis.", "Manfaat praktis."])]),
                _sb("1.5 Metode Penulisan", "Makalah ini menggunakan kajian pustaka."),
            ]),
            "II": Bab(judul="Pembahasan", subbab=[
                _sb("2.1 Konsep Gamifikasi", "Gamifikasi adalah penerapan elemen permainan (Smith, 2024). Namun efeknya beragam (Lee, 2023)."),
                _sb("2.2 Pengaruh terhadap Motivasi", "Pengaruh gamifikasi terhadap motivasi tampak pada beberapa studi (Lee, 2023). "
                    "Keterbatasan utamanya ialah desain tanpa kontrol."),
            ]),
            "III": Bab(judul="Penutup", subbab=[
                _sb("3.1 Kesimpulan", "Peta penerapan gamifikasi menunjukkan ragam platform. Pengaruh gamifikasi terhadap motivasi "
                    "tampak positif tetapi terbatas. Keterbatasan: bukti sedikit."),
                _sb("3.2 Saran", "Penelitian lanjutan perlu menguji pengaruh gamifikasi terhadap motivasi dengan kelompok kontrol."),
            ]),
        })


def _ids(fs):
    return [f.rule_id for f in fs]


def test_makalah_bersih_tanpa_temuan_blocker_atau_major():
    fs = run_lints(_bersih())
    assert not [f for f in fs if f.severity in ("blocker", "major")], [(f.rule_id, f.message) for f in fs]


def test_tier_off_kosong_dan_katalog_lengkap():
    assert run_lints(_bersih(), tier="off") == []
    ids = {r["id"] for r in rules_catalog()}
    assert {"CIT-001", "STR-001", "STR-002", "STR-003", "RED-001", "CLM-001", "TRC-001", "LNG-001", "DOM-001", "REF-002"} <= ids
    assert "TPL-001" not in ids  # ada di template_check.py


def test_aturan_rusak_tidak_mematikan_laporan(monkeypatch):
    from malas.enhance.lint import RuleMeta
    boom = RuleMeta("CIT-001", "x", "blocker", "none", "", lambda m, c: 1 / 0)
    monkeypatch.setitem(RULES, "CIT-001", boom)
    m = _bersih()
    m.bab["I"].subbab[0].judul = "1.1 Latar Bekalang"
    assert "LNG-001" in _ids(run_lints(m))


def test_cit001_sitasi_satu_huruf_adalah_blocker():
    """Regresi F01."""
    m = _bersih()
    m.bab["II"].subbab[0].content[0].isi += " Kerangka (M dkk., 2026) dan M dkk. (2026)."
    fs = [f for f in run_lints(m) if f.rule_id == "CIT-001"]
    assert fs and all(f.severity == "blocker" for f in fs)


def test_str001_nomor_ganda_dan_str002_butir_dan_str003_bagian_wajib():
    m = _bersih()
    m.bab["II"].subbab[0].judul = "2.1 2.1 Konsep Gamifikasi"
    m.bab["I"].subbab[1].content = [ContentList(items=[
        "Berdasarkan latar belakang, rumusan masalahnya sebagai berikut:", "Bagaimana peta?", "Bagaimana pengaruh?",
        "Rumusan pertama merujuk pada kebutuhan memetakan landasan. " * 10])]
    del m.bab["III"].subbab[1]  # tanpa Saran
    ids = _ids(run_lints(m))
    assert "STR-001" in ids and "STR-002" in ids and "STR-003" in ids


def test_red001_angka_sama_di_dua_subbab():
    m = _bersih()
    m.bab["II"].subbab[0].content[0].isi += " " + STAT
    m.bab["II"].subbab[1].content[0].isi += " " + STAT
    assert "RED-001" in _ids(run_lints(m))


def test_clm001_kausal_pada_studi_tanpa_kontrol_memakai_kartu():
    m = _bersih()
    m.bab["II"].subbab[1].content[0].isi += " Studi itu membuktikan gamifikasi meningkatkan motivasi (Smith, 2024)."
    assert "CLM-001" not in _ids(run_lints(m))  # tanpa kartu: dilewati
    m.evidence[ref_key(REFS[0])] = EvidenceCard(ref_key=ref_key(REFS[0]), design="pre_post", has_control=False,
                                                outcome="hasil_belajar", causal_ok=False, confidence="sedang")
    ids = _ids(run_lints(m))
    assert "CLM-001" in ids and "CLM-004" in ids  # kausal + klaim motivasi dari ukuran hasil belajar


def test_clm002_tanpa_sisi_kritis():
    m = _bersih()
    m.bab["II"].subbab[1].content[0].isi = "Gamifikasi meningkatkan motivasi (Lee, 2023). Semua studi sepakat (Smith, 2024)."
    assert "CLM-002" in _ids(run_lints(m))


def test_trc001_rm_tanpa_jejak_di_kesimpulan():
    m = _bersih()
    m.bab["III"].subbab[0].content = [ContentText(isi="Secara umum teknologi pendidikan terus berkembang pesat di era digital.")]
    assert "TRC-001" in _ids(run_lints(m))


def test_trc002_populasi_kesimpulan_tak_sesuai_lingkup():
    m = _bersih()
    m.subjek = "siswa MTs"
    m.bab["III"].subbab[0].content[0].isi += " Hasil ini penting bagi mahasiswa PAI."
    assert "TRC-002" in _ids(run_lints(m))


def test_dom001_checklist_domain_tak_tercakup():
    m = _bersih()
    m.blueprint = Blueprint(domain_checklist=["mufradat", "nahwu", "sharaf", "maharah"])
    assert "DOM-001" in _ids(run_lints(m))
    m.bab["II"].subbab[0].content[0].isi += " Mufradat, nahwu, sharaf, dan maharah dibahas."
    assert "DOM-001" not in _ids(run_lints(m))


def test_ref002_judul_kapital_dan_tak_alfabet():
    m = _bersih()
    m.daftar_pustaka = [ReferenceItem(title="JUDUL SEMUA KAPITAL DI SINI YA", authors=["Zed Zorn"], year=2020, venue="J"),
                        ReferenceItem(title="Another paper about things", authors=["Ana Abel"], year=2021, venue="J")]
    ids = _ids(run_lints(m))
    assert "REF-002" in ids


def test_lng001_autofix_aman_dan_judul_tidak_diubah():
    m = _bersih()
    m.bab["II"].subbab[0].content[0].isi += " Lingkungan yang di gamifikasi dan   spasi ganda."
    m.bab["II"].subbab[0].judul = "2.1 Konsep Latar Bekalang"
    fixed, sisa, n = apply_auto_fixes(m)
    teks = fixed.bab["II"].subbab[0].content[0].isi
    assert "digamifikasi" in teks and "   " not in teks and n >= 2
    assert fixed.bab["II"].subbab[0].judul == "2.1 Konsep Latar Bekalang"  # judul = kunci state
    assert "di gamifikasi" in m.bab["II"].subbab[0].content[0].isi  # asli tak berubah
    assert score_findings(sisa) < score_findings(run_lints(m))


def test_autofix_membuang_pengantar_dan_penjelasan_butir():
    m = _bersih()
    m.bab["I"].subbab[1].content = [ContentList(items=["Rumusannya sebagai berikut:", "Apa A?", "Apa B?", "Penjelasan panjang. " * 30])]
    fixed, _, _ = apply_auto_fixes(m)
    assert fixed.bab["I"].subbab[1].content[0].items == ["Apa A?", "Apa B?"]


def test_laporan_stats_dan_urutan_deterministik():
    m = _bersih()
    m.bab["II"].subbab[0].content[0].isi += " (M dkk., 2026)"
    a, b = run_lints(m), run_lints(m)
    assert [f.model_dump() for f in a] == [f.model_dump() for f in b]
    st = lint_report_stats(a)
    assert st["by_severity"]["blocker"] >= 1 and st["total"] == len(a) and st["score"] >= 8
    assert a[0].severity == "blocker"  # urut keparahan


def test_profil_penelitian_tidak_menandai_penelitian_ini():
    m = _bersih()
    m.bab["I"].subbab[4].content[0].isi = "Penelitian ini memakai metode kajian pustaka."
    assert any(f.rule_id == "LNG-001" for f in run_lints(m))
    m.jenis_makalah = "penelitian"
    assert not any("penelitian" in f.message and f.rule_id == "LNG-001" for f in run_lints(m, ctx=LintContext(profile="penelitian")))


@pytest.mark.parametrize("tier", ["lite", "standard", "deep"])
def test_semua_tier_menjalankan_lint(tier):
    assert run_lints(_bersih(), tier=tier) == run_lints(_bersih())
