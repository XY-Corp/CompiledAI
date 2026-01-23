"""XY Benchmark converter - converts XY format to generic DatasetInstance.

Strategy: Pass COMPLETE raw data as input, let workflow figure it out.
- `output_format`: Structure description extracted from schema (NO values)
- `expected_output`: Ground truth values for evaluation
- `context`: Schema for task signature grouping
"""

import json
from pathlib import Path

from .base import DatasetConverter, DatasetInstance


class XYConverter(DatasetConverter):
    """Converts XY Benchmark format to generic DatasetInstance.

    XY format:
    {
        "id": "classification_01",
        "prompt_template": "Classify this: {text}",
        "schema": {"type": "object", "properties": {...}},
        "instances": [
            {"id": "inst_1", "input": {"text": "..."}, "expected_output": "category"}
        ]
    }

    Converts to:
    DatasetInstance(
        id="classification_01_inst_1",
        input=<complete raw JSON with prompt_template and input>,
        context={"schema": {...}},  # For signature grouping
        possible_outputs=["category"]
    )

    Key principle: input varies, context defines task type.
    Tasks with same schema share compiled workflows.
    """

    def convert(self, raw_data: dict) -> list[DatasetInstance]:
        """Convert raw XY task data to DatasetInstance list.

        Structure:
        - input: COMPLETE raw task data (prompt_template + input values as JSON)
        - output_format: Structure description from schema OR explicit output_format field (NO values)
        - expected_output: Ground truth values for LLM evaluation
        - context: Schema for signature grouping (tasks with same schema share workflows)
        """
        instances = []

        task_id = raw_data.get("id", "unknown")
        prompt_template = raw_data.get("prompt_template", "{input}")
        schema = raw_data.get("schema", {})

        # Extract output_format - prefer explicit field, fallback to schema
        output_format = raw_data.get("output_format")
        if not output_format and schema:
            # Generate output_format from schema (structure only, no values)
            output_format = self._schema_to_output_format(schema)

        for inst in raw_data.get("instances", []):
            inst_id = inst.get("id", "unknown")
            input_data = inst.get("input", {})
            expected = inst.get("expected_output")

            # The input is the COMPLETE raw data - no pre-processing
            # Workflow receives everything and figures out what to do
            raw_input = json.dumps({
                "prompt_template": prompt_template,
                "input": input_data,
            })

            # Wrap expected in list for backward compatibility
            possible_outputs = [expected] if expected is not None else []

            # Context includes:
            # - _task_schema: For signature grouping (prefixed to avoid variable name conflicts)
            # - input fields: Passed directly to workflow as variables
            context = {
                "_task_schema": schema,  # Prefixed to avoid conflict with workflow variables
                **input_data,  # Pass input fields directly (e.g., address, text, ticket, etc.)
            }

            instances.append(DatasetInstance(
                id=f"{task_id}_{inst_id}",
                input=raw_input,  # Complete raw input as JSON (for reference)
                output_format=output_format or {},  # Structure description
                expected_output=expected,  # Ground truth for evaluation
                context=context,
                possible_outputs=possible_outputs,  # Deprecated, kept for compatibility
            ))

        return instances

    def _schema_to_output_format(self, schema: dict) -> dict:
        """Convert JSON schema to output_format (structure description without values).

        Example:
            Input schema:
            {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"}
                }
            }

            Output format:
            {
                "type": "object",
                "fields": {
                    "street": "string - street address",
                    "city": "string - city name"
                }
            }
        """
        if not schema:
            return {}

        output_format = {"type": schema.get("type", "object")}

        properties = schema.get("properties", {})
        if properties:
            fields = {}
            for field_name, field_schema in properties.items():
                field_type = field_schema.get("type", "string")
                description = field_schema.get("description", field_name.replace("_", " "))
                fields[field_name] = f"{field_type} - {description}"
            output_format["fields"] = fields

        return output_format

    def load_file(self, path: str) -> list[DatasetInstance]:
        """Load XY dataset from JSON file."""
        with open(path) as f:
            data = json.load(f)

        # Handle both single task and list of tasks
        if isinstance(data, list):
            instances = []
            for task in data:
                instances.extend(self.convert(task))
            return instances
        else:
            return self.convert(data)

    def load_directory(self, dir_path: str) -> list[DatasetInstance]:
        """Load all XY dataset files from a directory.

        Looks for JSON files in:
        1. tasks/ subdirectory (standard XY layout)
        2. Root directory (fallback)
        """
        instances = []
        path = Path(dir_path)

        # Check for tasks subdirectory (standard XY layout)
        tasks_dir = path / "tasks"
        if tasks_dir.exists():
            for json_file in tasks_dir.glob("*.json"):
                instances.extend(self.load_file(str(json_file)))
        else:
            # Fallback: look in root directory
            for json_file in path.glob("*.json"):
                instances.extend(self.load_file(str(json_file)))

        return instances
