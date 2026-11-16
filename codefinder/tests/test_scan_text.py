import pytest

from codefinder.finder import find_codes, make_hits, scan_text
from codefinder.ocr import OcrResult, ocr_hits


@pytest.fixture
def cfg(tmp_path):
    path = tmp_path / "codes.csv"
    path.write_text(
        "code,kind,value,context\nTESTCODE,phrase,zork blat,\n", encoding="utf-8"
    )
    return str(path)


@pytest.mark.parametrize("text", [None, "", "   \n\t"])
def test_empty_input_gives_no_hits(cfg, text):
    assert find_codes(text, cfg) == []


def test_non_string_input_is_rejected(cfg):
    with pytest.raises(TypeError):
        find_codes(123, cfg)


def test_multiline_text(cfg):
    assert find_codes("hello\nzork\nblat\nworld", cfg) == ["TESTCODE"]


def test_ocr_noise_and_leetspeak(cfg):
    assert find_codes("Z0RK   BL4T", cfg) == ["TESTCODE"]


def test_lookalike_letters(cfg):
    assert find_codes("z\u043erk blat", cfg) == ["TESTCODE"]


def test_long_text(cfg):
    assert find_codes("lorem ipsum " * 5000 + "zork blat", cfg) == ["TESTCODE"]


def test_scan_text_labels_the_source(cfg):
    assert scan_text("zork blat", "vision", cfg) == [
        {"code": "TESTCODE", "source": "vision"}
    ]
    assert scan_text("zork blat", config_path=cfg)[0]["source"] == "text"


def test_harmless_text_has_no_hits(cfg):
    assert scan_text("guten morgen", "ocr", cfg) == []


def test_ocr_hits_use_the_shared_shape():
    result = OcrResult(text="", codes=["A"])
    assert ocr_hits(result) == make_hits(["A"], "ocr")
