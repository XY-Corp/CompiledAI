"""OpenCode-based workflow generator with per-activity code generation.

Pipeline:
1. Natural language input -> YAML planning (Phase 1)
2. Parse YAML to extract activity specs
3. Generate each activity separately with precise spec (Phase 2)
4. Validate each activity against its spec
5. Assemble activities and run integration test (Phase 3)
6. Iterate on errors until success or max attempts
"""

import ast
import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml

from .models import ActivitySpec, GeneratedActivity, WorkflowSpec
from .prompts import ACTIVITY_GENERATION_PROMPT, YAML_PLANNING_PROMPT, format_fix_prompt
from .runner import OpenCodeOutput, OpenCodeRunner
from .validator import ValidationResult, validate_activity, validate_syntax

logger = logging.getLogger(__name__)


class GenerationStage(Enum):
    """Stages of workflow generation."""

    PLANNING = "planning"
    ACTIVITY_GEN = "activity_generation"
    VALIDATION = "validation"
    FIX = "fix"
    ASSEMBLY = "assembly"


@dataclass
class MetricEntry:
    """Single metric entry for generation tracking."""

    stage: str
    success: bool
    duration_seconds: float
    model: str
    tokens_input: int = 0
    tokens_output: int = 0
    error: Optional[str] = None
    iteration: int = 1
    activity_name: Optional[str] = None  # For per-activity tracking


@dataclass
class GenerationMetrics:
    """Metrics for a workflow generation run."""

    entries: list[MetricEntry] = field(default_factory=list)
    total_time_seconds: float = 0.0
    first_try_success: bool = False
    activities_generated: int = 0
    activities_first_try: int = 0

    def add(self, entry: MetricEntry):
        """Add a metric entry."""
        self.entries.append(entry)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "total_time_seconds": self.total_time_seconds,
            "first_try_success": self.first_try_success,
            "activities_generated": self.activities_generated,
            "activities_first_try": self.activities_first_try,
            "total_iterations": len(
                [e for e in self.entries if e.stage == "validation"]
            ),
            "entries": [
                {
                    "stage": e.stage,
                    "success": e.success,
                    "duration_seconds": e.duration_seconds,
                    "model": e.model,
                    "tokens_input": e.tokens_input,
                    "tokens_output": e.tokens_output,
                    "error": e.error,
                    "iteration": e.iteration,
                    "activity_name": e.activity_name,
                }
                for e in self.entries
            ],
            "stages_summary": self._stages_summary(),
        }

    def _stages_summary(self) -> dict:
        """Summarize by stage."""
        summary = {}
        for entry in self.entries:
            if entry.stage not in summary:
                summary[entry.stage] = {"count": 0, "success": 0, "total_time": 0.0}
            summary[entry.stage]["count"] += 1
            if entry.success:
                summary[entry.stage]["success"] += 1
            summary[entry.stage]["total_time"] += entry.duration_seconds
        return summary


@dataclass
class ValidationIssue:
    """A validation issue found in generated code."""

    validator: str
    severity: str
    message: str
    line: Optional[int] = None
    code: Optional[str] = None


@dataclass
class GenerationResult:
    """Result of a workflow generation attempt."""

    success: bool
    workflow_yaml: str = ""
    activities_code: str = ""
    workflow_path: Optional[Path] = None
    activities_path: Optional[Path] = None
    iterations: int = 0
    errors: list[str] = field(default_factory=list)
    validation_issues: list[ValidationIssue] = field(default_factory=list)
    test_output: str = ""
    total_time_seconds: float = 0.0
    metrics: Optional[GenerationMetrics] = None
    workflow_spec: Optional[WorkflowSpec] = None
    generated_activities: list[GeneratedActivity] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "workflow_yaml": self.workflow_yaml,
            "activities_code": self.activities_code,
            "workflow_path": str(self.workflow_path) if self.workflow_path else None,
            "activities_path": str(self.activities_path) if self.activities_path else None,
            "iterations": self.iterations,
            "errors": self.errors,
            "validation_issues": [
                {
                    "validator": v.validator,
                    "severity": v.severity,
                    "message": v.message,
                    "line": v.line,
                    "code": v.code,
                }
                for v in self.validation_issues
            ],
            "test_output": self.test_output,
            "total_time_seconds": self.total_time_seconds,
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }


