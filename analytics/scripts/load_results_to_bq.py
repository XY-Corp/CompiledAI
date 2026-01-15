import logging
import sys
from pathlib import Path
import pyarrow as pa
import json

# Add project root to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from analytics.utils.logger import get_logger

LOGGER_NAME = "compiled_ai_analytics"
LOGGER: logging.Logger = get_logger(LOGGER_NAME)

def get_results_path() -> Path:
    """Get the path to the results directory."""
    return Path(__file__).parent.parent.parent / "results"

def get_results_files() -> list[Path]:
    """Get the list of results files."""
    return list(get_results_path().glob("*.json"))

def load_result_file(result_file: Path) -> pa.Table:
    """Load a result file into a PyArrow table."""
    with open(result_file, "r") as f:
        result = json.load(f)
    return pa.Table.from_pydict(result)

def main() -> None:
    """Main function."""
    LOGGER.info("🚀 Starting Compiled AI Analytics...")
    results_files = get_results_files()
    LOGGER.info(f"🔍 Found {len(results_files)} results files.")
    for result_file in results_files:
        LOGGER.info(f"🔍 Loading {result_file} to BigQuery...")
        table: pa.Table = load_result_file(result_file)
        LOGGER.info(f"🔍 Loaded {table.num_rows} rows from {result_file}.")
    # LOGGER.info("✅ Results loaded to BigQuery.")
    # LOGGER.info("🎉 Compiled AI Analytics completed successfully!")


if __name__ == "__main__":
    main()