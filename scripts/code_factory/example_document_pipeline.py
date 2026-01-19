"""Example: Document Processing Pipeline Workflow.

This example demonstrates generating a workflow that processes multiple
documents in parallel, extracting text, analyzing content, and generating
a summary report.

Run with: uv run python scripts/code_factory/example_document_pipeline.py
"""

import asyncio
from dotenv import load_dotenv

load_dotenv()

from compiled_ai.factory import CodeFactory


async def main():
    factory = CodeFactory(verbose=True)

    result = await factory.generate_and_execute(
        """Create a document processing pipeline workflow that:
        1. Accepts a list of document URLs to process
        2. For each document in parallel (max 3 concurrent):
           - Download the document from the URL
           - Extract text content from the document
           - Analyze the document for key entities and topics
        3. After all documents are processed:
           - Aggregate the analysis results
           - Generate a summary report
           - Store the report in the output location

        Use a forEach pattern with max_concurrent=3 for parallel processing.""",
        test_variables={
            "document_urls": [
                "https://example.com/docs/quarterly_report_q1.pdf",
                "https://example.com/docs/quarterly_report_q2.pdf",
                "https://example.com/docs/annual_summary.pdf",
            ],
            "output_location": "s3://reports-bucket/summaries/",
            "analysis_config": {
                "extract_entities": True,
                "extract_topics": True,
                "sentiment_analysis": False,
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
        print("EXECUTION RESULT")
        print("-" * 70)
        for key, value in result.execution_result.items():
            if isinstance(value, dict) and "mocked" in value:
                print(f"  {key}: [mocked activity result]")
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