class CodeGenerator:
    """Generate CompiledAI workflows using OpenCode with per-activity generation."""

    DEFAULT_MODELS = [
        "anthropic/claude-sonnet-4-5-20250929",
        "anthropic/claude-sonnet-4-20250514",
        "gemini/gemini-2.5-pro",
    ]

    def __init__(
        self,
        model: Optional[str] = None,
        max_iterations: int = 3,
        max_activity_retries: int = 2,
        timeout_per_step: int = 120,
        enable_security_validation: bool = True,
        security_severity_threshold: str = "high",
    ):
        """Initialize the generator.

        Args:
            model: Model to use for generation (None = auto-detect)
            max_iterations: Maximum full workflow iterations
            max_activity_retries: Max retries per activity generation
            timeout_per_step: Timeout for each OpenCode invocation
            enable_security_validation: Whether to run security validators
            security_severity_threshold: Minimum severity to fail
        """
        self.model = model
        self.max_iterations = max_iterations
        self.max_activity_retries = max_activity_retries
        self.timeout_per_step = timeout_per_step
        self.enable_security_validation = enable_security_validation
        self.security_severity_threshold = security_severity_threshold

        self._runner: Optional[OpenCodeRunner] = None
        self._active_model: Optional[str] = None

        # Try to import validators
        self._validators_available = False
        try:
            from compiled_ai.validation import CodeShieldValidator, SASTValidator

            self._validators_available = True
            self._code_validator = CodeShieldValidator(
                severity_threshold=security_severity_threshold
            )
            self._sast_validator = SASTValidator(
                severity_threshold=security_severity_threshold
            )
            logger.info("Security validators loaded successfully")
        except ImportError as e:
            logger.warning(f"Security validators not available: {e}")

    def _get_runner(self) -> OpenCodeRunner:
        """Get or create the OpenCode runner with a working model."""
        if self._runner is not None:
            return self._runner

        models_to_try = [self.model] if self.model else self.DEFAULT_MODELS

        for model in models_to_try:
            try:
                runner = OpenCodeRunner(
                    model=model,
                    timeout=self.timeout_per_step,
                )
                logger.info(f"Using model: {model}")
                self._runner = runner
                self._active_model = model
                return runner
            except Exception as e:
                logger.warning(f"Model {model} not available: {e}")
                continue

        raise RuntimeError(
            f"No working model found. Tried: {models_to_try}. "
            "Ensure OpenCode is installed and configured."
        )

    def generate(
        self,
        task_description: str,
        output_dir: Optional[Path] = None,
        verbose: bool = True,
    ) -> GenerationResult:
        """Generate a workflow from natural language description.

        Args:
            task_description: Natural language description of the workflow
            output_dir: Directory to save generated files (temp dir if None)
            verbose: Whether to print progress

        Returns:
            GenerationResult with generated files and status
        """
        start_time = datetime.now()
        metrics = GenerationMetrics()

        # Create output directory
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = Path(tempfile.mkdtemp(prefix="opencode_workflow_"))

        errors: list[str] = []
        validation_issues: list[ValidationIssue] = []

        if verbose:
            print(f"Generating workflow for: {task_description[:80]}...")
            print(f"Output directory: {output_dir}")

        try:
            runner = self._get_runner()
            runner.working_dir = output_dir
            if verbose:
                print(f"Using model: {self._active_model}")
        except RuntimeError as e:
            logger.error(f"Failed to initialize: {e}")
            return GenerationResult(
                success=False,
                errors=[str(e)],
                total_time_seconds=(datetime.now() - start_time).total_seconds(),
                metrics=metrics,
            )

        # Phase 1: Generate workflow YAML
        if verbose:
            print("\n[Phase 1] Generating workflow YAML...")

        step_start = datetime.now()
        planning_result = runner.run(
            YAML_PLANNING_PROMPT.format(task_description=task_description),
            verbose=verbose,
        )

        metrics.add(
            MetricEntry(
                stage=GenerationStage.PLANNING.value,
                success=planning_result.success,
                duration_seconds=(datetime.now() - step_start).total_seconds(),
                model=self._active_model or "unknown",
                error=planning_result.stderr if not planning_result.success else None,
            )
        )

        if not planning_result.success:
            errors.append(f"Planning failed: {planning_result.stderr}")
            if verbose:
                print(f"Planning failed: {planning_result.stderr}")

        # Parse the generated YAML
        workflow_path = output_dir / "workflow.yaml"
        if not workflow_path.exists():
            return GenerationResult(
                success=False,
                errors=["workflow.yaml not created"],
                total_time_seconds=(datetime.now() - start_time).total_seconds(),
                metrics=metrics,
            )

        workflow_spec = self._parse_workflow_yaml(workflow_path)
        if workflow_spec is None:
            return GenerationResult(
                success=False,
                errors=["Failed to parse workflow.yaml"],
                total_time_seconds=(datetime.now() - start_time).total_seconds(),
                metrics=metrics,
            )

        if verbose:
            print(f"  Parsed {len(workflow_spec.activities)} activities")

        # Phase 2: Generate each activity separately
        if verbose:
            print("\n[Phase 2] Generating activities...")

        generated_activities: list[GeneratedActivity] = []

        for i, spec in enumerate(workflow_spec.activities, 1):
            if verbose:
                print(f"  [{i}/{len(workflow_spec.activities)}] Generating {spec.name}...")

            gen_activity = self._generate_activity(
                spec,
                output_dir,
                metrics,
                verbose=verbose,
            )
            generated_activities.append(gen_activity)
            metrics.activities_generated += 1

            if gen_activity.is_valid and gen_activity.generation_attempts == 1:
                metrics.activities_first_try += 1

            if not gen_activity.is_valid:
                errors.extend(gen_activity.validation_errors)

        # Phase 3: Assembly and Integration Test
        if verbose:
            print("\n[Phase 3] Assembling and testing...")

        activities_path = output_dir / "activities.py"
        assembled_code = self._assemble_activities(
            workflow_spec, generated_activities, activities_path
        )

        # Run integration test
        test_result = self._run_integration_test(activities_path, verbose=verbose)

        if not test_result["success"]:
            errors.append(test_result["error"])
            validation_issues.extend(
                [ValidationIssue(**issue) for issue in test_result.get("validation_issues", [])]
            )

        total_time = (datetime.now() - start_time).total_seconds()
        metrics.total_time_seconds = total_time

        # Determine overall success
        all_activities_valid = all(a.is_valid for a in generated_activities)
        success = all_activities_valid and test_result["success"]

        if all_activities_valid and len(errors) == 0:
            metrics.first_try_success = True

        result = GenerationResult(
            success=success,
            workflow_yaml=workflow_path.read_text() if workflow_path.exists() else "",
            activities_code=assembled_code,
            workflow_path=workflow_path if workflow_path.exists() else None,
            activities_path=activities_path if activities_path.exists() else None,
            iterations=1,  # Per-activity retries tracked separately
            errors=errors,
            validation_issues=validation_issues,
            test_output=test_result.get("output", ""),
            total_time_seconds=total_time,
            metrics=metrics,
            workflow_spec=workflow_spec,
            generated_activities=generated_activities,
        )

        if verbose:
            status = "SUCCESS" if result.success else "FAILED"
            print(f"\n{status} ({total_time:.1f}s)")
            if metrics.first_try_success:
                print("  First-try success!")
            print(
                f"  Activities: {metrics.activities_first_try}/{metrics.activities_generated} first-try"
            )
            if result.success:
                print(f"  Workflow: {workflow_path}")
                print(f"  Activities: {activities_path}")

        logger.info(
            f"Generation complete: success={result.success}, "
            f"activities={metrics.activities_generated}, time={total_time:.1f}s"
        )

        return result

    def _parse_workflow_yaml(self, yaml_path: Path) -> Optional[WorkflowSpec]:
        """Parse workflow YAML and extract activity specs.

        Args:
            yaml_path: Path to workflow.yaml

        Returns:
            WorkflowSpec or None if parsing fails
        """
        try:
            content = yaml_path.read_text()
            data = yaml.safe_load(content)

            if not data or "activities" not in data:
                logger.error("No activities found in workflow YAML")
                return None

            return WorkflowSpec.from_dict(data)
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing workflow: {e}")
            return None

    def _generate_activity(
        self,
        spec: ActivitySpec,
        output_dir: Path,
        metrics: GenerationMetrics,
        verbose: bool = False,
    ) -> GeneratedActivity:
        """Generate a single activity with retry on validation failure.

        Args:
            spec: Activity specification
            output_dir: Output directory
            metrics: Metrics tracker
            verbose: Print progress

        Returns:
            GeneratedActivity with code and validation status
        """
        runner = self._get_runner()
        errors: list[str] = []
        code = ""

        for attempt in range(1, self.max_activity_retries + 1):
            step_start = datetime.now()

            # Build the prompt
            prompt = ACTIVITY_GENERATION_PROMPT.format(
                name=spec.name,
                goal=spec.goal,
                inputs=spec.format_inputs_for_prompt(),
                output_type=spec.output.type,
                output_description=spec.output.description,
                signature=self._build_signature(spec),
            )

            # Generate with OpenCode
            result = runner.run(prompt, working_dir=output_dir, verbose=verbose)

            duration = (datetime.now() - step_start).total_seconds()
            metrics.add(
                MetricEntry(
                    stage=GenerationStage.ACTIVITY_GEN.value,
                    success=result.success,
                    duration_seconds=duration,
                    model=self._active_model or "unknown",
                    error=result.stderr if not result.success else None,
                    iteration=attempt,
                    activity_name=spec.name,
                )
            )

            if not result.success:
                errors.append(f"Generation failed: {result.stderr}")
                continue

            # Extract code from output or generated files
            code = self._extract_activity_code(result, spec.name, output_dir)
            if not code:
                errors.append(f"Could not extract code for {spec.name}")
                continue

            # Validate against spec
            validation = validate_activity(code, spec)

            if validation.valid:
                if verbose and attempt > 1:
                    print(f"    Validated after {attempt} attempts")
                return GeneratedActivity(
                    spec=spec,
                    code=code,
                    is_valid=True,
                    generation_attempts=attempt,
                )

            # Validation failed - retry with fix prompt
            errors.extend(validation.errors)

            if attempt < self.max_activity_retries:
                if verbose:
                    print(f"    Validation failed, retrying ({attempt + 1}/{self.max_activity_retries})...")

                # Build fix prompt
                fix_prompt = format_fix_prompt(
                    name=spec.name,
                    goal=spec.goal,
                    input_types=", ".join(f"{i.name}: {i.type}" for i in spec.inputs),
                    output_type=spec.output.type,
                    current_code=code,
                    validation_errors="\n".join(f"- {e}" for e in validation.errors),
                )

                # Run fix
                fix_result = runner.run(fix_prompt, working_dir=output_dir, verbose=verbose)

                metrics.add(
                    MetricEntry(
                        stage=GenerationStage.FIX.value,
                        success=fix_result.success,
                        duration_seconds=(datetime.now() - step_start).total_seconds(),
                        model=self._active_model or "unknown",
                        error=fix_result.stderr if not fix_result.success else None,
                        iteration=attempt,
                        activity_name=spec.name,
                    )
                )

                if fix_result.success:
                    fixed_code = self._extract_activity_code(fix_result, spec.name, output_dir)
                    if fixed_code:
                        code = fixed_code

        # All attempts failed
        return GeneratedActivity(
            spec=spec,
            code=code,
            is_valid=False,
            validation_errors=errors,
            generation_attempts=self.max_activity_retries,
        )

    def _build_signature(self, spec: ActivitySpec) -> str:
        """Build Python function signature from spec."""
        params = []
        for inp in spec.inputs:
            if inp.default is not None:
                params.append(f"{inp.name}: {inp.type} = {inp.default!r}")
            elif not inp.required:
                params.append(f"{inp.name}: {inp.type} = None")
            else:
                params.append(f"{inp.name}: {inp.type}")
        return ", ".join(params)

    def _extract_activity_code(
        self,
        result: OpenCodeOutput,
        func_name: str,
        output_dir: Path,
    ) -> str:
        """Extract activity code from OpenCode output.

        Tries multiple sources:
        1. Look for Python file containing the function
        2. Extract from stdout
        """
        # Check for created/modified .py files
        for file_path in result.files_created + result.files_modified:
            if file_path.endswith(".py"):
                try:
                    content = Path(file_path).read_text()
                    # Check if it contains our function
                    if f"def {func_name}" in content:
                        return content
                except Exception:
                    pass

        # Look for any .py file in output dir
        for py_file in output_dir.glob("*.py"):
            try:
                content = py_file.read_text()
                if f"def {func_name}" in content:
                    return content
            except Exception:
                pass

        # Try to extract from stdout
        if result.stdout:
            # Look for Python code block
            if "```python" in result.stdout:
                code_match = result.stdout.split("```python")[1].split("```")[0]
                if f"def {func_name}" in code_match:
                    return code_match.strip()

        return ""

    def _assemble_activities(
        self,
        workflow_spec: WorkflowSpec,
        activities: list[GeneratedActivity],
        output_path: Path,
    ) -> str:
        """Assemble all activities into a single Python file.

        Args:
            workflow_spec: Workflow specification
            activities: List of generated activities
            output_path: Where to write the assembled file

        Returns:
            The assembled Python code
        """
        # Collect all imports from activity code
        imports = set()
        imports.add("from typing import Any, Optional")

        for activity in activities:
            tree = None
            try:
                tree = ast.parse(activity.code)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(f"import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        names = ", ".join(alias.name for alias in node.names)
                        imports.add(f"from {node.module} import {names}")

        # Build the file
        lines = [
            f'"""Activity implementations for {workflow_spec.name}.',
            "",
            f"{workflow_spec.description}",
            "",
            "Generated by CompiledAI Code Generator.",
            '"""',
            "",
        ]

        # Add imports
        for imp in sorted(imports):
            lines.append(imp)
        lines.append("")
        lines.append("")

        # Add activity functions
        for activity in activities:
            # Extract just the function definition
            func_code = self._extract_function_from_code(activity.code, activity.spec.name)
            if func_code:
                lines.append(func_code)
                lines.append("")
                lines.append("")

        # Add test block
        lines.extend(self._generate_test_block(workflow_spec, activities))

        code = "\n".join(lines)

        # Write to file
        output_path.write_text(code)

        return code

    def _extract_function_from_code(self, code: str, func_name: str) -> str:
        """Extract just a function definition from code."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func_name:
                # Get source lines
                lines = code.split("\n")
                start = node.lineno - 1
                end = node.end_lineno if node.end_lineno else len(lines)
                return "\n".join(lines[start:end])

        return code

    def _generate_test_block(
        self,
        workflow_spec: WorkflowSpec,
        activities: list[GeneratedActivity],
    ) -> list[str]:
        """Generate a test block for the activities."""
        lines = [
            'if __name__ == "__main__":',
            "    import sys",
            "",
            "    print('Testing activities...')",
            "    try:",
        ]

        for activity in activities:
            if activity.is_valid:
                # Generate sample test call
                test_args = []
                for inp in activity.spec.inputs:
                    if inp.type == "str":
                        test_args.append('"test"')
                    elif inp.type == "int":
                        test_args.append("42")
                    elif inp.type == "float":
                        test_args.append("3.14")
                    elif inp.type == "bool":
                        test_args.append("True")
                    elif inp.type.startswith("list"):
                        test_args.append("[]")
                    elif inp.type.startswith("dict"):
                        test_args.append("{}")
                    else:
                        test_args.append("None")

                args_str = ", ".join(test_args)
                lines.append(f"        result = {activity.spec.name}({args_str})")
                lines.append(f"        print(f'  {activity.spec.name}: OK')")
                lines.append("")

        lines.extend([
            "        print('All tests passed!')",
            "",
            "    except Exception as e:",
            '        print(f"Test failed: {e}")',
            "        sys.exit(1)",
        ])

        return lines

    def _run_integration_test(
        self,
        activities_path: Path,
        verbose: bool = False,
    ) -> dict:
        """Run integration test on assembled activities.

        Returns:
            Dict with 'success', 'error', 'output', 'validation_issues'
        """
        validation_issues: list[dict] = []

        if not activities_path.exists():
            return {
                "success": False,
                "error": "activities.py not found",
                "output": "",
                "validation_issues": [],
            }

        # Validate syntax
        activities_code = activities_path.read_text()
        syntax_result = validate_syntax(activities_code)
        if not syntax_result.valid:
            return {
                "success": False,
                "error": f"Syntax error: {syntax_result.errors[0]}",
                "output": "",
                "validation_issues": [],
            }

        # Security validation
        if self.enable_security_validation and self._validators_available:
            try:
                shield_result = self._code_validator.validate(activities_code)
                if shield_result.is_threat:
                    for issue in shield_result.details.get("issues", []):
                        validation_issues.append({
                            "validator": issue.get("tool", "code_shield"),
                            "severity": issue.get("severity", "unknown"),
                            "message": issue.get("message", "Security issue"),
                            "line": issue.get("line"),
                            "code": issue.get("code"),
                        })

                high_severity = [i for i in validation_issues if i["severity"] in ["high", "critical"]]
                if high_severity:
                    return {
                        "success": False,
                        "error": f"Security validation failed: {len(high_severity)} high-severity issues",
                        "output": "",
                        "validation_issues": validation_issues,
                    }
            except Exception as e:
                logger.warning(f"Security validation error: {e}")

        # Run the activities file
        try:
            result = subprocess.run(
                ["python", str(activities_path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(activities_path.parent),
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Test failed:\n{result.stderr or result.stdout or 'Unknown error'}",
                    "output": result.stdout,
                    "validation_issues": validation_issues,
                }

            if verbose:
                print(f"    Tests passed")

            return {
                "success": True,
                "error": "",
                "output": result.stdout,
                "validation_issues": validation_issues,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Tests timed out",
                "output": "",
                "validation_issues": validation_issues,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Test execution error: {e}",
                "output": "",
                "validation_issues": validation_issues,
            }


def main():
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate CompiledAI workflows using OpenCode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a simple workflow
  python -m compiled_ai.factory.code_generator "Create a workflow that validates emails"

  # Specify output directory
  python -m compiled_ai.factory.code_generator -o ./my_workflow "Process CSV files"

  # Use specific model
  python -m compiled_ai.factory.code_generator -m anthropic/claude-sonnet-4 "Build a data pipeline"
        """,
    )
    parser.add_argument("task", help="Task description in natural language")
    parser.add_argument("-o", "--output", help="Output directory", default=None)
    parser.add_argument(
        "-m", "--model", help="Model to use (auto-detect if not specified)", default=None
    )
    parser.add_argument(
        "-i",
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum workflow iterations (default: 3)",
    )
    parser.add_argument(
        "-r",
        "--max-retries",
        type=int,
        default=2,
        help="Maximum retries per activity (default: 2)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=120,
        help="Timeout per step in seconds (default: 120)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    parser.add_argument(
        "--no-security", action="store_true", help="Disable security validation"
    )
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    parser.add_argument("--metrics-file", help="Save metrics to file")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    generator = CodeGenerator(
        model=args.model,
        max_iterations=args.max_iterations,
        max_activity_retries=args.max_retries,
        timeout_per_step=args.timeout,
        enable_security_validation=not args.no_security,
    )

    result = generator.generate(
        args.task,
        output_dir=Path(args.output) if args.output else None,
        verbose=not args.quiet and not args.json,
    )

    # Save metrics if requested
    if args.metrics_file and result.metrics:
        metrics_path = Path(args.metrics_file)
        metrics_path.write_text(json.dumps(result.metrics.to_dict(), indent=2))
        if not args.quiet:
            print(f"Metrics saved to: {metrics_path}")

    # Output result
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.success:
            print(f"\nWorkflow generated successfully!")
            print(f"Workflow: {result.workflow_path}")
            print(f"Activities: {result.activities_path}")
            if result.metrics:
                print(f"First-try success: {result.metrics.first_try_success}")
        else:
            print(f"\nGeneration failed after {result.iterations} iterations")
            for error in result.errors[-3:]:
                print(f"  - {error[:100]}")
            exit(1)


if __name__ == "__main__":
    main()
