"""Tahap LLM enhancing (blueprint, kartu, tabel, guardrail, kritik, tambal, dukungan-sumber) dengan LLM palsu."""
import json
from types import SimpleNamespace

from malas.crews.models.TaskOutput import Bab, ContentList, ContentTable, ContentText, Makalah, ReferenceItem, SubBab
from malas.enhance.blueprint import build_blueprint, parse_blueprint
from malas.enhance.budget import Budget
from malas.enhance.critic import parse_findings, run_critic
from malas.enhance.evidence import ref_key_of
from malas.enhance.guardrail import check_candidate, make_guardrail
from malas.enhance.models import EvidenceCard
from malas.enhance.patch import run_patches
from malas.enhance.support import candidates, run_support_check
from malas.enhance.tables import attach_synthesis_table, build_synthesis_table

REFS = [ReferenceItem(title="Gamification effects on motivation", authors=["John Smith"], year=2024, doi="10.1/a",
                      excerpt="Quasi experiment with control group n = 70 students; motivation improved."),
        ReferenceItem(title="Arabic learning motivation review", authors=["Ana Lee"], year=2023, doi="10.1/b"),
        ReferenceItem(title="Pre post study of quizzes", authors=["Bob Kim"], year=2022, doi="10.1/c")]


def _m() -> Makalah:
    def sb(j, t):
        return SubBab(judul=j, content=[ContentText(isi=t)])
    return Makalah(judul="Gamifikasi Bahasa Arab", daftar_pustaka=list(REFS), bab={
        "I": Bab(subbab=[sb("1.1 Latar Belakang", "Latar (Smith, 2024)."),
                         SubBab(judul="1.2 Rumusan Masalah", kind="daftar",
                                content=[ContentList(items=["Bagaimana peta?", "Bagaimana pengaruh?"])])]),
        "II": Bab(subbab=[sb("2.1 Konsep", "Konsep dasar (Smith, 2024). Namun terbatas."),
                          sb("2.2 Dampak studi", "Dampak terlihat (Lee, 2023). Studi itu membuktikan peningkatan (Kim, 2022).")]),
        "III": Bab(subbab=[sb("3.1 Kesimpulan", "Pengaruh gamifikasi terbatas. Peta penerapan beragam.")]),
    })


def _cards(m: Makalah):
    for r, d, ctrl in zip(REFS, ("kuasi_eksperimen", "slr", "pre_post"), (True, None, False)):
        m.evidence[ref_key_of(r)] = EvidenceCard(ref_key=ref_key_of(r), design=d, has_control=ctrl, n=70 if ctrl else None,
                                                 population="siswa", outcome="motivasi", key_result="meningkat",
                                                 limitations="sampel kecil", causal_ok=bool(ctrl) and d == "kuasi_eksperimen")


def test_blueprint_membuang_kunci_fiktif_dan_gagal_aman():
    m = _m()
    raw = json.dumps({"research_questions": ["Bagaimana peta?", "Bagaimana pengaruh?", "A?", "B?"],
                      "rq_map": {"Bagaimana peta?": ["2.1 Konsep", "9.9 Fiktif"], "RM asing?": ["2.1 Konsep"]},
                      "subbab_tasks": {"2.1 Konsep": "Jelaskan konsep.", "9.9 Fiktif": "x"},
                      "domain_checklist": ["a", "b", "c"], "avoid_repeat": ["angka F"]})
    bp = parse_blueprint(raw, m)
    assert len(bp.research_questions) == 3 and bp.rq_map == {"Bagaimana peta?": ["2.1 Konsep"]}
    assert list(bp.subbab_tasks) == ["2.1 Konsep"] and bp.domain_checklist == ["a", "b", "c"]
    assert parse_blueprint("bukan json", m) is None
    assert build_blueprint(m, lambda p: "ngawur", Budget(10_000)) is None
    assert build_blueprint(m, lambda p: raw, Budget(0)) is None  # anggaran habis -> lewati


def test_blueprint_resume_tidak_memanggil_llm_lagi():
    m = _m()
    m.blueprint = parse_blueprint(json.dumps({"subbab_tasks": {"2.1 Konsep": "t"}, "domain_checklist": ["x"]}), m)
    assert build_blueprint(m, lambda p: 1 / 0, Budget(10_000)) is m.blueprint


def test_tabel_sintesis_dari_kartu_dan_tidak_ganda():
    m = _m()
    assert build_synthesis_table(m) is None  # tanpa kartu
    _cards(m)
    t = build_synthesis_table(m)
    assert t.header[0].startswith("Penulis") and len(t.rows) == 3 and "Smith" in t.rows[0][0]
    assert attach_synthesis_table(m) is True
    assert isinstance(m.bab["II"].subbab[1].content[-1], ContentTable)  # sub-bab "Dampak studi"
    assert attach_synthesis_table(m) is False


