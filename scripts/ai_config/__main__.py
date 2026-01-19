#!/usr/bin/env python3
"""
CLI entry point for AI-powered monerosim config generator.

Usage:
    # Interactive mode (recommended)
    python -m scripts.ai_config

    # Direct mode with description
    python -m scripts.ai_config "50 miners and 200 users for 8 hours"

    # With options
    python -m scripts.ai_config --output my_config.yaml "upgrade scenario with 100 nodes"
    python -m scripts.ai_config --save-scenario scenario.yaml "spy nodes monitoring network"

Configuration:
    On first run, you'll be prompted for LLM settings (API URL, key, model).
    Settings are saved to ~/.monerosim/ai_config.yaml for future use.

    Or set environment variables:
        OPENAI_API_KEY      API key for LLM provider
        OPENAI_BASE_URL     Base URL for OpenAI-compatible API
        AI_CONFIG_MODEL     Model name
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
    # Interactive mode (recommended for first-time users)
    python -m scripts.ai_config

    # Direct generation
    python -m scripts.ai_config "5 miners and 50 users"

    # Save both expanded YAML and compact scenario
    python -m scripts.ai_config -o config.yaml -s scenario.yaml "upgrade scenario"

    # Validate an existing config
    python -m scripts.ai_config --validate existing_config.yaml
        """
    )

    parser.add_argument(
        "request",
        nargs="?",
        help="Natural language description of the simulation scenario (omit for interactive mode)"
    )

    parser.add_argument(
        "--output", "-o",
        default="generated_config.yaml",
        help="Output YAML file path (default: generated_config.yaml)"
    )

    parser.add_argument(
        "--save-scenario", "-s",
        help="Save the compact scenario.yaml (before expansion) to this path"
    )

    parser.add_argument(
        "--model", "-m",
        help="Model name (overrides config/env)"
    )

    parser.add_argument(
        "--base-url", "-u",
        help="API base URL (overrides config/env)"
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

    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable interactive mode even when no request is provided"
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

    # Determine if we should use interactive mode
    use_interactive = (
        not args.request and
        not args.no_interactive and
        sys.stdin.isatty() and
        sys.stdout.isatty()
    )

    if use_interactive:
        return run_interactive_mode(args)
    else:
        return run_direct_mode(args)


def get_llm_config(args):
    """Get LLM configuration from args, env vars, or config file."""
    # Priority: CLI args > env vars > config file

    # Check CLI args and env vars first
    api_key = os.environ.get('OPENAI_API_KEY')
    base_url = args.base_url or os.environ.get('OPENAI_BASE_URL')
    model = args.model or os.environ.get('AI_CONFIG_MODEL')

    if api_key and base_url:
        return {
            'api_key': api_key,
            'base_url': base_url,
            'model': model or 'qwen2.5:7b'
        }

    # Try config file
    from pathlib import Path
    config_path = Path.home() / '.monerosim' / 'ai_config.yaml'

    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
                if config:
                    # CLI args override config file
                    return {
                        'api_key': config.get('api_key', ''),
                        'base_url': args.base_url or config.get('base_url', ''),
                        'model': args.model or config.get('model', 'qwen2.5:7b')
                    }
        except Exception:
            pass

    return None


def run_interactive_mode(args):
    """Run in interactive mode with prompts and menus."""
    from .interactive import run_interactive, check_llm_config, Colors

    # Check/prompt for LLM config
    config = get_llm_config(args)

    if not config or not config.get('base_url'):
        config = check_llm_config()
        if not config:
            print("LLM configuration required. Exiting.", file=sys.stderr)
            return 1

    # Set env vars for the provider
    os.environ['OPENAI_API_KEY'] = config['api_key']
    os.environ['OPENAI_BASE_URL'] = config['base_url']
    if config.get('model'):
        os.environ['AI_CONFIG_MODEL'] = config['model']

    # Create provider and generator
    provider = LLMProvider(
        model=config.get('model'),
        base_url=config.get('base_url'),
    )

    generator = ConfigGenerator(
        provider=provider,
        max_attempts=args.max_attempts,
        verbose=False  # Interactive mode handles its own output
    )

    # Run interactive loop
    try:
        success = run_interactive(
            generator=generator,
            output_file=args.output,
            save_scenario=args.save_scenario
        )
        return 0 if success else 1
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted.{Colors.RESET}")
        return 130


def run_direct_mode(args):
    """Run in direct mode (non-interactive)."""
    if not args.request:
        print("Error: Please provide a scenario description or run without arguments for interactive mode.",
              file=sys.stderr)
        return 1

    # Get config
    config = get_llm_config(args)

    if not config or not config.get('api_key'):
        print("Error: LLM configuration not found.", file=sys.stderr)
        print("Either:", file=sys.stderr)
        print("  1. Run interactively: python -m scripts.ai_config", file=sys.stderr)
        print("  2. Set environment variables: OPENAI_API_KEY, OPENAI_BASE_URL", file=sys.stderr)
        print("  3. Create config file: ~/.monerosim/ai_config.yaml", file=sys.stderr)
        return 1

    # Create provider
    provider = LLMProvider(
        model=config.get('model'),
        base_url=config.get('base_url'),
        api_key=config.get('api_key'),
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
        save_scenario=args.save_scenario
    )

    # Report result
    if result.success:
        print(f"\nSuccess! Config saved to: {args.output}")
        if args.save_scenario:
            print(f"Scenario saved to: {args.save_scenario}")
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
