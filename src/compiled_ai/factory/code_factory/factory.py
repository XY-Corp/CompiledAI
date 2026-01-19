"""Code Factory orchestrator with regeneration loop and actual execution."""

import ast
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .models import WorkflowSpec, GeneratedFiles
from .agents import create_agents
from .llm_adapter import AdapterMetrics, extract_usage_from_result, ProviderType
from .template_registry import TemplateRegistry
from .registration import ActivityRegistrar, RegistrationPolicy

# Add XYLocalWorkflowExecutor to path for validation and execution
_executor_path = Path(__file__).parent.parent / "XYLocalWorkflowExecutor" / "src"
if str(_executor_path) not in sys.path:
    sys.path.insert(0, str(_executor_path))

from xy_local_executor.dsl.parser import build_dsl_input
from xy_local_executor.dsl.models import DSLInput
from xy_local_executor import LocalWorkflowExecutor
from xy_local_executor.mocks import ActivityMocks


@dataclass
class FactoryResult:
    """Result from Code Factory execution."""

    success: bool
    plan: Optional[WorkflowSpec] = None
    generated: Optional[GeneratedFiles] = None
    dsl_input: Optional[DSLInput] = None
    validation_errors: list[str] = field(default_factory=list)
    regeneration_count: int = 0
    metrics: Optional[AdapterMetrics] = None
    execution_result: Optional[dict] = None

    @property
    def workflow_yaml(self) -> str:
        """Get the generated workflow YAML."""
        return self.generated.workflow_yaml if self.generated else ""

    @property
    def activities_code(self) -> str:
        """Get the generated activities Python code."""
        return self.generated.activities_code if self.generated else ""


