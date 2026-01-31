"""Crush-based workflow generator with iterative refinement.

Pipeline:
1. Natural language input
2. Generate workflow YAML (planning)
3. Generate activity implementations (coding)
4. Validate with CompiledAI validation pipeline
5. Iterate on errors until success or max attempts
"""

import json
import logging
import tempfile
import subprocess
import ast
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
from enum import Enum

try:
    from .runner import CrushRunner, CrushOutput
except ImportError:
    from runner import CrushRunner, CrushOutput

# Configure logging
logger = logging.getLogger(__name__)


class GenerationStage(Enum):
    """Stages of workflow generation."""
    PLANNING = "planning"
    CODING = "coding"
    VALIDATION = "validation"
    FIX = "fix"


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


@dataclass
class GenerationMetrics:
    """Metrics for a workflow generation run."""
    entries: list[MetricEntry] = field(default_factory=list)
    total_time_seconds: float = 0.0
    first_try_success: bool = False
    
    def add(self, entry: MetricEntry):
        """Add a metric entry."""
        self.entries.append(entry)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "total_time_seconds": self.total_time_seconds,
            "first_try_success": self.first_try_success,
            "total_iterations": len([e for e in self.entries if e.stage == "validation"]),
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


# Improved prompt templates for better first-try success
PLANNING_PROMPT = '''You are an expert at generating CompiledAI workflow specifications.

## Task
{task_description}

## Requirements
Generate a workflow YAML file that:
1. Has a unique snake_case workflow_id
2. Includes clear variable definitions with types
3. Defines activities with precise input/output specifications
4. Uses appropriate execution pattern (sequence, parallel, or foreach)

## Output Format
Create a file named `workflow.yaml` with this exact structure:

```yaml
workflow_id: <unique_snake_case_id>
name: <Human Readable Workflow Name>
description: |
  <Multi-line description of what this workflow accomplishes
   and any important details about its behavior.>

# Input variables for the workflow
variables:
  - name: <input_var_name>
    type: <python_type>  # str, int, float, bool, list, dict
    description: <What this variable represents>
    default_value: null  # or a sensible default
    required: true  # or false

# Activities that make up the workflow
activities:
  - name: <activity_function_name>  # snake_case
    description: <Clear description of what this activity does>
    inputs:
      - name: <param_name>
        type: <python_type>
        description: <Detailed description of this parameter>
    output:
      type: <return_type>  # dict, list, str, int, bool, or custom
      description: <What the output represents>
    result_variable: <variable_name_to_store_result>
    
  # Add more activities as needed...

# How activities are executed
execution_pattern: sequence  # or: parallel, foreach
# For foreach: add 'foreach_variable: list_var_name'
```

## Guidelines
- Use descriptive, unambiguous names
- Keep activities focused on a single responsibility
- Ensure proper data flow between activities via result_variable
- Include edge case handling in descriptions
- Make the workflow testable with sample data

Save ONLY the YAML content to: workflow.yaml
'''

CODING_PROMPT = '''You are an expert Python developer implementing CompiledAI workflow activities.

## Context
Read the workflow specification from workflow.yaml and implement all activities.

## Requirements for Each Activity
1. Exact function signature matching the YAML spec
2. Complete type hints for parameters and return values
3. Comprehensive docstring with Args, Returns, and Raises
4. Input validation with clear error messages
5. Proper error handling for edge cases
6. Pure functions where possible (no side effects)

## Output Format
Create a file named `activities.py` with this structure:

```python
"""Activity implementations for <workflow_name>.

Generated by CompiledAI Workflow Factory.
"""

from typing import Any
import re  # Add imports as needed


def <activity_name>(param1: type1, param2: type2) -> ReturnType:
    """<One-line description>.
    
    <Extended description if needed>
    
    Args:
        param1: <Description of param1>
        param2: <Description of param2>
        
    Returns:
        <Description of return value>
        
    Raises:
        ValueError: <When raised>
        TypeError: <When raised>
    """
    # Input validation
    if not isinstance(param1, expected_type):
        raise TypeError(f"param1 must be <type>, got {{type(param1).__name__}}")
    
    # Implementation
    result = ...
    
    return result


# Implement all other activities...


# Test block - REQUIRED
if __name__ == "__main__":
    import sys
    
    print("Testing activities...")
    
    # Test each activity with sample data
    try:
        # Test activity 1
        result1 = activity1(sample_input)
        assert result1 is not None, "activity1 returned None"
        print(f"  ✓ activity1: {{result1}}")
        
        # Test activity 2
        result2 = activity2(result1)
        print(f"  ✓ activity2: {{result2}}")
        
        # Add more tests...
        
        print("\\nAll tests passed! ✅")
        
    except Exception as e:
        print(f"\\nTest failed: {{e}} ❌")
        sys.exit(1)
```

## Important
- Test with realistic sample data matching the workflow inputs
- Ensure tests cover normal cases AND edge cases
- Make assertions meaningful (not just "not None")
- Print test results for debugging

Save ONLY the Python code to: activities.py
'''

