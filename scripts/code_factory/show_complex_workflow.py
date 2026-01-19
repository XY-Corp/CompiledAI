"""Demo showing complex workflow ASCII visualization."""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from compiled_ai.factory.code_factory.visualizer import visualize_workflow
from rich.console import Console

console = Console()


def show_example_workflows():
    """Show various workflow patterns with ASCII diagrams."""

    # Example 1: Simple sequence
    console.print("\n[bold cyan]Example 1: Simple Sequential Workflow[/bold cyan]\n")
    simple_yaml = """
workflow_id: ticket_classification
name: Support Ticket Classification
description: Classify and route support tickets
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
          result: classification
      - activity:
          name: route_to_team
          params:
            category: ${{ classification.category }}
            ticket_id: ${{ ticket_text }}
          result: routing_result
"""
    console.print(visualize_workflow(simple_yaml))

    # Example 2: Parallel processing
    console.print("\n[bold cyan]Example 2: Parallel Data Processing[/bold cyan]\n")
    parallel_yaml = """
workflow_id: multi_source_analysis
name: Multi-Source Data Analysis
description: Analyze data from multiple sources in parallel
variables:
  input_data: null
root:
  sequence:
    elements:
      - parallel:
          elements:
            - activity:
                name: analyze_sentiment
                params:
                  text: ${{ input_data }}
                result: sentiment_score
            - activity:
                name: extract_entities
                params:
                  text: ${{ input_data }}
                result: entities
            - activity:
                name: detect_language
                params:
                  text: ${{ input_data }}
                result: language
      - activity:
          name: combine_results
          params:
            sentiment: ${{ sentiment_score }}
            entities: ${{ entities }}
            language: ${{ language }}
          result: final_analysis
"""
    console.print(visualize_workflow(parallel_yaml))

    # Example 3: ForEach with concurrency
    console.print("\n[bold cyan]Example 3: Batch Processing with ForEach[/bold cyan]\n")
    foreach_yaml = """
workflow_id: batch_email_processing
name: Batch Email Processing
description: Process multiple emails with concurrency control
variables:
  emails: []
  max_concurrent: 10
root:
  sequence:
    elements:
      - activity:
          name: validate_emails
          params:
            emails: ${{ emails }}
          result: valid_emails
      - foreach:
          items: valid_emails
          max_concurrent: 10
          element:
            sequence:
              elements:
                - activity:
                    name: classify_email
                    params:
                      email: ${{ item }}
                    result: classification
                - activity:
                    name: extract_metadata
                    params:
                      email: ${{ item }}
                    result: metadata
"""
    console.print(visualize_workflow(foreach_yaml))

    # Example 4: Complex nested workflow
    console.print("\n[bold cyan]Example 4: Complex Order Processing Pipeline[/bold cyan]\n")
    complex_yaml = """
workflow_id: order_processing_pipeline
name: E-Commerce Order Processing Pipeline
description: Multi-stage order processing with validation, payment, and fulfillment
variables:
  orders: []
  notification_settings: {email: true, sms: false}
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
          max_concurrent: 5
          element:
            sequence:
              elements:
                - activity:
                    name: check_inventory
                    params:
                      order_items: ${{ item.items }}
                    result: inventory_status
                - activity:
                    name: process_payment
                    params:
                      order: ${{ item }}
                      amount: ${{ item.total }}
                    result: payment_result
                - parallel:
                    elements:
                      - activity:
                          name: update_inventory
                          params:
                            order_id: ${{ item.id }}
                            items: ${{ item.items }}
                          result: inventory_updated
                      - activity:
                          name: send_confirmation
                          params:
                            order: ${{ item }}
                            settings: ${{ notification_settings }}
                          result: notification_sent
                      - activity:
                          name: log_transaction
                          params:
                            order_id: ${{ item.id }}
                            payment: ${{ payment_result }}
                          result: log_entry
"""
    console.print(visualize_workflow(complex_yaml))


if __name__ == "__main__":
    console.print("\n" + "=" * 80)
    console.print("[bold]ASCII WORKFLOW VISUALIZATION EXAMPLES[/bold]")
    console.print("=" * 80)

    show_example_workflows()

    console.print("\n" + "=" * 80)
    console.print("[bold green]✅ All examples displayed![/bold green]")
    console.print("=" * 80)
    console.print("\n[dim]These diagrams appear automatically when running Code Factory with verbose=True[/dim]\n")
