"""60-bit SimHash for near-duplicate detection.

Per spec §5.2.5:
- 60-bit fingerprint (fits in PostgreSQL bigint, leaving sign bit free).
- Token hash: MD5 (first 8 bytes), masked to 60 bits.
- Similarity threshold: Hamming distance ≤ 9 ≈ 85% similarity (1 - 9/60).

Used by T9 clustering and dedupe.
"""
from __future__ import annotations

import hashlib

from nev_pipeline.tokenizer import tokenize

BITS = 60
_MASK = (1 << BITS) - 1
DEFAULT_THRESHOLD = 9  # ≈ 1 - 9/60 = 85% similarity per spec


def _token_hash(token: str) -> int:
    """Hash a token to a 60-bit integer (MD5 → first 8 bytes → mask)."""
    # MD5 is used here only as a fast, well-distributed non-cryptographic hash
    # for the SimHash fingerprint. Not a security primitive.
    digest = hashlib.md5(token.encode("utf-8"), usedforsecurity=False).digest()
    return int.from_bytes(digest[:8], "big") & _MASK


def simhash(text: str) -> int:
    """Compute 60-bit SimHash fingerprint of `text`.

    Empty / token-less input → 0.
    """
    tokens = tokenize(text)
    if not tokens:
        return 0
    weights = [0] * BITS
    for tok in tokens:
        h = _token_hash(tok)
        for i in range(BITS):
            weights[i] += 1 if (h >> i) & 1 else -1
    result = 0
    for i in range(BITS):
        if weights[i] > 0:
            result |= 1 << i
    return result


def hamming_distance(a: int, b: int) -> int:
    """Bit-count of XOR — # differing bits."""
    return bin(a ^ b).count("1")


def are_similar(a: int, b: int, threshold: int = DEFAULT_THRESHOLD) -> bool:
    """True iff Hamming distance ≤ threshold (default 9 ≈ 85% similarity)."""
    return hamming_distance(a, b) <= threshold
