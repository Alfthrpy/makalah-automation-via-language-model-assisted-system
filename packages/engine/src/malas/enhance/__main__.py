"""CLI: python -m malas.enhance --lint <checkpoint.json|makalah.json> [--json] [--printed] [--fix OUT.json]"""
import argparse
import json
import sys
from pathlib import Path

from malas import checkpoint
from malas.crews.models.TaskOutput import Makalah
from malas.enhance.autofix import apply_auto_fixes
from malas.enhance.lint import LintContext, lint_report_stats, run_lints


def _load(path: Path) -> Makalah:
    ck = checkpoint.load(path)
    if ck:
        return Makalah.model_validate(ck["state"])
    return Makalah.model_validate(json.loads(path.read_text(encoding="utf-8")))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="malas.enhance", description="Lint deterministik makalah (0 token).")
    ap.add_argument("--lint", required=True, type=Path, help="checkpoint job atau JSON Makalah")
    ap.add_argument("--json", action="store_true", help="keluaran JSON")
    ap.add_argument("--printed", action="store_true", help="teks hasil cetak/impor (tanpa perapian konverter)")
    ap.add_argument("--fix", type=Path, help="tulis Makalah hasil perbaikan otomatis ke berkas ini")
    a = ap.parse_args(argv)
    m = _load(a.lint)
    ctx = LintContext(source="printed" if a.printed else "state")
    findings = run_lints(m, ctx=ctx)
    if a.fix:
        m2, findings, n = apply_auto_fixes(m, ctx)
        a.fix.write_text(m2.model_dump_json(indent=1), encoding="utf-8")
        print(f"{n} perubahan otomatis -> {a.fix}", file=sys.stderr)
    if a.json:
        print(json.dumps({"stats": lint_report_stats(findings), "findings": [f.model_dump() for f in findings]},
                         ensure_ascii=False, indent=1))
    else:
        print(lint_report_stats(findings))
        for f in findings:
            print(f"{f.rule_id} {f.severity:7} {f.where.subbab or '-':30.30} | {f.message}")
    return 1 if any(f.severity == "blocker" for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
