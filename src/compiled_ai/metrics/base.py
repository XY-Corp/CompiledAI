"""Base metrics framework for collecting and storing benchmark results."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


@dataclass
class BenchmarkMetadata:
    """Metadata for a benchmark run."""

    benchmark_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    task_name: str = ""
    method: str = ""  # "compiled", "direct_llm", "langchain", "multi_agent"
    model: str = ""
    notes: str = ""


@dataclass
class MetricsResult:
    """Container for a single metrics measurement."""

    name: str
    value: float | int | str | bool
    unit: str = ""
    category: str = ""  # token_efficiency, latency, consistency, etc.
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class MetricsCollector:
    """Collects and aggregates benchmark metrics."""

    def __init__(self, metadata: BenchmarkMetadata | None = None) -> None:
        """Initialize the metrics collector.

        Args:
            metadata: Optional benchmark metadata
        """
        self.metadata = metadata or BenchmarkMetadata(
            benchmark_id=datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        self.results: list[MetricsResult] = []

    def record(
        self,
        name: str,
        value: float | int | str | bool,
        unit: str = "",
        category: str = "",
    ) -> None:
        """Record a metric value.

        Args:
            name: Metric name
            value: Metric value
            unit: Optional unit string
            category: Metric category
        """
        result = MetricsResult(
            name=name,
            value=value,
            unit=unit,
            category=category,
        )
        self.results.append(result)

    def get_by_category(self, category: str) -> list[MetricsResult]:
        """Get all metrics in a category.

        Args:
            category: Category to filter by

        Returns:
            List of metrics in the category
        """
        return [r for r in self.results if r.category == category]

    def get_by_name(self, name: str) -> MetricsResult | None:
        """Get a metric by name (returns most recent).

        Args:
            name: Metric name

        Returns:
            Most recent metric with that name, or None
        """
        matches = [r for r in self.results if r.name == name]
        return matches[-1] if matches else None

    def to_dict(self) -> dict[str, Any]:
        """Convert all metrics to a dictionary."""
        return {
            "metadata": asdict(self.metadata),
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save_json(self, path: str | Path) -> None:
        """Save metrics to a JSON file.

        Args:
            path: Output file path
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert metrics to a pandas DataFrame.

        Returns:
            DataFrame with metrics data

        Raises:
            ImportError: If pandas is not installed
        """
        if not HAS_PANDAS:
            raise ImportError("pandas is required for to_dataframe()")

        records = []
        for result in self.results:
            record = result.to_dict()
            record.update(asdict(self.metadata))
            records.append(record)

        return pd.DataFrame(records)

    def save_parquet(self, path: str | Path) -> None:
        """Save metrics to a Parquet file.

        Args:
            path: Output file path

        Raises:
            ImportError: If pandas is not installed
        """
        if not HAS_PANDAS:
            raise ImportError("pandas is required for save_parquet()")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df = self.to_dataframe()
        df.to_parquet(path, index=False)

    @classmethod
    def load_json(cls, path: str | Path) -> "MetricsCollector":
        """Load metrics from a JSON file.

        Args:
            path: Input file path

        Returns:
            MetricsCollector with loaded data
        """
        path = Path(path)
        data = json.loads(path.read_text())

        metadata = BenchmarkMetadata(**data["metadata"])
        collector = cls(metadata)

        for result_data in data["results"]:
            collector.results.append(MetricsResult(**result_data))

        return collector


def merge_collectors(collectors: list[MetricsCollector]) -> MetricsCollector:
    """Merge multiple collectors into one.

    Args:
        collectors: List of collectors to merge

    Returns:
        New collector with all results
    """
    if not collectors:
        return MetricsCollector()

    merged = MetricsCollector(metadata=collectors[0].metadata)
    for collector in collectors:
        merged.results.extend(collector.results)

    return merged
