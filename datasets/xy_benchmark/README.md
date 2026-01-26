# CompiledAI-Bench

A benchmark for evaluating Compiled AI systems on enterprise workflow tasks.

## Overview

CompiledAI-Bench tests the ability of LLM-based systems to generate correct, validated code from workflow specifications. Unlike agent benchmarks that evaluate runtime reasoning, this benchmark focuses on **one-shot code generation** with **deterministic execution**.

## Task Categories

| Category | Description | Example Tasks |
|----------|-------------|---------------|
| **Document Processing** | Extract and transform structured data from documents | EOB parsing, invoice extraction, form processing |
| **Data Transformation** | Map, merge, and normalize data between schemas | Patient record merge, FHIR mapping, data normalization |
| **Decision Logic** | Implement business rules and eligibility checks | Insurance eligibility, claims routing, validation rules |
| **API Orchestration** | Coordinate multi-step API workflows | Lab result sync, data pipeline coordination |

## Task Format

Each task includes:

```json
{
  "id": "task_id",
  "name": "Human-readable name",
  "category": "document_processing|data_transformation|decision_logic|api_orchestration",
  "difficulty": "easy|medium|hard",
  "specification": {
    "natural_language": "Plain English description of the task",
    "input_schema": { /* JSON Schema */ },
    "output_schema": { /* JSON Schema */ }
  },
  "test_cases": [
    {
      "id": "tc_001",
      "input": { /* Test input */ },
      "expected_output": { /* Expected output */ }
    }
  ],
  "validation_hints": { /* Implementation guidance */ }
}
```

## Evaluation Metrics

### Primary Metrics
- **Exact Match Rate**: Percentage of test cases with correct output
- **Functional Pass Rate**: Percentage passing all validation stages

### Secondary Metrics
- **Generation Tokens**: Tokens consumed during code generation
- **Security Score**: Static analysis findings (Bandit/Semgrep)
- **Type Coverage**: mypy type checking coverage
- **Cyclomatic Complexity**: Code complexity measure

### Operational Metrics
- **First Pass Rate**: Percentage passing validation without regeneration
- **Regeneration Distribution**: Distribution of retry attempts

## Usage

```python
import json
from pathlib import Path

# Load benchmark index
with open("index.json") as f:
    index = json.load(f)

# Load a specific task
task_path = index["tasks"][0]["path"]
with open(task_path) as f:
    task = json.load(f)

# Run evaluation
for test_case in task["test_cases"]:
    input_data = test_case["input"]
    expected = test_case["expected_output"]
    
    # Generate code from specification
    generated_code = your_model.generate(task["specification"])
    
    # Execute and compare
    actual = execute_generated_code(generated_code, input_data)
    assert actual == expected
```

## Current Status

- **Tasks**: 7 (target: 80)
- **Test Cases**: 15 (target: 400)
- **Categories Covered**: 4/4

## Contributing

To add new tasks:
1. Create a JSON file in the appropriate `tasks/` subdirectory
2. Follow the task format schema
3. Include at least 3 test cases with varied inputs
4. Update `index.json` with the new task

## License

MIT License - XY.AI Labs
