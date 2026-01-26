"""Dataset converters - convert any dataset to generic {input, possible_outputs} format."""

from .base import DatasetInstance, DatasetConverter
from .xy_converter import XYConverter
from .bfcl_converter import BFCLConverter
from .swebench_converter import SWEBenchConverter, load_swebench
from .eltbench_converter import ELTBenchConverter, load_eltbench
from .runner import run_benchmark, run_benchmark_with_baseline_name, BenchmarkResult, InstanceResult

__all__ = [
    "DatasetInstance",
    "DatasetConverter",
    "XYConverter",
    "BFCLConverter",
    "SWEBenchConverter",
    "load_swebench",
    "ELTBenchConverter",
    "load_eltbench",
    "run_benchmark",
    "run_benchmark_with_baseline_name",
    "BenchmarkResult",
    "InstanceResult",
]
