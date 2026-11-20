"""DOM-001: cakupan `Blueprint.domain_checklist` di Bab II (istilah wajib domain)."""
from __future__ import annotations

from malas.crews.models.TaskOutput import Makalah
from malas.enhance.lint import LintContext, make_finding, rule
from malas.enhance.lint._util import bab_order, fold, iter_subbab, sub_text
from malas.enhance.models import Finding, Location


@rule("DOM-001", "Istilah wajib domain (Blueprint.domain_checklist) kurang tercakup", "major", "patch",
      needs="blueprint")
def dom001(makalah: Makalah, ctx: LintContext) -> list[Finding]:
    bp = makalah.blueprint
    terms = [t for t in (bp.domain_checklist if bp else []) if t.strip()]
    if not terms:
        return []
    body = fold(" ".join(sub_text(s) for k, _, s in iter_subbab(makalah) if bab_order(k) == 2))
    if not body.strip():
        body = fold(" ".join(sub_text(s) for _, _, s in iter_subbab(makalah)))
    missing = [t for t in terms if fold(t.strip()) not in body]
    cov = 1 - len(missing) / len(terms)
    if cov >= ctx.th("dom001_min_coverage"):
        return []
    return [make_finding("DOM-001", Location(bab="II"),
                         f"Cakupan istilah domain {cov:.0%} (< {ctx.th('dom001_min_coverage'):.0%}); belum dibahas: "
                         f"{', '.join(missing[:6])}.", ", ".join(missing),
                         hint="Bahas istilah/contoh domain yang belum muncul dengan sumber yang relevan.")]
