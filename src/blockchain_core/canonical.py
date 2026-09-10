"""Canonical byte-encoding used everywhere a hash or signature is computed"""
from __future__ import annotations

import json
from typing import Any


class CanonicalizationError(ValueError):
    """"Raised when a structure cannot be canonically encoded."""
def _validate(value:Any) -> Any:
  if isinstance(value, bool):
    return value
  if isinstance(value, float):
    raise CanonicalizationError(
      "canonical encoding forbids float values: use integer epoch-ms for timestamps")
  if isinstance(value, dict):
    normalized = {}
    for key, val in value.items():
      if not isinstance(key, str):
        raise CanonicalizationError(f"canonical encoding forbids non-string keys: got {key!r}")
      normalized[key] = _validate(val)
    return normalized
  if isinstance(value, list):
    return [_validate(item) for item in value]
  return value

def canonicalize(obj: Any) -> bytes:
  normalized = _validate(obj)
  return json.dumps(
    normalized,
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=False,
  ).encode('utf-8')