FIX_PROMPT = '''You are debugging CompiledAI workflow code. Fix all errors.

## Error Details
```
{error_output}
```

## Current Files

### workflow.yaml
```yaml
{workflow_yaml}
```

### activities.py
```python
{activities_code}
```

{validation_context}

## Your Task
1. Analyze the error carefully
2. Identify the root cause
3. Fix BOTH workflow.yaml AND activities.py as needed
4. Ensure the fix doesn't break other parts
5. Update tests to verify the fix

## Common Issues to Check
- Type mismatches between YAML spec and Python code
- Missing imports
- Incorrect function signatures
- Missing input validation
- Incorrect return types
- Test data that doesn't match expected types

Update the files with your fixes. Both files must be complete and working.
'''


class CrushGenerator:
    """Generate CompiledAI workflows using Crush with Claude."""
    
    # Model preference order (will try each until one works)
    DEFAULT_MODELS = [
        "bedrock/anthropic.claude-opus-4-5-20251101-v1:0",
        "bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0",
        "anthropic/claude-sonnet-4-20250514",
        "gemini/gemini-2.5-pro",
    ]
    
    def __init__(
        self,
        model: Optional[str] = None,
        max_iterations: int = 5,
        timeout_per_step: int = 180,
        enable_security_validation: bool = True,
        security_severity_threshold: str = "high",
    ):
        """Initialize the generator.
        
        Args:
            model: Model to use for generation (None = auto-detect)
            max_iterations: Maximum fix iterations before giving up
            timeout_per_step: Timeout for each Crush invocation
            enable_security_validation: Whether to run security validators
            security_severity_threshold: Minimum severity to fail ("low", "medium", "high")
        """
        self.model = model
        self.max_iterations = max_iterations
        self.timeout_per_step = timeout_per_step
        self.enable_security_validation = enable_security_validation
        self.security_severity_threshold = security_severity_threshold
        
        # Will be initialized lazily
        self._runner: Optional[CrushRunner] = None
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
    
    def _get_runner(self) -> CrushRunner:
        """Get or create the Crush runner with a working model."""
        if self._runner is not None:
            return self._runner
        
        models_to_try = [self.model] if self.model else self.DEFAULT_MODELS
        
        for model in models_to_try:
            try:
                runner = CrushRunner(
                    model=model,
                    timeout=self.timeout_per_step,
                )
                
                # Quick test to see if model works
                logger.info(f"Testing model: {model}")
                self._runner = runner
                self._active_model = model
                logger.info(f"Using model: {model}")
                return runner
                
            except Exception as e:
                logger.warning(f"Model {model} not available: {e}")
                continue
        
        raise RuntimeError(
            f"No working model found. Tried: {models_to_try}. "
            "Ensure Crush is configured with valid API credentials."
        )
    
    def generate(
        self,
        task_description: str,
        output_dir: Optional[Path] = None,
        verbose: bool = True,
    ) -> GenerationResult:
        """Generate a workflow from natural language description.
        
        Args:
            task_description: Natural language description of what the workflow should do
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
            output_dir = Path(tempfile.mkdtemp(prefix="crush_workflow_"))
        
        errors: list[str] = []
        validation_issues: list[ValidationIssue] = []
        iteration = 0
        
        if verbose:
            print(f"🚀 Generating workflow for: {task_description[:80]}...")
            print(f"📁 Output directory: {output_dir}")
        
        try:
            runner = self._get_runner()
            runner.working_dir = output_dir
            
            if verbose:
                print(f"🤖 Using model: {self._active_model}")
        except RuntimeError as e:
            logger.error(f"Failed to initialize: {e}")
            return GenerationResult(
                success=False,
                errors=[str(e)],
                total_time_seconds=(datetime.now() - start_time).total_seconds(),
                metrics=metrics,
            )
        
        # Step 1: Generate workflow YAML
        if verbose:
            print("\n📋 Step 1: Generating workflow YAML...")
        
        step_start = datetime.now()
        planning_result = runner.run(
            PLANNING_PROMPT.format(task_description=task_description),
            verbose=verbose,
        )
        
        metrics.add(MetricEntry(
            stage=GenerationStage.PLANNING.value,
            success=planning_result.success,
            duration_seconds=(datetime.now() - step_start).total_seconds(),
            model=self._active_model or "unknown",
            error=planning_result.stderr if not planning_result.success else None,
        ))
        
        if not planning_result.success:
            errors.append(f"Planning failed: {planning_result.stderr}")
            if verbose:
                print(f"❌ Planning failed: {planning_result.stderr}")
        
        # Step 2: Generate activities
        if verbose:
            print("\n🔧 Step 2: Generating activity implementations...")
        
        step_start = datetime.now()
        coding_result = runner.run(
            CODING_PROMPT,
            verbose=verbose,
        )
        
        metrics.add(MetricEntry(
            stage=GenerationStage.CODING.value,
            success=coding_result.success,
            duration_seconds=(datetime.now() - step_start).total_seconds(),
            model=self._active_model or "unknown",
            error=coding_result.stderr if not coding_result.success else None,
        ))
        
        if not coding_result.success:
            errors.append(f"Coding failed: {coding_result.stderr}")
            if verbose:
                print(f"❌ Coding failed: {coding_result.stderr}")
        
        # Step 3: Validate and iterate
        workflow_path = output_dir / "workflow.yaml"
        activities_path = output_dir / "activities.py"
        
        first_validation = True
        
        for iteration in range(1, self.max_iterations + 1):
            if verbose:
                print(f"\n🧪 Iteration {iteration}: Validating and testing...")
            
            step_start = datetime.now()
            validation_result = self._validate_and_test(
                workflow_path,
                activities_path,
                verbose=verbose,
            )
            
            metrics.add(MetricEntry(
                stage=GenerationStage.VALIDATION.value,
                success=validation_result["success"],
                duration_seconds=(datetime.now() - step_start).total_seconds(),
                model=self._active_model or "unknown",
                error=validation_result.get("error") if not validation_result["success"] else None,
                iteration=iteration,
            ))
            
            if validation_result["success"]:
                if verbose:
                    print("✅ Validation passed!")
                if first_validation:
                    metrics.first_try_success = True
                break
            
            first_validation = False
            errors.append(validation_result["error"])
            
            # Collect validation issues
            for issue in validation_result.get("validation_issues", []):
                validation_issues.append(ValidationIssue(**issue))
            
            if verbose:
                print(f"⚠️ Validation failed: {validation_result['error'][:200]}")
            
            if iteration < self.max_iterations:
                if verbose:
                    print(f"🔄 Attempting fix (iteration {iteration + 1}/{self.max_iterations})...")
                
                # Read current files
                workflow_yaml = workflow_path.read_text() if workflow_path.exists() else ""
                activities_code = activities_path.read_text() if activities_path.exists() else ""
                
                # Build validation context
                validation_context = ""
                if validation_result.get("validation_issues"):
                    validation_context = "\n## Security/Validation Issues\n"
                    for issue in validation_result["validation_issues"]:
                        validation_context += f"- [{issue['validator']}] {issue['severity']}: {issue['message']}"
                        if issue.get('line'):
                            validation_context += f" (line {issue['line']})"
                        validation_context += "\n"
                
                # Run fix
                step_start = datetime.now()
                fix_result = runner.run(
                    FIX_PROMPT.format(
                        error_output=validation_result["error"],
                        workflow_yaml=workflow_yaml,
                        activities_code=activities_code,
                        validation_context=validation_context,
                    ),
                    verbose=verbose,
                )
                
                metrics.add(MetricEntry(
                    stage=GenerationStage.FIX.value,
                    success=fix_result.success,
                    duration_seconds=(datetime.now() - step_start).total_seconds(),
                    model=self._active_model or "unknown",
                    error=fix_result.stderr if not fix_result.success else None,
                    iteration=iteration,
                ))
                
                if not fix_result.success:
                    errors.append(f"Fix attempt failed: {fix_result.stderr}")
        
        # Read final files
        workflow_yaml = workflow_path.read_text() if workflow_path.exists() else ""
        activities_code = activities_path.read_text() if activities_path.exists() else ""
        
        # Final validation
        final_validation = self._validate_and_test(
            workflow_path,
            activities_path,
            verbose=False,
        )
        
        total_time = (datetime.now() - start_time).total_seconds()
        metrics.total_time_seconds = total_time
        
        result = GenerationResult(
            success=final_validation["success"],
            workflow_yaml=workflow_yaml,
            activities_code=activities_code,
            workflow_path=workflow_path if workflow_path.exists() else None,
            activities_path=activities_path if activities_path.exists() else None,
            iterations=iteration,
            errors=errors,
            validation_issues=validation_issues,
            test_output=final_validation.get("output", ""),
            total_time_seconds=total_time,
            metrics=metrics,
        )
        
        if verbose:
            status = "✅ SUCCESS" if result.success else "❌ FAILED"
            print(f"\n{status} after {iteration} iterations ({total_time:.1f}s)")
            if metrics.first_try_success:
                print("  🎯 First-try success!")
            if result.success:
                print(f"  📄 Workflow: {workflow_path}")
                print(f"  🐍 Activities: {activities_path}")
        
        # Log metrics
        logger.info(f"Generation complete: success={result.success}, "
                   f"iterations={iteration}, time={total_time:.1f}s, "
                   f"first_try={metrics.first_try_success}")
        
        return result
    
    def _validate_and_test(
        self,
        workflow_path: Path,
        activities_path: Path,
        verbose: bool = False,
    ) -> dict:
        """Validate and test generated files.
        
        Returns:
            Dict with 'success' bool, 'error' str, 'output' str, and 'validation_issues' list
        """
        validation_issues: list[dict] = []
        
        # Check files exist
        if not workflow_path.exists():
            return {"success": False, "error": "workflow.yaml not found", "output": "", "validation_issues": []}
        
        if not activities_path.exists():
            return {"success": False, "error": "activities.py not found", "output": "", "validation_issues": []}
        
        # Validate YAML
        try:
            workflow_yaml = workflow_path.read_text()
            parsed_yaml = yaml.safe_load(workflow_yaml)
            
            # Check required fields
            required_fields = ["workflow_id", "name", "activities"]
            for field in required_fields:
                if field not in parsed_yaml:
                    return {
                        "success": False,
                        "error": f"workflow.yaml missing required field: {field}",
                        "output": "",
                        "validation_issues": [],
                    }
                    
        except yaml.YAMLError as e:
            return {"success": False, "error": f"Invalid YAML: {e}", "output": "", "validation_issues": []}
        
        # Validate Python syntax
        try:
            activities_code = activities_path.read_text()
            ast.parse(activities_code)
        except SyntaxError as e:
            return {"success": False, "error": f"Python syntax error: {e}", "output": "", "validation_issues": []}
        
        # Run security validation if enabled
        if self.enable_security_validation and self._validators_available:
            try:
                # CodeShield validation
                shield_result = self._code_validator.validate(activities_code)
                if shield_result.is_threat:
                    for issue in shield_result.details.get("issues", []):
                        validation_issues.append({
                            "validator": issue.get("tool", "code_shield"),
                            "severity": issue.get("severity", "unknown"),
                            "message": issue.get("message", "Security issue detected"),
                            "line": issue.get("line"),
                            "code": issue.get("code"),
                        })
                
                # SAST validation
                sast_result = self._sast_validator.validate(activities_code)
                if sast_result.is_threat:
                    for issue in sast_result.details.get("issues", []):
                        validation_issues.append({
                            "validator": "sast",
                            "severity": issue.get("severity", "unknown"),
                            "message": issue.get("message", "SAST issue detected"),
                            "line": issue.get("line"),
                            "code": issue.get("code"),
                        })
                
                # If high-severity issues found, fail validation
                high_severity_issues = [
                    i for i in validation_issues 
                    if i["severity"] in ["high", "critical"]
                ]
                if high_severity_issues:
                    return {
                        "success": False,
                        "error": f"Security validation failed: {len(high_severity_issues)} high-severity issues found",
                        "output": "",
                        "validation_issues": validation_issues,
                    }
                    
            except Exception as e:
                logger.warning(f"Security validation error (non-blocking): {e}")
        
        # Run the activities file (tests)
        try:
            result = subprocess.run(
                ["python", str(activities_path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(activities_path.parent),
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                return {
                    "success": False,
                    "error": f"Test failed:\n{error_msg}",
                    "output": result.stdout,
                    "validation_issues": validation_issues,
                }
            
            return {
                "success": True,
                "error": "",
                "output": result.stdout,
                "validation_issues": validation_issues,
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Tests timed out", "output": "", "validation_issues": validation_issues}
        except Exception as e:
            return {"success": False, "error": f"Test execution error: {e}", "output": "", "validation_issues": validation_issues}


def main():
    """CLI entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate CompiledAI workflows using Crush",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a simple workflow
  python -m compiled_ai.factory.crush_generator.generator "Create a workflow that validates emails"
  
  # Specify output directory
  python -m compiled_ai.factory.crush_generator.generator -o ./my_workflow "Process CSV files"
  
  # Use specific model
  python -m compiled_ai.factory.crush_generator.generator -m anthropic/claude-sonnet-4 "Build a data pipeline"
  
  # Disable security validation
  python -m compiled_ai.factory.crush_generator.generator --no-security "Quick prototype"
        """
    )
    parser.add_argument("task", help="Task description in natural language")
    parser.add_argument("-o", "--output", help="Output directory", default=None)
    parser.add_argument("-m", "--model", help="Model to use (auto-detect if not specified)", default=None)
    parser.add_argument("-i", "--max-iterations", type=int, default=5,
                        help="Maximum fix iterations (default: 5)")
    parser.add_argument("-t", "--timeout", type=int, default=180,
                        help="Timeout per step in seconds (default: 180)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    parser.add_argument("--no-security", action="store_true", 
                        help="Disable security validation")
    parser.add_argument("--security-threshold", choices=["low", "medium", "high"],
                        default="high", help="Security severity threshold (default: high)")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    parser.add_argument("--metrics-file", help="Save metrics to file")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    generator = CrushGenerator(
        model=args.model,
        max_iterations=args.max_iterations,
        timeout_per_step=args.timeout,
        enable_security_validation=not args.no_security,
        security_severity_threshold=args.security_threshold,
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
            print(f"📊 Metrics saved to: {metrics_path}")
    
    # Output result
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.success:
            print(f"\n✅ Workflow generated successfully!")
            print(f"📄 Workflow: {result.workflow_path}")
            print(f"🐍 Activities: {result.activities_path}")
            if result.metrics:
                print(f"📊 First-try success: {result.metrics.first_try_success}")
        else:
            print(f"\n❌ Generation failed after {result.iterations} iterations")
            for error in result.errors[-3:]:  # Show last 3 errors
                print(f"  - {error[:100]}")
            exit(1)


if __name__ == "__main__":
    main()
