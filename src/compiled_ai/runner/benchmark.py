"""Benchmark runner for executing baselines on datasets."""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..baselines.base import BaseBaseline, BaselineResult, TaskInput, get_baseline
from ..evaluation import EvaluationResult, get_evaluator
from ..metrics import MetricsCollector, merge_collectors
from .dataset import Dataset, Task
from .loader import DatasetLoader


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark execution."""

    dataset_name: str
    baseline_name: str

    # Filtering
    categories: list[str] | None = None
    difficulties: list[str] | None = None
    task_ids: list[str] | None = None
    max_instances: int | None = None

    # Execution
    timeout_seconds: float = 60.0

    # Output
    output_dir: Path = field(default_factory=lambda: Path("results"))
    save_responses: bool = True


@dataclass
class InstanceLog:
    """Log entry for a single task instance execution."""

    instance_id: str
    prompt: str
    output: str
    expected_output: Any
    success: bool
    error: str | None = None
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    evaluation_score: float = 0.0
    evaluation_details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Results for a single task."""

    task: Task
    results: list[BaselineResult] = field(default_factory=list)
    logs: list[InstanceLog] = field(default_factory=list)
    metrics: MetricsCollector = field(default_factory=MetricsCollector)

    @property
    def success_rate(self) -> float:
        """Calculate success rate for this task."""
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.success) / len(self.results)

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency for successful results."""
        successful = [r.latency_ms for r in self.results if r.success]
        return sum(successful) / len(successful) if successful else 0.0


@dataclass
class BenchmarkResult:
    """Complete benchmark results."""

    config: BenchmarkConfig
    task_results: list[TaskResult] = field(default_factory=list)
    metrics: MetricsCollector = field(default_factory=MetricsCollector)

    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration_seconds(self) -> float:
        """Total benchmark duration in seconds."""
        return self.end_time - self.start_time

    @property
    def overall_success_rate(self) -> float:
        """Calculate overall success rate across all tasks."""
        total = sum(len(tr.results) for tr in self.task_results)
        success = sum(
            sum(1 for r in tr.results if r.success) for tr in self.task_results
        )
        return success / total if total > 0 else 0.0

    def to_dict(self, include_logs: bool = True) -> dict[str, Any]:
        """Convert results to dictionary for serialization.

        Args:
            include_logs: Whether to include detailed prompt/output logs

        Returns:
            Dictionary representation of results
        """
        result = {
            "config": {
                "dataset": self.config.dataset_name,
                "baseline": self.config.baseline_name,
            },
            "summary": {
                "duration_seconds": self.duration_seconds,
                "overall_success_rate": self.overall_success_rate,
                "total_tasks": len(self.task_results),
                "total_instances": sum(
                    len(tr.results) for tr in self.task_results
                ),
            },
            "tasks": [
                {
                    "task_id": tr.task.task_id,
                    "name": tr.task.name,
                    "category": tr.task.category.value,
                    "difficulty": tr.task.difficulty.value,
                    "success_rate": tr.success_rate,
                    "avg_latency_ms": tr.avg_latency_ms,
                    "instance_count": len(tr.results),
                }
                for tr in self.task_results
            ],
            "metrics": self.metrics.to_dict(),
        }

        # Add detailed logs if requested
        if include_logs and self.config.save_responses:
            result["logs"] = [
                {
                    "task_id": tr.task.task_id,
                    "instances": [
                        {
                            "instance_id": log.instance_id,
                            "prompt": log.prompt,
                            "output": log.output,
                            "expected_output": log.expected_output,
                            "success": log.success,
                            "error": log.error,
                            "latency_ms": log.latency_ms,
                            "input_tokens": log.input_tokens,
                            "output_tokens": log.output_tokens,
                            "evaluation_score": log.evaluation_score,
                            "evaluation_details": log.evaluation_details,
                        }
                        for log in tr.logs
                    ],
                }
                for tr in self.task_results
            ]

        return result

    def save(self, path: Path | None = None) -> Path:
        """Save results to JSON file.

        Args:
            path: Path to save to. If None, generates timestamped path.

        Returns:
            Path where results were saved
        """
        if path is None:
            self.config.output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            path = self.config.output_dir / (
                f"{self.config.baseline_name}_{self.config.dataset_name}"
                f"_{timestamp}.json"
            )

        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

        return path


class BenchmarkRunner:
    """Runs baselines on datasets and collects metrics."""

    def __init__(self, datasets_dir: Path | str = "datasets") -> None:
        """Initialize the benchmark runner.

        Args:
            datasets_dir: Base directory for datasets
        """
        self.loader = DatasetLoader(datasets_dir)

    def run(
        self, config: BenchmarkConfig, **baseline_kwargs: Any
    ) -> BenchmarkResult:
        """Run a benchmark with the given configuration.

        Args:
            config: Benchmark configuration
            **baseline_kwargs: Additional arguments for the baseline

        Returns:
            BenchmarkResult with all metrics
        """
        # Load dataset
        dataset = self.loader.load(config.dataset_name)
        return self.run_with_dataset(config, dataset, **baseline_kwargs)

    def run_with_dataset(
        self, config: BenchmarkConfig, dataset: Dataset, **baseline_kwargs: Any
    ) -> BenchmarkResult:
        """Run a benchmark with a pre-loaded dataset.

        Args:
            config: Benchmark configuration
            dataset: Pre-loaded Dataset object
            **baseline_kwargs: Additional arguments for the baseline

        Returns:
            BenchmarkResult with all metrics
        """
        result = BenchmarkResult(config=config)
        result.start_time = time.time()

        # Filter tasks
        tasks = self._filter_tasks(dataset, config)

        # Initialize baseline
        baseline = get_baseline(config.baseline_name, **baseline_kwargs)

        # Run each task
        for task in tasks:
            task_result = self._run_task(task, baseline, config)
            result.task_results.append(task_result)
            result.metrics = merge_collectors([result.metrics, task_result.metrics])

        result.end_time = time.time()

        # Save results
        if config.output_dir:
            result.save()

        return result

    def _filter_tasks(
        self, dataset: Dataset, config: BenchmarkConfig
    ) -> list[Task]:
        """Filter tasks based on configuration.

        Args:
            dataset: Dataset to filter
            config: Configuration with filter criteria

        Returns:
            Filtered list of tasks
        """
        tasks = dataset.tasks

        if config.task_ids:
            tasks = [t for t in tasks if t.task_id in config.task_ids]

        if config.categories:
            tasks = [t for t in tasks if t.category.value in config.categories]

        if config.difficulties:
            tasks = [t for t in tasks if t.difficulty.value in config.difficulties]

        return tasks

    def _run_task(
        self, task: Task, baseline: BaseBaseline, config: BenchmarkConfig
    ) -> TaskResult:
        """Run a baseline on a single task.

        Args:
            task: Task to run
            baseline: Baseline to execute
            config: Benchmark configuration

        Returns:
            TaskResult with all instance results
        """
        task_result = TaskResult(task=task)

        instances = task.instances
        if config.max_instances:
            instances = instances[: config.max_instances]

        # Get evaluator for this task's evaluation type
        evaluator = self._get_evaluator(task.evaluation_type)

        for instance in instances:
            # Build the prompt
            prompt = task.prompt_template.format(**instance.input_data)

            # Convert to TaskInput
            # Build metadata with output_format if available (CRITICAL for Code Factory)
            metadata = {
                "task_name": task.name,
                "category": task.category.value,
                "difficulty": task.difficulty.value,
                "expected_output": instance.expected_output,  # Include for format reference
            }

            # Add output_format if available (needed for Code Factory compilation)
            if hasattr(instance, 'metadata') and instance.metadata and "output_format" in instance.metadata:
                metadata["output_format"] = instance.metadata["output_format"]

            task_input = TaskInput(
                task_id=f"{task.task_id}_{instance.instance_id}",
                prompt=prompt,
                context=instance.input_data,
                metadata=metadata,
            )

            # Run baseline
            result = baseline.run(task_input)

            # Evaluate output against expected
            eval_result = self._evaluate_output(
                evaluator, result.output, instance.expected_output
            )

            # Update result success based on evaluation
            result.success = eval_result.success

            task_result.results.append(result)

            # Create log entry with evaluation details
            log = InstanceLog(
                instance_id=instance.instance_id,
                prompt=prompt,
                output=result.output,
                expected_output=instance.expected_output,
                success=eval_result.success,
                error=result.error or eval_result.error,
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                evaluation_score=eval_result.score,
                evaluation_details=eval_result.details,
            )
            task_result.logs.append(log)

            # Print immediate feedback if verbose baseline (e.g., code_factory)
            if hasattr(baseline, 'verbose') and baseline.verbose:
                from rich.console import Console
                console = Console()
                status_icon = "✓" if eval_result.success else "✗"
                status_color = "green" if eval_result.success else "red"
                console.print(f"\n[{status_color}]{status_icon}[/{status_color}] [cyan]{task.task_id}_{instance.instance_id}[/cyan]")
                if result.error:
                    console.print(f"  [dim]Error:[/dim] [red]{result.error}[/red]")
                console.print(f"  [dim]Expected:[/dim] [green]{instance.expected_output}[/green]")
                console.print(f"  [dim]Actual:[/dim]   [yellow]{result.output}[/yellow]")

        # Collect metrics
        task_result.metrics = baseline.to_metrics_collector(task_result.results)

        return task_result

    def _get_evaluator(self, evaluation_type: str):
        """Get evaluator for the given evaluation type.

        Args:
            evaluation_type: Type of evaluation (exact_match, json_match, ast_match, schema)

        Returns:
            Evaluator instance
        """
        # Map evaluation types to evaluator names
        type_mapping = {
            "exact_match": "exact_match",
            "fuzzy_match": "fuzzy_match",
            "json_match": "json_match",
            "ast_match": "ast_match",
            "schema": "schema",
            "milestone": "fuzzy_match",  # Fallback for AgentBench
        }

        evaluator_name = type_mapping.get(evaluation_type, "exact_match")
        return get_evaluator(evaluator_name)

    def _evaluate_output(
        self, evaluator, output: str, expected: Any
    ) -> EvaluationResult:
        """Evaluate output against expected result.

        Args:
            evaluator: Evaluator to use
            output: LLM output
            expected: Expected result

        Returns:
            EvaluationResult
        """
        try:
            return evaluator.evaluate(output, expected)
        except Exception as e:
            return EvaluationResult(
                success=False,
                score=0.0,
                error=f"Evaluation error: {e}",
            )
