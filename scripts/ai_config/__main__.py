#!/usr/bin/env python3
"""
CLI entry point for AI-powered monerosim config generator.

Usage:
    python -m scripts.ai_config "50 miners and 200 users for 8 hours"
    python -m scripts.ai_config --output my_config.yaml "upgrade scenario with 100 nodes"
    python -m scripts.ai_config --save-script gen.py "spy nodes monitoring network"

Environment variables:
    OPENAI_API_KEY      API key for LLM provider
    OPENAI_BASE_URL     Base URL for OpenAI-compatible API (default: https://api.openai.com/v1)
    AI_CONFIG_MODEL     Model name (default: gpt-4o-mini)
"""

import argparse
import sys
import os

from .generator import ConfigGenerator, LLMProvider


def main():
    parser = argparse.ArgumentParser(
        description="AI-powered monerosim configuration generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic usage with local LLM
    OPENAI_API_KEY=x OPENAI_BASE_URL=http://localhost:8082/v1 \\
        python -m scripts.ai_config "50 miners and 200 users"

    # Save both YAML and generator script
    python -m scripts.ai_config -o config.yaml -s generator.py "upgrade scenario"

    # Use specific model
    python -m scripts.ai_config --model gpt-4o "complex scenario..."

Environment variables:
    OPENAI_API_KEY      API key (use 'x' for local servers that don't need auth)
    OPENAI_BASE_URL     API base URL (e.g., http://localhost:8082/v1)
    AI_CONFIG_MODEL     Default model name
        """
    )

    parser.add_argument(
        "request",
        nargs="?",
        help="Natural language description of the simulation scenario"
    )

    parser.add_argument(
        "--output", "-o",
        default="generated_config.yaml",
        help="Output YAML file path (default: generated_config.yaml)"
    )

    parser.add_argument(
        "--save-script", "-s",
        help="Save the generator Python script to this path"
    )

    parser.add_argument(
        "--model", "-m",
        help="Model name (overrides AI_CONFIG_MODEL env var)"
    )

    parser.add_argument(
        "--base-url", "-u",
        help="API base URL (overrides OPENAI_BASE_URL env var)"
    )

    parser.add_argument(
        "--max-attempts", "-a",
        type=int,
        default=3,
        help="Maximum correction attempts (default: 3)"
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress messages"
    )

    parser.add_argument(
        "--validate", "-v",
        help="Validate an existing YAML config file (no generation)"
    )

    args = parser.parse_args()

    # Validation-only mode
    if args.validate:
        from .validator import ConfigValidator
        validator = ConfigValidator()
        try:
            report = validator.validate_file(args.validate)
            print(report.to_summary())
            return 0 if report.is_valid else 1
        except Exception as e:
            print(f"Error validating {args.validate}: {e}", file=sys.stderr)
            return 1

    # Generation mode
    if not args.request:
        parser.print_help()
        return 1

    # Check for API key
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        print("For local LLM servers, use: OPENAI_API_KEY=x", file=sys.stderr)
        return 1

    # Create provider
    provider = LLMProvider(
        model=args.model,
        base_url=args.base_url,
    )

    # Create generator
    generator = ConfigGenerator(
        provider=provider,
        max_attempts=args.max_attempts,
        verbose=not args.quiet
    )

    # Generate
    result = generator.generate(
        user_request=args.request,
        output_file=args.output,
        save_script=args.save_script
    )

    # Report result
    if result.success:
        print(f"\nSuccess! Config saved to: {args.output}")
        if args.save_script:
            print(f"Generator script saved to: {args.save_script}")
        if result.validation_report:
            print(f"\nSummary: {result.validation_report.miner_count} miners, "
                  f"{result.validation_report.user_count} users, "
                  f"{result.validation_report.spy_count} spy nodes")
        return 0
    else:
        print(f"\nGeneration failed after {result.attempts} attempts.", file=sys.stderr)
        if result.errors:
            print("\nErrors:", file=sys.stderr)
            for err in result.errors[-3:]:  # Show last 3 errors
                print(f"  - {err[:200]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
