"""Benchmarking utilities for local workflow execution.

This module provides tools for collecting and reporting activity timing data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ActivityBenchmark:
    """Benchmark data for a single activity execution."""
    name: str
    path: str  # DSL tree path (e.g., "root.seq[0].foreach.item[3].activity[name]")
    start_time: datetime
    end_time: datetime
    duration_ms: float
    status: str  # "success", "error", "skipped"
    error: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "path": self.path,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
        }


@dataclass
class ActivitySummary:
    """Summary statistics for an activity type."""
    name: str
    count: int
    total_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    error_count: int


@dataclass
class BenchmarkSummary:
    """Summary of all benchmarks."""
    activities: List[ActivitySummary]
    total_activities: int
    total_duration_ms: float
    total_errors: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def wall_clock_ms(self) -> float:
        """Total wall-clock time (accounts for parallel execution)."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return self.total_duration_ms


class BenchmarkCollector:
    """Collect and report activity benchmarks."""

    def __init__(self):
        self.benchmarks: List[ActivityBenchmark] = []
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None

    def start(self):
        """Mark the start of workflow execution."""
        self._start_time = datetime.now()

    def end(self):
        """Mark the end of workflow execution."""
        self._end_time = datetime.now()

    def record(self, benchmark: ActivityBenchmark):
        """Record an activity benchmark."""
        self.benchmarks.append(benchmark)

    def clear(self):
        """Clear all recorded benchmarks."""
        self.benchmarks.clear()
        self._start_time = None
        self._end_time = None

    def summary(self) -> BenchmarkSummary:
        """Generate summary statistics."""
        # Group by activity name
        by_name: Dict[str, List[ActivityBenchmark]] = {}
        for b in self.benchmarks:
            by_name.setdefault(b.name, []).append(b)

        activities = []
        for name, items in sorted(by_name.items()):
            durations = [b.duration_ms for b in items]
            error_count = sum(1 for b in items if b.status == "error")

            activities.append(ActivitySummary(
                name=name,
                count=len(items),
                total_ms=sum(durations),
                avg_ms=sum(durations) / len(durations) if durations else 0,
                min_ms=min(durations) if durations else 0,
                max_ms=max(durations) if durations else 0,
                error_count=error_count,
            ))

        return BenchmarkSummary(
            activities=activities,
            total_activities=len(self.benchmarks),
            total_duration_ms=sum(b.duration_ms for b in self.benchmarks),
            total_errors=sum(1 for b in self.benchmarks if b.status == "error"),
            start_time=self._start_time,
            end_time=self._end_time,
        )

    def to_json(self, indent: int = 2) -> str:
        """Export benchmarks to JSON."""
        summary = self.summary()
        return json.dumps({
            "summary": {
                "total_activities": summary.total_activities,
                "total_duration_ms": summary.total_duration_ms,
                "total_errors": summary.total_errors,
                "wall_clock_ms": summary.wall_clock_ms,
            },
            "activities": [
                {
                    "name": a.name,
                    "count": a.count,
                    "total_ms": a.total_ms,
                    "avg_ms": a.avg_ms,
                    "min_ms": a.min_ms,
                    "max_ms": a.max_ms,
                    "error_count": a.error_count,
                }
                for a in summary.activities
            ],
            "benchmarks": [b.to_dict() for b in self.benchmarks],
        }, indent=indent)

    def print_report(self, show_details: bool = False):
        """Print a formatted benchmark report to stdout."""
        summary = self.summary()

        print()
        print("=" * 80)
        print("BENCHMARK REPORT")
        print("=" * 80)
        print()
        print(f"{'Activity':<40} {'Count':>6} {'Total(ms)':>12} {'Avg(ms)':>10} {'Max(ms)':>10}")
        print("-" * 80)

        for a in summary.activities:
            error_marker = f" ({a.error_count} errors)" if a.error_count else ""
            print(
                f"{a.name:<40} {a.count:>6} {a.total_ms:>12,.0f} "
                f"{a.avg_ms:>10,.0f} {a.max_ms:>10,.0f}{error_marker}"
            )

        print("-" * 80)
        print(f"Total activities: {summary.total_activities}")
        print(f"Total duration: {summary.total_duration_ms:,.0f}ms ({summary.total_duration_ms/1000:.1f}s)")
        if summary.wall_clock_ms != summary.total_duration_ms:
            efficiency = (summary.total_duration_ms / summary.wall_clock_ms * 100) if summary.wall_clock_ms > 0 else 0
            print(f"Wall-clock time: {summary.wall_clock_ms:,.0f}ms ({summary.wall_clock_ms/1000:.1f}s)")
            print(f"Parallel efficiency: {efficiency:.0f}%")
        if summary.total_errors:
            print(f"Errors: {summary.total_errors}")
        print("=" * 80)

        if show_details:
            print()
            print("ACTIVITY DETAILS")
            print("-" * 80)
            for b in sorted(self.benchmarks, key=lambda x: x.start_time):
                status_icon = "x" if b.status == "error" else "v"
                print(f"[{status_icon}] {b.name} ({b.duration_ms:.0f}ms) - {b.path}")
                if b.error:
                    print(f"    Error: {b.error}")
