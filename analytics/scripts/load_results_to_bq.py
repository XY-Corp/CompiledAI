import logging
import sys
from pathlib import Path
from typing import List
from google.cloud import bigquery
import pyarrow as pa
import json
import uuid
from pydantic import BaseModel

# Add project root to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from analytics.table_defs import ConfigRow, SummaryRow, TaskRow, MetricRow, MetricResultRow
from analytics.utils.logger import get_logger
from analytics.utils.bigquery_helper import BigQueryHelper

BIGQUERY_PROJECT_ID = "xy-multi-agents-research"
BIGQUERY_DATASET_ID = "compiled_ai_analytics"
LOGGER_NAME = "compiled_ai_analytics"
LOGGER: logging.Logger = get_logger(LOGGER_NAME)

def build_uuid_from_string(string: str) -> uuid.UUID:
    """Build a UUID from a string."""
    return uuid.uuid5(uuid.NAMESPACE_URL, string)

def get_results_path() -> Path:
    """Get the path to the results directory."""
    return Path(__file__).parent.parent.parent / "results"

def get_results_files() -> list[Path]:
    """Get the list of results files."""
    return list(get_results_path().glob("*.json"))

def load_result_file(result_file: Path) -> dict:
    """Load a result file into a BigQuery table."""
    with open(result_file, "r") as f:
        result: dict = json.load(f)
    return result

def convert_uuids_to_strings(obj):
    """Recursively convert UUID objects to strings in a dict."""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: convert_uuids_to_strings(value) for key, value in obj.items()}
    else:
        return obj

def build_arrow_table(rows: List[BaseModel]) -> pa.Table:
    """Build the arrow table from a list of Pydantic BaseModel instances.
    
    Args:
        rows: List of Pydantic BaseModel instances from table_defs.py
    """
    if not rows:
        return pa.Table.from_pylist([])
    
    # Convert Pydantic models to dicts and UUIDs to strings
    rows_dict = [convert_uuids_to_strings(row.model_dump()) for row in rows]
    
    # Handle mixed type columns (e.g., value field in MetricResultRow can be str | float)
    # Convert mixed numeric/string columns to strings to avoid PyArrow type inference issues
    if rows_dict and 'value' in rows_dict[0]:
        for row in rows_dict:
            if 'value' in row and isinstance(row['value'], (int, float)):
                row['value'] = str(row['value'])
    
    # Use from_pylist which handles mixed types better than from_pydict
    return pa.Table.from_pylist(rows_dict)

def build_and_load_tables(files: List[dict]):
    """Build the tables from the results files."""
    tables: List[pa.Table] = []
    config_rows: dict[uuid.UUID, ConfigRow] = {}
    summary_rows: List[SummaryRow] = []
    task_rows: List[TaskRow] = []
    metric_rows: List[MetricRow] = []
    metric_result_rows: List[MetricResultRow] = []
    for file in files:
        config_data = file["config"]
        key: str = f"{config_data['dataset']}_{config_data['baseline']}"
        config_id: uuid.UUID = build_uuid_from_string(key)
        if config_id not in config_rows:
            config_rows[config_id] = ConfigRow(id=config_id, **config_data)

        # --- Summary ---
        summary_data = file["summary"]
        summary_id: uuid.UUID = build_uuid_from_string(f"{config_id}_summary")
        summary_rows.append(SummaryRow(id=summary_id, config_id=config_id, **summary_data))
        
        # --- Tasks ---
        task_data = file["tasks"]
        for task in task_data:
            task_id: uuid.UUID = build_uuid_from_string(f"{config_id}_task_{task['task_id']}")
            task_rows.append(TaskRow(id=task_id, summary_id=summary_id, **task))

        # Extract metrics data
        metric_data = file["metrics"]

        # --- Metrics ---
        metric_metadata = metric_data["metadata"]
        metric_metadata_id: uuid.UUID = build_uuid_from_string(f"{config_id}_metric_metadata")
        metric_rows.append(MetricRow(id=metric_metadata_id, config_id=config_id, **metric_metadata))
        
        # --- Metric Results ---
        metric_results = metric_data["results"]
        for metric_result in metric_results:
            metric_result_id: uuid.UUID = build_uuid_from_string(f"{metric_metadata_id}_metric_result_{metric_result['name']}")
            metric_result_rows.append(MetricResultRow(id=metric_result_id, metric_id=metric_metadata_id, **metric_result))

    config_table = build_arrow_table(list(config_rows.values()))
    summary_table = build_arrow_table(summary_rows)
    task_table = build_arrow_table(task_rows)
    metric_table = build_arrow_table(metric_rows)
    metric_result_table = build_arrow_table(metric_result_rows)

    bigquery_helper = BigQueryHelper(BIGQUERY_PROJECT_ID, BIGQUERY_DATASET_ID, LOGGER)
    bigquery_helper.ensure_dataset()
    bigquery_helper.upload("config", config_table, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    bigquery_helper.upload("summary", summary_table, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    bigquery_helper.upload("task", task_table, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    bigquery_helper.upload("metric", metric_table, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
    bigquery_helper.upload("metric_result", metric_result_table, write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)

def main() -> None:
    """Main function."""
    LOGGER.info("🚀 Starting Compiled AI Analytics...")
    results_files = get_results_files()
    LOGGER.info(f"🔍 Found {len(results_files)} results files.")
    results: List[dict] = []
    for result_file in results_files:
        LOGGER.info(f"🔍 Processing {result_file}...")
        result = load_result_file(result_file)
        results.append(result)
    build_and_load_tables(results)
    LOGGER.info("🎉 Attempting to connect to BigQuery...")

if __name__ == "__main__":
    main()