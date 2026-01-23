# CompiledAI - Code Factory

This project implements "Compiled AI" - a paradigm where LLMs generate deterministic code at compile-time rather than executing dynamically at runtime.

## Key Concepts

- **Code Factory**: Generates Temporal workflow YAMLs and Python activities from natural language
- **Template Registry**: Searchable library of activity templates with semantic search (Ball Tree + embeddings)
- **Self-Healing Loop**: Auto-regeneration on validation failures with error feedback
- **Workflow Cache**: LRU cache for reusing compiled workflows based on task signatures

## Directory Structure

- `src/compiled_ai/factory/code_factory/` - Core factory implementation
  - `factory.py` - Main CodeFactory class with Planner and Coder agents
  - `models.py` - Pydantic models (WorkflowSpec, ActivitySpec, etc.)
  - `template_registry.py` - Searchable activity templates
  - `semantic_search.py` - Ball Tree semantic search with embeddings
  - `task_signature.py` - Task fingerprinting for caching
  - `workflow_cache.py` - LRU cache for compiled workflows
  - `dynamic_loader.py` - Runtime execution of generated code
  - `visualizer.py` - ASCII workflow diagrams
- `workflows/` - Generated and example workflows
- `tests/` - Test suite

## Common Tasks

```bash
# Run tests
uv run pytest tests/

# Run the benchmark
uv run python -m compiled_ai.baselines.code_factory

# Search activities (Python)
from compiled_ai.factory.code_factory import TemplateRegistry
registry = TemplateRegistry()
results = registry.semantic_search("extract email fields")
```

## Code Style

- Use async/await for all LLM and I/O operations
- Type hints required (mypy strict mode)
- Pydantic for all data models
- Keep activities pure and side-effect free where possible

## CRITICAL: Generic Dataset Handling

**ALL datasets MUST go through the EXACT SAME Code Factory pipeline. NO special code paths for different datasets.**

The architecture:
1. **Standardized Format**: Transform any dataset (BFCL, AgentBench, DocILE, etc.) to standardized format:
   - `input`: The input variables for the task (ALWAYS extracted the same way)
   - `context`: Additional context (functions, schemas, etc.)
   - `valid_outputs`: List of acceptable outputs (ALWAYS extracted the same way, supports multiple valid answers)
   - `evaluation_type`: How to compare outputs

   **Input/Output extraction is ALWAYS done by the transformer, NEVER in the baseline.**
   The baseline receives standardized `TaskInput` with `prompt`, `context`, and `metadata["expected_output"]`.

2. **Single Code Path**: All tasks flow through `_run_async()` which uses:
   - `TaskSignatureExtractor` for task classification
   - `WorkflowCacheManager` for caching compiled workflows
   - `_compile()` for workflow generation (calls `CodeFactory.generate()`)
   - `_save_workflow_artifacts()` for saving to disk
   - `ActivityRegistry` for tracking activity accuracy
   - `MetricsTracker` for compilation/execution metrics
   - `_execute_compiled()` for running the workflow

3. **NO hardcoded patterns**: Never write dataset-specific parameter extraction, function implementations, or output formatting. The Planner → Coder pipeline handles everything generically.

4. **Task Description Building**: For datasets that need special formatting (like BFCL with function definitions), use adapter classes to BUILD the task description, then pass it through the normal `_run_async()` flow:
   ```python
   # CORRECT: Build description, use normal flow
   task_description = adapter.build_task_description(query, functions)
   modified_input = TaskInput(prompt=task_description, context={...})
   return await self._run_async(modified_input)

   # WRONG: Separate code path that bypasses infrastructure
   factory_result = await factory.generate(...)  # Missing registry, metrics, artifacts!
   ```

This ensures we can add new benchmark datasets without writing new code paths - just add a transformer to convert to standardized format.
