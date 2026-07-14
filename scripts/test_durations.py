"""Tests for the duration/time parsing helpers in scripts/.

Scope: pure functions only, no I/O. Pins the recently-fixed compound-duration
parsing behavior (verified by execution) so an upcoming refactor of
generate_config.main() / scenario_parser.expand_scenario can't silently regress
the public contract. Covers three sibling parsers that must stay in agreement:

  - ai_config/validator.py       parse_time_to_seconds
  - config_generation/timeline.py parse_duration
  - smoke_assertions.py / append_run_history.py parse_wall_time (byte-identical pair)

These do NOT exercise the Rust engine, Shadow, or any daemon.
"""
import inspect

import pytest

from scripts.ai_config.validator import parse_time_to_seconds, seconds_to_human
from scripts.config_generation.timeline import parse_duration, format_time_offset
from scripts.smoke_assertions import parse_wall_time as parse_wall_time_smoke
from scripts.append_run_history import parse_wall_time as parse_wall_time_hist


# ---------------------------------------------------------------------------
# Shared value table: both parse_time_to_seconds and parse_duration agree here.
# (compound forms like "1h30m" are the recently-added behavior being pinned.)
# ---------------------------------------------------------------------------
AGREED_CASES = [
    ("2.5h", 9000),
    ("1h30m", 5400),
    ("90m", 5400),
    ("45s", 45),
    ("5400", 5400),   # bare digits interpreted as seconds
    ("3h", 10800),
    ("30m", 1800),
    ("3h30s", 10830),  # compound with gap in units
    ("6h6m", 21960),
    ("0s", 0),
]


@pytest.mark.parametrize("text, expected", AGREED_CASES)
def test_parse_time_to_seconds_values(text, expected):
    assert parse_time_to_seconds(text) == expected


@pytest.mark.parametrize("text, expected", AGREED_CASES)
def test_parse_duration_values(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text, expected", AGREED_CASES)
def test_two_parsers_agree(text, expected):
    # The docstring in timeline.parse_duration promises it matches
    # validator.parse_time_to_seconds; pin that they return the same value.
    assert parse_time_to_seconds(text) == parse_duration(text) == expected


@pytest.mark.parametrize("bad", ["abc", "", "5x", "1h x", "h", "1.5", "nanm"])
def test_parse_time_to_seconds_raises_on_garbage(bad):
    with pytest.raises(ValueError):
        parse_time_to_seconds(bad)


@pytest.mark.parametrize("bad", ["abc", "", "5x", "1h x", "h", "1.5", "nanm"])
def test_parse_duration_raises_on_garbage(bad):
    with pytest.raises(ValueError):
        parse_duration(bad)


def test_parse_time_to_seconds_accepts_numeric_passthrough():
    # int/float inputs are returned truncated-to-int, not re-parsed as strings.
    assert parse_time_to_seconds(3600) == 3600
    assert parse_time_to_seconds(90.7) == 90


def test_parse_time_to_seconds_strips_whitespace():
    assert parse_time_to_seconds(" 2h ") == 7200
    assert parse_time_to_seconds("2h ") == 7200


# ---------------------------------------------------------------------------
# ALIGNED behavior: both parsers accept case-insensitive unit letters. Their
# docstrings promise matching semantics; validator.parse_time_to_seconds now
# lower-cases its input the same way timeline.parse_duration always has, so a
# scenario author isn't tripped by "2H". (Was a pinned divergence — the
# validator used to reject uppercase; that has been aligned.)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [("2H", 7200), ("30M", 1800), ("45S", 45)])
def test_parse_duration_is_case_insensitive(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text, expected", [("2H", 7200), ("30M", 1800), ("45S", 45)])
def test_parse_time_to_seconds_is_case_insensitive(text, expected):
    assert parse_time_to_seconds(text) == expected


@pytest.mark.parametrize("text, expected", [("2H", 7200), ("1H30M", 5400), ("45S", 45)])
def test_two_parsers_agree_on_uppercase_units(text, expected):
    # The alignment guarantee: both parsers return the same value for
    # uppercase (and mixed-case) unit letters, not just lowercase.
    assert parse_time_to_seconds(text) == parse_duration(text) == expected


# ---------------------------------------------------------------------------
# parse_wall_time: compound tokens OK, unparseable -> None (not 0).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("parse_wall_time", [parse_wall_time_smoke, parse_wall_time_hist])
class TestParseWallTime:
    @pytest.mark.parametrize("text, expected", [
        ("14m 48s", 888),
        ("1h 2m 3s", 3723),
        ("10h 42m", 38520),
        ("0s", 0),          # a real zero measurement stays 0, not None
        ("90s", 90),
    ])
    def test_parseable(self, parse_wall_time, text, expected):
        assert parse_wall_time(text) == expected

    @pytest.mark.parametrize("text", ["unknown", "", "n/a", "pending"])
    def test_unparseable_is_none(self, parse_wall_time, text):
        # None (not 0) so a missing wall time can't masquerade as "0s / instant".
        assert parse_wall_time(text) is None


def test_parse_wall_time_functions_are_byte_identical():
    """Pin the documented keep-in-sync contract between the two copies.

    smoke_assertions.py carries the comment "keep in sync with
    scripts/append_run_history.py:parse_wall_time (byte-identical)".
    inspect.getsource reads each function's text straight from its source
    file, so this fails the moment the two definitions drift apart.
    """
    src_smoke = inspect.getsource(parse_wall_time_smoke)
    src_hist = inspect.getsource(parse_wall_time_hist)
    assert src_smoke == src_hist


# ---------------------------------------------------------------------------
# Formatting helpers (inverse-ish of the parsers; cheap to pin).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seconds, expected", [
    (9045, "2h 30m 45s"),
    (3600, "1h"),
    (90, "1m 30s"),
    (0, "0s"),          # falls through to "0s" when no other parts
])
def test_seconds_to_human(seconds, expected):
    assert seconds_to_human(seconds) == expected


@pytest.mark.parametrize("seconds, expected", [
    (3600, "1h"),     # exact hours -> "Nh"
    (7200, "2h"),
    (300, "5m"),      # whole minutes -> "Nm"
    (90, "90s"),      # 90s is not a whole minute (90 % 60 != 0) -> "Ns"
    (45, "45s"),
    (3661, "3661s"),  # not a whole minute or hour -> seconds
])
def test_format_time_offset_config_form(seconds, expected):
    # for_config=True prefers the coarsest exact unit: whole hours -> "Nh",
    # whole minutes -> "Nm", else "Ns".
    assert format_time_offset(seconds) == expected
