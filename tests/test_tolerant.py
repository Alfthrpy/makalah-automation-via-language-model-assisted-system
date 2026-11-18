import pytest

from malas.crews.models.TaskOutput import ContentList, ContentText
from malas.tolerant import (
    ParseError, TolerantConverter, extract_json, parse_kata_pengantar, parse_outline, parse_references,
    parse_subbab,
)


def test_extract_json_dari_pagar_dan_prosa():
    assert extract_json('Berikut hasilnya:\n```json\n{"a": 1}\n```\nSemoga membantu.') == {"a": 1}
    assert extract_json('teks {bukan json} lalu {"b": [1, 2]} selesai') == {"b": [1, 2]}
    assert extract_json("tanpa json sama sekali") is None


def test_subbab_json_valid_dan_bentuk_alternatif():
    s = parse_subbab('{"judul": "1.1", "content": [{"type": "text", "isi": "Halo"}, {"type": "list", "items": ["a", "b"]}]}')
    assert isinstance(s.content[0], ContentText) and isinstance(s.content[1], ContentList)
    # kunci alternatif + string tunggal + pagar markdown
    s = parse_subbab('```json\n{"content": [{"paragraph": "Isi satu"}, "Isi dua", {"poin": ["x", "y"], "judul": "Daftar:"}]}\n```')
    assert [type(c).__name__ for c in s.content] == ["ContentText", "ContentText", "ContentList"]
    assert s.content[2].title_items == "Daftar:" and s.content[2].items == ["x", "y"]
    # kunci 'isi' di level atas (tanpa 'content'): dulu menghasilkan SubBab kosong tanpa error
    s = parse_subbab('{"judul": "x", "isi": "Satu paragraf penuh."}')
    assert s.content[0].isi == "Satu paragraf penuh."


def test_subbab_prosa_markdown_menjadi_paragraf_dan_daftar():
    teks = ("Final Answer: ## 1.1 Latar Belakang\n\nParagraf **pertama** tentang topik.\nlanjutan kalimat.\n\n"
            "Poin penting berikut:\n- Satu\n- Dua\n\n1. Alpha\n2. Beta\n")
    s = parse_subbab(teks)
    assert s.content[0].isi == "Paragraf pertama tentang topik. lanjutan kalimat."
    assert s.content[1].title_items == "Poin penting berikut:" and s.content[1].items == ["Satu", "Dua"]
    assert s.content[2].items == ["Alpha", "Beta"]


@pytest.mark.parametrize("bad", ["", "   \n ", '{"judul": "x"}', "```json\n```"])
def test_subbab_kosong_ditolak(bad):
    with pytest.raises(ParseError):
        parse_subbab(bad)


def test_kata_pengantar():
    assert parse_kata_pengantar('{"isi": "Puji syukur.\\nTerima kasih."}').isi == "Puji syukur.\nTerima kasih."
    assert parse_kata_pengantar("## KATA PENGANTAR\n\nPuji syukur kami panjatkan.").isi == "Puji syukur kami panjatkan."
    with pytest.raises(ParseError):
        parse_kata_pengantar("  ")


def test_references_bentuk_longgar():
    teks = '''```json
[{"judul": "Deep Learning", "author": "Ana Lee; Bob Kim", "tahun": "2023", "url": "https://x.org/1", "abstract": "Ringkasan"},
 {"title": "Tanpa tahun", "authors": ["A B"]},
 {"title": "Dengan DOI", "authors": "Solo Author", "year": 2020, "doi": "10.1/abc"}]
```'''
    r = parse_references(teks).references
    assert [x.title for x in r] == ["Deep Learning", "Dengan DOI"]  # tanpa tahun dibuang, bukan dikarang
    assert r[0].authors == ["Ana Lee", "Bob Kim"] and r[0].year == 2023 and r[0].excerpt == "Ringkasan"
    assert r[1].link == "https://doi.org/10.1/abc"
    with pytest.raises(ParseError):
        parse_references("tidak ada referensi")


def test_outline_json_dan_prosa():
    o = parse_outline('{"subbabs": {"Bab 1": {"sections": ["1.1 A", "1.2 B"]}, "Bab 2": ["2.1 C"]}}')
    assert list(o.subbabs) == ["Bab 1", "Bab 2"] and o.subbabs["Bab 2"].sections == ["2.1 C"]
    o = parse_outline("**Bab 1: Pendahuluan**\n- 1.1 Latar Belakang\n- 1.2 Rumusan Masalah\n\n## Bab 2: Pembahasan\n2.1 Teori\n")
    assert o.subbabs["Bab 1: Pendahuluan"].sections == ["1.1 Latar Belakang", "1.2 Rumusan Masalah"]
    assert o.subbabs["Bab 2: Pembahasan"].sections == ["2.1 Teori"]


def test_converter_mengembalikan_error_bukan_melempar():
    from crewai.utilities.converter import ConverterError

    from malas.crews.models.TaskOutput import SubBab

    c = TolerantConverter(text="   ", llm=object(), model=SubBab, instructions="x")
    assert isinstance(c.to_pydantic(), ConverterError)  # CrewAI lalu memakai teks mentah; tidak crash
    ok = TolerantConverter(text="Satu paragraf.", llm=object(), model=SubBab, instructions="x").to_pydantic()
    assert ok.content[0].isi == "Satu paragraf."


def test_jalur_asli_crewai_memakai_converter_toleran_tanpa_llm():
    """Reproduksi galat 'Agent must be provided...': keluaran bukan JSON -> sebelumnya crash."""
    from types import SimpleNamespace

    from crewai.utilities.converter import convert_to_model

    from malas.crews.models.TaskOutput import SubBab

    agent = SimpleNamespace(function_calling_llm=None, llm=SimpleNamespace(supports_function_calling=lambda: False))
    out = convert_to_model("Ini hanya paragraf biasa, bukan JSON.", SubBab, None, agent, TolerantConverter)
    assert isinstance(out, SubBab) and out.content[0].isi.startswith("Ini hanya paragraf")
