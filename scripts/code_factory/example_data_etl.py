"""Example: Data ETL (Extract-Transform-Load) Workflow.

This example demonstrates generating a workflow that extracts data from
multiple sources, transforms it, validates the results, and loads it
into a data warehouse.

Run with: uv run python scripts/code_factory/example_data_etl.py
"""

import asyncio
from dotenv import load_dotenv

load_dotenv()

from compiled_ai.factory import CodeFactory


async def main():
    factory = CodeFactory(verbose=True)

    result = await factory.generate_and_execute(
        """Create a data ETL workflow that:
        1. Extract phase (run in parallel):
           - Extract sales data from the sales database
           - Extract inventory data from the inventory API
           - Extract customer data from the CRM system
        2. Transform phase (sequence):
           - Join the extracted datasets on common keys
           - Apply data quality checks and flag anomalies
           - Calculate derived metrics (revenue, margins, etc.)
           - Normalize and clean the data
        3. Load phase:
           - Load the transformed data into the data warehouse
           - Update the data catalog with new metadata
           - Send a completion notification with statistics

        Use parallel execution for independent extractions.""",
        test_variables={
            "extraction_date": "2024-01-15",
            "sales_db_config": {
                "host": "sales-db.internal",
                "database": "sales_prod",
                "table": "transactions",
            },
            "inventory_api_url": "https://inventory-api.internal/v2/stock",
            "crm_config": {
                "endpoint": "https://crm.internal/api",
                "resource": "customers",
            },
            "warehouse_config": {
                "host": "warehouse.internal",
                "schema": "analytics",
                "table": "daily_metrics",
            },
            "notification_channel": "slack://data-team",
        },
    )

    print("\n" + "=" * 70)
    print("RESULT SUMMARY")
    print("=" * 70)
    print(f"Success: {result.success}")
    print(f"Regeneration attempts: {result.regeneration_count}")

    if result.plan:
        print(f"\nWorkflow: {result.plan.name}")
        print(f"Pattern: {result.plan.execution_pattern}")
        print(f"Activities ({len(result.plan.activities)}):")
        for activity in result.plan.activities:
            print(f"  - {activity.name}: {activity.description}")
        print(f"\nReasoning: {result.plan.reasoning}")

    if result.success and result.generated:
        print("\n" + "-" * 70)
        print("GENERATED WORKFLOW YAML")
        print("-" * 70)
        print(result.workflow_yaml)

        print("\n" + "-" * 70)
        print("GENERATED ACTIVITIES CODE")
        print("-" * 70)
        print(result.activities_code)

    if result.execution_result:
        print("\n" + "-" * 70)
        print("EXECUTION RESULT (Final Variables)")
        print("-" * 70)
        for key, value in result.execution_result.items():
            if isinstance(value, dict):
                if "mocked" in value:
                    print(f"  {key}: {{status: success, mocked: true}}")
                else:
                    print(f"  {key}: {value}")
            elif isinstance(value, (list, str)) and len(str(value)) > 80:
                print(f"  {key}: {str(value)[:77]}...")
            else:
                print(f"  {key}: {value}")

    if result.validation_errors:
        print("\n" + "-" * 70)
        print("VALIDATION ERRORS")
        print("-" * 70)
        for error in result.validation_errors:
            print(f"  - {error}")

    if result.metrics:
        print("\n" + "-" * 70)
        print("METRICS")
        print("-" * 70)
        print(f"  Input tokens: {result.metrics.total_input_tokens}")
        print(f"  Output tokens: {result.metrics.total_output_tokens}")
        print(f"  Total tokens: {result.metrics.total_tokens}")
        print(f"  LLM calls: {result.metrics.total_calls}")
        if result.metrics.latencies_ms:
            print(f"  Avg latency: {result.metrics.avg_latency_ms:.0f}ms")


if __name__ == "__main__":
    asyncio.run(main())
