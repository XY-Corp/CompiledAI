"""PydanticAI-based Code Factory for generating Temporal workflow YAMLs and activities."""

from .factory import CodeFactory, FactoryResult, BFCLResult
from .models import (
    ActivityParam,
    ActivitySpec,
    WorkflowVariable,
    WorkflowSpec,
    GeneratedActivity,
    GeneratedFiles,
    BFCLFunctionCallOutput,
)
# NOTE: Dataset conversion is now handled by compiled_ai.datasets converters
from .template_registry import (
    TemplateRegistry,
    TemplateCategory,
    ActivityTemplate,
    SearchResult,
)
from .semantic_search import (
    SemanticActivityIndex,
    SemanticSearchResult,
)
from .registration import (
    ActivityRegistrar,
    RegistrationPolicy,
    RegistrationResult,
)
from .visualizer import visualize_workflow, WorkflowVisualizer
from .task_signature import TaskSignature, TaskSignatureExtractor
from .workflow_cache import WorkflowCacheManager, CachedWorkflow
from .dynamic_loader import DynamicModuleLoader, DynamicLoadError
from .compilation_metrics import CompilationMetricsTracker, CompilationStats
from .retry import retry_with_backoff, run_agent_with_retry

__all__ = [
    # Core factory
    "CodeFactory",
    "FactoryResult",
    "BFCLResult",
    # Models
    "ActivityParam",
    "ActivitySpec",
    "WorkflowVariable",
    "WorkflowSpec",
    "GeneratedActivity",
    "GeneratedFiles",
    "BFCLFunctionCallOutput",
    # Template registry
    "TemplateRegistry",
    "TemplateCategory",
    "ActivityTemplate",
    "SearchResult",
    # Semantic search
    "SemanticActivityIndex",
    "SemanticSearchResult",
    # Registration
    "ActivityRegistrar",
    "RegistrationPolicy",
    "RegistrationResult",
    # Visualization
    "visualize_workflow",
    "WorkflowVisualizer",
    # Task classification and caching
    "TaskSignature",
    "TaskSignatureExtractor",
    "WorkflowCacheManager",
    "CachedWorkflow",
    # Dynamic execution
    "DynamicModuleLoader",
    "DynamicLoadError",
    # Metrics tracking
    "CompilationMetricsTracker",
    "CompilationStats",
    # Retry utilities
    "retry_with_backoff",
    "run_agent_with_retry",
]
