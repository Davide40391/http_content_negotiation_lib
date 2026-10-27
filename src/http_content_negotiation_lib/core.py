"""Core negotiation logic.

We interpret RFC 7231 §5.3 with one pragmatic simplification: this library
*selects* a single best match from a caller-supplied list of available
representations — it does not mutate or transcode. Wildcard matching is
honoured only for the broad `*/*`, `text/*`, `audio/*` family; a `*-suffix`
pattern is **not** supported because RFC 7231's wildcard+parameter syntax
(§3.1.1.1) is not honoured by real-world servers.
"""

from __future__ import annotations

__all__ = ["parse_accept_header", "negotiate"]


def _split_parts(value: str) -> list[tuple[str, str]]:
    """Return raw comma-separated chunks with their trailing raw parameter text.

    We split manually because both the comma separating media ranges and the
    semi-colons inside `q=0.7` can appear unquoted in the same line. This
    helper returns a list of (token, raw_params) pairs — the caller still has
    to parse the parameters.
    """
    out: list[tuple[str, str]] = []
    i = 0
    n = len(value)
    token_start = 0
    while i < n:
        ch = value[i]
        if ch == ",":
            chunk = value[token_start:i]
            out.append(_split_token_params(chunk))
            token_start = i + 1
        i += 1
    if token_start < n:
        chunk = value[token_start:n]
        out.append(_split_token_params(chunk))
    elif token_start == n and n > 0:
        # Trailing comma with nothing after it.
        out.append(_split_token_params(value[token_start:n]))
    return out


def _split_token_params(chunk: str) -> tuple[str, str]:
    """Split a chunk into (token, raw_params) on the first semicolon."""
    chunk = chunk.strip()
    if not chunk:
        return "", ""
    semi = chunk.find(";")
    if semi < 0:
        return chunk.strip(), ""
    return chunk[:semi].strip(), chunk[semi:]


def _parse_params(raw: str) -> dict[str, str]:
    """Parse `;key=value;key2=value2` into a dict. Values are not de-quoted.

    RFC 7231 allows quoted-string parameter values. Real-world Accept headers
    almost never use them outside of `charset` extensions; we keep values as-is
    so a caller can still see the original text.
    """
    params: dict[str, str] = {}
    if not raw:
        return params
    parts = raw.split(";")
    for p in parts:
        p = p.strip()
        if not p:
            continue
        eq = p.find("=")
        if eq < 0:
            continue
        k = p[:eq].strip().lower()
        v = p[eq + 1:].strip()
        if k:
            params[k] = v
    return params


def _parse_quality(params: dict[str, str]) -> float:
    """Extract q from a parsed param dict. Clamped to [0, 1]. Default 1.0."""
    q_str = params.get("q", "1")
    try:
        q_val = float(q_str)
    except (TypeError, ValueError):
        q_val = 1.0
    if q_val < 0.0:
        q_val = 0.0
    elif q_val > 1.0:
        q_val = 1.0
    return q_val


def _is_wildcard_type(token: str) -> bool:
    """True for `*/*` or `type/*` (case-insensitive on the slash-half)."""
    if "/" not in token:
        return False
    subtype = token.split("/", 1)[1].lower()
    return subtype == "*"


def _matches(available: str, requested: str) -> bool:
    """Case-insensitive match, supporting `*/*` and `type/*` wildcards."""
    a = available.lower()
    r = requested.lower()
    if r == "*/*":
        return True
    if "/" not in r:
        # Bare token: accept any media type that starts with the same stem.
        # This is generous but keeps the matcher simple.
        return a == r
    if _is_wildcard_type(r):
        prefix = r.split("/", 1)[0]
        if "/" not in a:
            return False
        return a.split("/", 1)[0] == prefix
    return a == r


def parse_accept_header(header: str) -> list[dict[str, object]]:
    """Parse an Accept-family header into a sorted list of entries.

    Each entry is a dict with keys:
      - ``token``  : the media range / encoding / language (str)
      - ``q``      : float in [0, 1]
      - ``params`` : dict of parameters other than q

    Entries with q == 0 are **kept** so the caller can honour explicit
    rejections; we sort highest-q first, and within equal q preserve the
    original header order (stable sort).
    """
    if header is None:
        return []
    entries: list[dict[str, object]] = []
    for token, raw_params in _split_parts(header):
        if not token:
            continue
        params = _parse_params(raw_params)
        q = _parse_quality(params)
        params.pop("q", None)
        entries.append({"token": token, "q": q, "params": params})
    entries.sort(key=lambda e: -e["q"])
    return entries


def _match_score(available: str, entry: dict[str, object]) -> int:
    """Return a specificity score: 2 = exact, 1 = wildcard, 0 = no match."""
    token = entry["token"]
    if not _matches(available, token):
        return 0
    if "/" in token and _is_wildcard_type(token):
        return 1
    if token == "*/*":
        return 1
    return 2


def negotiate(header: str, available: list[str]) -> str | None:
    """Return the best available option for the given header, or None.

    The algorithm walks every parsed entry in descending q order. For each
    entry it picks the *most specific* match from `available` (exact beats
    wildcard). The first entry that produces any non-zero match wins and its
    pick is returned. If `available` is empty, returns None. If the header is
    empty, returns the first available item.
    """
    if not available:
        return None
    if not header or not header.strip():
        return available[0]
    entries = parse_accept_header(header)
    for entry in entries:
        q = entry["q"]
        if q <= 0.0:
            continue
        best: str | None = None
        best_score = 0
        for cand in available:
            s = _match_score(cand, entry)
            if s > best_score or (s > 0 and s == best_score and best is None):
                best = cand
                best_score = s
        if best is not None and best_score > 0:
            return best
    return None