def test_guardrail_menolak_lalu_soft_fail_di_percobaan_terakhir():
    m = _m()
    bad = SubBab(judul="2.2 Dampak studi", content=[ContentText(isi="Kerangka (M dkk., 2026) membuktikan.")])
    ctx = {"state": m, "judul": "2.2 Dampak studi", "report": []}
    g = make_guardrail(lambda: ctx, max_retries=1)
    out = SimpleNamespace(pydantic=bad, raw="")
    ok1, fb = g(out)
    assert ok1 is False and "sitasi" in fb.lower() or "M dkk" in fb
    ok2, _ = g(out)  # percobaan terakhir: SELALU lolos (crewAI akan melempar bila retry habis)
    assert ok2 is True and ctx["report"]
    # pemanggilan pertama crewAI 1.15: pydantic belum terisi, raw JSON harus dibaca
    raw = json.dumps({"content": [{"type": "text", "isi": "Kerangka (M dkk., 2026)."}]})
    g2 = make_guardrail(lambda: ctx, max_retries=1)
    assert g2(SimpleNamespace(pydantic=None, raw=raw))[0] is False
    assert make_guardrail(lambda: None)(SimpleNamespace(pydantic=None, raw=""))[0] is True  # tanpa konteks: lolos


def test_guardrail_lolos_bila_bersih():
    m = _m()
    ok = SubBab(judul="2.1 Konsep", content=[ContentText(isi="Konsep dasar (Smith, 2024). Namun terbatas.")])
    assert check_candidate(m, "2.1 Konsep", ok.content) == []


def test_kritik_memvalidasi_lokasi_dan_batas():
    m = _m()
    raw = json.dumps({"findings": [
        {"subbab": "2.2 Dampak studi", "paragraph": 0, "severity": "major", "message": "Klaim terlalu kuat.", "hint": "Lunakkan."},
        {"subbab": "9.9 Fiktif", "paragraph": 0, "severity": "major", "message": "x"},
        {"subbab": "2.1 Konsep", "paragraph": 99, "severity": "minor", "message": "Terlalu singkat."},
        {"subbab": "2.1 Konsep", "message": ""}]})
    fs = parse_findings(raw, m, [])
    assert [f.where.subbab for f in fs] == ["2.2 Dampak studi", "2.1 Konsep"]
    assert fs[0].source == "critic" and fs[0].fix == "patch" and fs[1].where.paragraph is None
    assert run_critic(m, [], lambda p: raw, Budget(0)) == []
    assert run_critic(m, [], lambda p: "ngawur", Budget(100_000)) == []


def test_tambal_diterima_bila_lebih_baik_dan_ditolak_bila_memburuk():
    m = _m()
    from malas.enhance.models import Finding, Location
    f = Finding(rule_id="CRT-001", severity="major", where=Location(bab="II", subbab="2.2 Dampak studi"),
                message="Kuat", fix="patch", hint="lunakkan", source="critic")
    # kandidat memperburuk: menambah sitasi tak sah (blocker baru) -> ditolak, teks asli utuh
    asli = m.bab["II"].subbab[1].content[0].isi
    jelek = json.dumps({"content": [{"type": "text", "isi": asli + " Tambahan (Palsu, 1999)."}]})
    rep = run_patches(m, [f], lambda p: jelek, Budget(100_000))
    assert rep.rejected == ["2.2 Dampak studi"] and m.bab["II"].subbab[1].content[0].isi == asli
    # anggaran habis -> dilewati
    assert run_patches(m, [f], lambda p: jelek, Budget(0)).skipped_budget == 1
    # panjang tak wajar (terpotong) -> ditolak
    assert run_patches(m, [f], lambda p: json.dumps({"content": [{"type": "text", "isi": "x"}]}), Budget(100_000)).rejected
    # perbaikan yang menurunkan skor lint (membuang klaim kausal pada studi non-kausal) -> diterima
    _cards(m)
    baik = json.dumps({"content": [{"type": "text", "isi": "Dampak terlihat (Lee, 2023). Studi itu menunjukkan "
                                                           "peningkatan (Kim, 2022), dengan keterbatasan desain."}]})
    sebelum = m.bab["II"].subbab[1].content[0].isi
    rep = run_patches(m, [f], lambda p: baik, Budget(100_000))
    assert rep.accepted == ["2.2 Dampak studi"] and m.bab["II"].subbab[1].content[0].isi != sebelum


def test_cek_dukungan_hanya_kalimat_berisiko_berkutipan_rendah_overlap():
    m = _m()
    m.bab["II"].subbab[1].content[0].isi = "Gamifikasi menaikkan nilai ujian sebesar 45% pada semua siswa (Lee, 2023)."
    assert len(candidates(m)) == 1
    verdict = json.dumps({"hasil": [{"n": 1, "verdict": "tidak"}]})
    fs = run_support_check(m, lambda p: verdict, Budget(100_000))
    assert len(fs) == 1 and fs[0].rule_id == "CIT-003" and fs[0].where.subbab == "2.2 Dampak studi"
    assert run_support_check(m, lambda p: "ngawur", Budget(100_000)) == []
