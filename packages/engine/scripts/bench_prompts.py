"""Benchmark UKURAN PROMPT penulis pada makalah nyata (tanpa LLM nyata): token masukan per sub-bab, tier off/lite/deep.

Cara kerja: untuk tiap sub-bab k, state diisi dari JSON `Makalah` (hasil `paper_to_makalah.py`) dengan sub-bab k.. dikosongkan,
lalu alur ASLI `MalasFlow` dijalankan (mode mock, resume dari checkpoint) dan pesan yang dikirim crewAI ke LLM untuk sub-bab k
direkam (system + user, termasuk scaffolding crewAI). Isi referensi (abstrak) dari OpenAlex. Token ~ karakter/4 (taksiran, sama
dengan telemetri engine; tokenizer asli tidak tersedia offline).

    PYTHONPATH=packages/engine/src python packages/engine/scripts/bench_prompts.py \
        --paper /tmp/paper.json --abstracts /tmp/refs_abs.json --out hasil.json
"""
import argparse
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("MALAS_MOCK", "1")
os.environ.setdefault("MALAS_REFSEARCH", "1")
os.environ.setdefault("MALAS_FULLTEXT", "0")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")


class StopBench(Exception):
    pass


def load_state(paper: Path, abstracts: Path):
    from malas.citations import check_citations
    from malas.crews.models.TaskOutput import Makalah
    m = Makalah.model_validate(json.loads(paper.read_text(encoding="utf-8")))
    ab = json.loads(abstracts.read_text(encoding="utf-8"))
    for r in m.daftar_pustaka:
        doi = (r.doi or "").replace("https://doi.org/", "")
        r.excerpt = (ab.get(doi) or {}).get("abstract") or r.excerpt
        r.link = r.link or (f"https://doi.org/{doi}" if doi else None)
    # sub-bab pemakai referensi = sub-bab yang menyitirnya di makalah asli (aproksimasi penugasan refsearch)
    from malas.citations import _ref_keys, content_text, extract_citations
    keys = [_ref_keys(r) for r in m.daftar_pustaka]
    for bab in m.bab.values():
        for sb in bab.subbab:
            for c in extract_citations(content_text(sb.content)):
                for i, k in enumerate(keys):
                    if (c.surname, c.year) in k and sb.judul not in m.daftar_pustaka[i].sections:
                        m.daftar_pustaka[i].sections.append(sb.judul)
    check_citations(m)
    return m


def measure(paper: Path, abstracts: Path, tier: str, k: int) -> dict:
    os.environ["MALAS_ENHANCE"] = tier
    from malas import checkpoint
    from malas.main import MalasFlow
    from malas.mock.mock_llm import AutoFakeLLM

    m = load_state(paper, abstracts)
    flat = [sb for b in m.bab.values() for sb in b.subbab]
    target = flat[k].judul
    for sb in flat[k:]:
        sb.content = []
    rec: dict = {}
    orig_call = AutoFakeLLM.call

    def call(self, messages, **kw):
        task = kw.get("from_task")
        if task is not None and getattr(task, "output_pydantic", None).__name__ == "SubBab" and "msgs" not in rec:
            txt = messages if isinstance(messages, str) else "\n".join(str(x.get("content", "")) for x in messages)
            rec["msgs"] = len(txt)
        return orig_call(self, messages, **kw)

    AutoFakeLLM.call = call
    with tempfile.TemporaryDirectory() as d:
        ck = Path(d) / "ck.json"
        checkpoint.save(ck, m, {"calls": 0, "prompt": 0, "completion": 0, "total": 0}, {})
        flow = MalasFlow()
        flow.input_data = {"judul": m.judul, "mata_kuliah": m.mata_kuliah or "Teknologi Pembelajaran PAI"}
        flow.checkpoint_path, flow.resume, flow.output_path = ck, True, str(Path(d) / "o.docx")
        orig = MalasFlow._write_subbab

        def stop(self, crew, writer, inputs, judul):
            orig(self, crew, writer, inputs, judul)
            raise StopBench(judul)

        MalasFlow._write_subbab = stop
        try:
            flow.kickoff()
        except StopBench:
            pass
        finally:
            MalasFlow._write_subbab = orig
            AutoFakeLLM.call = orig_call
    return {"subbab": target, "chars": rec.get("msgs", 0), "tokens_est": rec.get("msgs", 0) // 4}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", required=True, type=Path)
    ap.add_argument("--abstracts", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--tiers", default="off,lite,deep")
    a = ap.parse_args()
    n = len([1 for b in load_state(a.paper, a.abstracts).bab.values() for _ in b.subbab])
    res: dict = {}
    for tier in a.tiers.split(","):
        rows = [measure(a.paper, a.abstracts, tier, k) for k in range(n)]
        res[tier] = {"per_subbab": rows, "mean": round(statistics.mean(r["tokens_est"] for r in rows)),
                     "total": sum(r["tokens_est"] for r in rows)}
        print(f"{tier:5} total {res[tier]['total']:6} tok | rata-rata {res[tier]['mean']:5}/sub-bab", file=sys.stderr)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
