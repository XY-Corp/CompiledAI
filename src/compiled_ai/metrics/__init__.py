"""Metrics: Token efficiency, latency, consistency, reliability, code quality, validation, cost.

This module provides comprehensive metrics for evaluating Compiled AI systems
based on the framework.md research including MLPerf, AgentBench, CLASSic,
and Pan & Wang 2025 benchmarks.
"""

from .base import BenchmarkMetadata, MetricsCollector, MetricsResult, merge_collectors
from .code_quality import CodeQualityMetrics, calculate_pass_at_k
from .consistency import ConsistencyMetrics, SchemaComplianceMetrics
from .cost import APIPricing, CostMetrics, calculate_tco
from .latency import LatencyComparison, LatencyMetrics
from .reliability import CLASSicMetrics, FailureMode, ReliabilityMetrics
from .token_efficiency import TokenComparison, TokenMetrics
from .validation_pipeline import ValidationPipelineMetrics, ValidationStage

__all__ = [
    # Base
    "BenchmarkMetadata",
    "MetricsCollector",
    "MetricsResult",
    "merge_collectors",
    # Token Efficiency
    "TokenMetrics",
    "TokenComparison",
    # Latency
    "LatencyMetrics",
    "LatencyComparison",
    # Consistency
    "ConsistencyMetrics",
    "SchemaComplianceMetrics",
    # Reliability
    "ReliabilityMetrics",
    "CLASSicMetrics",
    "FailureMode",
    # Code Quality
    "CodeQualityMetrics",
    "calculate_pass_at_k",
    # Validation Pipeline
    "ValidationPipelineMetrics",
    "ValidationStage",
    # Cost
    "CostMetrics",
    "APIPricing",
    "calculate_tco",
]
