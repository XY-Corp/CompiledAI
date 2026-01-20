"""Activity accuracy registry for tracking workflow reliability."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class WorkflowStats:
    """Statistics for a workflow's performance."""

    workflow_id: str
    category: str
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_used: str | None = None
    created_at: str | None = None

    # Recent failures for debugging
    recent_failures: list[dict[str, str]] = field(default_factory=list)
    max_failures_tracked: int = 5

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        if self.usage_count == 0:
            return 0.0
        return self.success_count / self.usage_count

    def record_success(self, task_id: str) -> None:
        """Record a successful execution."""
        self.usage_count += 1
        self.success_count += 1
        self.last_used = datetime.now().isoformat()

    def record_failure(self, task_id: str, error: str) -> None:
        """Record a failed execution."""
        self.usage_count += 1
        self.failure_count += 1
        self.last_used = datetime.now().isoformat()

        # Track recent failures (keep last N)
        self.recent_failures.append({
            "task_id": task_id,
            "error": error[:200],  # Truncate long errors
            "timestamp": datetime.now().isoformat(),
        })

        # Keep only recent failures
        if len(self.recent_failures) > self.max_failures_tracked:
            self.recent_failures = self.recent_failures[-self.max_failures_tracked:]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "workflow_id": self.workflow_id,
            "category": self.category,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(self.success_rate, 3),
            "last_used": self.last_used,
            "created_at": self.created_at,
            "recent_failures": self.recent_failures,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowStats":
        """Create from dictionary."""
        return cls(
            workflow_id=data["workflow_id"],
            category=data["category"],
            usage_count=data.get("usage_count", 0),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            last_used=data.get("last_used"),
            created_at=data.get("created_at"),
            recent_failures=data.get("recent_failures", []),
        )


class ActivityRegistry:
    """Manages the activity accuracy registry."""

    def __init__(self, registry_path: Path | str = "workflows/.registry/registry.json"):
        """Initialize registry.

        Args:
            registry_path: Path to the registry JSON file
        """
        self.registry_path = Path(registry_path)
        self.workflows: dict[str, WorkflowStats] = {}
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        if not self.registry_path.exists():
            # Create default registry
            self._save()
            return

        try:
            with open(self.registry_path) as f:
                data = json.load(f)

            # Load workflow stats
            workflows_data = data.get("workflows", {})
            for workflow_id, stats_data in workflows_data.items():
                self.workflows[workflow_id] = WorkflowStats.from_dict(stats_data)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Failed to load registry: {e}. Creating new registry.")
            self.workflows = {}

    def _save(self) -> None:
        """Save registry to disk."""
        # Ensure directory exists
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "workflows": {
                workflow_id: stats.to_dict()
                for workflow_id, stats in self.workflows.items()
            },
        }

        with open(self.registry_path, "w") as f:
            json.dump(data, f, indent=2)

    def register_workflow(self, workflow_id: str, category: str) -> None:
        """Register a new workflow if not already registered.

        Args:
            workflow_id: Unique workflow identifier
            category: Workflow category (e.g., "classification", "extraction")
        """
        if workflow_id not in self.workflows:
            self.workflows[workflow_id] = WorkflowStats(
                workflow_id=workflow_id,
                category=category,
                created_at=datetime.now().isoformat(),
            )
            self._save()

    def record_execution(
        self, workflow_id: str, task_id: str, success: bool, error: str | None = None
    ) -> None:
        """Record a workflow execution result.

        Args:
            workflow_id: Workflow that was executed
            task_id: Task that was run
            success: Whether execution succeeded
            error: Error message if failed
        """
        if workflow_id not in self.workflows:
            # Auto-register if not known
            self.register_workflow(workflow_id, category="unknown")

        stats = self.workflows[workflow_id]

        if success:
            stats.record_success(task_id)
        else:
            stats.record_failure(task_id, error or "Unknown error")

        self._save()

    def get_stats(self, workflow_id: str) -> WorkflowStats | None:
        """Get statistics for a workflow.

        Args:
            workflow_id: Workflow to query

        Returns:
            WorkflowStats if found, None otherwise
        """
        return self.workflows.get(workflow_id)

    def get_all_stats(self) -> list[WorkflowStats]:
        """Get all workflow statistics.

        Returns:
            List of all workflow stats, sorted by usage count
        """
        return sorted(
            self.workflows.values(),
            key=lambda s: s.usage_count,
            reverse=True,
        )

    def get_reliable_workflows(self, min_usage: int = 3, min_success_rate: float = 0.8) -> list[WorkflowStats]:
        """Get workflows that are proven reliable.

        Args:
            min_usage: Minimum number of uses to be considered
            min_success_rate: Minimum success rate (0.0 to 1.0)

        Returns:
            List of reliable workflows
        """
        return [
            stats
            for stats in self.workflows.values()
            if stats.usage_count >= min_usage and stats.success_rate >= min_success_rate
        ]

    def get_unreliable_workflows(self, min_usage: int = 3, max_success_rate: float = 0.5) -> list[WorkflowStats]:
        """Get workflows that are unreliable.

        Args:
            min_usage: Minimum number of uses to be considered
            max_success_rate: Maximum success rate (0.0 to 1.0)

        Returns:
            List of unreliable workflows
        """
        return [
            stats
            for stats in self.workflows.values()
            if stats.usage_count >= min_usage and stats.success_rate <= max_success_rate
        ]
