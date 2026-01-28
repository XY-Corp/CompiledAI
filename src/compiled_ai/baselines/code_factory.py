"""Code Factory Baseline: Compiled workflow with template-assisted generation.

This baseline demonstrates the core Compiled AI value proposition:
1. Compilation Phase: Generate workflow once (expensive LLM calls)
2. Execution Phase: Run compiled workflow many times (cheap, deterministic)
"""

import asyncio
import json
import time
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .base import BaseBaseline, BaselineResult, TaskInput, register_baseline
from ..factory.code_factory import (
    CodeFactory,
    FactoryResult,
    TaskSignatureExtractor,
    WorkflowCacheManager,
    DynamicModuleLoader,
    CompilationMetricsTracker,
)
from ..factory.code_factory.activity_registry import ActivityRegistry
from ..factory.code_factory.visualizer import visualize_workflow
from ..utils.llm_client import TokenTracker
from ..validation import PromptInjectionValidator, PIIScanner, CodeShieldValidator, CanaryManager

console = Console()


@register_baseline("code_factory")
class CodeFactoryBaseline(BaseBaseline):
    """Code Factory baseline - compiles workflow once, executes many times.

    Workflow:
    1. Compilation (first task): Generate workflow with template search
    2. Execution (all tasks): Run compiled workflow deterministically

    Value Proposition:
    - Amortizes expensive compilation over many executions
    - Deterministic outputs after compilation
    - Template registry enables code reuse
    - Lower runtime token costs at scale
    """

    description = "Compiled workflow with template-assisted code generation"

    def __init__(
        self,
        provider: str = "anthropic",
        model: str | None = None,
        verbose: bool = False,
        max_regenerations: int = 3,
        enable_registry: bool = True,
        auto_register: bool = True,
        enable_cache: bool = False,
        cache_size: int = 50,
        similarity_threshold: float = 0.7,
        log_dir: str | None = "logs",
        use_function_call_template: bool = True,
        function_call_model: str | None = None,
        function_call_temperature: float | None = 0.0,
        function_call_max_tokens: int | None = 8192,
        enable_security: bool = True,
        enable_output_gate: bool = False,
    ) -> None:
        """Initialize the Code Factory baseline.

        Args:
            provider: LLM provider ("anthropic", "openai", or "gemini")
            model: Model name. Defaults to provider's default model.
            verbose: Enable verbose logging
            max_regenerations: Maximum retry attempts for code generation
            enable_registry: Enable template registry for activity search
            auto_register: Automatically register successful activities
            enable_cache: Enable LLM response caching (passed to CodeFactory)
            cache_size: Maximum number of workflows to cache (default: 50)
            similarity_threshold: Minimum similarity for workflow reuse (default: 0.7)
            log_dir: Directory for compilation logs (None to disable file logging)
            use_function_call_template: Use fixed YAML template for function-calling tasks (saves ~50% tokens)
            function_call_model: Model to use for function-call template mode (e.g., "claude-3-5-haiku-20241022" for faster/cheaper)
            function_call_temperature: Temperature for function-call mode (default: 0.0 for deterministic)
            function_call_max_tokens: Max output tokens for function-call mode (default: 8192)
            enable_security: Enable security validation gates (INPUT GATE + CODE GATE)
            enable_output_gate: Enable OUTPUT GATE for system prompt leakage detection (uses CanaryManager)
        """
        self.provider = provider
        self.model = model or self._default_model(provider)
        self.verbose = verbose
        self.max_regenerations = max_regenerations
        self.enable_registry = enable_registry
        self.auto_register = auto_register
        self.enable_cache = enable_cache
        self.similarity_threshold = similarity_threshold
        self.log_dir = log_dir
        self.use_function_call_template = use_function_call_template
        self.function_call_model = function_call_model
        self.function_call_temperature = function_call_temperature
        self.function_call_max_tokens = function_call_max_tokens

        # NEW: Task classification and caching
        self.signature_extractor = TaskSignatureExtractor()
        self.workflow_cache = WorkflowCacheManager(max_cache_size=cache_size)

        # NEW: Dynamic execution
        self.module_loader = DynamicModuleLoader()

        # NEW: Metrics tracking
        self.metrics_tracker = CompilationMetricsTracker()

        # NEW: Activity accuracy registry
        self.activity_registry = ActivityRegistry()

        # NEW: Security validation gates
        self.enable_security = enable_security
        if enable_security:
            self._input_validators = [
                PromptInjectionValidator(),
                PIIScanner(),
            ]
            self._code_validators = [
                CodeShieldValidator(severity_threshold="warning"),
            ]
        else:
            self._input_validators = []
            self._code_validators = []

        # NEW: OUTPUT GATE for system prompt leakage detection
        self.enable_output_gate = enable_output_gate
        self._canary_manager: CanaryManager | None = None
        self._current_canary_token: str | None = None
        if enable_output_gate:
            self._canary_manager = CanaryManager(prefix="CANARY_CF")

        # Create LLM client for activity execution
        from ..utils.llm_client import create_client, LLMConfig
        self.llm_client = create_client(
            provider=provider,
            config=LLMConfig(model=self.model, temperature=0.0, max_tokens=4096),
            enable_cache=enable_cache,
        )

        # OLD: Legacy compilation state (kept for backward compatibility)
        self._compiled: Optional[FactoryResult] = None
        self._compilation_task_id: Optional[str] = None
        self._compilation_tokens = 0
        self._compilation_latency_ms = 0.0

        # Token tracking
        self.token_tracker = TokenTracker()

        # Multi-example compilation support
        self._current_examples: list[TaskInput] | None = None

    def _default_model(self, provider: str) -> str:
        """Get default model for provider."""
        defaults = {
            "anthropic": "claude-opus-4-5-20251101",  # Opus 4.5 with extended thinking
            "openai": "gpt-4o",
            "gemini": "gemini-2.0-flash",
        }
        return defaults.get(provider, "claude-opus-4-5-20251101")

    def _check_input_gate(self, content: str) -> tuple[bool, dict[str, Any]]:
        """Check INPUT GATE: Run prompt injection and PII validators on input.

        Args:
            content: The input prompt/content to validate

        Returns:
            Tuple of (is_blocked, gate_result_dict)
        """
        if not self.enable_security or not self._input_validators:
            return False, {}

        gate_result = {
            "gate": "input",
            "validators_run": [],
            "threats_detected": [],
        }

        for validator in self._input_validators:
            validator_name = validator.__class__.__name__
            try:
                result = validator.validate(content)
                gate_result["validators_run"].append(validator_name)

                if result.is_threat:
                    gate_result["threats_detected"].append({
                        "validator": validator_name,
                        "score": result.score,
                        "details": result.details,
                    })

                    if self.verbose:
                        console.print(
                            f"[red]🛡️ INPUT GATE BLOCKED by {validator_name}[/red]\n"
                            f"  Score: {result.score:.2f}\n"
                            f"  Details: {result.details}"
                        )

                    gate_result["blocked"] = True
                    gate_result["blocked_by"] = validator_name
                    return True, gate_result

            except Exception as e:
                if self.verbose:
                    console.print(f"[yellow]⚠️ Validator {validator_name} error: {e}[/yellow]")
                gate_result["validators_run"].append(f"{validator_name} (error)")

        gate_result["blocked"] = False
        return False, gate_result

    def _check_code_gate(self, code: str) -> tuple[bool, dict[str, Any]]:
        """Check CODE GATE: Run security validators on generated code.

        Args:
            code: The generated Python code (activities.py content)

        Returns:
            Tuple of (is_blocked, gate_result_dict)
        """
        if not self.enable_security or not self._code_validators:
            return False, {}

        gate_result = {
            "gate": "code",
            "validators_run": [],
            "issues_detected": [],
        }

        for validator in self._code_validators:
            validator_name = validator.__class__.__name__
            try:
                result = validator.validate(code)
                gate_result["validators_run"].append(validator_name)

                if result.is_threat:
                    issues = result.details.get("issues", [])
                    gate_result["issues_detected"].extend(issues)

                    if self.verbose:
                        console.print(
                            f"[red]🛡️ CODE GATE BLOCKED by {validator_name}[/red]\n"
                            f"  Issues: {len(issues)}\n"
                            f"  Details: {issues[:3]}..."  # Show first 3
                        )

                    gate_result["blocked"] = True
                    gate_result["blocked_by"] = validator_name
                    gate_result["total_issues"] = len(issues)
                    return True, gate_result

            except Exception as e:
                if self.verbose:
                    console.print(f"[yellow]⚠️ Code validator {validator_name} error: {e}[/yellow]")
                gate_result["validators_run"].append(f"{validator_name} (error)")

        gate_result["blocked"] = False
        return False, gate_result

    def _check_output_gate(self, output: str, session_id: str) -> tuple[bool, dict[str, Any]]:
        """Check OUTPUT GATE: Detect system prompt leakage via canary tokens.

        Args:
            output: The LLM output/response to check for canary leakage
            session_id: Session identifier for canary token lookup

        Returns:
            Tuple of (is_leaked, gate_result_dict)
        """
        if not self.enable_output_gate or not self._canary_manager:
            return False, {}

        gate_result = {
            "gate": "output",
            "validator": "canary_manager",
        }

        # Check for canary leakage
        leakage_result = self._canary_manager.check_leakage(output, session_id)

        if leakage_result.leaked:
            if self.verbose:
                console.print(
                    f"[red]🛡️ OUTPUT GATE BLOCKED - System prompt leaked![/red]\n"
                    f"  Canary token found at position: {leakage_result.match_position}"
                )

            gate_result["blocked"] = True
            gate_result["leaked"] = True
            gate_result["match_position"] = leakage_result.match_position
            gate_result["reason"] = "System prompt leaked - canary token detected in output"
            return True, gate_result

        gate_result["blocked"] = False
        gate_result["leaked"] = False
        return False, gate_result

    def run(self, task_input: TaskInput) -> BaselineResult:
        """Execute Code Factory baseline on a single task.

        Strategy: Compile once, run many times.
        All datasets treated the same - no special cases.

        Args:
            task_input: Task input with prompt and context

        Returns:
            BaselineResult with output and metrics
        """
        return asyncio.run(self._run_async(task_input))

    def run_batch(self, inputs: list[TaskInput]) -> list[BaselineResult]:
        """Run baseline on multiple inputs, grouping by signature for multi-example compilation.

        Args:
            inputs: List of task inputs to process

        Returns:
            List of results for each input
        """
        return asyncio.run(self._run_batch_async(inputs))

    async def _run_batch_async(self, inputs: list[TaskInput]) -> list[BaselineResult]:
        """Async batch processing with multi-example compilation.

        Groups tasks by signature and compiles with up to 10 examples for better generalization.
        """
        from collections import defaultdict

        # Group inputs by task template ID (extracted from task_id)
        # This ensures all instances of the same task are compiled together
        signature_groups: dict[str, list[TaskInput]] = defaultdict(list)
        for task_input in inputs:
            # Extract task template from task_id (e.g., "classification_01_ticket_001" -> "classification_01")
            # Pattern: {task_name}_{task_number}_{instance_name}_{instance_number}
            task_id_parts = task_input.task_id.split("_")

            # Find all numeric parts
            numeric_indices = [i for i, part in enumerate(task_id_parts) if part.isdigit()]

            if len(numeric_indices) >= 1:
                # Template is everything up to and including the FIRST numeric part (task number)
                # e.g., "classification_01_ticket_001" -> "classification_01"
                template_id = "_".join(task_id_parts[:numeric_indices[0] + 1])
            else:
                # No numeric parts - use task_id as-is (fallback)
                template_id = task_input.task_id

            signature_groups[template_id].append(task_input)

        # Process each group
        results = []
        for sig_key, group_inputs in signature_groups.items():
            # Take up to 10 examples for compilation
            compilation_examples = group_inputs[:10]

            if self.verbose:
                console.print(
                    f"[cyan]Processing group '{sig_key}' with {len(group_inputs)} tasks "
                    f"({len(compilation_examples)} examples for compilation)[/cyan]"
                )

            # Process first task (triggers compilation with all examples)
            first_result = await self._run_async_with_examples(
                group_inputs[0], compilation_examples
            )
            results.append(first_result)

            # Process remaining tasks (will use cached workflow)
            for task_input in group_inputs[1:]:
                result = await self._run_async(task_input)
                results.append(result)

        return results

    async def _run_async_with_examples(
        self, task_input: TaskInput, examples: list[TaskInput]
    ) -> BaselineResult:
        """Run async with multiple examples for compilation."""
        # Temporarily store examples for compilation
        self._current_examples = examples
        try:
            return await self._run_async(task_input)
        finally:
            self._current_examples = None

    async def _run_async(self, task_input: TaskInput) -> BaselineResult:
        """Async implementation with task classification and caching."""
        start_time = time.perf_counter()

        # Separate timing tracking for generation vs execution
        generation_time_ms: float | None = None
        execution_time_ms: float | None = None

        # SECURITY: INPUT GATE - Check before any processing
        if self.enable_security:
            input_blocked, input_gate_result = self._check_input_gate(task_input.prompt)
            if input_blocked:
                return BaselineResult(
                    task_id=task_input.task_id,
                    output=json.dumps({
                        "blocked": True,
                        **input_gate_result,
                    }),
                    success=True,  # Security gate worked correctly
                    error=None,
                    latency_ms=(time.perf_counter() - start_time) * 1000,
                    input_tokens=0,
                    output_tokens=0,
                    llm_calls=0,
                )

        try:
            # NEW: Extract task signature for classification
            signature = self.signature_extractor.extract(task_input)

            if self.verbose:
                console.print(
                    f"\n[bold blue]Task Signature:[/bold blue] "
                    f"[cyan]{signature.category}[/cyan] | "
                    f"[dim]{signature.prompt_hash[:8]}...[/dim]"
                )

            # NEW: Check cache for exact or similar match
            cached_workflow = self.workflow_cache.get(signature)
            if not cached_workflow:
                # Try similarity-based match
                cached_workflow = self.workflow_cache.find_similar(
                    signature, threshold=self.similarity_threshold
                )

            # Determine if compilation is needed
            needs_compilation = cached_workflow is None

            if needs_compilation:
                # Compilation phase
                compile_start = time.perf_counter()

                if self.verbose:
                    console.print(f"[yellow]⚡ Compilation needed for: {signature.category}[/yellow]")

                # Use stored examples if available (from run_batch), otherwise single task
                examples = getattr(self, '_current_examples', None) or [task_input]
                if self.verbose and len(examples) > 1:
                    console.print(f"[green]📚 Compiling with {len(examples)} examples for better generalization[/green]")

                compile_result = await self._compile(examples)

                # Record generation time
                generation_time_ms = (time.perf_counter() - compile_start) * 1000

                if not compile_result.success:
                    # Register failed workflow in activity registry
                    workflow_id = "compilation_failed"
                    if compile_result.plan:
                        workflow_id = compile_result.plan.workflow_id

                    self.activity_registry.register_workflow(
                        workflow_id=workflow_id,
                        category=signature.category,
                    )
                    self.activity_registry.record_execution(
                        workflow_id=workflow_id,
                        task_id=task_input.task_id,
                        success=False,
                        error=f"Compilation failed: {compile_result.validation_errors}",
                    )

                    return BaselineResult(
                        task_id=task_input.task_id,
                        output="",
                        success=False,
                        error=f"Compilation failed: {compile_result.validation_errors}",
                        latency_ms=(time.perf_counter() - start_time) * 1000,
                        input_tokens=compile_result.metrics.total_tokens if compile_result.metrics else 0,
                        output_tokens=0,
                        llm_calls=compile_result.regeneration_count + 1,
                    )

                # Cache the compiled workflow
                self.workflow_cache.put(signature, compile_result)

                # Register new workflow in activity registry
                if compile_result.plan:
                    self.activity_registry.register_workflow(
                        workflow_id=compile_result.plan.workflow_id,
                        category=signature.category,
                    )

                # Track compilation metrics
                compilation_tokens = compile_result.metrics.total_tokens if compile_result.metrics else 0
                self.metrics_tracker.record_compilation(
                    signature=signature,
                    tokens=compilation_tokens,
                    latency_ms=(time.perf_counter() - start_time) * 1000,
                    task_id=task_input.task_id,
                )

                factory_result = compile_result
            else:
                # Reusing cached workflow
                if self.verbose:
                    console.print(f"[green]♻️  Reusing cached workflow for: {signature.category}[/green]")

                factory_result = cached_workflow.factory_result

                # Track execution (will update latency later)
                self.metrics_tracker.record_execution(
                    signature=signature, tokens=0, latency_ms=0, success=True
                )

            # Store for debugging
            self._last_factory_result = factory_result

            # Execution phase (uses cached or freshly compiled workflow)
            execution_start = time.perf_counter()

            exec_result = await self._execute_compiled(
                task_input=task_input, factory_result=factory_result
            )

            # Record execution time
            execution_time_ms = (time.perf_counter() - execution_start) * 1000

            total_latency_ms = (time.perf_counter() - start_time) * 1000

            # SECURITY: OUTPUT GATE - Check for system prompt leakage
            if self.enable_output_gate and exec_result.get("output"):
                output_leaked, output_gate_result = self._check_output_gate(
                    output=exec_result.get("output", ""),
                    session_id=task_input.task_id,
                )
                if output_leaked:
                    return BaselineResult(
                        task_id=task_input.task_id,
                        output=json.dumps({
                            "blocked": True,
                            **output_gate_result,
                        }),
                        success=True,  # Security gate worked correctly
                        error=None,
                        latency_ms=total_latency_ms,
                        input_tokens=0,
                        output_tokens=0,
                        llm_calls=0,
                        generation_time_ms=generation_time_ms,
                        execution_time_ms=execution_time_ms,
                    )

            # Update execution latency in metrics
            if not needs_compilation and exec_result.get("success"):
                self.metrics_tracker.update_execution_latency(
                    signature=signature, latency_ms=total_latency_ms
                )

            # Calculate tokens to report with full breakdown
            if needs_compilation:
                # Get compilation token breakdown from factory result
                if factory_result.metrics:
                    gen_input_tokens = factory_result.metrics.total_input_tokens
                    gen_output_tokens = factory_result.metrics.total_output_tokens
                    compilation_tokens = factory_result.metrics.total_tokens
                else:
                    gen_input_tokens = 0
                    gen_output_tokens = 0
                    compilation_tokens = 0
                input_tokens = compilation_tokens
            else:
                gen_input_tokens = None
                gen_output_tokens = None
                compilation_tokens = 0
                input_tokens = 0  # Cached execution = 0 tokens

            # Track execution tokens (from LLM activities during workflow execution)
            exec_input_tokens = exec_result.get("input_tokens", 0)
            exec_output_tokens = exec_result.get("output_tokens", 0)
            execution_tokens = exec_input_tokens + exec_output_tokens

            # Record execution in activity registry
            workflow_id = "unknown"
            if factory_result and hasattr(factory_result, 'plan') and factory_result.plan:
                workflow_id = factory_result.plan.workflow_id

            success = exec_result.get("success", False)
            error = exec_result.get("error")

            self.activity_registry.record_execution(
                workflow_id=workflow_id,
                task_id=task_input.task_id,
                success=success,
                error=error,
            )

            return BaselineResult(
                task_id=task_input.task_id,
                output=exec_result.get("output", ""),
                success=success,
                error=error,
                latency_ms=total_latency_ms,
                input_tokens=input_tokens,
                output_tokens=execution_tokens,
                llm_calls=0,
                generation_time_ms=generation_time_ms,
                execution_time_ms=execution_time_ms,
                # Token breakdown
                generation_input_tokens=gen_input_tokens,
                generation_output_tokens=gen_output_tokens,
                execution_input_tokens=exec_input_tokens,
                execution_output_tokens=exec_output_tokens,
            )

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            if self.verbose:
                console.print(f"[red]Error: {e}[/red]\n[dim]{error_details}[/dim]")

            # Record exception in activity registry
            signature = self.signature_extractor.extract(task_input)
            self.activity_registry.register_workflow(
                workflow_id="exception",
                category=signature.category,
            )
            self.activity_registry.record_execution(
                workflow_id="exception",
                task_id=task_input.task_id,
                success=False,
                error=str(e),
            )

            return BaselineResult(
                task_id=task_input.task_id,
                output="",
                success=False,
                error=str(e),
                latency_ms=(time.perf_counter() - start_time) * 1000,
                llm_calls=0,
            )

    async def _compile(self, task_examples: list[TaskInput]) -> FactoryResult:
        """Compile workflow from task examples.

        This is the expensive phase with LLM calls for planning and code generation.

        Args:
            task_examples: List of task examples to learn from (max 10)

        Returns:
            FactoryResult with compiled workflow
        """
        # Use first example as primary task
        task_input = task_examples[0]
        if self.verbose:
            console.print(
                Panel.fit(
                    f"[bold cyan]Task:[/bold cyan] {task_input.task_id}\n"
                    f"[bold cyan]Prompt:[/bold cyan] {task_input.prompt}",
                    title="🏭 [bold yellow]Compilation Phase[/bold yellow]",
                    border_style="yellow",
                )
            )

        # Generate canary token for OUTPUT GATE if enabled
        canary_token: str | None = None
        if self.enable_output_gate and self._canary_manager:
            canary_token = self._canary_manager.generate(session_id=task_input.task_id)
            self._current_canary_token = canary_token
            if self.verbose:
                console.print(f"[cyan]🔐 OUTPUT GATE: Canary token injected for leakage detection[/cyan]")

        # Initialize factory with registry
        factory = CodeFactory(
            provider=self.provider,
            model=self.model,
            verbose=self.verbose,
            max_regenerations=self.max_regenerations,
            enable_registry=self.enable_registry,
            auto_register=self.auto_register,
            log_dir=self.log_dir,
            canary_token=canary_token,
        )

        # Generate workflow from task prompt with context information
        start_time = time.perf_counter()

        # Build enriched task description with multiple examples for better generalization
        import json
        task_description = task_input.prompt

        # Add multiple input/output examples (up to 10)
        if len(task_examples) > 1:
            task_description += f"\n\n**TRAINING EXAMPLES ({len(task_examples)} examples provided for generalization):**\n"
            task_description += f"\nYou have access to {len(task_examples)} examples to learn patterns and generalize your implementation.\n"

            for idx, example in enumerate(task_examples, 1):
                task_description += f"\n--- Example {idx} ---\n"
                if example.context:
                    task_description += f"**Inputs:**\n"
                    for key, value in example.context.items():
                        value_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                        value_preview = value_str[:150] + "..." if len(value_str) > 150 else value_str
                        task_description += f"  {key}: {value_preview}\n"

                if example.metadata and "expected_output" in example.metadata:
                    expected = example.metadata["expected_output"]
                    expected_str = json.dumps(expected) if isinstance(expected, (dict, list)) else str(expected)
                    expected_preview = expected_str[:150] + "..." if len(expected_str) > 150 else expected_str
                    task_description += f"**Expected Output:** {expected_preview}\n"

        # Document input variables - CRITICAL: prompt is the varying input!
        task_description += f"\n\n**IMPORTANT: The task provides these input variables:**\n"
        task_description += f"- `prompt` (string) - **THE RAW INPUT DATA** that varies per instance. Your activity MUST parse and process this!\n"

        if task_input.context:
            context_keys = list(task_input.context.keys())
            for key in context_keys:
                value = task_input.context[key]
                value_type = type(value).__name__
                task_description += f"- `{key}` ({value_type}) - context for task type\n"

        all_vars = ["prompt"] + (list(task_input.context.keys()) if task_input.context else [])
        task_description += f"\n**CRITICAL:** Your workflow MUST use `prompt` as the input variable. The prompt contains the raw data to process."
        task_description += f"\nAvailable variables: {', '.join(all_vars)}"

        # Use output_format (structure description) for compilation - NO specific values!
        # This prevents baking in example values into the compiled workflow
        if task_input.metadata and "output_format" in task_input.metadata:
            output_format = task_input.metadata["output_format"]
            if output_format:
                format_str = json.dumps(output_format, indent=2) if isinstance(output_format, dict) else str(output_format)

                task_description += f"\n\n**OUTPUT FORMAT (STRUCTURE DESCRIPTION - NO HARDCODED VALUES!):**\n"
                task_description += f"Your activity must return data matching this structure:\n"
                task_description += f"```json\n{format_str}\n```\n"
                task_description += f"\n**CRITICAL RULES:**\n"
                task_description += f"- The format above describes FIELD NAMES and TYPES only\n"
                task_description += f"- Extract ACTUAL values from the `prompt` variable at runtime\n"
                task_description += f"- Do NOT hardcode any values from examples\n"
                task_description += f"- Do NOT add extra fields\n"
                task_description += f"- Match field names EXACTLY as specified"

        # Fallback to expected_output for legacy datasets without output_format
        elif task_input.metadata and "expected_output" in task_input.metadata:
            expected = task_input.metadata["expected_output"]
            expected_str = json.dumps(expected, indent=2) if isinstance(expected, (dict, list)) else str(expected)

            task_description += f"\n\n**OUTPUT FORMAT (STRUCTURE REFERENCE - VALUES ARE EXAMPLES ONLY!):**\n"
            task_description += f"Your activity must return this structure:\n"
            task_description += f"```json\n{expected_str}\n```\n"
            task_description += f"\n**CRITICAL RULES:**\n"
            task_description += f"- The values above are EXAMPLES ONLY - do NOT hardcode them\n"
            task_description += f"- Extract ACTUAL values from the `prompt` variable at runtime\n"
            task_description += f"- Match the structure (field names, nesting, types) EXACTLY\n"
            task_description += f"- Do NOT add extra fields"

        # Detect if this is a function-calling task (has `functions` in context)
        is_function_call_task = (
            self.use_function_call_template and
            task_input.context and
            "functions" in task_input.context
        )

        if is_function_call_task:
            # Use template-based generation (skips Planner, saves ~50% tokens)
            model_info = f" with {self.function_call_model}" if self.function_call_model else ""
            if self.verbose:
                console.print(f"[cyan]🚀 Using function-call template (skipping Planner){model_info}[/cyan]")
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold blue]Generating activity (template mode)..."),
                    console=console,
                ) as progress:
                    progress.add_task("compile", total=None)
                    result = await factory.generate_function_call_workflow(
                        task_description=task_description,
                        task_id=task_input.task_id,
                        examples=task_examples,
                        coder_model=self.function_call_model,
                        temperature=self.function_call_temperature,
                        max_tokens=self.function_call_max_tokens,
                    )
            else:
                result = await factory.generate_function_call_workflow(
                    task_description=task_description,
                    task_id=task_input.task_id,
                    examples=task_examples,
                    coder_model=self.function_call_model,
                    temperature=self.function_call_temperature,
                    max_tokens=self.function_call_max_tokens,
                )
        else:
            # Use full Planner + Coder pipeline (for complex workflows)
            if self.verbose:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold blue]Generating workflow (full pipeline)..."),
                    console=console,
                ) as progress:
                    progress.add_task("compile", total=None)
                    result = await factory.generate(task_description, examples=task_examples)
            else:
                result = await factory.generate(task_description, examples=task_examples)

        self._compilation_latency_ms = (time.perf_counter() - start_time) * 1000

        # Track compilation tokens
        if result.metrics:
            self._compilation_tokens = result.metrics.total_tokens

        if result.success:
            # SECURITY: CODE GATE - Check generated code before saving
            if self.enable_security and result.activities_code:
                code_blocked, code_gate_result = self._check_code_gate(result.activities_code)
                if code_blocked:
                    result.success = False
                    result.validation_errors = result.validation_errors or []
                    result.validation_errors.append(
                        f"CODE GATE blocked: {code_gate_result.get('blocked_by', 'unknown')} "
                        f"found {code_gate_result.get('total_issues', 0)} security issues"
                    )
                    # Store gate result for metrics
                    result._code_gate_result = code_gate_result
                    if self.verbose:
                        console.print(
                            Panel(
                                f"[red]🛡️ CODE GATE BLOCKED[/red]\n"
                                f"Validator: {code_gate_result.get('blocked_by')}\n"
                                f"Issues: {code_gate_result.get('total_issues', 0)}",
                                title="❌ [bold red]Security Validation Failed[/bold red]",
                                border_style="red",
                            )
                        )
                    # Fall through to the else block for failure handling

        if result.success:
            self._compiled = result
            self._compilation_task_id = task_input.task_id

            # Save workflow artifacts for inspection
            self._save_workflow_artifacts(result, task_description, task_input.task_id)

            if self.verbose:
                console.print(
                    Panel(
                        f"[green]✓[/green] Workflow: [bold]{result.plan.name}[/bold]\n"
                        f"[green]✓[/green] Activities: {len(result.plan.activities)}\n"
                        f"[green]✓[/green] Tokens: {self._compilation_tokens:,}\n"
                        f"[green]✓[/green] Latency: {self._compilation_latency_ms:.0f}ms\n"
                        f"[green]✓[/green] Regenerations: {result.regeneration_count}",
                        title="✅ [bold green]Compilation Success[/bold green]",
                        border_style="green",
                    )
                )

                # Show workflow diagram
                console.print("\n[bold cyan]Workflow Structure:[/bold cyan]\n")
                diagram = visualize_workflow(result.workflow_yaml)
                console.print(diagram)
        else:
            if self.verbose:
                console.print(
                    Panel(
                        f"[red]✗[/red] Errors: {result.validation_errors}",
                        title="❌ [bold red]Compilation Failed[/bold red]",
                        border_style="red",
                    )
                )

        return result

    def _save_workflow_artifacts(
        self, factory_result: FactoryResult, task_description: str, task_id: str
    ) -> None:
        """Save workflow artifacts to disk for inspection.

        Args:
            factory_result: Successful compilation result
            task_description: The enriched task description sent to planner
            task_id: Task identifier for organizing artifacts
        """
        from pathlib import Path
        import json

        # Create workflows directory
        workflows_dir = Path("workflows") / factory_result.plan.workflow_id
        workflows_dir.mkdir(parents=True, exist_ok=True)

        # Save workflow YAML
        yaml_file = workflows_dir / "workflow.yaml"
        yaml_file.write_text(factory_result.workflow_yaml)

        # Save activities Python code
        activities_file = workflows_dir / "activities.py"
        activities_file.write_text(factory_result.activities_code)

        # Save metadata for each activity
        for activity in factory_result.plan.activities:
            meta = {
                "activity_name": activity.name,
                "description": activity.description,
                "task_id": task_id,
                "task_description": task_description,
                "inputs": [
                    {
                        "name": param.name,
                        "type": param.type,
                        "description": param.description,
                        "required": param.required,
                    }
                    for param in activity.inputs
                ],
                "output": {
                    "type": activity.output.type if activity.output else None,
                    "description": activity.output.description if activity.output else None,
                    "fields": activity.output.fields if activity.output else None,
                } if activity.output else None,
                "reference_activity": activity.reference_activity,
                "workflow_spec": {
                    "workflow_id": factory_result.plan.workflow_id,
                    "name": factory_result.plan.name,
                    "description": factory_result.plan.description,
                    "execution_pattern": factory_result.plan.execution_pattern,
                },
            }

            meta_file = workflows_dir / f"{activity.name}_meta.json"
            meta_file.write_text(json.dumps(meta, indent=2))

        # Save overall workflow metadata
        workflow_meta = {
            "workflow_id": factory_result.plan.workflow_id,
            "name": factory_result.plan.name,
            "description": factory_result.plan.description,
            "task_id": task_id,
            "task_description": task_description,
            "activities": [a.name for a in factory_result.plan.activities],
            "variables": [
                {"name": v.name, "default": v.default_value}
                for v in factory_result.plan.variables
            ],
            "execution_pattern": factory_result.plan.execution_pattern,
            "reasoning": factory_result.plan.reasoning,
            "metrics": {
                "total_tokens": factory_result.metrics.total_tokens if factory_result.metrics else 0,
                "regeneration_count": factory_result.regeneration_count,
            },
        }

        workflow_meta_file = workflows_dir / "workflow_meta.json"
        workflow_meta_file.write_text(json.dumps(workflow_meta, indent=2))

        if self.verbose:
            console.print(f"  [dim]💾 Saved artifacts to: {workflows_dir}[/dim]")

    async def _execute_compiled(
        self, task_input: TaskInput, factory_result: FactoryResult
    ) -> dict[str, Any]:
        """Execute compiled workflow with dynamic activity loading.

        NO LLM FALLBACK - if workflow fails, task fails.
        This ensures scientific validity of metrics.

        Args:
            task_input: Task to execute
            factory_result: Compiled workflow to execute

        Returns:
            Execution result dict with token tracking
        """
        try:
            if self.verbose:
                console.print(
                    f"\n[bold blue]▸[/bold blue] Executing task: [cyan]{task_input.task_id}[/cyan]"
                )

            # Create a token tracker for this execution
            execution_tracker = TokenTracker()

            # Wrap the LLM client to track execution tokens
            class TrackedLLMClient:
                """Wrapper that tracks token usage during execution."""
                def __init__(self, client, tracker):
                    self.client = client
                    self.tracker = tracker

                def generate(self, prompt: str, **kwargs):
                    response = self.client.generate(prompt, **kwargs)
                    self.tracker.record(response)
                    return response

            tracked_client = TrackedLLMClient(self.llm_client, execution_tracker)

            # NEW: Load activities dynamically from generated code with tracked client
            activities = self.module_loader.load(
                activities_code=factory_result.activities_code,
                workflow_id=factory_result.plan.workflow_id,
                llm_client=tracked_client,
            )

            if self.verbose:
                console.print(
                    f"  [dim]✓ Loaded {len(activities)} activities: {list(activities.keys())}[/dim]"
                )

            # Create executor with loaded activities
            from ..factory.XYLocalWorkflowExecutor.src.xy_local_executor import (
                LocalWorkflowExecutor,
            )
            import tempfile
            from pathlib import Path

            executor = LocalWorkflowExecutor(
                mock_activities=activities,
                dry_run=False,
                verbose=self.verbose,
            )

            # Prepare input variables from context AND prompt
            variables = {}

            # Always include the prompt/input as a variable
            # This is the user query that contains values to extract
            variables["prompt"] = task_input.prompt

            # Add context data AS-IS - executor handles Python objects directly
            if task_input.context:
                for key, value in task_input.context.items():
                    # For scalar values, convert to string. For complex types, pass as-is
                    if isinstance(value, (dict, list)):
                        # Pass complex objects directly - executor handles them
                        variables[key] = value
                    else:
                        # Convert scalars to strings
                        variables[key] = str(value)

            if self.verbose:
                console.print(f"  [dim]Variables: {list(variables.keys())}[/dim]")
                for key, value in variables.items():
                    value_preview = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                    console.print(f"  [dim]  {key} = {value_preview}[/dim]")

            # Write workflow YAML to temp file
            temp_dir = tempfile.mkdtemp(prefix="code_factory_")
            workflow_file = Path(temp_dir) / "workflow.yaml"
            workflow_file.write_text(factory_result.workflow_yaml)

            # Execute workflow
            result = await executor.run_yaml(str(workflow_file), variables=variables)

            # Clean up temp directory
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

            # Extract output from result
            output = self._extract_output(result)

            if self.verbose:
                output_preview = str(output)[:100] + ("..." if len(str(output)) > 100 else "")
                console.print(f"  [green]✓ Output: {output_preview}[/green]")

            return {
                "success": True,
                "output": str(output),
                "input_tokens": execution_tracker.input_tokens,
                "output_tokens": execution_tracker.output_tokens,
            }

        except Exception as e:
            # NO FALLBACK - strict mode for scientific validity
            import traceback
            error_details = traceback.format_exc()

            if self.verbose:
                console.print(
                    Panel(
                        f"[red]{str(e)}[/red]\n\n[dim]{error_details}[/dim]",
                        title="❌ [bold red]Execution Error[/bold red]",
                        border_style="red",
                    )
                )

            return {
                "success": False,
                "error": str(e),
                "output": "",
                "error_details": error_details,
                "input_tokens": 0,
                "output_tokens": 0,
            }

    def _extract_output(self, result: Any) -> str:
        """Extract output from workflow result.

        The LocalWorkflowExecutor returns all workflow variables as a dict.
        We need to find the final result variable by looking for common
        output variable names or the last non-input variable.

        Args:
            result: Workflow execution result (dict of all variables)

        Returns:
            Extracted output string or JSON
        """
        if not isinstance(result, dict):
            return str(result)

        # Try common final result variable names (in priority order)
        result_keys = [
            "final_result",
            "final_output",
            "result",
            "output",
            "response",
            "answer",
        ]

        for key in result_keys:
            if key in result:
                value = result[key]
                # If the value is a dict, convert to JSON for structured output
                if isinstance(value, dict):
                    import json
                    return json.dumps(value)
                return str(value)

        # Fallback: Find the last set variable that looks like output
        # (exclude obvious input variables, but include transformed/result data)
        candidates = {}
        for k, v in result.items():
            # Include variables that look like results (transformed_*, *_result, *_output)
            # Exclude obvious inputs (source_*, *_input, *_prompt, *_text, *_schema)
            is_likely_input = (
                any(k.startswith(prefix) for prefix in ["source_"]) or
                any(k.endswith(suffix) for suffix in ["_input", "_prompt", "_text", "_schema"])
            )
            if not is_likely_input:
                candidates[k] = v

        # Return the last candidate (assuming last set = final result)
        if candidates:
            last_key = list(candidates.keys())[-1]
            value = candidates[last_key]
            if isinstance(value, dict):
                import json
                return json.dumps(value)
            return str(value)

        # Ultimate fallback: stringify the whole dict
        import json
        return json.dumps(result)

    def get_compilation_summary(self) -> dict[str, Any]:
        """Get enhanced compilation summary with cache and amortization analysis.

        Returns:
            Dictionary with:
            - cache_statistics: Workflow cache metrics
            - amortization_analysis: Cost amortization and break-even points
            - configuration: Baseline configuration
        """
        cache_stats = self.workflow_cache.get_statistics()
        amortization = self.metrics_tracker.get_amortization_report()

        return {
            "cache_statistics": cache_stats,
            "amortization_analysis": amortization,
            "configuration": {
                "cache_size": self.workflow_cache._max_size,
                "similarity_threshold": self.similarity_threshold,
                "registry_enabled": self.enable_registry,
                "auto_register": self.auto_register,
            },
        }

    def get_token_summary(self) -> dict[str, Any]:
        """Get cumulative token usage summary.

        Returns:
            Dictionary with token usage statistics
        """
        return {
            "compilation_tokens": self._compilation_tokens,
            "compilation_latency_ms": self._compilation_latency_ms,
            "execution_token_savings": "0 per task (deterministic execution)",
            "compiled_workflow": self._compiled is not None,
        }
