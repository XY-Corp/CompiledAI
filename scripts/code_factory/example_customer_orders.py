"""Example: Customer Order Processing Workflow.

This example demonstrates generating a workflow that processes customer orders,
validates them, calculates totals, and sends confirmation emails.

Run with: uv run python scripts/code_factory/example_customer_orders.py
"""

import asyncio
from dotenv import load_dotenv

load_dotenv()

from compiled_ai.factory import CodeFactory


async def main():
    factory = CodeFactory(verbose=True)

    result = await factory.generate_and_execute(
        """Create a customer order processing workflow that:
        1. Fetches customer details from the customer ID
        2. Validates the order items and checks inventory
        3. Calculates the order total including tax and shipping
        4. Creates the order record in the database
        5. Sends an order confirmation email to the customer

        The workflow should handle a single customer order.""",
        test_variables={
            "customer_id": "CUST_12345",
            "order_items": [
                {"product_id": "PROD_001", "quantity": 2, "price": 29.99},
                {"product_id": "PROD_002", "quantity": 1, "price": 49.99},
            ],
            "shipping_address": {
                "street": "123 Main St",
                "city": "San Francisco",
                "state": "CA",
                "zip": "94102",
            },
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
        print(f"Activities: {[a.name for a in result.plan.activities]}")

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
        print("EXECUTION RESULT")
        print("-" * 70)
        for key, value in result.execution_result.items():
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
