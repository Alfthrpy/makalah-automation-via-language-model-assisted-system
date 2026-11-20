import pytest

from malas.names import family_of, is_confident, is_institution, normalize_author


@pytest.mark.parametrize("raw,expected", [
    ("Raseena P M", "Raseena, P. M."),           # kasus nyata OpenAlex: bukan "M"
    ("Maya C", "Maya, C."),
    ("Rizka Utami", "Utami, R."),
    ("Abdul Wasih Kattikulangara", "Kattikulangara, A. W."),
    ("Smith, John", "Smith, J."),
    ("Smith, J. A.", "Smith, J. A."),            # idempoten
    ("Smith JA", "Smith, J. A."),                # gaya Europe PMC
    ("J. R. Smith", "Smith, J. R."),
    ("Syihabuddin Syihabuddin", "Syihabuddin, S."),
    ("Jean-Paul Sartre", "Sartre, J.-P."),
    ("Dr. Siti Nurhaliza, M.Pd.", "Nurhaliza, S."),   # koma tak boleh membuat gelar jadi keluarga
    ("Siti Nurhaliza M.Pd.", "Nurhaliza, S."),
    ("Badan Pusat Statistik", "Badan Pusat Statistik"),
    ("Wikipedia", "Wikipedia"),
    ("Utami", "Utami"),
    ("", ""),
    ("  Ana   Lee ", "Lee, A."),
])
def test_normalize_author(raw, expected):
    assert normalize_author(raw) == expected


def test_normalisasi_idempoten():
    for raw in ["Raseena P M", "Rizka Utami", "Badan Pusat Statistik", "Smith, J. A.", "Jean-Paul Sartre"]:
        once = normalize_author(raw)
        assert normalize_author(once) == once


def test_family_of_tidak_pernah_satu_huruf_untuk_nama_lengkap():
    for raw in ["Raseena P M", "Maya C", "Abdul Rahman K", "Smith JA"]:
        assert len(family_of(raw)) > 1


def test_kepercayaan_heuristik():
    assert not is_confident("Raseena P M")      # keluarga ditebak dari inisial di belakang
    assert is_confident("Rizka Utami")
    assert is_confident("Smith, John")


def test_is_institution():
    assert is_institution("Wikipedia") and is_institution("Badan Pusat Statistik")
    assert not is_institution("Rizka Utami")
