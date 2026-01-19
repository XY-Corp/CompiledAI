# Code Factory with Activity Template Registry

## Quick Start

```python
from compiled_ai.factory.code_factory import CodeFactory

# Initialize with registry enabled
factory = CodeFactory(
    provider="anthropic",
    verbose=True,
    enable_registry=True,      # Enable template search
    auto_register=True,        # Auto-register successful activities
)

# Generate workflow - planner will search templates automatically
result = await factory.generate(
    "Extract customer data and send confirmation email"
)

if result.success:
    print(f"✅ Generated: {result.plan.name}")
    print(f"Activities: {[a.name for a in result.plan.activities]}")
```

## Features

### 1. Built-in Templates (8 total)
- **LLM Activities**: `llm_generate`, `llm_extract`, `llm_classify`, `llm_transform`
- **HTTP**: `http_fetch`
- **Notifications**: `send_email`
- **Data**: `validate_data`, `json_transform`

### 2. Template Search
The planner agent has access to a `search_templates` tool:

```python
# Templates are automatically searched during planning
# You can also search manually:
results = factory.registry.search("extract data from text", limit=5)
for r in results:
    print(f"{r.template.name} (score: {r.score})")
```

### 3. Auto-Registration
Successfully validated activities are automatically added to the registry:

```python
# After generation, check registry growth
initial = len(factory.registry.list_all())
result = await factory.generate("Process customer orders")
final = len(factory.registry.list_all())
print(f"Added {final - initial} new templates")
```

## Examples

### Running the Test Suite
```bash
uv run python scripts/code_factory/test_registry.py
```

Tests:
- ✅ Built-in template loading
- ✅ Template search functionality
- ✅ Factory integration
- ✅ Auto-registration
- ✅ Registry growth

### Running the Simple Example
```bash
uv run python scripts/code_factory/example_registry_usage.py
```

Demonstrates:
- Registry initialization
- Template browsing
- Template search
- Workflow generation with templates
- Registry growth tracking

## API Reference

### CodeFactory

```python
CodeFactory(
    provider: str = "anthropic",           # LLM provider
    model: str | None = None,              # Model name (optional)
    verbose: bool = False,                 # Enable logging
    max_regenerations: int = 3,            # Max retry attempts
    enable_registry: bool = True,          # Enable template registry
    auto_register: bool = True,            # Auto-register activities
)
```

### TemplateRegistry

```python
registry = TemplateRegistry()

# Search templates
results = registry.search(
    query="extract data",                  # Natural language query
    category=TemplateCategory.LLM,         # Optional category filter
    limit=5                                # Max results
)

# List all templates
templates = registry.list_all(category=TemplateCategory.DATA)

# Get specific template
template = registry.get("llm_extract")
```

### ActivityRegistrar

```python
registrar = ActivityRegistrar(
    registry=registry,
    policy=RegistrationPolicy(
        require_validation=True,           # Require validation before registration
        allow_duplicates=False,            # Skip duplicates
        min_success_rate=0.8,              # Minimum success rate (future)
        max_name_length=50                 # Max activity name length
    )
)

# Manual registration
result = registrar.attempt_registration(
    name="my_activity",
    source_code="async def my_activity()...",
    generation_prompt="Create an activity that...",
    parent_templates=["llm_extract"],
    validation_result={"passed": True}
)
```

## Template Categories

- `llm` - LLM-based activities (generation, extraction, classification)
- `http` - HTTP requests and API calls
- `data` - Data processing and validation
- `notification` - Email, SMS, alerts
- `database` - Database operations
- `file` - File I/O operations
- `custom` - Custom generated activities

## How It Works

1. **User provides task description** → "Extract customer data from support tickets"

2. **Planner agent searches templates** using `search_templates` tool
   - Finds `llm_extract` template (built-in)
   - Reviews source code and description
   - Designs workflow structure

3. **Coder agent generates custom code**
   - Receives template as inspiration
   - Adapts pattern to specific task
   - Generates new activity code

4. **Validation pipeline**
   - Syntax check (AST, mypy)
   - Execution test
   - Output validation

5. **Auto-registration** (if successful)
   - Extracts metadata (category, tags, description)
   - Checks for duplicates
   - Adds to registry for future use

## Design Principles

1. **Templates as Inspiration**: Activities are code examples, not direct execution targets
2. **Always Generate New Code**: Coder adapts templates, never copies verbatim
3. **Self-Improving**: Registry grows with successful generations
4. **Hybrid Search**: Keyword + tag + category matching (fast, no heavy dependencies)
5. **Lineage Tracking**: Track which templates inspired new activities

## Files

- [`test_registry.py`](test_registry.py) - Comprehensive test suite
- [`example_registry_usage.py`](example_registry_usage.py) - Simple usage example
- [`IMPLEMENTATION_SUMMARY.md`](IMPLEMENTATION_SUMMARY.md) - Detailed implementation notes
- [`README.md`](README.md) - This file

## Next Steps

### Immediate
- ✅ Core registry implemented
- ✅ Auto-registration working
- ✅ Tests passing

### Near-term (Phase 3)
- [ ] Dataset integration (BFCL, XY Benchmark, AgentBench)
- [ ] Dataset-driven test suite
- [ ] Success rate tracking per dataset

### Future (Phase 4)
- [ ] Semantic search with embeddings
- [ ] Template versioning
- [ ] Disk persistence
- [ ] Template lineage from planner searches
- [ ] Multi-template composition
- [ ] ML-based success prediction

## Support

For issues or questions:
- Check [`IMPLEMENTATION_SUMMARY.md`](IMPLEMENTATION_SUMMARY.md) for detailed architecture
- Run tests: `uv run python scripts/code_factory/test_registry.py`
- Review example: `uv run python scripts/code_factory/example_registry_usage.py`