class CodeFactory:
    """PydanticAI-based factory with regeneration loop and actual execution.

    This factory uses two PydanticAI agents:
    1. Planner Agent: Designs workflow structure from natural language
    2. Coder Agent: Generates YAML and Python code from the plan

    Features:
    - Structured outputs via Pydantic models
    - Automatic regeneration on validation failure
    - Actual workflow execution with mocked or real activities
    - Metrics tracking for token usage and latency

    Example:
        ```python
        factory = CodeFactory(verbose=True)
        result = await factory.generate_and_execute(
            "Process customer orders and send confirmations",
            test_variables={"orders": ["order1", "order2"]}
        )
        if result.success:
            print(result.workflow_yaml)
        ```
    """

    def __init__(
        self,
        provider: ProviderType = "anthropic",
        model: str | None = None,
        verbose: bool = False,
        max_regenerations: int = 3,
        enable_registry: bool = True,
        auto_register: bool = True,
    ):
        """Initialize the Code Factory.

        Args:
            provider: LLM provider ("anthropic", "openai", or "gemini")
            model: Specific model name, or None for provider default
            verbose: Print progress messages
            max_regenerations: Maximum attempts to fix validation errors
            enable_registry: Enable template registry for activity search
            auto_register: Automatically register successful activities
        """
        self.provider = provider
        self.model = model
        self.verbose = verbose
        self.max_regenerations = max_regenerations

        # Registry components
        self.registry = TemplateRegistry() if enable_registry else None
        self.registrar = (
            ActivityRegistrar(self.registry) if auto_register and self.registry else None
        )

    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    async def generate(self, task_description: str) -> FactoryResult:
        """Generate workflow from natural language description.

        This method:
        1. Uses the planner agent to design workflow structure
        2. Uses the coder agent to generate YAML and Python code
        3. Validates the generated YAML against the DSL schema
        4. Retries with error feedback if validation fails

        Args:
            task_description: Natural language description of the workflow

        Returns:
            FactoryResult with generated code and validation status
        """
        result = FactoryResult(success=False)
        metrics = AdapterMetrics()

        # Create agents (planner gets registry for template search)
        planner, coder, _ = create_agents(
            provider=self.provider,
            model=self.model,
            registry=self.registry,
        )

        # Step 1: Planning Agent -> WorkflowSpec
        self._log("[Planning] Designing workflow structure...")
        if self.verbose:
            print("\n" + "="*80)
            print("PLANNER PROMPT:")
            print("="*80)
            print(task_description)
            print("="*80 + "\n")
        start_time = time.perf_counter()
        plan_result = await planner.run(task_description)
        latency_ms = (time.perf_counter() - start_time) * 1000

        result.plan = plan_result.output

        # Track metrics
        input_tokens, output_tokens = extract_usage_from_result(plan_result)
        metrics.record(input_tokens, output_tokens, latency_ms)

        self._log(f"[Planning] Created: {result.plan.name}")
        self._log(f"[Planning] Activities: {[a.name for a in result.plan.activities]}")
        self._log(f"[Planning] Pattern: {result.plan.execution_pattern}")

        # Step 2: Code Generation with Regeneration Loop
        error_feedback = ""
        for attempt in range(self.max_regenerations + 1):
            self._log(f"[Coding] Generation attempt {attempt + 1}...")

            coder_prompt = self._build_coder_prompt(result.plan, error_feedback)
            start_time = time.perf_counter()
            code_result = await coder.run(coder_prompt)
            latency_ms = (time.perf_counter() - start_time) * 1000

            result.generated = code_result.output
            result.regeneration_count = attempt

            # Track metrics
            input_tokens, output_tokens = extract_usage_from_result(code_result)
            metrics.record(input_tokens, output_tokens, latency_ms)

            # Validate YAML structure
            validation_error = self._validate_yaml(result)
            if validation_error is None:
                result.success = True
                self._log(f"[Validation] YAML valid on attempt {attempt + 1}")
                break
            else:
                error_feedback = validation_error
                result.validation_errors.append(f"Attempt {attempt + 1}: {validation_error}")
                self._log(f"[Validation] Failed: {validation_error}")

                if attempt == self.max_regenerations:
                    self._log("[Validation] Max regenerations reached")

        result.metrics = metrics

        # Auto-register successful activities
        if result.success and self.registrar:
            self._register_activities(result, task_description)

        return result

    def _validate_yaml(self, result: FactoryResult) -> str | None:
        """Validate YAML against DSL schema.

        Args:
            result: FactoryResult containing the generated YAML

        Returns:
            Error message string if invalid, None if valid
        """
        if not result.generated or not result.plan:
            return "No generated content to validate"

        try:
            dsl_input = build_dsl_input(
                config_flow_id=result.plan.workflow_id,
                execution_yaml=result.generated.workflow_yaml,
                input_data={},
                metadata={"user_id": "test", "organization_id": "test"},
            )
            result.dsl_input = dsl_input
            return None
        except Exception as e:
            return str(e)

    async def generate_and_execute(
        self,
        task_description: str,
        test_variables: dict[str, Any] | None = None,
        activity_implementations: dict[str, Callable] | None = None,
    ) -> FactoryResult:
        """Generate workflow and execute with real or mocked activities.

        This method extends generate() by also executing the generated workflow.
        If no activity implementations are provided, all activities are mocked
        with instant success responses.

        Args:
            task_description: Natural language description of the workflow
            test_variables: Input variables to pass to the workflow
            activity_implementations: Optional dict mapping activity names to
                async functions. If not provided, activities are mocked.

        Returns:
            FactoryResult with generated code, validation status, and execution result
        """
        result = await self.generate(task_description)

        if not result.success:
            return result

        # Determine activities to use (provided or mocked)
        if activity_implementations:
            activities = activity_implementations
        else:
            # Use mocks for all activities defined in the plan
            activities = {
                activity.name: ActivityMocks.instant_success
                for activity in result.plan.activities
            }

        self._log(f"[Execution] Running workflow with {len(activities)} activities...")

        try:
            executor = LocalWorkflowExecutor(
                mock_activities=activities,
                dry_run=False,  # Actual execution
                verbose=self.verbose,
            )

            # Write YAML to temp file for executor
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                f.write(result.generated.workflow_yaml)
                temp_path = f.name

            # Execute the workflow
            execution_output = await executor.run_yaml(
                temp_path,
                variables=test_variables or {},
            )
            result.execution_result = execution_output

            self._log("[Execution] Workflow completed successfully!")

        except Exception as e:
            result.validation_errors.append(f"Execution failed: {e}")
            result.success = False
            self._log(f"[Execution] Failed: {e}")

        return result

    def _build_coder_prompt(
        self, plan: WorkflowSpec, error_feedback: str = ""
    ) -> str:
        """Build prompt for coder agent, including any error feedback.

        Args:
            plan: WorkflowSpec from the planner agent
            error_feedback: Previous validation error to help fix issues

        Returns:
            Formatted prompt string for the coder agent
        """
        variables_str = "\n".join(
            f"  - {v.name}: {v.default_value}" for v in plan.variables
        )

        # Build detailed activity specs with input/output schemas
        activities_str = ""
        for activity in plan.activities:
            activities_str += f"\n  Activity: {activity.name}\n"
            activities_str += f"  Description: {activity.description}\n"

            # Add input schema
            if activity.inputs:
                activities_str += "  Input Parameters:\n"
                for param in activity.inputs:
                    required_str = "required" if param.required else "optional"
                    activities_str += f"    - {param.name}: {param.type} ({required_str}) - {param.description}\n"
            else:
                activities_str += "  Input Parameters: (none specified)\n"

            # Add output schema
            if activity.output:
                activities_str += f"  Output: {activity.output.type} - {activity.output.description}\n"
                if activity.output.fields:
                    activities_str += "  Output Fields:\n"
                    for field_name, field_type in activity.output.fields.items():
                        activities_str += f"    - {field_name}: {field_type}\n"
            else:
                activities_str += "  Output: dict with status field (default)\n"

            # Add reference activity if available
            if activity.reference_activity:
                activities_str += f"  Reference (inspiration): {activity.reference_activity}\n"

            activities_str += "\n"

        base_prompt = f"""Generate workflow code based on this plan:

Workflow ID: {plan.workflow_id}
Name: {plan.name}
Description: {plan.description}

Variables:
{variables_str or "  (none)"}

Activities (with exact schemas):
{activities_str}

Execution Pattern: {plan.execution_pattern}

CRITICAL REQUIREMENTS:
1. Generate function signatures that EXACTLY match the input parameters defined above
2. Return values must EXACTLY match the output schema defined above
3. Parameter names, types, and return structure must be precise
4. Always include required imports at the top of activities.py
"""

        # Add template inspiration if reference activities are specified
        template_section = self._build_template_inspiration_section(plan)
        if template_section:
            base_prompt += f"\n{template_section}"

        if error_feedback:
            base_prompt += f"""

IMPORTANT: Previous generation failed validation with error:
{error_feedback}

Please fix the issues and regenerate valid YAML.
"""
        return base_prompt

    def _build_template_inspiration_section(self, plan: WorkflowSpec) -> str:
        """Build section with template activity source code for inspiration.

        Args:
            plan: WorkflowSpec with reference_activity fields

        Returns:
            Formatted section with template source code, or empty string if none
        """
        # Collect unique reference activities
        reference_activities = set()
        for activity in plan.activities:
            if activity.reference_activity:
                reference_activities.add(activity.reference_activity)

        if not reference_activities:
            return ""

        # Get activity registry to fetch source code
        from ..activities import get_registry

        registry = get_registry()
        template_section = "\n## TEMPLATE INSPIRATION (adapt, don't copy!):\n\n"

        for ref_name in reference_activities:
            source = registry.get_source(ref_name)
            if source:
                template_section += f"### Reference Activity: {ref_name}\n"
                template_section += "```python\n"
                template_section += source
                template_section += "\n```\n\n"
                template_section += "IMPORTANT: This is INSPIRATION only. Generate NEW code with:\n"
                template_section += "- Different parameter names matching your workflow\n"
                template_section += "- Different output structure matching your schema\n"
                template_section += "- Adapted logic for your specific use case\n\n"

        return template_section

    def _register_activities(
        self, result: FactoryResult, task_description: str
    ) -> None:
        """Attempt to register generated activities in the template registry.

        Args:
            result: Successful FactoryResult
            task_description: Original task description (used as generation prompt)
        """
        if not result.generated or not result.plan:
            return

        for activity in result.plan.activities:
            # Extract source code for this activity
            source = self._extract_activity_code(
                result.generated.activities_code, activity.name
            )

            if source:
                reg_result = self.registrar.attempt_registration(
                    name=activity.name,
                    source_code=source,
                    generation_prompt=activity.description or task_description,
                    parent_templates=[],  # TODO: Track which templates were used
                    validation_result={"passed": True},
                )

                if reg_result.success:
                    self._log(f"[Registry] Registered: {activity.name}")
                elif reg_result.conflict:
                    self._log(
                        f"[Registry] Skipped {activity.name}: already exists"
                    )

    def _extract_activity_code(
        self, activities_code: str, activity_name: str
    ) -> str | None:
        """Extract source code for a specific activity from generated file.

        Args:
            activities_code: Full Python code string with all activities
            activity_name: Name of the specific activity to extract

        Returns:
            Source code for the activity, or None if not found
        """
        try:
            # Parse the Python code
            tree = ast.parse(activities_code)

            # Find the function definition
            for node in ast.walk(tree):
                if isinstance(node, ast.AsyncFunctionDef) and node.name == activity_name:
                    # Get the source code for this function
                    lines = activities_code.split("\n")
                    start_line = node.lineno - 1
                    end_line = node.end_lineno

                    if end_line:
                        source_lines = lines[start_line:end_line]
                        return "\n".join(source_lines)

            return None
        except Exception as e:
            self._log(f"[Registry] Failed to extract {activity_name}: {e}")
            return None
