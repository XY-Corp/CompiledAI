"""Crush-based workflow generator with iterative refinement.

Pipeline:
1. Natural language input
2. Generate workflow YAML (planning)
3. Generate activity implementations (coding)
4. Validate and test
5. Iterate on errors until success or max attempts
"""

import tempfile
import subprocess
import ast
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

try:
    from .runner import CrushRunner, CrushOutput
except ImportError:
    from runner import CrushRunner, CrushOutput


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
    test_output: str = ""
    total_time_seconds: float = 0.0
    
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
            "test_output": self.test_output,
            "total_time_seconds": self.total_time_seconds,
        }


# Prompt templates for workflow generation
PLANNING_PROMPT = '''You are generating a CompiledAI workflow specification.

Task: {task_description}

Generate a workflow YAML file with the following structure:

```yaml
workflow_id: <snake_case_unique_id>
name: <Human Readable Name>
description: <What this workflow accomplishes>

variables:
  - name: input_data
    description: <Description of input>
    default_value: null
  # Add more as needed

activities:
  - name: <activity_function_name>
    description: <What this activity does>
    inputs:
      - name: <param_name>
        type: <python_type>
        description: <Detailed description>
    output:
      type: dict  # or str, list, etc.
      description: <What the output represents>
    result_variable: <var_name_to_store_result>

execution_pattern: sequence  # or parallel, foreach
```

Requirements:
1. Use snake_case for all names
2. Activities should be pure Python functions (no external API calls in this example)
3. Each activity should have clear inputs and outputs
4. Include proper type hints in descriptions
5. Make the workflow testable with sample data

Save the YAML to: workflow.yaml
'''

CODING_PROMPT = '''Based on the workflow specification in workflow.yaml, generate the Python activity implementations.

Requirements:
1. Create a Python file with all activity functions
2. Each function must match the signature from the YAML
3. Include proper type hints
4. Include docstrings explaining what each function does
5. Make functions pure (no side effects) where possible
6. Include input validation
7. Handle edge cases gracefully

At the end of the file, add a simple test block:

```python
if __name__ == "__main__":
    # Test each activity with sample data
    print("Testing activities...")
    # Add test calls
    print("All tests passed!")
```

Save the Python code to: activities.py
'''

FIX_PROMPT = '''The generated code has errors. Please fix them.

Error output:
{error_output}

Current workflow.yaml:
{workflow_yaml}

Current activities.py:
{activities_code}

Please fix the errors and update both files as needed.
Ensure the code:
1. Has no syntax errors
2. Has no import errors
3. Passes basic tests
4. Matches the workflow specification

Update the files with the fixes.
'''


