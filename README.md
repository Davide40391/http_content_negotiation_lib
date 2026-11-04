# http_content_negotiation_lib

Parses `Accept`, `Accept-Encoding`, and `Accept-Language` headers and returns the best match from a caller-supplied list of available options.

```python
from http_content_negotiation_lib import negotiate, parse_accept_header

# Accept
best = negotiate("text/html;q=0.3, application/json;q=0.9",
                 ["text/html", "application/json"])
assert best == "application/json"

# Same function works for encodings and languages
assert negotiate("gzip;q=0.5, br;q=0.9", ["gzip", "br"]) == "br"
assert negotiate("en;q=0.9, fr;q=0.1", ["en", "fr"]) == "en"

# Inspect the parsed entries if you need more detail
entries = parse_accept_header("text/html;q=0.7;charset=utf-8")
# [{'token': 'text/html', 'q': 0.7, 'params': {'charset': 'utf-8'}}]
```

## Why this exists

Every HTTP server eventually needs to pick one representation from many. The decision is mechanical — sort by quality, filter by what you have, pick the most specific match — but the spec (RFC 7231 §5.3) has just enough corners that hand-rolling it in each project invites bugs. This library does that one job and nothing else.

The trade-off: `negotiate()` only **selects**. It does not transcode, compress, or translate. If the caller has `application/json` and the client asked for `text/xml`, the result is `None` and the caller decides what to do about it.

## Edge cases you will hit

- **`q=0` entries are kept in `parse_accept_header()` output** but are skipped during matching, so they act as explicit rejections rather than disappearing silently.
- **Only `*/*` and `type/*` wildcards are supported.** The `type/*+suffix` construct from RFC 7231 §3.1.1.1 is not honoured; it is rare in real traffic and supporting it cleanly requires a separate parser.
- **An empty header returns the first available option**, matching the spec's "absent header = any representation is acceptable" rule.
- **Parameter values are not de-quoted.** If a client sends `charset="utf-8"` the stored value is the literal string `"utf-8"` including quotes. Real Accept headers almost never quote values.

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

