"""SHA-256 wrappers - the only place hashlib is called"""
from __future__ import annotations

import hashlib
from typing import Any

from .canonical import canonicalize


def sha256_hex(data: bytes) -> str:
  return hashlib.sha256(data).hexdigest()

def sha256_of_canonical(obj: Any) -> str:
  return sha256_hex(canonicalize(obj))