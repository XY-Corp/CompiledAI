"""Code Factory orchestrator with regeneration loop and actual execution."""

import ast
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic_ai.settings import ModelSettings

from .models import WorkflowSpec, GeneratedFiles, BFCLFunctionCallOutput
from .agents import create_agents, create_bfcl_agent
from .llm_adapter import AdapterMetrics, extract_usage_from_result, ProviderType
from .retry import run_agent_with_retry
from .template_registry import TemplateRegistry
from .registration import ActivityRegistrar, RegistrationPolicy
from .dynamic_loader import DynamicModuleLoader

# Evaluation imports for self-healing loop (go up to compiled_ai level)
from ...evaluation import get_evaluator
from ...evaluation.base import Evaluator, EvaluationResult
from ...utils.llm_client import create_client, LLMConfig

# Add XYLocalWorkflowExecutor to path for validation and execution
_executor_path = Path(__file__).parent.parent / "XYLocalWorkflowExecutor" / "src"
if str(_executor_path) not in sys.path:
    sys.path.insert(0, str(_executor_path))

from xy_local_executor.dsl.parser import build_dsl_input
from xy_local_executor.dsl.models import DSLInput
from xy_local_executor import LocalWorkflowExecutor
from xy_local_executor.mocks import ActivityMocks


# =============================================================================
# Function Call Template: Skip Planner for simple function-calling tasks
# Used when task has `functions` in context (works with any dataset)
# =============================================================================
FUNCTION_CALL_TEMPLATE = """workflow_id: {workflow_id}
name: Function Call Extractor
description: |
  Extract function name and parameters from natural language query

variables:
  prompt: null
  functions: null

root:
  sequence:
    elements:
      - activity:
          name: extract_function_call
          params:
            prompt: ${{{{ prompt }}}}
            functions: ${{{{ functions }}}}
          result: function_call
"""


