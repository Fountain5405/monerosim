"""
AI-powered monerosim configuration generator.

This package provides an agentic approach to generating monerosim YAML configs:
1. User describes scenario in natural language
2. LLM generates Python script that creates the YAML
3. Validator analyzes the generated YAML
4. Feedback loop corrects any discrepancies

Usage:
    python -m scripts.ai_config "500 users, 50 miners, upgrade at 7h"
"""

from .validator import ConfigValidator, ValidationReport
from .generator import ConfigGenerator

__all__ = ['ConfigValidator', 'ValidationReport', 'ConfigGenerator']
