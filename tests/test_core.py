# http_content_negotiation_lib — tests for core negotiation.

import math
import unittest

from http_content_negotiation_lib.core import (
    negotiate,
    parse_accept_header,
)


class TestParseAcceptHeader(unittest.TestCase):
    def test_simple_single(self):
        out = parse_accept_header("text/html")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["token"], "text/html")
        self.assertAlmostEqual(out[0]["q"], 1.0)

    def test_quality_ordering(self):
        out = parse_accept_header("text/html;q=0.3, application/json;q=0.9")
        self.assertEqual(out[0]["token"], "application/json")
        self.assertEqual(out[1]["token"], "text/html")
        self.assertTrue(math.isclose(out[0]["q"], 0.9))

    def test_stable_order_on_ties(self):
        out = parse_accept_header("text/html, application/json, text/plain")
        tokens = [e["token"] for e in out]
        self.assertEqual(tokens, ["text/html", "application/json", "text/plain"])

    def test_q_zero_kept(self):
        out = parse_accept_header("text/html;q=0, application/json")
        tokens = [e["token"] for e in out]
        self.assertIn("text/html", tokens)

    def test_q_clamped(self):
        out = parse_accept_header("text/html;q=2.5")
        self.assertTrue(out[0]["q"] <= 1.0)

    def test_empty_header(self):
        self.assertEqual(parse_accept_header(""), [])

    def test_whitespace_tolerant(self):
        out = parse_accept_header("  text/html  ;  q=0.5  ,  application/json  ")
        self.assertEqual(out[0]["token"], "application/json")

    def test_q_removed_from_params(self):
        out = parse_accept_header("text/html;q=0.7;charset=utf-8")
        self.assertNotIn("q", out[0]["params"])
        self.assertEqual(out[0]["params"].get("charset"), "utf-8")


class TestNegotiate(unittest.TestCase):
    def test_exact_match(self):
        self.assertEqual(negotiate("text/html", ["text/html", "application/json"]), "text/html")

    def test_prefers_higher_q(self):
        result = negotiate("text/html;q=0.3, application/json;q=0.9", ["text/html", "application/json"])
        self.assertEqual(result, "application/json")

    def test_wildcard_slash_slash(self):
        result = negotiate("*/*", ["text/html", "application/json"])
        self.assertEqual(result, "text/html")

    def test_partial_wildcard(self):
        result = negotiate("text/*", ["application/json", "text/plain"])
        self.assertEqual(result, "text/plain")

    def test_q_zero_blocks(self):
        result = negotiate("text/html;q=0, application/json", ["text/html", "application/json"])
        self.assertEqual(result, "application/json")

    def test_no_match_returns_none(self):
        self.assertIsNone(negotiate("image/png", ["text/html", "application/json"]))

    def test_empty_header_returns_first_available(self):
        self.assertEqual(negotiate("", ["text/html", "application/json"]), "text/html")

    def test_empty_available_returns_none(self):
        self.assertIsNone(negotiate("text/html", []))

    def test_case_insensitive(self):
        self.assertEqual(negotiate("TEXT/HTML", ["text/html"]), "text/html")

    def test_accept_encoding(self):
        # Same algorithm works for encodings/languages.
        self.assertEqual(negotiate("gzip;q=0.5, br;q=0.9", ["gzip", "br"]), "br")

    def test_accept_language(self):
        self.assertEqual(negotiate("en;q=0.9, fr;q=0.1", ["en", "fr"]), "en")

    def test_specificity_exact_beats_wildcard(self):
        # text/html is explicitly listed AND matches text/*, exact should win.
        result = negotiate("text/html, text/*", ["text/html", "text/plain"])
        self.assertEqual(result, "text/html")


if __name__ == "__main__":
    unittest.main()