class CrushGenerator:
    """Generate CompiledAI workflows using Crush with Claude Opus."""
    
    def __init__(
        self,
        model: str = "bedrock/anthropic.claude-opus-4-5-20251101-v1:0",
        max_iterations: int = 5,
        timeout_per_step: int = 120,
    ):
        """Initialize the generator.
        
        Args:
            model: Model to use for generation
            max_iterations: Maximum fix iterations before giving up
            timeout_per_step: Timeout for each Crush invocation
        """
        self.model = model
        self.max_iterations = max_iterations
        self.runner = CrushRunner(
            model=model,
            timeout=timeout_per_step,
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
        
        # Create output directory
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = Path(tempfile.mkdtemp(prefix="crush_workflow_"))
        
        # Update runner working directory
        self.runner.working_dir = output_dir
        
        errors = []
        iteration = 0
        
        if verbose:
            print(f"🚀 Generating workflow for: {task_description[:80]}...")
            print(f"📁 Output directory: {output_dir}")
        
        # Step 1: Generate workflow YAML
        if verbose:
            print("\n📋 Step 1: Generating workflow YAML...")
        
        planning_result = self.runner.run(
            PLANNING_PROMPT.format(task_description=task_description),
            verbose=verbose,
        )
        
        if not planning_result.success:
            errors.append(f"Planning failed: {planning_result.stderr}")
            if verbose:
                print(f"❌ Planning failed: {planning_result.stderr}")
        
        # Step 2: Generate activities
        if verbose:
            print("\n🔧 Step 2: Generating activity implementations...")
        
        coding_result = self.runner.run(
            CODING_PROMPT,
            verbose=verbose,
        )
        
        if not coding_result.success:
            errors.append(f"Coding failed: {coding_result.stderr}")
            if verbose:
                print(f"❌ Coding failed: {coding_result.stderr}")
        
        # Step 3: Validate and iterate
        workflow_path = output_dir / "workflow.yaml"
        activities_path = output_dir / "activities.py"
        
        for iteration in range(1, self.max_iterations + 1):
            if verbose:
                print(f"\n🧪 Iteration {iteration}: Validating and testing...")
            
            validation_result = self._validate_and_test(
                workflow_path,
                activities_path,
                verbose=verbose,
            )
            
            if validation_result["success"]:
                if verbose:
                    print("✅ Validation passed!")
                break
            
            errors.append(validation_result["error"])
            if verbose:
                print(f"⚠️ Validation failed: {validation_result['error'][:200]}")
            
            if iteration < self.max_iterations:
                if verbose:
                    print(f"🔄 Attempting fix (iteration {iteration + 1}/{self.max_iterations})...")
                
                # Read current files
                workflow_yaml = workflow_path.read_text() if workflow_path.exists() else ""
                activities_code = activities_path.read_text() if activities_path.exists() else ""
                
                # Run fix
                fix_result = self.runner.run(
                    FIX_PROMPT.format(
                        error_output=validation_result["error"],
                        workflow_yaml=workflow_yaml,
                        activities_code=activities_code,
                    ),
                    verbose=verbose,
                )
                
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
        
        result = GenerationResult(
            success=final_validation["success"],
            workflow_yaml=workflow_yaml,
            activities_code=activities_code,
            workflow_path=workflow_path if workflow_path.exists() else None,
            activities_path=activities_path if activities_path.exists() else None,
            iterations=iteration,
            errors=errors,
            test_output=final_validation.get("output", ""),
            total_time_seconds=total_time,
        )
        
        if verbose:
            status = "✅ SUCCESS" if result.success else "❌ FAILED"
            print(f"\n{status} after {iteration} iterations ({total_time:.1f}s)")
            if result.success:
                print(f"  📄 Workflow: {workflow_path}")
                print(f"  🐍 Activities: {activities_path}")
        
        return result
    
    def _validate_and_test(
        self,
        workflow_path: Path,
        activities_path: Path,
        verbose: bool = False,
    ) -> dict:
        """Validate and test generated files.
        
        Returns:
            Dict with 'success' bool, 'error' str, and 'output' str
        """
        errors = []
        
        # Check files exist
        if not workflow_path.exists():
            return {"success": False, "error": "workflow.yaml not found", "output": ""}
        
        if not activities_path.exists():
            return {"success": False, "error": "activities.py not found", "output": ""}
        
        # Validate YAML
        try:
            workflow_yaml = workflow_path.read_text()
            yaml.safe_load(workflow_yaml)
        except yaml.YAMLError as e:
            return {"success": False, "error": f"Invalid YAML: {e}", "output": ""}
        
        # Validate Python syntax
        try:
            activities_code = activities_path.read_text()
            ast.parse(activities_code)
        except SyntaxError as e:
            return {"success": False, "error": f"Python syntax error: {e}", "output": ""}
        
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
                }
            
            return {
                "success": True,
                "error": "",
                "output": result.stdout,
            }
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Tests timed out", "output": ""}
        except Exception as e:
            return {"success": False, "error": f"Test execution error: {e}", "output": ""}


def main():
    """CLI entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate CompiledAI workflows using Crush")
    parser.add_argument("task", help="Task description in natural language")
    parser.add_argument("-o", "--output", help="Output directory", default=None)
    parser.add_argument("-m", "--model", help="Model to use", 
                        default="bedrock/anthropic.claude-opus-4-5-20251101-v1:0")
    parser.add_argument("-i", "--max-iterations", type=int, default=5,
                        help="Maximum fix iterations")
    parser.add_argument("-q", "--quiet", action="store_true", help="Quiet mode")
    
    args = parser.parse_args()
    
    generator = CrushGenerator(
        model=args.model,
        max_iterations=args.max_iterations,
    )
    
    result = generator.generate(
        args.task,
        output_dir=Path(args.output) if args.output else None,
        verbose=not args.quiet,
    )
    
    if result.success:
        print(f"\n✅ Workflow generated successfully!")
        print(f"Files: {result.workflow_path}, {result.activities_path}")
    else:
        print(f"\n❌ Generation failed after {result.iterations} iterations")
        for error in result.errors[-3:]:  # Show last 3 errors
            print(f"  - {error[:100]}")
        exit(1)


if __name__ == "__main__":
    main()
