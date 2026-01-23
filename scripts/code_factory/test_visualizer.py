"""Test workflow ASCII visualizer."""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from compiled_ai.factory.code_factory.visualizer import visualize_workflow


def test_simple_sequence():
    """Test visualizing a simple sequence workflow."""
    yaml_content = """
workflow_id: simple_classification
name: Simple Support Ticket Classification
description: Classifies support tickets into categories
variables:
  ticket_text: null
  categories: ['Billing', 'Technical', 'Account']
root:
  sequence:
    elements:
      - activity:
          name: classify_ticket
          params:
            ticket_text: ${{ ticket_text }}
            categories: ${{ categories }}
          result: classification_result
      - activity:
          name: log_result
          params:
            result: ${{ classification_result }}
          result: log_output
"""
    print("=" * 80)
    print("TEST 1: Simple Sequence Workflow")
    print("=" * 80)
    print(visualize_workflow(yaml_content))
    print()


def test_parallel_workflow():
    """Test visualizing a parallel workflow."""
    yaml_content = """
workflow_id: parallel_processing
name: Parallel Data Processing
description: Process multiple data sources in parallel
variables:
  input_data: null
root:
  parallel:
    elements:
      - activity:
          name: process_source_a
          params:
            data: ${{ input_data }}
          result: result_a
      - activity:
          name: process_source_b
          params:
            data: ${{ input_data }}
          result: result_b
      - activity:
          name: process_source_c
          params:
            data: ${{ input_data }}
          result: result_c
"""
    print("=" * 80)
    print("TEST 2: Parallel Workflow")
    print("=" * 80)
    print(visualize_workflow(yaml_content))
    print()


def test_foreach_workflow():
    """Test visualizing a foreach workflow."""
    yaml_content = """
workflow_id: batch_processing
name: Batch Processing Workflow
description: Process items in batches with concurrency control
variables:
  items: []
  max_concurrent: 5
root:
  foreach:
    items: items
    max_concurrent: 5
    element:
      activity:
        name: process_item
        params:
          item: ${{ item }}
        result: processed_item
"""
    print("=" * 80)
    print("TEST 3: ForEach Workflow")
    print("=" * 80)
    print(visualize_workflow(yaml_content))
    print()


def test_complex_workflow():
    """Test visualizing a complex nested workflow."""
    yaml_content = """
workflow_id: complex_workflow
name: Multi-Stage Order Processing
description: Complex workflow with sequence, parallel, and foreach
variables:
  orders: []
  notification_channels: ['email', 'sms']
root:
  sequence:
    elements:
      - activity:
          name: validate_orders
          params:
            orders: ${{ orders }}
          result: validated_orders
      - foreach:
          items: validated_orders
          max_concurrent: 10
          element:
            sequence:
              elements:
                - activity:
                    name: process_payment
                    params:
                      order: ${{ item }}
                    result: payment_result
                - parallel:
                    elements:
                      - activity:
                          name: update_inventory
                          params:
                            order: ${{ item }}
                          result: inventory_update
                      - activity:
                          name: send_confirmation
                          params:
                            order: ${{ item }}
                            channels: ${{ notification_channels }}
                          result: confirmation_sent
"""
    print("=" * 80)
    print("TEST 4: Complex Nested Workflow")
    print("=" * 80)
    print(visualize_workflow(yaml_content))
    print()


if __name__ == "__main__":
    test_simple_sequence()
    test_parallel_workflow()
    test_foreach_workflow()
    test_complex_workflow()

    print("=" * 80)
    print("✅ ALL VISUALIZATION TESTS COMPLETE")
    print("=" * 80)
