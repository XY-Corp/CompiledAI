"""PydanticAI-based Code Factory for generating Temporal workflow YAMLs and activities."""

from .factory import CodeFactory, FactoryResult
from .models import (
    ActivityParam,
    ActivitySpec,
    WorkflowVariable,
    WorkflowSpec,
    GeneratedActivity,
    GeneratedFiles,
)
from .template_registry import (
    TemplateRegistry,
    TemplateCategory,
    ActivityTemplate,
    SearchResult,
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

__all__ = [
    # Core factory
    "CodeFactory",
    "FactoryResult",
    # Models
    "ActivityParam",
    "ActivitySpec",
    "WorkflowVariable",
    "WorkflowSpec",
    "GeneratedActivity",
    "GeneratedFiles",
    # Template registry
    "TemplateRegistry",
    "TemplateCategory",
    "ActivityTemplate",
    "SearchResult",
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
]
