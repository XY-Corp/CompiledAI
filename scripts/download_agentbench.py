#!/usr/bin/env python3
"""Download AgentBench dataset from GitHub.

AgentBench is a multi-turn agent benchmark with 8 environments:
- OS: Operating system tasks
- DB: Database operations
- KG: Knowledge graph queries
- DCG: Digital card game
- LTP: Lateral thinking puzzles
- HH: House-holding (ALFWorld)
- WS: Web shopping
- WB: Web browsing (Mind2Web)

Usage:
    python scripts/download_agentbench.py
    python scripts/download_agentbench.py --output datasets/agentbench
"""

import argparse
import subprocess
from pathlib import Path


def download_agentbench(output_dir: Path) -> None:
    """Clone AgentBench repository from GitHub.

    Args:
        output_dir: Directory to clone the repository to
    """
    output_dir_parent = output_dir.parent
    output_dir_parent.mkdir(parents=True, exist_ok=True)

    if output_dir.exists():
        print(f"AgentBench already exists at {output_dir}")
        print("To re-download, remove the directory first:")
        print(f"  rm -rf {output_dir}")
        return

    print("Downloading AgentBench from GitHub...")
    print("Repository: https://github.com/THUDM/AgentBench")
    print(f"Destination: {output_dir}")
    print()

    try:
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "https://github.com/THUDM/AgentBench.git",
                str(output_dir),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository: {e}")
        return
    except FileNotFoundError:
        print("Error: git is not installed or not in PATH")
        return

    print()
    print("Download complete!")
    print()
    print("Dataset structure:")
    print(f"  {output_dir}/")
    print("  ├── data/")
    print("  │   ├── os/          (Operating System tasks)")
    print("  │   ├── db/          (Database tasks)")
    print("  │   ├── kg/          (Knowledge Graph tasks)")
    print("  │   ├── alfworld/    (House-Holding tasks)")
    print("  │   ├── webshop/     (Web Shopping tasks)")
    print("  │   └── mind2web/    (Web Browsing tasks)")
    print("  └── configs/")
    print("      └── tasks/       (YAML configurations)")
    print()
    print("Dataset sizes:")
    print("  - Dev split: 269 tasks (~4,000 LLM calls)")
    print("  - Test split: 1,014 tasks (~13,000 LLM calls)")
    print()
    print("Note: Some environments require Docker:")
    print("  docker pull longinyu/agentbench-ltp")
    print("  docker pull longinyu/agentbench-alfworld")
    print("  docker pull longinyu/agentbench-webshop")
    print("  docker pull longinyu/agentbench-mind2web")
    print("  docker pull longinyu/agentbench-card_game")
    print("  docker pull mysql:8  # for DB environment")
    print()
    print("Usage example:")
    print("  from compiled_ai.runner import DatasetLoader")
    print("  loader = DatasetLoader('datasets')")
    print(f"  agentbench = loader.load_external('agentbench', '{output_dir}')")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download AgentBench dataset from GitHub"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="datasets/agentbench",
        help="Output directory (default: datasets/agentbench)",
    )
    args = parser.parse_args()

    download_agentbench(Path(args.output))


if __name__ == "__main__":
    main()
