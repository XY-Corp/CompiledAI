# Code Factory Registry

This directory contains the persistent template registry for the Code Factory.

## Structure

```
workflows/
├── .registry/
│   ├── registry.json          # Template metadata and usage stats
│   └── templates/             # Saved activity templates
│       └── {template_name}.py # Individual template source code
├── {workflow_id}/             # Generated workflows
│   ├── workflow.yaml
│   └── activities.py
└── ...
```

## Registry Format

`registry.json` contains:
- **templates**: Map of template_name → metadata
  - category: Template category (llm, data, http, etc.)
  - tags: Search tags
  - description: What the template does
  - usage_count: How many times it's been used
  - success_rate: Success rate (0.0 to 1.0)
  - created_at: Timestamp
  - parent_templates: Templates this was derived from

## Purpose

The registry tracks:
1. **Successfully generated activities** for reuse
2. **Usage statistics** to prioritize popular patterns
3. **Template lineage** to understand evolution
4. **Search metadata** for fast template discovery

## Lifecycle

1. **Compilation** - Code Factory generates workflow
2. **Registration** - Successful activities saved as templates
3. **Search** - Future tasks search registry for similar patterns
4. **Adaptation** - Templates adapted (not copied) for new tasks
5. **Evolution** - New patterns learned and stored
