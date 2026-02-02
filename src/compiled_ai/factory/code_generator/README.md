# OpenCode-Based Workflow Generator

Generate complete CompiledAI workflows from natural language descriptions using the OpenCode CLI with Claude or other language models.

## Features

- **Natural Language Input**: Describe what you want in plain English
- **Per-Activity Generation**: Each activity is generated separately with precise specs
- **Spec Validation**: Validates generated code against the activity specification
- **Iterative Refinement**: Automatically fixes errors through multiple iterations
- **Security Validation**: Integrates with CompiledAI's security validation pipeline
- **Metrics Tracking**: Tracks generation time, iterations, and first-try success rate
- **Multi-Model Support**: Works with Claude (Anthropic), Gemini, and other OpenCode-supported models

## Installation

1. Install OpenCode CLI:
```bash
go install github.com/opencode-ai/opencode@latest
```

2. Configure your model provider credentials (Anthropic for Claude, Google for Gemini, etc.)

3. Verify installation:
```bash
opencode --version
opencode models  # List available models
```

## Quick Start

### Python API

```python
from compiled_ai.factory.code_generator import CodeGenerator

# Create generator (auto-detects available model)
generator = CodeGenerator()

# Generate a workflow
result = generator.generate(
    "Create a workflow that validates email addresses and categorizes them"
)

if result.success:
    print(f"Generated successfully!")
    print(f"Workflow: {result.workflow_path}")
    print(f"Activities: {result.activities_path}")
    print(f"Activities first-try: {result.metrics.activities_first_try}/{result.metrics.activities_generated}")
else:
    print(f"Failed")
    for error in result.errors[-3:]:
        print(f"  - {error[:100]}")
```

### CLI

```bash
# Basic usage
python -m compiled_ai.factory.code_generator "Validate email addresses"

# With output directory
python -m compiled_ai.factory.code_generator -o ./my_workflow "Process CSV files"

# With specific model
python -m compiled_ai.factory.code_generator \
    -m anthropic/claude-sonnet-4-5-20250929 \
    "Build a data pipeline"

# JSON output (for scripting)
python -m compiled_ai.factory.code_generator --json "Create a validator" > result.json

# Save metrics
python -m compiled_ai.factory.code_generator \
    --metrics-file metrics.json \
    "Process user data"

# Disable security validation (faster, less safe)
python -m compiled_ai.factory.code_generator --no-security "Quick prototype"
```

## CLI Options

| Option | Description |
|--------|-------------|
| `-o, --output DIR` | Output directory for generated files |
| `-m, --model MODEL` | Model to use (e.g., `anthropic/claude-sonnet-4-5-20250929`) |
| `-i, --max-iterations N` | Maximum workflow iterations (default: 3) |
| `-r, --max-retries N` | Maximum retries per activity (default: 2) |
| `-t, --timeout SECONDS` | Timeout per step (default: 120) |
| `-q, --quiet` | Quiet mode (minimal output) |
| `--json` | Output result as JSON |
| `--no-security` | Disable security validation |
| `--metrics-file FILE` | Save metrics to file |

## Generation Pipeline

The generator uses a three-phase pipeline:

### Phase 1: YAML Planning
- Takes natural language task description
- Generates `workflow.yaml` with activity specifications
- Each activity includes: name, goal, inputs (with types), output (with type)

### Phase 2: Per-Activity Code Generation
- For each activity in the workflow:
  1. Extract precise spec (goal, inputs, output)
  2. Build focused prompt with spec
  3. OpenCode generates single function
  4. Validate signature matches spec
  5. Retry with error feedback if validation fails

### Phase 3: Assembly + Integration Test
- Combine activities into `activities.py`
- Run end-to-end validation
- Execute test block

## Generated Output

The generator creates two files:

### workflow.yaml
```yaml
workflow_id: email_validator
name: Email Validator
description: |
  Validates email addresses and categorizes them into valid and invalid lists.

variables:
  - name: email_list
    type: list[str]
    description: List of email addresses to validate
    required: true

activities:
  - name: validate_email
    goal: Check if email string matches standard email format
    inputs:
      - name: email
        type: str
        description: Email address to validate
    output:
      type: bool
      description: True if valid, False otherwise
    result_variable: is_valid

  - name: categorize_emails
    goal: Categorize emails into valid and invalid lists
    inputs:
      - name: emails
        type: list[str]
        description: List of emails to categorize
    output:
      type: dict
      description: Dict with 'valid' and 'invalid' lists
    result_variable: categorized

execution_pattern: sequence
```

### activities.py
```python
"""Activity implementations for Email Validator."""

import re
from typing import Any, Optional

def validate_email(email: str) -> bool:
    """Check if email string matches standard email format.

    Args:
        email: Email address to validate

    Returns:
        True if email format is valid, False otherwise

    Raises:
        TypeError: If email is not a string
    """
    if not isinstance(email, str):
        raise TypeError(f"email must be str, got {type(email).__name__}")

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def categorize_emails(emails: list[str]) -> dict:
    """Categorize emails into valid and invalid lists.

    Args:
        emails: List of email addresses

    Returns:
        Dict with 'valid' and 'invalid' lists
    """
    if not isinstance(emails, list):
        raise TypeError(f"emails must be list, got {type(emails).__name__}")

    result = {"valid": [], "invalid": []}
    for email in emails:
        if validate_email(email):
            result["valid"].append(email)
        else:
            result["invalid"].append(email)

    return result


if __name__ == "__main__":
    import sys

    print('Testing activities...')
    try:
        result = validate_email("test")
        print(f'  validate_email: OK')

        result = categorize_emails([])
        print(f'  categorize_emails: OK')

        print('All tests passed!')

    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
```

## Activity Specification

Each activity in the YAML includes a precise specification:

```yaml
- name: validate_email_format    # snake_case function name
  goal: Check if email matches standard format  # Single-sentence purpose
  inputs:
    - name: email               # Parameter name
      type: str                 # Python type annotation
      description: The email address to validate
  output:
    type: bool                  # Python return type
    description: True if valid, False otherwise
  result_variable: is_valid     # For data flow to next activity
```

## Metrics

The generator tracks detailed metrics:

```python
if result.metrics:
    print(f"Total time: {result.metrics.total_time_seconds:.1f}s")
    print(f"Activities: {result.metrics.activities_first_try}/{result.metrics.activities_generated} first-try")

    # Stage breakdown
    for stage, stats in result.metrics._stages_summary().items():
        print(f"  {stage}: {stats['success']}/{stats['count']} succeeded")
```

## Security Validation

By default, generated code is validated using:
- **Bandit**: Python SAST scanner
- **detect-secrets**: Credential detection
- **Semgrep**: Pattern-based security rules
- **CodeShield**: Meta's LLM code validator

Disable for faster iteration (not recommended for production):
```python
generator = CodeGenerator(enable_security_validation=False)
```

## Troubleshooting

### "OpenCode CLI not found"
Install OpenCode: `go install github.com/opencode-ai/opencode@latest`

### "No working model found"
Configure credentials for your model provider:
- **Anthropic**: Set `ANTHROPIC_API_KEY`
- **Gemini**: Set `GOOGLE_API_KEY`

### "Security validation failed"
The generated code has security issues. Either:
1. Let the generator fix them (happens automatically)
2. Disable validation: `--no-security`

## License

Part of CompiledAI. See the main repository license.