@dataclass
class BFCLResult:
    """Result from BFCL function call generation."""

    success: bool
    function_name: str = ""
    arguments: dict = field(default_factory=dict)
    reasoning: str = ""
    error: str | None = None
    metrics: Optional[AdapterMetrics] = None

    def to_bfcl_format(self) -> dict:
        """Convert to BFCL ground truth format: {function_name: {args}}."""
        return {self.function_name: self.arguments}

    def to_json(self) -> str:
        """Convert to JSON string for evaluation."""
        return json.dumps(self.to_bfcl_format())


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

    # Validation tracking (Phase 2: self-healing loop)
    yaml_validated: bool = False
    execution_validated: bool = False
    examples_tested: int = 0

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
        log_dir: str | None = "logs",
        canary_token: str | None = None,
    ):
        """Initialize the Code Factory.

        Args:
            provider: LLM provider ("anthropic", "openai", or "gemini")
            model: Specific model name, or None for provider default
            verbose: Print progress messages
            max_regenerations: Maximum attempts to fix validation errors
            enable_registry: Enable template registry for activity search
            auto_register: Automatically register successful activities
            log_dir: Directory for compilation logs (None to disable file logging)
            canary_token: Optional canary token to inject into system prompts for leakage detection
        """
        self.provider = provider
        self.model = model
        self.verbose = verbose
        self.max_regenerations = max_regenerations
        self.log_dir = Path(log_dir) if log_dir else None
        self.canary_token = canary_token

        # Registry components
        self.registry = TemplateRegistry(enable_semantic=False) if enable_registry else None
        self.registrar = (
            ActivityRegistrar(self.registry) if auto_register and self.registry else None
        )

        # Multi-example support
        self._current_examples: list[Any] | None = None  # TaskInput list for current compilation

        # Semantic search index for workflow activities
        self._workflow_index = None
        self._workflow_sources: dict[str, str] = {}  # activity_name -> source code
        self._load_workflow_activities()

        # Current log file for this compilation
        self._current_log_file: Path | None = None

    def _log(self, message: str) -> None:
        """Print message if verbose mode is enabled and write to log file."""
        if self.verbose:
            print(message)
        self._log_to_file(message)

    def _log_to_file(self, message: str, section: str | None = None) -> None:
        """Write message to current log file.

        Args:
            message: Message to log
            section: Optional section header (e.g., "PLANNER PROMPT", "ERROR")
        """
        if not self._current_log_file:
            return

        with open(self._current_log_file, "a", encoding="utf-8") as f:
            if section:
                f.write(f"\n{'='*80}\n")
                f.write(f"{section}\n")
                f.write(f"{'='*80}\n")
            f.write(f"{message}\n")

    def _setup_log_file(self, task_id: str) -> None:
        """Set up a new log file for this compilation.

        Args:
            task_id: Task identifier for naming the log file
        """
        if not self.log_dir:
            self._current_log_file = None
            return

        # Create logs directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create log file (no timestamp needed, each run has its own directory)
        log_filename = f"{task_id}.log"
        self._current_log_file = self.log_dir / log_filename

        # Write header
        from datetime import datetime
        self._log_to_file(f"Code Factory Compilation Log", section="HEADER")
        self._log_to_file(f"Task ID: {task_id}")
        self._log_to_file(f"Timestamp: {datetime.now().isoformat()}")
        self._log_to_file(f"Provider: {self.provider}")
        self._log_to_file(f"Model: {self.model}")
        self._log_to_file(f"Max Regenerations: {self.max_regenerations}")

    def _load_workflow_activities(self) -> None:
        """Load activities from workflows directory into semantic index.

        Scans workflows/ for activities.py files and indexes them for
        semantic search to find similar existing implementations.
        """
        from pathlib import Path
        import re

        try:
            from .semantic_search import SemanticActivityIndex
            self._workflow_index = SemanticActivityIndex()
        except ImportError:
            return  # sentence-transformers not installed

        workflows_dir = Path("workflows")
        if not workflows_dir.exists():
            return

        activities = []

        for workflow_dir in workflows_dir.iterdir():
            if not workflow_dir.is_dir() or workflow_dir.name.startswith("."):
                continue

            activities_file = workflow_dir / "activities.py"
            if not activities_file.exists():
                continue

            content = activities_file.read_text()

            # Extract function definitions with docstrings
            # Pattern: async def func_name(...): """docstring"""
            func_pattern = r'(?:async\s+)?def\s+(\w+)\s*\([^)]*\)[^:]*:\s*(?:"""([^"]*?)"""|\'\'\'([^\']*?)\'\'\')?'
            matches = re.findall(func_pattern, content, re.DOTALL)

            for match in matches:
                func_name = match[0]
                docstring = (match[1] or match[2] or "").strip()

                if func_name.startswith("_"):
                    continue  # Skip private functions

                # Extract tags from workflow directory name
                tags = workflow_dir.name.replace("_", " ").split()

                # Store source code for later retrieval
                # Extract the full function source
                func_source = self._extract_function_source(content, func_name)
                if func_source:
                    self._workflow_sources[func_name] = func_source

                description = docstring[:200] if docstring else f"Activity from {workflow_dir.name}"
                activities.append((func_name, description, tags, func_source or ""))

        if activities:
            self._workflow_index.add_activities_batch(activities)

    def _extract_function_source(self, content: str, func_name: str) -> str | None:
        """Extract complete function source code from file content."""
        import re

        # Find function start - use DOTALL to match multi-line signatures
        pattern = rf'^((?:async\s+)?def\s+{re.escape(func_name)}\s*\(.*?\)\s*(?:->\s*[^:]+)?\s*:)'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if not match:
            return None

        # Start from the matched function definition
        start = match.start()
        end_of_signature = match.end()
        lines = content[start:].split("\n")

        # Find the line where the signature ends (contains ':')
        signature_lines = content[start:end_of_signature].split("\n")
        func_lines = signature_lines.copy()

        # Get base indentation from the 'def' line
        base_indent = len(lines[0]) - len(lines[0].lstrip())

        # Continue from after the signature
        remaining_lines = lines[len(signature_lines):]
        in_function_body = True

        for line in remaining_lines:
            # Empty lines are part of function
            if not line.strip():
                func_lines.append(line)
                continue

            # Check indentation
            current_indent = len(line) - len(line.lstrip())

            # Stop when we hit a line at base level or less (next function/class/etc)
            if current_indent <= base_indent and line.strip():
                break

            func_lines.append(line)

        return "\n".join(func_lines)

    def _add_to_workflow_semantic_index(self, result: FactoryResult) -> None:
        """Add newly generated activities to semantic index for future matching.

        Args:
            result: Successful FactoryResult with generated code
        """
        if not self._workflow_index or not result.generated:
            return

        import re

        activities_code = result.generated.activities_code
        if not activities_code:
            return

        # Extract function definitions
        func_pattern = r'(?:async\s+)?def\s+(\w+)\s*\([^)]*\)[^:]*:\s*(?:"""([^"]*?)"""|\'\'\'([^\']*?)\'\'\')?'
        matches = re.findall(func_pattern, activities_code, re.DOTALL)

        activities_to_add = []
        for match in matches:
            func_name = match[0]
            docstring = (match[1] or match[2] or "").strip()

            if func_name.startswith("_"):
                continue

            # Skip if already in index
            if func_name in self._workflow_sources:
                continue

            # Extract source code
            func_source = self._extract_function_source(activities_code, func_name)
            if func_source:
                self._workflow_sources[func_name] = func_source

            # Create description from docstring or plan
            description = docstring[:200] if docstring else ""
            if not description and result.plan:
                # Try to find matching activity in plan for description
                for activity in result.plan.activities:
                    if activity.name == func_name:
                        description = activity.description
                        break

            # Extract tags from workflow name
            tags = []
            if result.plan:
                tags = result.plan.name.lower().replace("_", " ").split()[:3]

            activities_to_add.append((func_name, description, tags, func_source or ""))
            self._log(f"[Semantic] Added '{func_name}' to semantic index")

        if activities_to_add:
            self._workflow_index.add_activities_batch(activities_to_add)

    async def generate(
        self,
        task_description: str,
        examples: list[Any] | None = None
    ) -> FactoryResult:
        """Generate workflow from natural language description.

        This method uses a two-level regeneration strategy:
        1. OUTER LOOP (Planner): Regenerates workflow structure if YAML validation fails
        2. INNER LOOP (Coder): Regenerates Python activities if execution validation fails

        This ensures:
        - YAML errors → regenerate Planner (creates new YAML)
        - Python/execution errors → regenerate Coder only (keeps valid YAML)

        Args:
            task_description: Natural language description of the workflow
            examples: Optional list of TaskInput examples for multi-example compilation

        Returns:
            FactoryResult with generated code and validation status
        """
        result = FactoryResult(success=False)
        metrics = AdapterMetrics()

        # Store examples for use in coder prompt
        self._current_examples = examples or []

        # Set up log file for this compilation
        task_id = "compilation"
        if examples and hasattr(examples[0], 'task_id'):
            task_id = examples[0].task_id
        self._setup_log_file(task_id)

        # Log task description
        self._log_to_file(task_description, section="TASK DESCRIPTION")

        # Create agents (planner gets registry for template search)
        planner, coder, _ = create_agents(
            provider=self.provider,
            model=self.model,
            registry=self.registry,
            canary_token=self.canary_token,
        )

        # Track total regeneration attempts (Planner + Coder combined)
        total_regeneration_count = 0

        # =======================================================================
        # OUTER LOOP: Planner regeneration (for YAML structure errors)
        # =======================================================================
        planner_error_feedback = ""
        for planner_attempt in range(self.max_regenerations + 1):
            # Step 1: Planning Agent -> WorkflowSpec
            self._log(f"[Planning] Attempt {planner_attempt + 1}: Designing workflow structure...")

            planner_prompt = self._build_planner_prompt(task_description, planner_error_feedback)

            # Log planner prompt to file
            self._log_to_file(planner_prompt, section=f"PLANNER PROMPT (Attempt {planner_attempt + 1})")

            if self.verbose:
                print("\n" + "="*80)
                print(f"PLANNER PROMPT (Attempt {planner_attempt + 1}):")
                print("="*80)
                print(planner_prompt)
                print("="*80 + "\n")

            start_time = time.perf_counter()
            plan_result = await run_agent_with_retry(planner, planner_prompt)
            latency_ms = (time.perf_counter() - start_time) * 1000

            result.plan = plan_result.data

            # Track metrics for planner call
            input_tokens, output_tokens = extract_usage_from_result(plan_result)
            metrics.record(input_tokens, output_tokens, latency_ms)

            # Log planner output
            self._log_to_file(
                f"Workflow ID: {result.plan.workflow_id}\n"
                f"Name: {result.plan.name}\n"
                f"Description: {result.plan.description}\n"
                f"Activities: {[a.name for a in result.plan.activities]}\n"
                f"Pattern: {result.plan.execution_pattern}\n"
                f"Tokens: {input_tokens} in / {output_tokens} out",
                section=f"PLANNER OUTPUT (Attempt {planner_attempt + 1})"
            )

            self._log(f"[Planning] Created: {result.plan.name}")
            self._log(f"[Planning] Activities: {[a.name for a in result.plan.activities]}")
            self._log(f"[Planning] Pattern: {result.plan.execution_pattern}")

            # Validate YAML from Planner IMMEDIATELY (before calling Coder)
            # Create a temporary GeneratedFiles just to validate the YAML
            result.generated = GeneratedFiles(
                workflow_yaml=result.plan.workflow_yaml or "",
                activities_code=""
            )

            yaml_error = self._validate_yaml(result)

            if yaml_error is not None:
                # YAML invalid - regenerate PLANNER
                planner_error_feedback = f"YAML VALIDATION ERROR:\n{yaml_error}"
                result.validation_errors.append(f"Planner Attempt {planner_attempt + 1} - YAML: {yaml_error}")
                self._log(f"[Validation] YAML from Planner invalid: {yaml_error[:100]}...")
                self._log_to_file(yaml_error, section=f"YAML VALIDATION ERROR (Planner Attempt {planner_attempt + 1})")

                total_regeneration_count += 1
                continue  # Regenerate PLANNER

            # YAML is valid!
            result.yaml_validated = True
            self._log(f"[Validation] YAML valid on Planner attempt {planner_attempt + 1}")

            # ===================================================================
            # INNER LOOP: Coder regeneration (for Python/execution errors)
            # ===================================================================
            coder_error_feedback = ""
            for coder_attempt in range(self.max_regenerations + 1):
                self._log(f"[Coding] Attempt {coder_attempt + 1}: Generating Python activities...")

                coder_prompt = self._build_coder_prompt(result.plan, coder_error_feedback)

                # Log coder prompt to file
                self._log_to_file(coder_prompt, section=f"CODER PROMPT (Planner {planner_attempt + 1}, Coder {coder_attempt + 1})")

                if self.verbose:
                    print("\n" + "="*80)
                    print(f"CODER PROMPT (Planner {planner_attempt + 1}, Coder {coder_attempt + 1}):")
                    print("="*80)
                    print(coder_prompt)
                    print("="*80 + "\n")

                start_time = time.perf_counter()
                code_result = await run_agent_with_retry(coder, coder_prompt)
                latency_ms = (time.perf_counter() - start_time) * 1000

                result.generated = code_result.data

                # Use YAML from Planner (Coder only generates Python activities)
                result.generated.workflow_yaml = result.plan.workflow_yaml or ""

                result.regeneration_count = total_regeneration_count

                # Track metrics for coder call
                input_tokens, output_tokens = extract_usage_from_result(code_result)
                metrics.record(input_tokens, output_tokens, latency_ms)

                # Log generated code
                self._log_to_file(
                    f"Workflow YAML (from Planner):\n{result.generated.workflow_yaml}\n\n"
                    f"Activities Code (from Coder):\n{result.generated.activities_code}",
                    section=f"GENERATED CODE (Planner {planner_attempt + 1}, Coder {coder_attempt + 1})"
                )

                # Execution validation (if examples available)
                if self._current_examples:
                    self._log(f"[Validation] Testing on {len(self._current_examples[:3])} examples...")

                    execution_error = await self._validate_execution(result, self._current_examples)

                    if execution_error is not None:
                        # Execution failed - regenerate CODER only
                        coder_error_feedback = execution_error
                        result.validation_errors.append(
                            f"Coder Attempt {coder_attempt + 1} (Planner {planner_attempt + 1}) - Execution: {execution_error[:500]}..."
                        )
                        self._log(f"[Validation] Execution failed: {execution_error[:200]}...")
                        self._log_to_file(
                            execution_error,
                            section=f"EXECUTION VALIDATION ERROR (Planner {planner_attempt + 1}, Coder {coder_attempt + 1})"
                        )

                        result.examples_tested = len([
                            ex for ex in self._current_examples[:3]
                            if hasattr(ex, 'metadata') and ex.metadata and "expected_output" in ex.metadata
                        ])
                        total_regeneration_count += 1
                        continue  # Regenerate CODER only

                    result.execution_validated = True
                    result.examples_tested = len([
                        ex for ex in self._current_examples[:3]
                        if hasattr(ex, 'metadata') and ex.metadata and "expected_output" in ex.metadata
                    ])
                    self._log(f"[Validation] All example executions passed!")
                    self._log_to_file(
                        "All examples passed!",
                        section=f"EXECUTION VALIDATION SUCCESS (Planner {planner_attempt + 1}, Coder {coder_attempt + 1})"
                    )

                # SUCCESS! Both YAML and execution valid (or no examples to test)
                result.success = True
                result.regeneration_count = total_regeneration_count
                break  # Exit inner (Coder) loop

            # Check if we succeeded in the inner loop
            if result.success:
                break  # Exit outer (Planner) loop

            # Inner loop exhausted without success - try regenerating Planner with different design
            if not result.success and coder_attempt >= self.max_regenerations:
                planner_error_feedback = (
                    "CODER FAILED REPEATEDLY:\n"
                    "The Coder could not generate valid Python activities for your workflow design.\n"
                    "Please try a DIFFERENT activity design with clearer schemas or simpler logic.\n"
                    f"Last error: {coder_error_feedback[:500] if coder_error_feedback else 'Unknown'}"
                )
                total_regeneration_count += 1
                self._log("[Planner] Coder exhausted - trying different workflow design...")

        # After both loops: set metrics
        result.metrics = metrics
        result.regeneration_count = total_regeneration_count

        if not result.success:
            self._log("[Validation] Max regenerations reached without success")

        # Log final result
        if result.success:
            self._log_to_file(
                f"SUCCESS!\n"
                f"YAML Validated: {result.yaml_validated}\n"
                f"Execution Validated: {result.execution_validated}\n"
                f"Examples Tested: {result.examples_tested}\n"
                f"Total Regeneration Count: {total_regeneration_count}\n"
                f"Total Tokens: {metrics.total_tokens}",
                section="FINAL RESULT"
            )
        else:
            self._log_to_file(
                f"FAILED!\n"
                f"Total Regeneration Count: {total_regeneration_count}\n"
                f"Validation Errors:\n" + "\n".join(result.validation_errors),
                section="FINAL RESULT"
            )

        # Auto-register successful activities
        if result.success and self.registrar:
            self._register_activities(result, task_description)

        # Add to semantic index for future similarity matching
        if result.success and result.generated:
            self._add_to_workflow_semantic_index(result)

        return result

    async def generate_function_call_workflow(
        self,
        task_description: str,
        task_id: str = "function_call_task",
        examples: list[Any] | None = None,
        coder_model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> FactoryResult:
        """Generate workflow for function-calling tasks using a template.

        This method SKIPS the Planner and uses a fixed YAML template for simple
        function-calling tasks (tasks with `functions` in context). This saves
        ~15-20K tokens and ~20-30s latency per task.

        Only the Coder agent runs to generate the Python activity implementation.
        Works with any dataset that follows the function-calling pattern.

        Args:
            task_description: Natural language description with function schemas
            task_id: Task identifier for logging and workflow_id
            examples: Optional list of TaskInput examples for validation
            coder_model: Optional model override for Coder (e.g., "claude-3-5-haiku-20241022" for faster/cheaper)
            temperature: Model temperature (0.0 = deterministic, lower = less verbose)
            max_tokens: Maximum output tokens (limits response length)

        Returns:
            FactoryResult with generated code and validation status
        """
        result = FactoryResult(success=False)
        metrics = AdapterMetrics()

        # Store examples for use in coder prompt
        self._current_examples = examples or []

        # Set up log file for this compilation
        self._setup_log_file(task_id)
        self._log_to_file(task_description, section="TASK DESCRIPTION")

        # Use template YAML - SKIP PLANNER entirely!
        workflow_yaml = FUNCTION_CALL_TEMPLATE.format(workflow_id=task_id)

        self._log(f"[Template] Using fixed YAML template (skipping Planner)")
        self._log_to_file(workflow_yaml, section="TEMPLATE YAML (No Planner)")

        # Create minimal WorkflowSpec for compatibility
        from .models import WorkflowSpec, WorkflowVariable, ActivitySpec, ActivityInputParam, ActivityOutputSchema

        result.plan = WorkflowSpec(
            workflow_id=task_id,
            name="Function Call Extractor",
            description="Extract function name and parameters from natural language query",
            variables=[
                WorkflowVariable(name="prompt", default_value=None),
                WorkflowVariable(name="functions", default_value=None),
            ],
            activities=[
                ActivitySpec(
                    name="extract_function_call",
                    description="Parse natural language query and extract function call with parameters",
                    inputs=[
                        ActivityInputParam(
                            name="prompt",
                            type="str",
                            description="The natural language query containing the function call request"
                        ),
                        ActivityInputParam(
                            name="functions",
                            type="list",
                            description="List of available function definitions with their parameter schemas"
                        ),
                    ],
                    output=ActivityOutputSchema(
                        type="dict",
                        description="Returns a dict with function name as key and parameters as nested dict value",
                        fields={"function_name": "dict[str, Any]"}
                    ),
                )
            ],
            execution_pattern="sequence",
            reasoning="BFCL template: single activity for function call extraction",
            workflow_yaml=workflow_yaml,
        )

        # Create Coder agent only (optionally with lighter model)
        effective_model = coder_model or self.model
        _, coder, _ = create_agents(
            provider=self.provider,
            model=effective_model,
            registry=self.registry,
            canary_token=self.canary_token,
        )

        if coder_model:
            self._log(f"[Template] Using lighter model for Coder: {coder_model}")

        # Build model settings for temperature/max_tokens control
        model_settings: ModelSettings | None = None
        if temperature is not None or max_tokens is not None:
            settings_dict = {}
            if temperature is not None:
                settings_dict["temperature"] = temperature
            if max_tokens is not None:
                settings_dict["max_tokens"] = max_tokens
            model_settings = ModelSettings(**settings_dict)
            self._log(f"[Template] Model settings: temperature={temperature}, max_tokens={max_tokens}")

        # Track total regeneration attempts
        total_regeneration_count = 0

        # Coder regeneration loop (no Planner loop since YAML is fixed)
        coder_error_feedback = ""
        for coder_attempt in range(self.max_regenerations + 1):
            self._log(f"[Coding] Attempt {coder_attempt + 1}: Generating Python activity...")

            coder_prompt = self._build_function_call_coder_prompt(task_description, coder_error_feedback)

            self._log_to_file(coder_prompt, section=f"FUNCTION CALL CODER PROMPT (Attempt {coder_attempt + 1})")

            if self.verbose:
                print("\n" + "="*80)
                print(f"FUNCTION CALL CODER PROMPT (Attempt {coder_attempt + 1}):")
                print("="*80)
                print(coder_prompt)
                print("="*80 + "\n")

            start_time = time.perf_counter()
            code_result = await run_agent_with_retry(
                coder, coder_prompt, model_settings=model_settings
            )
            latency_ms = (time.perf_counter() - start_time) * 1000

            result.generated = code_result.data
            result.generated.workflow_yaml = workflow_yaml  # Use template YAML
            result.regeneration_count = total_regeneration_count

            # Track metrics
            input_tokens, output_tokens = extract_usage_from_result(code_result)
            metrics.record(input_tokens, output_tokens, latency_ms)

            self._log_to_file(
                f"Workflow YAML (template):\n{workflow_yaml}\n\n"
                f"Activities Code (from Coder):\n{result.generated.activities_code}",
                section=f"GENERATED CODE (Attempt {coder_attempt + 1})"
            )

            # YAML is pre-validated (it's a template), so mark as valid
            result.yaml_validated = True

            # Execution validation (if examples available)
            if self._current_examples:
                self._log(f"[Validation] Testing on {len(self._current_examples[:3])} examples...")

                execution_error = await self._validate_execution(result, self._current_examples)

                if execution_error is not None:
                    coder_error_feedback = execution_error
                    result.validation_errors.append(
                        f"Coder Attempt {coder_attempt + 1} - Execution: {execution_error[:500]}..."
                    )
                    self._log(f"[Validation] Execution failed: {execution_error[:200]}...")
                    self._log_to_file(execution_error, section=f"EXECUTION VALIDATION ERROR (Attempt {coder_attempt + 1})")

                    result.examples_tested = len([
                        ex for ex in self._current_examples[:3]
                        if hasattr(ex, 'metadata') and ex.metadata and "expected_output" in ex.metadata
                    ])
                    total_regeneration_count += 1
                    continue  # Regenerate Coder

                result.execution_validated = True
                result.examples_tested = len([
                    ex for ex in self._current_examples[:3]
                    if hasattr(ex, 'metadata') and ex.metadata and "expected_output" in ex.metadata
                ])
                self._log(f"[Validation] All example executions passed!")
                self._log_to_file("All examples passed!", section=f"EXECUTION VALIDATION SUCCESS (Attempt {coder_attempt + 1})")

            # SUCCESS!
            result.success = True
            result.regeneration_count = total_regeneration_count
            break

        # Set final metrics
        result.metrics = metrics

        if not result.success:
            self._log("[Validation] Max regenerations reached without success")

        # Log final result
        if result.success:
            self._log_to_file(
                f"SUCCESS (Function Call Template)!\n"
                f"YAML Validated: {result.yaml_validated}\n"
                f"Execution Validated: {result.execution_validated}\n"
                f"Examples Tested: {result.examples_tested}\n"
                f"Total Regeneration Count: {total_regeneration_count}\n"
                f"Total Tokens: {metrics.total_tokens}\n"
                f"Tokens Saved: ~15-20K (skipped Planner)",
                section="FINAL RESULT"
            )
        else:
            self._log_to_file(
                f"FAILED (Function Call Template)!\n"
                f"Total Regeneration Count: {total_regeneration_count}\n"
                f"Validation Errors:\n" + "\n".join(result.validation_errors),
                section="FINAL RESULT"
            )

        # Auto-register successful activities
        if result.success and self.registrar:
            self._register_activities(result, task_description)

        # Add to semantic index
        if result.success and result.generated:
            self._add_to_workflow_semantic_index(result)

        return result

    def _build_function_call_coder_prompt(self, task_description: str, error_feedback: str = "") -> str:
        """Build a concise coder prompt for function-calling tasks.

        Optimized for minimal tokens while maintaining accuracy.
        """
        base_prompt = f"""Generate `extract_function_call` activity. Return ONLY `{{"func_name": {{params}}}}`.

## Task:
{task_description}

## Requirements:
- Return format: `{{"function_name": {{"param1": val1}}}}` - NO extra fields
- Extract values using JSON parsing, regex, or string matching (no LLM calls)
- Parse inputs defensively (prompt/functions may be JSON strings)
- Match parameter names EXACTLY from function schema

## Template:
```python
import re, json
from typing import Any

async def extract_function_call(prompt: str, functions: list, **kwargs) -> dict[str, Any]:
    # Parse inputs (may be JSON strings)
    try:
        data = json.loads(prompt) if isinstance(prompt, str) else prompt
        query = data.get("question", [[{{"content": prompt}}]])[0][0].get("content", str(prompt))
    except: query = str(prompt)

    funcs = json.loads(functions) if isinstance(functions, str) else functions
    func = funcs[0] if funcs else {{}}
    name = func.get("name", "")
    props = func.get("parameters", {{}}).get("properties", {{}})

    # Extract params - use regex for numbers, string matching for text
    params = {{}}
    # ... extract values from query based on props schema ...

    return {{name: params}}
```
"""

        if error_feedback:
            base_prompt += f"\n## FIX: {error_feedback[:300]}"

        return base_prompt

        return base_prompt

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

    def _build_planner_prompt(
        self, task_description: str, error_feedback: str = ""
    ) -> str:
        """Build prompt for planner agent, including any error feedback.

        Args:
            task_description: Original task description
            error_feedback: Previous validation error (e.g., YAML parsing failure)

        Returns:
            Formatted prompt string for the planner agent
        """
        prompt = task_description
        if error_feedback:
            prompt += f"""

**PREVIOUS ATTEMPT FAILED - PLEASE FIX:**
{error_feedback}

Fix the issues above and regenerate a valid workflow YAML.
Common fixes:
- Ensure 'variables' is a mapping (key: value), not a list
- Use null as default values for variables
- Use proper ${{{{ variable_name }}}} syntax in params
- Ensure all activities have valid 'name' and 'params' fields
- Use block scalars (|) for multi-line strings
"""
        return prompt

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

        # Add semantically similar activities as inspiration
        semantic_section = self._build_semantic_inspiration_section(plan)
        if semantic_section:
            base_prompt += f"\n{semantic_section}"

        # Add examples section if multiple examples are available
        examples_section = self._build_examples_section()
        if examples_section:
            base_prompt += f"\n{examples_section}"

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

    def _build_semantic_inspiration_section(self, plan: WorkflowSpec, min_similarity: float = 0.5) -> str:
        """Build section with semantically similar activities as inspiration.

        Uses the semantic search index to find existing workflow activities
        that are similar to what we're trying to generate.

        Args:
            plan: WorkflowSpec with activities to find matches for
            min_similarity: Minimum similarity threshold (0 to 1)

        Returns:
            Formatted section with similar activity source code
        """
        if not self._workflow_index:
            return ""

        section = ""
        seen_activities = set()

        for activity in plan.activities:
            # Search for similar activities using the activity description
            query = f"{activity.name} {activity.description}"
            results = self._workflow_index.search(query, k=1)

            if not results:
                continue

            top_match = results[0]

            # Skip if below threshold or already seen
            if top_match.similarity < min_similarity:
                continue
            if top_match.template_name in seen_activities:
                continue

            seen_activities.add(top_match.template_name)

            # Get the source code
            source = self._workflow_sources.get(top_match.template_name)
            if not source:
                continue

            if not section:
                section = "\n## SIMILAR EXISTING ACTIVITIES (use as inspiration):\n\n"
                section += "These are real working activities from your codebase that are semantically similar.\n"
                section += "Study their patterns and adapt them for your implementation.\n\n"

            section += f"### {top_match.template_name} (similarity: {top_match.similarity:.0%})\n"
            section += f"Similar to your activity: **{activity.name}**\n"
            section += "```python\n"
            section += source.strip()
            section += "\n```\n\n"

        return section

    def _build_examples_section(self) -> str:
        """Build examples section for coder prompt showing I/O patterns.

        Returns:
            Formatted examples section, or empty string if no examples
        """
        if not self._current_examples:
            return ""

        section = "\n## EXAMPLE INPUT/OUTPUT PATTERNS:\n\n"
        if len(self._current_examples) > 1:
            section += "Use these examples to understand expected behavior and generalize your implementation:\n\n"
        else:
            section += "Use this example to understand expected input/output behavior:\n\n"

        # Limit to 3 examples for prompt size management
        for idx, example in enumerate(self._current_examples[:3], 1):
            section += f"### Example {idx}:\n"

            # Show input variables
            if hasattr(example, 'context') and example.context:
                section += "**Input Variables:**\n```json\n"
                # Truncate large values to keep prompt size reasonable
                truncated_context = {}
                for key, value in example.context.items():
                    value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                    if len(value_str) > 150:
                        value_str = value_str[:150] + "..."
                    truncated_context[key] = value if len(json.dumps(value)) <= 150 else value_str
                section += json.dumps(truncated_context, indent=2)
                section += "\n```\n"

            # Show expected output
            if hasattr(example, 'metadata') and example.metadata and "expected_output" in example.metadata:
                expected = example.metadata["expected_output"]
                section += "**Expected Output:**\n```json\n"
                # Truncate if too large
                expected_str = json.dumps(expected, indent=2)
                if len(expected_str) > 150:
                    expected_str = expected_str[:150] + "..."
                section += expected_str
                section += "\n```\n\n"

        section += "**CRITICAL:** Your implementation must generalize to handle all these patterns correctly.\n"
        return section

    def _select_evaluator(self, expected_output: Any, metadata: dict, use_llm: bool = True) -> Evaluator:
        """Auto-select appropriate evaluator based on output type.

        Args:
            expected_output: The expected output to evaluate against
            metadata: Task metadata (may contain evaluator_type override)
            use_llm: Whether to use LLM-based evaluation (default: True)

        Returns:
            Appropriate evaluator instance
        """
        # Use LLM evaluator for format checking during regeneration
        if use_llm:
            return get_evaluator("llm")

        # Check for explicit override
        if "evaluator_type" in metadata:
            return get_evaluator(metadata["evaluator_type"])

        # Auto-detect from output type
        if isinstance(expected_output, (dict, list)):
            return get_evaluator("json_match")
        else:
            return get_evaluator("fuzzy_match", threshold=0.85)

    async def _execute_single_example(
        self,
        factory_result: FactoryResult,
        example: Any  # TaskInput
    ) -> dict[str, Any]:
        """Execute workflow on a single example.

        Args:
            factory_result: FactoryResult with compiled workflow
            example: TaskInput with context and expected output

        Returns:
            Dict with success, output, and optional error
        """
        import shutil

        try:
            # Load activities dynamically
            loader = DynamicModuleLoader()
            llm_client = create_client(
                provider=self.provider,
                config=LLMConfig(model=self.model, temperature=0.0, max_tokens=4096)
            )

            activities = loader.load(
                activities_code=factory_result.activities_code,
                workflow_id=factory_result.plan.workflow_id,
                llm_client=llm_client
            )

            # Create executor
            executor = LocalWorkflowExecutor(
                mock_activities=activities,
                dry_run=False,
                verbose=False  # Quiet during validation
            )

            # Prepare variables from context
            variables = {}

            # Always include the prompt/input as a variable (matches final execution)
            if hasattr(example, 'prompt'):
                variables["prompt"] = example.prompt

            if hasattr(example, 'context') and example.context:
                for key, value in example.context.items():
                    if isinstance(value, (dict, list)):
                        variables[key] = value
                    else:
                        variables[key] = str(value)

            # Write YAML to temp file
            temp_dir = tempfile.mkdtemp(prefix="code_factory_validation_")
            workflow_file = Path(temp_dir) / "workflow.yaml"
            workflow_file.write_text(factory_result.workflow_yaml)

            # Parse YAML to find the result variable name
            import yaml
            result_var_name = None
            try:
                workflow_data = yaml.safe_load(factory_result.workflow_yaml)
                if "root" in workflow_data and "sequence" in workflow_data["root"]:
                    elements = workflow_data["root"]["sequence"].get("elements", [])
                    for element in reversed(elements):  # Get last result variable
                        if "activity" in element and "result" in element["activity"]:
                            result_var_name = element["activity"]["result"]
                            break
            except:
                pass  # If parsing fails, fall back to heuristics

            try:
                # Execute with timeout
                import asyncio
                exec_output = await asyncio.wait_for(
                    executor.run_yaml(str(workflow_file), variables=variables),
                    timeout=30.0
                )

                # Extract output
                output = self._extract_output_from_execution(exec_output, result_var_name)

                return {"success": True, "output": output}

            except asyncio.TimeoutError:
                return {"success": False, "error": "Execution timeout (30s)", "output": ""}
            except Exception as e:
                return {"success": False, "error": str(e), "output": ""}
            finally:
                # Cleanup temp directory
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass

        except Exception as e:
            return {"success": False, "error": f"Setup error: {str(e)}", "output": ""}

    def _extract_output_from_execution(self, result: Any, result_var_name: str | None = None) -> str:
        """Extract output from execution result.

        Args:
            result: Execution result from LocalWorkflowExecutor (dict of all variables)
            result_var_name: Optional name of the result variable from YAML parsing

        Returns:
            String representation of output
        """
        # LocalWorkflowExecutor returns all variables, we need to find the output
        if isinstance(result, dict):
            # If we know the exact result variable name, use it
            if result_var_name and result_var_name in result:
                output = result[result_var_name]
                if isinstance(output, (dict, list)):
                    return json.dumps(output)
                return str(output)

            # Fallback: Look for keys containing common output terms
            output_terms = ["category", "classification", "result", "output", "response", "answer",
                           "extracted", "normalized", "transformed", "formatted", "email", "address"]

            for term in output_terms:
                for key, value in result.items():
                    if term in key.lower():
                        # Found a likely output field
                        if isinstance(value, (dict, list)):
                            return json.dumps(value)
                        return str(value)

            # Last resort: return whole dict as JSON
            return json.dumps(result)
        elif isinstance(result, str):
            return result
        else:
            return str(result)

    async def _validate_execution(
        self,
        result: FactoryResult,
        examples: list[Any]
    ) -> str | None:
        """Execute workflow on examples and validate output FORMAT using LLM (haiku).

        During regeneration, we use LLM evaluation to check:
        - format_correct: Does output match expected structure?
        - content_correct: Does output have correct values?

        We accept format_match or better (format correct even if values wrong).
        This is more lenient during compilation - final evaluation is stricter.

        Args:
            result: FactoryResult with compiled workflow
            examples: List of TaskInput examples with expected outputs

        Returns:
            Error message string if validation fails, None if all pass
        """
        # Only test examples with expected outputs
        test_examples = [
            ex for ex in examples[:3]  # Limit to 3 for speed
            if hasattr(ex, 'metadata') and ex.metadata and "expected_output" in ex.metadata
        ]

        if not test_examples:
            self._log("[Validation] No examples with expected outputs - skipping execution validation")
            return None

        failures = []

        # Use LLM evaluator (haiku) for format validation
        evaluator = self._select_evaluator(None, {}, use_llm=True)

        for idx, example in enumerate(test_examples, 1):
            try:
                # Execute workflow
                exec_result = await self._execute_single_example(result, example)

                if not exec_result["success"]:
                    failures.append(
                        f"Example {idx}/{len(test_examples)} - Execution Error:\n"
                        f"  {exec_result.get('error', 'Unknown error')}"
                    )
                    break  # Stop at first failure

                # Evaluate output using LLM
                expected = example.metadata["expected_output"]
                output_format = example.metadata.get("output_format", {})

                eval_result = evaluator.evaluate(
                    output=exec_result["output"],
                    expected=expected,
                    output_format=output_format,
                )

                # During regeneration, accept if format is correct (format_match or better)
                # match_type: total_match (1.0), content_match (0.8), format_match (0.3), failure (0.0)
                format_correct = eval_result.details.get("format_correct", False)
                match_type = eval_result.details.get("match_type", "failure")

                if self.verbose:
                    self._log(f"[Validation] Example {idx}: {match_type} (format_correct={format_correct})")

                # Accept format_match or better during compilation
                if not format_correct and match_type == "failure":
                    failures.append(self._format_evaluation_failure(
                        idx, len(test_examples), example, exec_result, eval_result
                    ))
                    break  # Stop at first failure

            except Exception as e:
                failures.append(
                    f"Example {idx}/{len(test_examples)} - Unexpected Error:\n"
                    f"  {str(e)}"
                )
                break

        if failures:
            return self._format_validation_feedback(failures, len(test_examples))

        return None  # All examples passed

    def _format_evaluation_failure(
        self,
        example_num: int,
        total: int,
        example: Any,
        exec_result: dict,
        eval_result: EvaluationResult
    ) -> str:
        """Format evaluation failure into actionable feedback.

        Args:
            example_num: Which example failed (1-indexed)
            total: Total number of examples tested
            example: The TaskInput that failed
            exec_result: Execution result dict
            eval_result: Evaluation result (from LLM evaluator)

        Returns:
            Formatted error message
        """
        # Extract LLM evaluation details
        match_type = eval_result.details.get("match_type", "failure")
        format_correct = eval_result.details.get("format_correct", False)
        content_correct = eval_result.details.get("content_correct", False)
        explanation = eval_result.details.get("explanation", "")

        msg = f"Example {example_num}/{total} FAILED (LLM eval: {match_type}):\n"

        # Show inputs
        if hasattr(example, 'context') and example.context:
            msg += "  Input: "
            input_str = json.dumps(example.context, indent=4)
            # Indent continuation lines
            msg += input_str.replace("\n", "\n         ")
            msg += "\n"

        # Show expected vs actual
        expected = example.metadata["expected_output"]
        msg += "  Expected: " + json.dumps(expected, indent=4).replace("\n", "\n            ") + "\n"

        # Format actual output - try to parse as JSON for better readability
        actual_output = exec_result["output"]
        try:
            actual_parsed = json.loads(actual_output)
            actual_formatted = json.dumps(actual_parsed, indent=4).replace("\n", "\n            ")
        except (json.JSONDecodeError, TypeError):
            # Not JSON, show raw output (truncated if very long)
            actual_formatted = actual_output[:1000] if len(actual_output) > 1000 else actual_output

        msg += "  Actual:   " + actual_formatted + "\n"

        # Show LLM evaluation summary
        msg += f"\n  LLM Evaluation:\n"
        msg += f"    - Match type: {match_type}\n"
        msg += f"    - Format correct: {format_correct}\n"
        msg += f"    - Content correct: {content_correct}\n"
        if explanation:
            msg += f"    - Explanation: {explanation}\n"

        # Show field-level matches if available
        field_matches = eval_result.details.get("field_matches", {})
        if field_matches:
            msg += "    - Field matches:\n"
            for field, matched in field_matches.items():
                status = "✓" if matched else "✗"
                msg += f"      {status} {field}\n"

        # Show error if any
        if eval_result.error:
            msg += f"  Error: {eval_result.error}\n"

        return msg

    def _format_validation_feedback(
        self,
        failures: list[str],
        total_examples: int
    ) -> str:
        """Format all failures into regeneration feedback.

        Args:
            failures: List of formatted failure messages
            total_examples: Total number of examples tested

        Returns:
            Complete feedback message for coder
        """
        feedback = "EXECUTION VALIDATION FAILED (LLM-based format check):\n"
        feedback += "Output format does not match expected structure.\n\n"

        for failure in failures:
            feedback += failure + "\n"

        feedback += f"\nFix these FORMAT issues:\n"
        feedback += "1. Ensure output has EXACTLY the right field names (check spelling, casing)\n"
        feedback += "2. Return the correct data types (string vs number, nested objects)\n"
        feedback += "3. Don't add extra fields that weren't requested\n"
        feedback += "4. Don't hardcode values - extract them from the input prompt\n"
        feedback += "5. For LLM-based activities, verify prompts ask for the exact structure\n"

        return feedback

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

    # ==================== BFCL Function Calling ====================

    async def generate_bfcl(
        self,
        user_query: str,
        functions: list[dict] | str,
    ) -> BFCLResult:
        """Generate a function call for BFCL benchmark tasks.

        This method takes a user query and available functions, then uses an
        LLM agent to select the appropriate function and extract parameters.

        Unlike the full workflow generation, this is a simpler single-step
        process optimized for function calling tasks.

        Args:
            user_query: Natural language user request
            functions: List of BFCL function definitions or JSON string

        Returns:
            BFCLResult with function name, arguments, and metrics

        Example:
            >>> factory = CodeFactory()
            >>> result = await factory.generate_bfcl(
            ...     "Find the area of a triangle with base 10 and height 5",
            ...     [{"name": "calculate_triangle_area", "parameters": {...}}]
            ... )
            >>> print(result.function_name)  # "calculate_triangle_area"
            >>> print(result.arguments)  # {"base": 10, "height": 5}
        """
        result = BFCLResult(success=False)
        metrics = AdapterMetrics()

        # Parse functions if JSON string
        if isinstance(functions, str):
            try:
                functions = json.loads(functions)
            except json.JSONDecodeError as e:
                result.error = f"Failed to parse functions JSON: {e}"
                return result

        # Create BFCL agent
        bfcl_agent = create_bfcl_agent(
            provider=self.provider,
            model=self.model,
        )

        # Build prompt with user query and available functions
        prompt = self._build_bfcl_prompt(user_query, functions)

        self._log(f"[BFCL] Processing query: {user_query[:50]}...")

        try:
            start_time = time.perf_counter()
            agent_result = await run_agent_with_retry(bfcl_agent, prompt)
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Track metrics
            input_tokens, output_tokens = extract_usage_from_result(agent_result)
            metrics.record(input_tokens, output_tokens, latency_ms)

            # Extract output
            output: BFCLFunctionCallOutput = agent_result.data

            result.success = True
            result.function_name = output.function_name
            result.arguments = output.arguments
            result.reasoning = output.reasoning
            result.metrics = metrics

            self._log(f"[BFCL] Selected: {output.function_name}")
            self._log(f"[BFCL] Arguments: {output.arguments}")

        except Exception as e:
            result.error = str(e)
            result.metrics = metrics
            self._log(f"[BFCL] Error: {e}")

        return result

    def _build_bfcl_prompt(
        self,
        user_query: str,
        functions: list[dict],
    ) -> str:
        """Build prompt for BFCL function calling agent.

        Args:
            user_query: User's natural language request
            functions: List of available function definitions

        Returns:
            Formatted prompt string
        """
        # Format functions for the prompt
        functions_text = "## Available Functions:\n\n"

        for func in functions:
            functions_text += f"### {func['name']}\n"
            functions_text += f"Description: {func.get('description', 'No description')}\n"

            params = func.get('parameters', {})
            properties = params.get('properties', {})
            required = params.get('required', [])

            if properties:
                functions_text += "Parameters:\n"
                for param_name, param_info in properties.items():
                    param_type = param_info.get('type', 'any')
                    param_desc = param_info.get('description', 'No description')
                    is_required = param_name in required
                    req_str = "(required)" if is_required else "(optional)"
                    functions_text += f"  - {param_name}: {param_type} {req_str} - {param_desc}\n"

            functions_text += "\n"

        prompt = f"""## User Query:
{user_query}

{functions_text}

Based on the user query and available functions, select the most appropriate function and extract the parameter values.

Remember:
- Use EXACT parameter names from the function definition
- Extract values from the user query
- Include optional parameters if mentioned in the query
- Convert types appropriately (strings to numbers, etc.)
"""

        return prompt
