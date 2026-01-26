"""ELT-Bench converter - converts ELT-Bench format to generic DatasetInstance.

ELT-Bench: End-to-end benchmark for evaluating AI agents on ELT pipelines.
Agent receives data source configs + target schema, must generate Terraform + SQL.

Strategy:
- `input`: Combined config.yaml + data_model.yaml + schemas (the task definition)
- `output_format`: Expected output structure (Terraform + SQL files)
- `expected_output`: Ground truth SQL for evaluation
- `context`: Source combination signature for workflow reuse (83% reuse potential!)
"""

import json
import yaml
from pathlib import Path
from typing import Any

from .base import DatasetConverter, DatasetInstance


class ELTBenchConverter(DatasetConverter):
    """Converts ELT-Bench format to generic DatasetInstance.

    ELT-Bench task structure:
    task_dir/
    ├── config.yaml          # Data source configurations
    ├── data_model.yaml      # Target schema to produce
    └── schemas/
        ├── table1.csv       # Source table schema
        └── table2.csv       # Source table schema

    Ground truth (in evaluation/):
    evaluation/task_name/
    └── model_name.sql       # Expected SQL transformation

    Converts to:
    DatasetInstance(
        id="california_schools",
        input="<combined config + model + schemas>",
        output_format={"terraform": {...}, "sql": {...}},
        expected_output={"ca__schools.sql": "<sql content>"},
        context={"sources": ["postgres", "mongodb", ...], "models": [...]}
    )
    """

    # Standard output format for all ELT-Bench tasks
    OUTPUT_FORMAT = {
        "terraform": {
            "description": "Terraform configuration for Airbyte data pipelines",
            "format": "HCL (.tf file)",
            "components": [
                "airbyte_source_* resources for each data source",
                "airbyte_destination_snowflake resource",
                "airbyte_connection resources linking sources to destination"
            ]
        },
        "sql": {
            "description": "SQL transformation queries for DBT",
            "format": "SQL files, one per data model",
            "patterns": [
                "CTEs for intermediate transformations",
                "JOINs to combine source tables",
                "CASE statements for categorical columns",
                "Window functions for ranked columns",
                "Aggregations (SUM, AVG, COUNT) as needed"
            ]
        }
    }

    def __init__(self, base_path: str | Path = "datasets/benchmarks/ELT-Bench"):
        """Initialize converter with path to ELT-Bench dataset.

        Args:
            base_path: Path to ELT-Bench root directory
        """
        self.base_path = Path(base_path)
        self.tasks_path = self.base_path / "elt-bench"
        self.eval_path = self.base_path / "evaluation"

    def convert(self, raw_data: dict) -> list[DatasetInstance]:
        """Convert raw ELT-Bench task data to DatasetInstance list.

        Args:
            raw_data: Dict with task_name and loaded config/model/schemas

        Returns:
            List containing one DatasetInstance
        """
        task_name = raw_data.get("task_name", "unknown")
        config = raw_data.get("config", {})
        data_model = raw_data.get("data_model", {})
        schemas = raw_data.get("schemas", {})
        ground_truth_sql = raw_data.get("ground_truth_sql", {})

        # Build input - this is what the agent sees
        input_text = self._build_input(task_name, config, data_model, schemas)

        # Extract source types for signature (enables 83% workflow reuse)
        sources = self._extract_source_types(config)

        # Extract model names
        models = []
        if data_model and "models" in data_model:
            models = [m.get("name", "") for m in data_model["models"]]

        # Context for signature grouping - tasks with same sources share workflows
        context = {
            "sources": sorted(sources),
            "source_signature": "_".join(sorted(sources)),  # e.g., "api_files_mongodb_postgres_s3"
            "models": models,
            "num_models": len(models),
            "_task_type": "elt_pipeline",
            "_eval_type": "sql_execution",
        }

        return [DatasetInstance(
            id=task_name,
            input=input_text,
            output_format=self.OUTPUT_FORMAT,
            expected_output=ground_truth_sql,
            context=context,
            possible_outputs=[ground_truth_sql] if ground_truth_sql else [],
        )]

    def load_file(self, path: str) -> list[DatasetInstance]:
        """Load a single ELT-Bench task from directory.

        Args:
            path: Path to task directory (e.g., elt-bench/california_schools)

        Returns:
            List of DatasetInstance
        """
        task_dir = Path(path)
        return self._load_task(task_dir)

    def load_all(self, max_tasks: int | None = None) -> list[DatasetInstance]:
        """Load all ELT-Bench tasks.

        Args:
            max_tasks: Maximum number of tasks to load (None for all)

        Returns:
            List of DatasetInstance for all tasks
        """
        instances = []
        task_dirs = sorted(self.tasks_path.iterdir())

        for i, task_dir in enumerate(task_dirs):
            if max_tasks and i >= max_tasks:
                break
            if not task_dir.is_dir():
                continue

            try:
                instances.extend(self._load_task(task_dir))
            except Exception as e:
                print(f"Warning: Failed to load {task_dir.name}: {e}")

        return instances

    def _load_task(self, task_dir: Path) -> list[DatasetInstance]:
        """Load a single task from its directory."""
        task_name = task_dir.name

        # Load config.yaml
        config_file = task_dir / "config.yaml"
        config = {}
        if config_file.exists():
            with open(config_file) as f:
                config = yaml.safe_load(f) or {}

        # Load data_model.yaml
        model_file = task_dir / "data_model.yaml"
        data_model = {}
        if model_file.exists():
            with open(model_file) as f:
                data_model = yaml.safe_load(f) or {}

        # Load schemas
        schemas = {}
        schemas_dir = task_dir / "schemas"
        if schemas_dir.exists():
            for schema_file in schemas_dir.iterdir():
                if schema_file.suffix == ".csv":
                    table_name = schema_file.stem
                    with open(schema_file) as f:
                        schemas[table_name] = f.read()

        # Load ground truth SQL
        ground_truth_sql = {}
        eval_dir = self.eval_path / task_name
        if eval_dir.exists():
            for sql_file in eval_dir.iterdir():
                if sql_file.suffix == ".sql":
                    model_name = sql_file.stem
                    with open(sql_file) as f:
                        ground_truth_sql[model_name] = f.read()

        raw_data = {
            "task_name": task_name,
            "config": config,
            "data_model": data_model,
            "schemas": schemas,
            "ground_truth_sql": ground_truth_sql,
        }

        return self.convert(raw_data)

    def _build_input(
        self,
        task_name: str,
        config: dict,
        data_model: dict,
        schemas: dict
    ) -> str:
        """Build the input string that the agent will receive."""
        parts = [
            f"# ELT Pipeline Task: {task_name}",
            "",
            "## Data Sources (config.yaml)",
            "```yaml",
            yaml.dump(config, default_flow_style=False),
            "```",
            "",
            "## Target Data Model (data_model.yaml)",
            "```yaml",
            yaml.dump(data_model, default_flow_style=False),
            "```",
            "",
            "## Source Table Schemas",
        ]

        for table_name, schema_csv in schemas.items():
            parts.extend([
                f"### {table_name}",
                "```csv",
                schema_csv.strip(),
                "```",
                "",
            ])

        parts.extend([
            "## Task",
            "Generate:",
            "1. Terraform code (main.tf) to configure Airbyte pipelines",
            "2. SQL transformations for each data model",
        ])

        return "\n".join(parts)

    def _extract_source_types(self, config: dict) -> list[str]:
        """Extract the types of data sources from config."""
        sources = []

        # Check for each source type
        source_keys = [
            'postgres', 'mongodb', 'mysql', 'custom_api',
            'flat_files', 's3', 'aws_s3', 'gcs', 'azure_blob'
        ]

        for key in source_keys:
            if config.get(key):
                # Normalize aws_s3 to s3
                normalized = 's3' if key == 'aws_s3' else key
                if normalized not in sources:
                    sources.append(normalized)

        return sources


# Convenience function for quick loading
def load_eltbench(
    base_path: str = "datasets/benchmarks/ELT-Bench",
    max_tasks: int | None = None
) -> list[DatasetInstance]:
    """Load ELT-Bench dataset.

    Args:
        base_path: Path to ELT-Bench directory
        max_tasks: Max tasks to load (None for all 100)

    Returns:
        List of DatasetInstance
    """
    converter = ELTBenchConverter(base_path)
    return converter.load_all(max_tasks=max_tasks)
