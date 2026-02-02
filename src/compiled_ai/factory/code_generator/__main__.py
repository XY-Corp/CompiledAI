"""CLI entry point for the OpenCode workflow generator.

Usage:
    python -m compiled_ai.factory.code_generator "Your task description"

    # Or from within the factory directory:
    python -m code_generator "Your task description"
"""

from .generator import main

if __name__ == "__main__":
    main()
