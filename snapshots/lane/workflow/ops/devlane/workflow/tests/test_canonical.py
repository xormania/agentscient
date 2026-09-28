"""canonical.py — the definition of the wire form (PLAN §2)."""

import datetime as dt
import json
import unittest

import support  # noqa: F401  (puts the workflow dir on sys.path)
import canonical


class CanonicalBytes(unittest.TestCase):
    def test_is_byte_identical_to_the_definition(self):
        # PLAN §2 defines canonical form as exactly this call.  The assertion
        # is the definition, not a restatement of the implementation.
        cases = [
            {},
            {"b": 1, "a": 2},
            {"z": [3, 2, 1], "a": {"n": None, "t": True}},
            {"nested": {"c": 1, "b": {"z": 0, "a": []}}},
            [1, "two", None, False],
            {"unicode": "café — 中文"},
            {"empty_str": "", "zero": 0, "neg": -1},
            "bare string",
            42,
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(
                    canonical.dumps(case),
                    json.dumps(case, sort_keys=True, separators=(",", ":")),
                )

    def test_dumpb_is_utf8_of_dumps(self):
        obj = {"k": "café"}
        self.assertEqual(canonical.dumpb(obj), canonical.dumps(obj).encode("utf-8"))

    def test_non_ascii_is_escaped_so_the_bytes_are_ascii(self):
        # ensure_ascii is on by definition; a second spelling would be a
        # second hash.
        self.assertEqual(canonical.dumpb({"k": "é"}), b'{"k":"\\u00e9"}')

    def test_refuses_values_that_are_not_json(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                canonical.dumps({"k": bad})

    def test_loads_refuses_non_json_constants(self):
        with self.assertRaises(ValueError):
            canonical.loads(b'{"k":NaN}')


class Digests(unittest.TestCase):
    def test_known_digest_of_the_empty_object(self):
        # sha256 of the two bytes {}
        self.assertEqual(
            canonical.digest({}),
            "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        )

    def test_digest_ignores_key_order_in_the_input_value(self):
        self.assertEqual(
            canonical.digest({"a": 1, "b": 2}), canonical.digest({"b": 2, "a": 1})
        )

    def test_zero_digest_is_64_zeroes(self):
        self.assertEqual(canonical.ZERO_DIGEST, "0" * 64)
        self.assertEqual(len(canonical.ZERO_DIGEST), 64)


class IsCanonical(unittest.TestCase):
    def test_accepts_canonical_bytes(self):
        self.assertTrue(canonical.is_canonical(canonical.dumpb({"b": 1, "a": 2})))

    def test_rejects_a_re_encoding_that_means_the_same_thing(self):
        # The whole point: a rewritten row is a rewritten record even when it
        # decodes to the same value.
        for variant in (
            b'{"a": 2, "b": 1}',   # whitespace
            b'{"b":1,"a":2}',      # key order
            b'{"a":2,"b":1}\n',    # trailing newline
            b'{"a":2e0,"b":1}',    # number spelling (canonical is 2.0)
            b'{"a":2.00,"b":1}',   # number spelling (trailing zero)
            b'{"a":2,"a":2,"b":1}',  # duplicate key collapses on re-encode
        ):
            with self.subTest(variant=variant):
                self.assertFalse(canonical.is_canonical(variant))

    def test_rejects_undecodable_bytes(self):
        self.assertFalse(canonical.is_canonical(b'{"a":'))
        self.assertFalse(canonical.is_canonical(b"\xff\xfe"))


class Times(unittest.TestCase):
    def test_wire_form_has_exactly_six_fractional_digits_and_a_z(self):
        raw = canonical.format_time(
            dt.datetime(2026, 8, 20, 15, 4, 5, 123456, dt.timezone.utc)
        )
        self.assertEqual(raw, "2026-08-20T15:04:05.123456Z")

    def test_zero_microseconds_still_spell_six_digits(self):
        raw = canonical.format_time(dt.datetime(2026, 1, 2, 3, 4, 5, 0, dt.timezone.utc))
        self.assertEqual(raw, "2026-01-02T03:04:05.000000Z")

    def test_non_utc_is_converted_not_spelled_with_an_offset(self):
        tz = dt.timezone(dt.timedelta(hours=2))
        raw = canonical.format_time(dt.datetime(2026, 8, 20, 17, 4, 5, 0, tz))
        self.assertEqual(raw, "2026-08-20T15:04:05.000000Z")

    def test_parse_refuses_an_equivalent_offset_spelling(self):
        with self.assertRaises(ValueError):
            canonical.parse_time("2026-08-20T15:04:05.123456+00:00")

    def test_parse_refuses_a_missing_fraction(self):
        with self.assertRaises(ValueError):
            canonical.parse_time("2026-08-20T15:04:05Z")

    def test_now_round_trips(self):
        raw = canonical.now()
        self.assertEqual(canonical.format_time(canonical.parse_time(raw)), raw)


if __name__ == "__main__":
    unittest.main()
