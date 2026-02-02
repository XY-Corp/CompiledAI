# Crush-Based Workflow Generator

Generate complete CompiledAI workflows from natural language descriptions using the Crush CLI with Claude or other language models.

## Features

- **Natural Language Input**: Describe what you want in plain English
- **Complete Generation**: Creates both workflow YAML and Python activity implementations
- **Iterative Refinement**: Automatically fixes errors through multiple iterations
- **Security Validation**: Integrates with CompiledAI's security validation pipeline
- **Metrics Tracking**: Tracks generation time, iterations, and first-try success rate
- **Multi-Model Support**: Works with Claude (Bedrock), Gemini, and other Crush-supported models

## Installation

1. Install Crush CLI:
```bash
brew install charmbracelet/tap/crush
```

2. Configure your model provider credentials (AWS for Bedrock, Google for Gemini, etc.)

3. Verify installation:
```bash
crush --version
crush models  # List available models
```

## Quick Start

### Python API

```python
from compiled_ai.factory.crush_generator import CrushGenerator

# Create generator (auto-detects available model)
generator = CrushGenerator()

# Generate a workflow
result = generator.generate(
    "Create a workflow that validates email addresses and categorizes them"
)

if result.success:
    print(f"✅ Generated successfully!")
    print(f"Workflow: {result.workflow_path}")
    print(f"Activities: {result.activities_path}")
    print(f"Iterations: {result.iterations}")
    print(f"First-try success: {result.metrics.first_try_success}")
else:
    print(f"❌ Failed after {result.iterations} iterations")
    for error in result.errors[-3:]:
        print(f"  - {error[:100]}")
```

### CLI

```bash
# Basic usage
python -m compiled_ai.factory.crush_generator "Validate email addresses"

# With output directory
python -m compiled_ai.factory.crush_generator -o ./my_workflow "Process CSV files"

# With specific model
python -m compiled_ai.factory.crush_generator \
    -m bedrock/anthropic.claude-opus-4-5-20251101-v1:0 \
    "Build a data pipeline"

# JSON output (for scripting)
python -m compiled_ai.factory.crush_generator --json "Create a validator" > result.json

# Save metrics
python -m compiled_ai.factory.crush_generator \
    --metrics-file metrics.json \
    "Process user data"

# Disable security validation (faster, less safe)
python -m compiled_ai.factory.crush_generator --no-security "Quick prototype"
```

## CLI Options

| Option | Description |
|--------|-------------|
| `-o, --output DIR` | Output directory for generated files |
| `-m, --model MODEL` | Model to use (e.g., `bedrock/anthropic.claude-opus-4-5-20251101-v1:0`) |
| `-i, --max-iterations N` | Maximum fix iterations (default: 5) |
| `-t, --timeout SECONDS` | Timeout per step (default: 180) |
| `-q, --quiet` | Quiet mode (minimal output) |
| `--json` | Output result as JSON |
| `--no-security` | Disable security validation |
| `--security-threshold` | Security severity threshold (`low`, `medium`, `high`) |
| `--metrics-file FILE` | Save metrics to file |

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
    type: list
    description: List of email addresses to validate
    required: true

activities:
  - name: validate_email
    description: Validate a single email address format
    inputs:
      - name: email
        type: str
        description: Email address to validate
    output:
      type: bool
      description: True if valid, False otherwise
    result_variable: is_valid

  - name: categorize_emails
    description: Categorize emails into valid and invalid lists
    inputs:
      - name: emails
        type: list
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
from typing import Any


def validate_email(email: str) -> bool:
    """Validate email format using regex.
    
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


def categorize_emails(emails: list) -> dict:
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
    print("Testing activities...")
    
    # Test validate_email
    assert validate_email("test@example.com") == True
    assert validate_email("invalid-email") == False
    print("  ✓ validate_email")
    
    # Test categorize_emails
    result = categorize_emails(["good@test.com", "bad", "also@valid.org"])
    assert len(result["valid"]) == 2
    assert len(result["invalid"]) == 1
    print("  ✓ categorize_emails")
    
    print("\nAll tests passed! ✅")
```

## Example Workflows

### Simple Validation
```python
result = generator.generate("""
    Create a workflow that:
    1. Takes a list of email addresses
    2. Validates each email format
    3. Returns valid and invalid lists
""")
```

### Multi-Step Data Pipeline
```python
result = generator.generate("""
    Create a workflow that:
    1. Parses JSON input data
    2. Validates the schema
    3. Transforms nested objects to flat structure
    4. Filters records where age > 18
    5. Calculates aggregate statistics
    6. Returns a summary report
""")
```

### Parallel Processing
```python
result = generator.generate("""
    Create a workflow with parallel execution:
    1. Takes a list of data sources
    2. Processes each source based on type (numbers, text, list)
    3. Merges all results into unified report
    
    Use foreach execution pattern for parallelism.
""")
```

## Metrics

The generator tracks detailed metrics:

```python
if result.metrics:
    print(f"Total time: {result.metrics.total_time_seconds:.1f}s")
    print(f"First-try success: {result.metrics.first_try_success}")
    
    # Stage breakdown
    for stage, stats in result.metrics._stages_summary().items():
        print(f"  {stage}: {stats['success']}/{stats['count']} succeeded")
```

Save metrics to file:
```bash
python -m compiled_ai.factory.crush_generator \
    --metrics-file metrics.json \
    "Create a workflow"
```

## Security Validation

By default, generated code is validated using:
- **Bandit**: Python SAST scanner
- **detect-secrets**: Credential detection
- **Semgrep**: Pattern-based security rules
- **CodeShield**: Meta's LLM code validator

Disable for faster iteration (not recommended for production):
```python
generator = CrushGenerator(enable_security_validation=False)
```

Or set severity threshold:
```python
generator = CrushGenerator(security_severity_threshold="high")  # Only fail on high
```

## Testing

Run the test suite:

```bash
# Unit tests only (no API calls)
python test_generator.py --unit-only

# Full tests with API
python test_generator.py -v

# With specific model
python test_generator.py -m bedrock/anthropic.claude-opus-4-5-20251101-v1:0 -v
```

## Troubleshooting

### "Crush CLI not found"
Install Crush: `brew install charmbracelet/tap/crush`

### "No working model found"
Configure credentials for your model provider:
- **AWS Bedrock**: Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- **Gemini**: Set `GOOGLE_API_KEY`
- **Anthropic**: Set `ANTHROPIC_API_KEY`

### "Security validation failed"
The generated code has security issues. Either:
1. Let the generator fix them (happens automatically)
2. Lower the threshold: `--security-threshold high`
3. Disable validation: `--no-security`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python test_generator.py --unit-only`
5. Submit a pull request

## License

Part of CompiledAI. See the main repository license.
