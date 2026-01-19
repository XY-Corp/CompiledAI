"""Workflow visualizer - converts workflow YAML to ASCII diagrams."""

import yaml
from typing import Any, Dict, List


class WorkflowVisualizer:
    """Generate ASCII diagrams from workflow YAML."""

    def __init__(self):
        self.indent = "  "
        self.vertical = "│"
        self.branch = "├─"
        self.last_branch = "└─"
        self.arrow = "→"

    def visualize(self, workflow_yaml: str) -> str:
        """Generate ASCII diagram from workflow YAML.

        Args:
            workflow_yaml: YAML string representing the workflow

        Returns:
            ASCII diagram string
        """
        try:
            workflow = yaml.safe_load(workflow_yaml)
            lines = []

            # Header
            lines.append("╔═══════════════════════════════════════════════════════════════════════════╗")
            lines.append(f"║ {workflow.get('name', 'Workflow'):<73} ║")
            lines.append("╠═══════════════════════════════════════════════════════════════════════════╣")

            # Variables section
            variables = workflow.get("variables", {})
            if variables:
                lines.append("║ Variables:                                                                ║")
                for i, (key, value) in enumerate(variables.items()):
                    value_str = str(value)[:50] if value is not None else "null"
                    line = f"║   • {key}: {value_str}"
                    lines.append(f"{line:<75}║")

            # Execution flow
            lines.append("╠═══════════════════════════════════════════════════════════════════════════╣")
            lines.append("║ Execution Flow:                                                           ║")
            lines.append("╠═══════════════════════════════════════════════════════════════════════════╣")

            # Parse root element
            root = workflow.get("root", {})
            flow_lines = self._visualize_element(root, prefix="", is_last=True)
            for flow_line in flow_lines:
                lines.append(f"║ {flow_line:<73} ║")

            lines.append("╚═══════════════════════════════════════════════════════════════════════════╝")

            return "\n".join(lines)

        except Exception as e:
            return f"Error generating diagram: {e}"

    def _visualize_element(
        self, element: Dict[str, Any], prefix: str = "", is_last: bool = True
    ) -> List[str]:
        """Recursively visualize workflow elements.

        Args:
            element: Workflow element (sequence, parallel, activity, etc.)
            prefix: Current indentation prefix
            is_last: Whether this is the last element in its parent

        Returns:
            List of formatted lines
        """
        lines = []

        # Sequence
        if "sequence" in element:
            lines.append(f"{prefix}┌─ SEQUENCE")
            elements = element["sequence"].get("elements", [])
            for i, child in enumerate(elements):
                is_child_last = i == len(elements) - 1
                child_prefix = prefix + ("  " if is_last else "│ ")
                child_lines = self._visualize_element(child, child_prefix, is_child_last)
                lines.extend(child_lines)

        # Parallel
        elif "parallel" in element:
            lines.append(f"{prefix}┌─ PARALLEL")
            elements = element["parallel"].get("elements", [])
            for i, child in enumerate(elements):
                is_child_last = i == len(elements) - 1
                child_prefix = prefix + ("  " if is_last else "│ ")
                lines.append(f"{child_prefix}├─╮")
                parallel_lines = self._visualize_element(child, child_prefix + "│ ", is_child_last)
                lines.extend(parallel_lines)

        # ForEach
        elif "foreach" in element:
            foreach_data = element["foreach"]
            items = foreach_data.get("items", "?")
            max_concurrent = foreach_data.get("max_concurrent", "∞")
            lines.append(f"{prefix}┌─ FOREACH (items: {items}, max: {max_concurrent})")

            child_element = foreach_data.get("element", {})
            if child_element:
                child_prefix = prefix + ("  " if is_last else "│ ")
                lines.append(f"{child_prefix}└─ Each iteration:")
                iteration_lines = self._visualize_element(child_element, child_prefix + "   ", True)
                lines.extend(iteration_lines)

        # Activity
        elif "activity" in element:
            activity_data = element["activity"]
            name = activity_data.get("name", "unnamed")
            result = activity_data.get("result", "")
            params = activity_data.get("params", {})

            # Activity box
            connector = "└─" if is_last else "├─"
            lines.append(f"{prefix}{connector} [ACTIVITY] {name}")

            # Parameters
            if params:
                param_prefix = prefix + ("  " if is_last else "│ ")
                for i, (key, value) in enumerate(params.items()):
                    is_last_param = i == len(params) - 1
                    param_connector = "  └─" if is_last_param else "  ├─"
                    value_str = str(value)[:40]
                    lines.append(f"{param_prefix}{param_connector} {key}: {value_str}")

            # Result variable
            if result:
                result_prefix = prefix + ("  " if is_last else "│ ")
                lines.append(f"{result_prefix}  {self.arrow} result: {result}")

        return lines


def visualize_workflow(workflow_yaml: str) -> str:
    """Generate ASCII diagram from workflow YAML.

    Args:
        workflow_yaml: YAML string representing the workflow

    Returns:
        ASCII diagram string
    """
    visualizer = WorkflowVisualizer()
    return visualizer.visualize(workflow_yaml)
