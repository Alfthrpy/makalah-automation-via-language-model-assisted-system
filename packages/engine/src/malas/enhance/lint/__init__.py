"""Registri lint deterministik L0 (docs/enhancing-engine.md §6.4, S07): 0 token, tanpa jaringan.

Pemakaian::

    from malas.enhance.lint import run_lints, lint_report_stats
    findings = run_lints(makalah)                  # list[Finding], urut keparahan lalu lokasi
    stats["quality"] = lint_report_stats(findings)

Aturan ditulis sebagai fungsi murni ``(Makalah, LintContext) -> Iterable[Finding]`` dan didaftarkan dengan
dekorator ``@rule("CIT-001", ...)``. Satu modul per kelas aturan (citations, references, structure, redundancy,
claims, traceability, language, domain). TPL-001 (template .docx) berada di luar paket ini.

Aturan yang butuh data opsional dilewati diam-diam bila datanya kosong: kartu bukti (`Makalah.evidence`) untuk
CLM-001/CLM-004/sebagian CIT-003, `Makalah.blueprint` untuk DOM-001. Laporan berisi temuan, BUKAN jaminan mutu.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from malas.crews.models.TaskOutput import Makalah
from malas.enhance.models import Finding, FixKind, Location, Severity, score_findings

log = logging.getLogger(__name__)

TIERS = ("off", "lite", "standard", "deep")  # cermin config.ENHANCE_TIERS (tanpa impor dotenv)
SEVERITY_ORDER = {"blocker": 0, "major": 1, "minor": 2, "info": 3}

# Ambang awal (dikalibrasi pada fixture sintetis + 1 makalah nyata; lihat tes & laporan benchmark).
DEFAULT_THRESHOLDS: dict[str, float] = {
    "trc001_min_score": 0.40,  # cakupan berbobot-IDF token RM di paragraf Kesimpulan terbaik
    "trc003_min_overlap": 0.25,  # tumpang-tindih token RM_i vs Tujuan_i
    "red002_jaccard": 0.60,  # shingling 5-kata
    "clm003_ratio": 0.50,  # rasio kalimat bergaya klaim tanpa sitasi
    "clm003_min_claims": 3,
    "dom001_min_coverage": 0.60,
    "ref003_indo_ratio": 0.60,
    "ref003_landmark_cited_by": 300,
    "str002_max_item_chars": 300,
    "str004_max_paragraphs": 6,
}


@dataclass
class LintContext:
    """Konteks opsional lint.

    - ``profile``: profil dokumen (default `Makalah.jenis_makalah`, mis. "kajian_pustaka").
    - ``source``: "state" (checkpoint pipeline; konverter S03/S04/S05 merapikan sebagian saat render) atau
      "printed" (teks hasil cetak/impor PDF: tak ada perapian lagi).
    - ``indo``: rencana refsearch menandai topik lokal Indonesia? None = tak diketahui.
    - ``trc002_body_fallback``: TRC-002 memakai populasi dari kalimat bersitasi di Bab II bila tak ada
      subjek/kartu (default mati: sesuai rancangan, aturan dilewati).
    """

    profile: str | None = None
    source: str = "state"
    indo: bool | None = None
    trc002_body_fallback: bool = False
    thresholds: dict[str, float] = field(default_factory=dict)

    def th(self, name: str) -> float:
        return self.thresholds.get(name, DEFAULT_THRESHOLDS[name])


RuleFn = Callable[[Makalah, LintContext], Iterable[Finding]]


@dataclass(frozen=True)
class RuleMeta:
    id: str
    description: str
    severity: Severity
    fix: FixKind
    needs: str = ""  # "evidence" | "blueprint" | "" (data opsional yang dibutuhkan)
    fn: RuleFn | None = None


RULES: dict[str, RuleMeta] = {}


def rule(rule_id: str, description: str, severity: Severity, fix: FixKind = "none", needs: str = ""):
    """Dekorator pendaftar aturan. ID unik `<KELAS>-<NNN>`."""
    if not re.fullmatch(r"[A-Z]{3}-\d{3}", rule_id):
        raise ValueError(f"ID aturan tidak sah: {rule_id}")

    def deco(fn: RuleFn) -> RuleFn:
        if rule_id in RULES:
            raise ValueError(f"Aturan ganda: {rule_id}")
        RULES[rule_id] = RuleMeta(rule_id, description, severity, fix, needs, fn)
        return fn

    return deco


def _clip(s: str, n: int = 200) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def make_finding(rule_id: str, where: Location | None, message: str, evidence: str = "", *,
                 severity: Severity | None = None, fix: FixKind | None = None, hint: str = "") -> Finding:
    """Bangun `Finding` dengan default dari metadata aturan; pesan/bukti dipotong <=200 karakter."""
    meta = RULES[rule_id]
    return Finding(rule_id=rule_id, severity=severity or meta.severity, where=where or Location(),
                   message=_clip(message), evidence=_clip(evidence), fix=fix or meta.fix, hint=_clip(hint, 300))


def _sort_key(makalah: Makalah):
    from malas.enhance.lint._util import bab_order

    order = {}
    for key, bab in makalah.bab.items():
        for i, sub in enumerate(bab.subbab):
            order.setdefault((key, sub.judul), i)

    def key(f: Finding):
        w = f.where
        return (SEVERITY_ORDER[f.severity], bab_order(w.bab) if w.bab else 100,
                order.get((w.bab, w.subbab), 999) if w.subbab else 999,
                w.paragraph if w.paragraph is not None else -1, f.rule_id, f.message)

    return key


def run_lints(makalah: Makalah, *, tier: str = "lite", ctx: LintContext | dict | None = None,
              only: Iterable[str] | None = None) -> list[Finding]:
    """Jalankan semua aturan L0 -> temuan terurut (keparahan, bab, sub-bab, paragraf, aturan). Deterministik.

    `tier="off"` -> []. Semua tier lain menjalankan semua aturan (lint gratis); aturan yang datanya belum ada
    (kartu/blueprint) lewat sendiri. Galat dalam satu aturan dicatat ke log dan tidak menghentikan yang lain.
    """
    if tier not in TIERS:
        raise ValueError(f"tier tidak dikenal: {tier}")
    if tier == "off":
        return []
    if ctx is None:
        ctx = LintContext()
    elif isinstance(ctx, dict):
        ctx = LintContext(**ctx)
    wanted = set(only) if only else None
    out: list[Finding] = []
    for rid in sorted(RULES):
        if wanted is not None and rid not in wanted:
            continue
        try:
            out.extend(RULES[rid].fn(makalah, ctx))
        except Exception:
            log.exception("aturan lint %s gagal", rid)
    return sorted(out, key=_sort_key(makalah))


def lint_report_stats(findings: list[Finding]) -> dict:
    """Ringkasan untuk `stats["quality"]`: hitungan per keparahan & per aturan, skor berbobot, jumlah auto-fix."""
    by_sev = {s: 0 for s in SEVERITY_ORDER}
    by_rule: dict[str, int] = {}
    for f in findings:
        by_sev[f.severity] += 1
        by_rule[f.rule_id] = by_rule.get(f.rule_id, 0) + 1
    return {"total": len(findings), "by_severity": by_sev, "by_rule": dict(sorted(by_rule.items())),
            "score": score_findings(findings), "auto_fixable": sum(1 for f in findings if f.fix == "auto")}


def rules_catalog() -> list[dict]:
    """Metadata semua aturan (id, deskripsi, keparahan default, fix, data yang dibutuhkan)."""
    return [{"id": m.id, "description": m.description, "severity": m.severity, "fix": m.fix, "needs": m.needs}
            for m in (RULES[k] for k in sorted(RULES))]


# Impor modul aturan di AKHIR berkas (efek samping: mendaftar ke RULES); `rule`/`make_finding` sudah terdefinisi.
from malas.enhance.lint import (  # noqa: F401
    citations,
    claims,
    domain,
    language,
    redundancy,
    references,
    structure,
    traceability,
)

__all__ = [
    "DEFAULT_THRESHOLDS",
    "RULES",
    "TIERS",
    "LintContext",
    "RuleMeta",
    "lint_report_stats",
    "make_finding",
    "rule",
    "rules_catalog",
    "run_lints",
]
