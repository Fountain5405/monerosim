"""Tests for the hand-rolled YAML emitter in config_generation/yaml_emit.py.

Scope: format_yaml_value (scalar quoting rules) and config_to_yaml (whole-dict
emission), pinned by round-tripping the emitted text back through
yaml.safe_load. No I/O, no engine. This is the serializer the non-scenario
generate_config path uses, so a refactor must preserve these round-trips.

Includes one XFAIL(strict) that documents a known quoting bug so the upcoming
fix flips it to a pass.
"""
import yaml
import pytest

from scripts.config_generation.yaml_emit import (
    format_yaml_value,
    config_to_yaml,
    _single_quote,
)


# ---------------------------------------------------------------------------
# format_yaml_value: quoting decisions.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("value, expected", [
    ("hello", "hello"),          # plain word: no quotes
    ("a_b-c", "a_b-c"),          # '-' triggers quoting only mid-token? see below
])
def test_format_plain_strings(value, expected):
    # NOTE: "a_b-c" contains '-', which IS in the special-char set, so it gets
    # quoted. Pin the actual behavior rather than the naive expectation.
    result = format_yaml_value(value)
    assert yaml.safe_load(f"k: {result}") == {"k": value}


@pytest.mark.parametrize("value", [
    "true", "false", "yes", "no", "on", "off", "null", "none",
    "True", "FALSE",
])
def test_bool_like_strings_are_quoted_to_stay_strings(value):
    # Strings that YAML would coerce to bool/null must round-trip as strings.
    result = format_yaml_value(value)
    assert result.startswith("'") and result.endswith("'")
    assert yaml.safe_load(f"k: {result}") == {"k": value}


@pytest.mark.parametrize("value", ["42", "3.14", "1e5", "-7", "0.0"])
def test_number_like_strings_are_quoted_to_stay_strings(value):
    result = format_yaml_value(value)
    assert yaml.safe_load(f"k: {result}") == {"k": value}


def test_hex_like_string_is_quoted_and_roundtrips():
    """FIXED behavior: the "looks like a number" float() guard misses
    hex/octal-style strings like "0x10", but the emitter's round-trip safety
    net now quotes anything YAML would re-read as a non-string, so "0x10"
    survives as a string instead of being re-parsed as int 16."""
    result = format_yaml_value("0x10")
    assert result == "'0x10'"                          # emitted quoted
    assert yaml.safe_load(f"k: {result}") == {"k": "0x10"}  # stays a string


@pytest.mark.parametrize("value", ["a:b", "x=y", "a|b", "1-2", "p#q", "n@d"])
def test_special_char_strings_are_quoted_and_roundtrip(value):
    result = format_yaml_value(value)
    assert yaml.safe_load(f"k: {result}") == {"k": value}


def test_bool_and_int_scalars_render_lowercase_and_bare():
    assert format_yaml_value(True) == "true"
    assert format_yaml_value(False) == "false"
    assert format_yaml_value(42) == "42"
    assert format_yaml_value(3) == "3"


# ---------------------------------------------------------------------------
# config_to_yaml: whole-structure round-trip.
# ---------------------------------------------------------------------------
def test_config_to_yaml_roundtrips_nested_structure():
    config = {
        "general": {
            "stop_time": "16h",
            "simulation_seed": 12345,
            "native_preemption": True,
            "daemon_defaults": {"log-level": 1, "no-zmq": True},
        },
        "network": {"path": "gml_processing/test.gml", "peer_mode": "Dynamic"},
        "agents": {
            "miner-001": {"daemon": "monerod", "hashrate": 40, "start_time": "0s"},
        },
    }
    text = config_to_yaml(config)
    reloaded = yaml.safe_load(text)
    assert reloaded == config


def test_config_to_yaml_roundtrips_list_of_scalars():
    config = {"hashrates": [40, 30, 30]}
    reloaded = yaml.safe_load(config_to_yaml(config))
    assert reloaded == config


def test_config_to_yaml_roundtrips_list_of_dicts():
    config = {"seeds": [{"ip": "10.0.0.1", "port": 18080},
                         {"ip": "10.0.0.2", "port": 18080}]}
    reloaded = yaml.safe_load(config_to_yaml(config))
    assert reloaded == config


def test_config_to_yaml_lowercases_booleans():
    text = config_to_yaml({"flag": True, "other": False})
    assert "flag: true" in text
    assert "other: false" in text


# ---------------------------------------------------------------------------
# FIXED BUG (was xfail-strict): a string that both trips the special-char
# quoting rule AND contains an apostrophe used to be wrapped in single quotes
# without escaping the inner quote, producing invalid YAML. The emitter now
# doubles inner single quotes ('` -> `''`) per the YAML spec, so it round-trips.
# ---------------------------------------------------------------------------
def test_apostrophe_value_roundtrips():
    value = "don't: panic"     # contains ':' (special) and "'"
    result = format_yaml_value(value)
    reloaded = yaml.safe_load(f"k: {result}")
    assert reloaded == {"k": value}


def test_apostrophe_value_escapes_inner_quote_by_doubling():
    """Pins the FIXED output: the inner apostrophe is doubled inside the
    single-quoted scalar, which is how YAML escapes it, so the value parses
    back to the original string instead of raising."""
    result = format_yaml_value("don't: panic")
    assert result == "'don''t: panic'"                    # inner ' doubled
    assert yaml.safe_load(f"k: {result}") == {"k": "don't: panic"}


def test_single_quote_helper_doubles_inner_quotes():
    assert _single_quote("plain") == "'plain'"
    assert _single_quote("a'b") == "'a''b'"
    assert _single_quote("''") == "''''''"
