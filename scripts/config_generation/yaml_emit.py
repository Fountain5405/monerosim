"""YAML serialization for monerosim config dicts.

A hand-rolled emitter (rather than ``yaml.safe_dump``) so the output
preserves OrderedDict key order, lower-cases booleans the way our schema
expects, and quotes strings that the YAML parser would otherwise
mis-interpret as numbers / booleans / etc.
"""

from typing import Any, Dict

import yaml


def config_to_yaml(config: Dict[str, Any], indent: int = 0) -> str:
    """Convert config dict to YAML string manually for clean output."""
    lines = []
    prefix = "  " * indent

    for key, value in config.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(config_to_yaml(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    # First key-value on same line as dash
                    first = True
                    for k, v in item.items():
                        if first:
                            if isinstance(v, dict):
                                lines.append(f"{prefix}  - {k}:")
                                lines.append(config_to_yaml(v, indent + 3))
                            elif isinstance(v, bool):
                                lines.append(f"{prefix}  - {k}: {str(v).lower()}")
                            else:
                                lines.append(f"{prefix}  - {k}: {format_yaml_value(v)}")
                            first = False
                        else:
                            if isinstance(v, dict):
                                lines.append(f"{prefix}    {k}:")
                                lines.append(config_to_yaml(v, indent + 3))
                            elif isinstance(v, bool):
                                lines.append(f"{prefix}    {k}: {str(v).lower()}")
                            else:
                                lines.append(f"{prefix}    {k}: {format_yaml_value(v)}")
                else:
                    lines.append(f"{prefix}  - {format_yaml_value(item)}")
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {str(value).lower()}")
        else:
            lines.append(f"{prefix}{key}: {format_yaml_value(value)}")

    return "\n".join(lines)


def _single_quote(value: str) -> str:
    """Wrap a string in single quotes, YAML-escaping inner single quotes.

    Per the YAML spec, a literal single quote inside a single-quoted scalar is
    written by doubling it (``'` -> `''``). Without this, a value containing an
    apostrophe closes the quote early and produces invalid YAML.
    """
    return "'" + value.replace("'", "''") + "'"


def _roundtrips_unquoted(value: str) -> bool:
    """True if the bare (unquoted) string re-reads as the same string.

    Safety net that catches scalars the explicit rules below miss — e.g.
    hex/octal-style strings like ``0x10`` (float() can't parse them, so the
    "looks like a number" guard skips them, yet YAML re-reads them as ints).
    Only ever used to ADD quoting, never to remove it.
    """
    if value == "":
        return False
    try:
        parsed = yaml.safe_load(value)
    except yaml.YAMLError:
        return False
    return isinstance(parsed, str) and parsed == value


def format_yaml_value(value: Any) -> str:
    """Format a value for YAML output."""
    if isinstance(value, str):
        # Quote strings that might be parsed as other types
        if value.lower() in ('true', 'false', 'yes', 'no', 'on', 'off', 'null', 'none'):
            return _single_quote(value)
        # Quote strings with special characters
        if any(c in value for c in ':{}[]&*#?|-<>=!%@\\'):
            return _single_quote(value)
        # Quote strings that look like numbers
        try:
            float(value)
            return _single_quote(value)
        except ValueError:
            pass
        # Final safety net: quote anything else YAML would not read back as the
        # same string (hex/octal-style ints, empty string, etc.).
        if not _roundtrips_unquoted(value):
            return _single_quote(value)
        return value
    elif isinstance(value, bool):
        return str(value).lower()
    else:
        return str(value)
