"""Tests for canonical serialization"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from blockchain_core.canonical import CanonicalizationError, canonicalize
from blockchain_core.hashing import sha256_hex

VECTORS_PATH = Path(__file__).resolve().parents[1] / "vectors" / "canonical_vectors.json"


def _load_vectors() -> list[dict]:
    return json.loads(VECTORS_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("vector", _load_vectors(), ids=lambda v: v["name"])
def test_vector_matches_expected_bytes_and_hash(vector: dict) -> None:
    result = canonicalize(vector["input"])
    assert result.decode("utf-8") == vector["expected_canonical"]
    assert sha256_hex(result) == vector["expected_sha256_hex"]


def test_canonicalize_is_order_independent() -> None:
    obj_a = {"b": 2, "a": 1, "nested": {"z": [3, 2, 1], "y": "AbC123"}}
    obj_b = {"nested": {"y": "AbC123", "z": [3, 2, 1]}, "a": 1, "b": 2}
    assert canonicalize(obj_a) == canonicalize(obj_b)


def test_rejects_float_value() -> None:
    with pytest.raises(CanonicalizationError):
        canonicalize({"issued_at": 1_700_000_000_123.0})


def test_rejects_non_string_dict_keys() -> None:
    with pytest.raises(CanonicalizationError):
        canonicalize({1: "x"})
    with pytest.raises(CanonicalizationError):
        canonicalize({1.5: "x"})


def test_does_not_mutate_string_case() -> None:
    result = canonicalize({"document_hash": "ABCDEF0123456789", "name": "Ada"})
    assert b'"ABCDEF0123456789"' in result
    assert b'"Ada"' in result


def _files_containing(
    root: Path, *, needles: tuple[str, ...], except_name: str | None = None
) -> list[Path]:
    return [
        path
        for path in root.rglob("*.py")
        if path.name != except_name
        and any(needle in path.read_text(encoding="utf-8") for needle in needles)
    ]


def test_hashlib_confined_to_hashing_module() -> None:
    src_root = Path(__file__).resolve().parents[2] / "src"
    offenders = _files_containing(
        src_root, except_name="hashing.py", needles=("import hashlib", "from hashlib")
    )
    assert offenders == []


def test_json_dumps_confined_to_canonical_module() -> None:
    src_root = Path(__file__).resolve().parents[2] / "src"
    offenders = _files_containing(src_root, except_name="canonical.py", needles=("json.dumps",))
    assert offenders == []


def test_no_stray_src_dot_imports() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    offenders: list[Path] = []
    for base in ("src", "tests"):
        offenders += _files_containing(
            repo_root / base, except_name="test_canonical.py", needles=("from src.", "import src.")
        )
    assert offenders == []