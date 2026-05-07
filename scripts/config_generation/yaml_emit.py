"""YAML serialization for monerosim config dicts.

A hand-rolled emitter (rather than ``yaml.safe_dump``) so the output
preserves OrderedDict key order, lower-cases booleans the way our schema
expects, and quotes strings that the YAML parser would otherwise
mis-interpret as numbers / booleans / etc.
"""

from typing import Any, Dict


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


def format_yaml_value(value: Any) -> str:
    """Format a value for YAML output."""
    if isinstance(value, str):
        # Quote strings that might be parsed as other types
        if value.lower() in ('true', 'false', 'yes', 'no', 'on', 'off', 'null', 'none'):
            return f"'{value}'"
        # Quote strings with special characters
        if any(c in value for c in ':{}[]&*#?|-<>=!%@\\'):
            return f"'{value}'"
        # Quote strings that look like numbers
        try:
            float(value)
            return f"'{value}'"
        except ValueError:
            pass
        return value
    elif isinstance(value, bool):
        return str(value).lower()
    else:
        return str(value)
