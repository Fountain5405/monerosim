"""Internals for ``scripts/generate_config.py``.

This package holds helpers extracted from the original single-file
``scripts/generate_config.py``. The public entry point and dataclasses
remain at ``scripts/generate_config``; this package is the implementation
detail that file pulls from.

Submodules:

  - timeline.py     : duration parsing/formatting, stagger/bootstrap/batch
                      and upgrade timing math, scale-guardrail prints (pure).
  - agent_emit.py   : per-agent dict construction (miners, users, relays;
                      regular and phased variants for upgrade scenarios).
  - general_emit.py : ``general:`` section + machine-parseable metadata
                      section construction.
  - yaml_emit.py    : config-dict to YAML string serialization.
"""
