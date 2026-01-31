"""CLI entry point for the Crush workflow generator.

Usage:
    python -m compiled_ai.factory.crush_generator "Your task description"
    
    # Or from within the factory directory:
    python -m crush_generator "Your task description"
"""

from .generator import main

if __name__ == "__main__":
    main()
