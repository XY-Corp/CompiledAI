"""Dataset loaders for various benchmark formats."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .dataset import Dataset, Task, TaskCategory, TaskDifficulty, TaskInstance
from .standardized import StandardizedDataset
from .transformers import get_transformer, transform_dataset


class DatasetAdapter(ABC):
    """Base adapter for converting external datasets."""

    name: str = "base"

    @abstractmethod
    def load(self, path: Path, **kwargs: Any) -> Dataset:
        """Load and convert external dataset to our format.

        Args:
            path: Path to the dataset
            **kwargs: Additional arguments for the adapter

        Returns:
            Dataset in our format
        """
        ...

    @abstractmethod
    def is_compatible(self, path: Path) -> bool:
        """Check if this adapter can handle the given path.

        Args:
            path: Path to check

        Returns:
            True if this adapter can load the dataset
        """
        ...


class BFCLAdapter(DatasetAdapter):
    """Adapter for Berkeley Function Calling Leaderboard v4.

    BFCL v4 focuses on function calling accuracy:
    - 5000+ test cases across multiple categories
    - Categories: simple, parallel, multiple, irrelevance, java, javascript
    - AST-based and executable evaluation

    Source: https://github.com/ShishirPatil/gorilla
    HuggingFace: gorilla-llm/Berkeley-Function-Calling-Leaderboard
    """

    name = "bfcl"

    # BFCL categories and their configurations
    # Note: HuggingFace version uses BFCL_v3_*.json files (JSONL format with .json extension)
    CATEGORIES: dict[str, dict[str, Any]] = {
        "simple": {"difficulty": "simple", "file_patterns": ["BFCL_v3_simple.json", "simple*.jsonl"]},
        "multiple": {"difficulty": "medium", "file_patterns": ["BFCL_v3_multiple.json", "multiple*.jsonl"]},
        "parallel": {"difficulty": "medium", "file_patterns": ["BFCL_v3_parallel.json", "parallel*.jsonl"]},
        "parallel_multiple": {
            "difficulty": "complex",
            "file_patterns": ["BFCL_v3_parallel_multiple.json", "parallel_multiple*.jsonl"],
        },
        "irrelevance": {"difficulty": "complex", "file_patterns": ["BFCL_v3_irrelevance.json", "irrelevance*.jsonl"]},
        "java": {"difficulty": "medium", "file_patterns": ["BFCL_v3_java.json", "java*.jsonl"]},
        "javascript": {"difficulty": "medium", "file_patterns": ["BFCL_v3_javascript.json", "javascript*.jsonl"]},
        "rest": {"difficulty": "medium", "file_patterns": ["BFCL_v3_rest.json"]},
        "sql": {"difficulty": "medium", "file_patterns": ["BFCL_v3_sql.json"]},
        # Executable categories (with actual function execution)
        "exec_simple": {"difficulty": "simple", "file_patterns": ["BFCL_v3_exec_simple.json"]},
        "exec_multiple": {"difficulty": "medium", "file_patterns": ["BFCL_v3_exec_multiple.json"]},
        "exec_parallel": {"difficulty": "medium", "file_patterns": ["BFCL_v3_exec_parallel.json"]},
        "exec_parallel_multiple": {"difficulty": "complex", "file_patterns": ["BFCL_v3_exec_parallel_multiple.json"]},
    }

    def load(self, path: Path, **kwargs: Any) -> Dataset:
        """Load BFCL v4 dataset.

        Args:
            path: Path to BFCL dataset directory
            categories: List of categories to load (default: all)
            max_per_category: Maximum instances per category (default: None)

        Returns:
            Dataset with function calling tasks
        """
        categories = kwargs.get("categories")
        max_per_category = kwargs.get("max_per_category")

        dataset = Dataset(
            name="BFCL v4",
            description="Berkeley Function Calling Leaderboard v4",
            version="4.0",
        )

        categories_to_load = categories or list(self.CATEGORIES.keys())

        for category in categories_to_load:
            if category not in self.CATEGORIES:
                continue

            config = self.CATEGORIES[category]
            instances: list[TaskInstance] = []

            # Load ground truth from possible_answer directory if available
            ground_truth_map = self._load_ground_truth(path, category)

            # Find matching files (search recursively)
            for pattern in config["file_patterns"]:
                for jsonl_file in path.glob(f"**/{pattern}"):
                    # Skip files in possible_answer directory
                    if "possible_answer" in str(jsonl_file):
                        continue

                    with open(jsonl_file) as f:
                        for i, line in enumerate(f):
                            if max_per_category and len(instances) >= max_per_category:
                                break
                            data = json.loads(line)

                            # Handle various question formats:
                            # - Nested: [[{"role": "user", "content": "..."}]]
                            # - List of strings: ["question1", "question2"]
                            # - Simple string: "question"
                            question = data.get("question", data.get("user_query", ""))
                            if isinstance(question, list):
                                if question and isinstance(question[0], list):
                                    # Nested format: [[{"role": "user", "content": "..."}]]
                                    inner = question[0]
                                    if inner and isinstance(inner[0], dict):
                                        question = inner[0].get("content", "")
                                    else:
                                        question = str(inner[0]) if inner else ""
                                elif question and isinstance(question[0], dict):
                                    # List of message dicts: [{"role": "user", "content": "..."}]
                                    question = question[0].get("content", "")
                                else:
                                    # List of strings
                                    question = question[0] if question else ""

                            # Format functions as JSON string for prompt
                            functions = data.get("function", [])
                            functions_str = json.dumps(functions, indent=2)

                            # Get ground truth from map or inline
                            instance_id = data.get("id", f"{category}_{i}")
                            ground_truth = ground_truth_map.get(
                                instance_id, data.get("ground_truth", {})
                            )

                            # Generate output_format from function definitions (CRITICAL for Code Factory)
                            output_format = self._generate_output_format_from_functions(functions)

                            # Expand ground truth arrays into first valid output
                            # BFCL format: {"func": {"param": [val1, val2]}} means val1 OR val2
                            expected_output = self._expand_ground_truth_to_first(ground_truth)

                            instances.append(
                                TaskInstance(
                                    instance_id=instance_id,
                                    input_data={
                                        "user_query": question,
                                        "functions": functions_str,
                                    },
                                    expected_output=expected_output,
                                    metadata={
                                        "category": category,
                                        "execution_result_type": data.get(
                                            "execution_result_type", ""
                                        ),
                                        "output_format": output_format,  # Add output_format for Code Factory
                                    },
                                )
                            )

            if instances:
                task = Task(
                    task_id=f"bfcl_{category}",
                    name=f"BFCL {category.replace('_', ' ').title()}",
                    description=f"Function calling: {category}",
                    category=TaskCategory.FUNCTION_CALLING,
                    difficulty=TaskDifficulty(config["difficulty"]),
                    prompt_template=(
                        "You have access to the following functions:\n\n"
                        "{functions}\n\n"
                        "User query: {user_query}\n\n"
                        "Generate the appropriate function call as JSON with "
                        "'name' and 'arguments' keys."
                    ),
                    instances=instances,
                    evaluation_type="ast_match",
                    tags=["function_calling", "bfcl", category],
                    source="bfcl_v4",
                )
                dataset.tasks.append(task)

        return dataset

    def _expand_ground_truth_to_first(self, ground_truth: list[dict]) -> dict:
        """Expand BFCL ground truth arrays to first valid output.

        BFCL format: [{"func_name": {"param": [val1, val2]}}]
        Where arrays mean "any of these values is valid"

        We take the first value from each array to create a single valid output.

        Args:
            ground_truth: Raw BFCL ground truth with arrays

        Returns:
            Single valid output dict: {"func_name": {"param": val1}}
        """
        if not ground_truth or not isinstance(ground_truth, list):
            return {}

        # Take first function call
        first_call = ground_truth[0] if ground_truth else {}
        if not isinstance(first_call, dict):
            return {}

        result = {}
        for func_name, params in first_call.items():
            if not isinstance(params, dict):
                result[func_name] = params
                continue

            # Expand parameter arrays
            expanded_params = {}
            for param_name, values in params.items():
                if isinstance(values, list) and values:
                    # Take first non-empty value
                    first_val = values[0]
                    # Empty string means optional - skip it
                    if first_val != "":
                        expanded_params[param_name] = first_val
                else:
                    expanded_params[param_name] = values

            result[func_name] = expanded_params

        return result

    def _generate_output_format_from_functions(self, functions: list[dict]) -> dict:
        """Generate output_format from function definitions.

        The output format describes the structure WITHOUT specific values.
        For BFCL, output is a function call: {func_name: {param: value, ...}}

        IMPORTANT: Function names are TOP-LEVEL keys, not nested under "functions".

        Args:
            functions: List of function definitions with name and parameters

        Returns:
            Output format dict with function names as top-level keys
        """
        if not functions:
            return {
                "type": "object",
                "description": "A single function call with the function name as the top-level key and its parameters as a nested object"
            }

        output_format = {
            "type": "object",
            "description": "A single function call with the function name as the top-level key and its parameters as a nested object"
        }

        for func in functions:
            func_name = func.get("name", "unknown")
            params_schema = func.get("parameters", {})
            properties = params_schema.get("properties", {})

            func_params = {}
            for param_name, param_def in properties.items():
                param_type = param_def.get("type", "any")
                param_desc = param_def.get("description", param_name)
                func_params[param_name] = f"{param_type} - {param_desc}"

            # Add function name as TOP-LEVEL key (not under "functions")
            output_format[func_name] = func_params

        return output_format

    def _load_ground_truth(self, path: Path, category: str) -> dict[str, Any]:
        """Load ground truth from possible_answer directory.

        Args:
            path: Base BFCL dataset path
            category: Category name

        Returns:
            Dictionary mapping instance IDs to ground truth
        """
        ground_truth_map: dict[str, Any] = {}

        # Try to find matching ground truth file
        possible_answer_dir = path / "possible_answer"
        if not possible_answer_dir.exists():
            return ground_truth_map

        # Map category to file name
        file_patterns = self.CATEGORIES.get(category, {}).get("file_patterns", [])

        for pattern in file_patterns:
            # Convert pattern to expected answer file name
            answer_file = possible_answer_dir / pattern.replace("*.jsonl", ".json")
            if answer_file.exists():
                with open(answer_file) as f:
                    for line in f:
                        data = json.loads(line)
                        instance_id = data.get("id")
                        if instance_id:
                            ground_truth_map[instance_id] = data.get("ground_truth", {})

        return ground_truth_map

    def is_compatible(self, path: Path) -> bool:
        """Check for BFCL-style files (JSONL or BFCL_v3_*.json)."""
        return any(path.glob("**/*.jsonl")) or any(path.glob("**/BFCL_v3_*.json"))


class DocILEAdapter(DatasetAdapter):
    """Adapter for DocILE document extraction benchmark.

    DocILE focuses on document information extraction:
    - 6,680 annotated business documents
    - 55 semantic field types
    - Tasks: KILE (key info extraction), LIR (line item recognition)

    Source: https://docile.rossum.ai/
    High relevance: Tests structured data extraction (EOB, invoices).
    """

    name = "docile"

    # DocILE field types for KILE task
    KILE_FIELDS = [
        "document_id",
        "vendor_name",
        "vendor_address",
        "customer_name",
        "customer_address",
        "invoice_id",
        "invoice_date",
        "due_date",
        "total_amount",
        "tax_amount",
        "currency",
    ]

    def load(self, path: Path, **kwargs: Any) -> Dataset:
        """Load DocILE dataset.

        Args:
            path: Path to DocILE dataset directory
            task_type: "kile" for key info extraction, "lir" for line items
            max_documents: Maximum documents to load (default: None)
            split: "train", "val", or "test" (default: loads all available)

        Returns:
            Dataset with document extraction tasks
        """
        task_type = kwargs.get("task_type", "kile")
        max_documents = kwargs.get("max_documents")
        split = kwargs.get("split")

        dataset = Dataset(
            name="DocILE",
            description="Document Information Localization and Extraction",
            version="1.0",
        )

        instances: list[TaskInstance] = []

        # DocILE has directory structure: annotated-trainval/[doc_id]/annotation.json
        doc_dirs = self._find_document_dirs(path, split)

        for i, doc_dir in enumerate(doc_dirs):
            if max_documents and len(instances) >= max_documents:
                break

            annotation_file = doc_dir / "annotation.json"
            ocr_file = doc_dir / "ocr.json"

            if not annotation_file.exists():
                continue

            with open(annotation_file) as f:
                annotation = json.load(f)

            # Load OCR text if available
            ocr_text = ""
            if ocr_file.exists():
                with open(ocr_file) as f:
                    ocr_data = json.load(f)
                    # Extract text from OCR results
                    if isinstance(ocr_data, dict):
                        ocr_text = ocr_data.get("text", "")
                    elif isinstance(ocr_data, list):
                        ocr_text = " ".join(
                            item.get("text", "") for item in ocr_data if isinstance(item, dict)
                        )

            # Extract fields based on task type
            if task_type == "kile":
                expected = self._extract_kile_fields(annotation)
            else:  # lir
                expected = self._extract_line_items(annotation)

            instances.append(
                TaskInstance(
                    instance_id=doc_dir.name,
                    input_data={
                        "document_text": ocr_text,
                        "document_path": str(doc_dir / "document.pdf"),
                        "task_type": task_type,
                    },
                    expected_output=expected,
                    metadata={
                        "has_pdf": (doc_dir / "document.pdf").exists(),
                        "has_ocr": ocr_file.exists(),
                    },
                )
            )

        if instances:
            task_name = "Key Information Extraction" if task_type == "kile" else "Line Item Recognition"
            task = Task(
                task_id=f"docile_{task_type}",
                name=f"DocILE {task_name}",
                description=f"Extract {'key fields' if task_type == 'kile' else 'line items'} from documents",
                category=TaskCategory.DOCUMENT_PROCESSING,
                difficulty=TaskDifficulty.MEDIUM if task_type == "kile" else TaskDifficulty.COMPLEX,
                prompt_template=(
                    "Extract structured information from this document:\n\n"
                    "{document_text}\n\n"
                    f"{'Extract key fields: ' + ', '.join(self.KILE_FIELDS) if task_type == 'kile' else 'Extract all line items with description, quantity, unit_price, and amount.'}\n"
                    "Return as JSON."
                ),
                instances=instances,
                evaluation_type="schema",
                tags=["document", "extraction", "docile", task_type],
                source="docile",
            )
            dataset.tasks.append(task)

        return dataset

    def _find_document_dirs(self, path: Path, split: str | None) -> list[Path]:
        """Find document directories in DocILE structure."""
        doc_dirs = []

        # Check for annotated-trainval directory
        trainval_dir = path / "annotated-trainval"
        test_dir = path / "test"

        if split in (None, "train", "val") and trainval_dir.exists():
            for doc_dir in trainval_dir.iterdir():
                if doc_dir.is_dir() and (doc_dir / "annotation.json").exists():
                    doc_dirs.append(doc_dir)

        if split in (None, "test") and test_dir.exists():
            for doc_dir in test_dir.iterdir():
                if doc_dir.is_dir() and (doc_dir / "annotation.json").exists():
                    doc_dirs.append(doc_dir)

        # Fallback: check path directly for annotation files
        if not doc_dirs:
            for doc_dir in path.iterdir():
                if doc_dir.is_dir() and (doc_dir / "annotation.json").exists():
                    doc_dirs.append(doc_dir)

        return sorted(doc_dirs)

    def _extract_kile_fields(self, annotation: dict) -> dict:
        """Extract key information fields from annotation."""
        fields = {}
        field_instances = annotation.get("field_instances", annotation.get("fields", []))

        if isinstance(field_instances, list):
            for field in field_instances:
                field_type = field.get("field_type", field.get("type", ""))
                value = field.get("text", field.get("value", ""))
                if field_type:
                    fields[field_type] = value
        elif isinstance(field_instances, dict):
            fields = field_instances

        return fields

    def _extract_line_items(self, annotation: dict) -> list[dict]:
        """Extract line items from annotation."""
        line_items = annotation.get("line_items", annotation.get("table_data", []))
        return line_items if isinstance(line_items, list) else []

    def is_compatible(self, path: Path) -> bool:
        """Check for DocILE directory structure."""
        # Check for annotated-trainval directory with document subdirs
        trainval_dir = path / "annotated-trainval"
        if trainval_dir.exists():
            for doc_dir in trainval_dir.iterdir():
                if doc_dir.is_dir() and (doc_dir / "annotation.json").exists():
                    return True

        # Fallback check for direct annotation files
        return (path / "annotations.json").exists() or (path / "test.json").exists()


class AgentBenchAdapter(DatasetAdapter):
    """Adapter for AgentBench multi-turn agent benchmark.

    AgentBench evaluates agent capabilities across 8 environments:
    - OS: Operating system tasks (bash commands)
    - DB: Database operations (SQL queries)
    - KG: Knowledge graph queries (SPARQL)
    - DCG: Digital card game
    - LTP: Lateral thinking puzzles
    - alfworld: House-holding tasks (ALFWorld)
    - webshop: Web shopping
    - mind2web: Web browsing (Mind2Web)

    Source: https://github.com/THUDM/AgentBench
    Medium relevance: Tests multi-step task completion.
    """

    name = "agentbench"

    # Environment configurations (matching actual AgentBench repo structure)
    ENVIRONMENTS: dict[str, dict[str, Any]] = {
        "os": {
            "name": "Operating System",
            "difficulty": "medium",
            "data_dirs": ["data/os_interaction/data", "data/os_interaction"],
            "requires_docker": False,
            "task_key": "description",
        },
        "db": {
            "name": "Database",
            "difficulty": "medium",
            "data_dirs": ["data/dbbench", "data/db"],
            "requires_docker": True,
            "task_key": "instruction",
        },
        "kg": {
            "name": "Knowledge Graph",
            "difficulty": "medium",
            "data_dirs": ["data/knowledgegraph", "data/kg"],
            "requires_docker": False,
            "task_key": "query",
        },
        "alfworld": {
            "name": "House-Holding (ALFWorld)",
            "difficulty": "complex",
            "data_dirs": ["data/alfworld"],
            "requires_docker": True,
            "task_key": "task",
        },
        "webshop": {
            "name": "Web Shopping",
            "difficulty": "complex",
            "data_dirs": ["data/webshop"],
            "requires_docker": True,
            "task_key": "instruction",
        },
        "mind2web": {
            "name": "Web Browsing (Mind2Web)",
            "difficulty": "complex",
            "data_dirs": ["data/mind2web"],
            "requires_docker": True,
            "task_key": "instruction",
        },
        "avalon": {
            "name": "Avalon Game",
            "difficulty": "complex",
            "data_dirs": ["data/avalon"],
            "requires_docker": True,
            "task_key": "instruction",
        },
        "ltp": {
            "name": "Lateral Thinking Puzzles",
            "difficulty": "medium",
            "data_dirs": ["data/lateralthinkingpuzzle", "data/ltp"],
            "requires_docker": True,
            "task_key": "puzzle",
        },
    }

    def load(self, path: Path, **kwargs: Any) -> Dataset:
        """Load AgentBench dataset.

        Args:
            path: Path to AgentBench repository directory
            environments: List of environments to load (default: all available)
            split: "dev" or "test" (default: "dev")
            max_per_env: Maximum tasks per environment (default: None)

        Returns:
            Dataset with multi-turn agent tasks
        """
        environments = kwargs.get("environments")
        split = kwargs.get("split", "dev")
        max_per_env = kwargs.get("max_per_env")

        dataset = Dataset(
            name="AgentBench",
            description="Multi-turn agent benchmark across 8 environments",
            version="1.0",
        )

        envs_to_load = environments or list(self.ENVIRONMENTS.keys())

        for env_name in envs_to_load:
            if env_name not in self.ENVIRONMENTS:
                continue

            config = self.ENVIRONMENTS[env_name]
            instances: list[TaskInstance] = []

            # Try multiple possible data locations
            data_paths = [path / d for d in config.get("data_dirs", [])]
            data_paths.extend([path / "data" / env_name, path / env_name])

            tasks_data = None
            for data_path in data_paths:
                if not data_path.exists():
                    continue

                # Look for task files (various naming conventions)
                for task_file in [
                    data_path / f"{split}.json",
                    data_path / f"{split}_tasks.json",
                    data_path / "tasks.json",
                    data_path / f"{split}.jsonl",
                ]:
                    if task_file.exists():
                        tasks_data = self._load_tasks_file(task_file, env_name)
                        break

                if tasks_data:
                    break

            if not tasks_data:
                continue

            task_key = config.get("task_key", "instruction")

            for i, task_data in enumerate(tasks_data):
                if max_per_env and len(instances) >= max_per_env:
                    break

                # Handle various AgentBench task formats using the task_key
                instruction = task_data.get(
                    task_key,
                    task_data.get("instruction", task_data.get("input", task_data.get("query", ""))),
                )

                # Get expected output with various key names
                expected = task_data.get(
                    "expected_result",
                    task_data.get("answer", task_data.get("label", task_data.get("evaluation", {}))),
                )
                # For OS tasks, the expected output is in evaluation.match
                if isinstance(expected, dict) and "match" in expected:
                    expected = expected["match"]

                instances.append(
                    TaskInstance(
                        instance_id=task_data.get("id", f"{env_name}_{split}_{i}"),
                        input_data={
                            "instruction": instruction,
                            "environment": env_name,
                            "init_state": task_data.get("init", task_data.get("create", {})),
                        },
                        expected_output=expected,
                        metadata={
                            "turns": task_data.get("turns", []),
                            "requires_docker": config["requires_docker"],
                            "split": split,
                            "labels": task_data.get("labels", []),
                        },
                    )
                )

            if instances:
                task = Task(
                    task_id=f"agentbench_{env_name}",
                    name=f"AgentBench {config['name']}",
                    description=f"Agent tasks in {config['name']} environment",
                    category=TaskCategory.API_ORCHESTRATION,
                    difficulty=TaskDifficulty(config["difficulty"]),
                    prompt_template=(
                        "Environment: {environment}\n\n"
                        "Initial state: {init_state}\n\n"
                        "Task: {instruction}"
                    ),
                    instances=instances,
                    evaluation_type="milestone",
                    tags=["agent", "multi_turn", env_name, split],
                    source="agentbench",
                )
                dataset.tasks.append(task)

        return dataset

    def _load_tasks_file(self, file_path: Path, env_name: str) -> list[dict]:
        """Load tasks from JSON or JSONL file.

        Handles various AgentBench formats:
        - List of task dicts (most environments)
        - Dict with task categories (ALFWorld)
        - JSONL format
        """
        with open(file_path) as f:
            if file_path.suffix == ".jsonl":
                return [json.loads(line) for line in f if line.strip()]
            else:
                data = json.load(f)

        # Handle list format (most common)
        if isinstance(data, list):
            return data

        # Handle dict format (ALFWorld uses {"task_type": [paths...]})
        if isinstance(data, dict):
            if "tasks" in data:
                return data["tasks"]

            # ALFWorld format: flatten task categories into task dicts
            tasks = []
            for task_type, items in data.items():
                if isinstance(items, list):
                    for i, item in enumerate(items):
                        if isinstance(item, str):
                            # ALFWorld path format
                            tasks.append({
                                "id": f"{task_type}_{i}",
                                "task": f"{task_type}: {item}",
                                "task_type": task_type,
                                "game_path": item,
                            })
                        elif isinstance(item, dict):
                            item.setdefault("task_type", task_type)
                            tasks.append(item)
            return tasks if tasks else [data]

        return [data]

    def is_compatible(self, path: Path) -> bool:
        """Check for AgentBench structure."""
        data_dir = path / "data"
        if not data_dir.exists():
            return False

        # Check for actual AgentBench directory names
        agentbench_dirs = [
            "os_interaction", "dbbench", "knowledgegraph", "alfworld",
            "webshop", "mind2web", "avalon", "lateralthinkingpuzzle",
        ]
        return any((data_dir / d).exists() for d in agentbench_dirs)


class SWEBenchAdapter(DatasetAdapter):
    """Adapter for SWE-bench (Software Engineering Benchmark).
    
    SWE-bench tests real-world GitHub issue resolution:
    - Given a codebase and issue description
    - Agent generates a patch that resolves the issue
    - Evaluation runs tests to verify the fix
    
    Variants:
    - lite: 300 curated instances
    - verified: 500 human-verified solvable instances  
    - full: 2,294 instances
    
    Source: https://github.com/princeton-nlp/SWE-bench
    Paper: ICLR 2024 Oral
    """
    
    name = "swebench"
    
    VARIANTS = {
        "lite": {"file_pattern": "swebench_lite.json", "expected_count": 300},
        "verified": {"file_pattern": "swebench_verified.json", "expected_count": 500},
        "full": {"file_pattern": "swebench_full.json", "expected_count": 2294},
    }
    
    def load(self, path: Path, **kwargs: Any) -> Dataset:
        """Load SWE-bench dataset.
        
        Args:
            path: Path to SWE-bench dataset directory
            variant: "lite", "verified", or "full" (default: lite)
            max_instances: Maximum instances to load (default: None)
            repos: List of repos to filter by (default: None = all)
            
        Returns:
            Dataset with code patching tasks
        """
        variant = kwargs.get("variant", "lite")
        max_instances = kwargs.get("max_instances")
        repos_filter = kwargs.get("repos")
        
        dataset = Dataset(
            name=f"SWE-bench {variant.capitalize()}",
            description="Real-world GitHub issue resolution benchmark",
            version="1.0",
        )
        
        # Find the data file
        data_file = None
        for pattern in [
            f"swebench_{variant}.json",
            f"swe-bench_{variant}.json",
            "test.json",
            "data.json",
        ]:
            candidate = path / pattern
            if candidate.exists():
                data_file = candidate
                break
        
        if not data_file:
            raise ValueError(f"No SWE-bench data file found in {path}")
        
        with open(data_file) as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            data = [data]
        
        # Group by repo for category organization
        repos: dict[str, list[dict]] = {}
        for item in data:
            repo = item.get("repo", "unknown")
            if repos_filter and repo not in repos_filter:
                continue
            if repo not in repos:
                repos[repo] = []
            repos[repo].append(item)
        
        instance_count = 0
        for repo, items in repos.items():
            instances: list[TaskInstance] = []
            
            for item in items:
                if max_instances and instance_count >= max_instances:
                    break
                
                instance_id = item.get("instance_id", f"unknown_{instance_count}")
                problem = item.get("problem_statement", "")
                hints = item.get("hints_text", "")
                patch = item.get("patch", "")
                
                # Build input with hints if available
                if hints and hints.strip():
                    input_text = f"{problem}\n\n---\nHints:\n{hints}"
                else:
                    input_text = problem
                
                # Parse test lists
                fail_to_pass = self._parse_json_list(item.get("FAIL_TO_PASS", "[]"))
                pass_to_pass = self._parse_json_list(item.get("PASS_TO_PASS", "[]"))
                
                instances.append(TaskInstance(
                    id=instance_id,
                    input=input_text,
                    expected_output=patch,
                    metadata={
                        "repo": repo,
                        "base_commit": item.get("base_commit", ""),
                        "version": item.get("version", ""),
                        "fail_to_pass": fail_to_pass,
                        "pass_to_pass": pass_to_pass,
                        "test_patch": item.get("test_patch", ""),
                        "environment_setup_commit": item.get("environment_setup_commit", ""),
                    }
                ))
                instance_count += 1
            
            if instances:
                # Determine difficulty based on patch size
                avg_patch_len = sum(len(i.expected_output) for i in instances) / len(instances)
                if avg_patch_len < 500:
                    difficulty = TaskDifficulty.SIMPLE
                elif avg_patch_len < 2000:
                    difficulty = TaskDifficulty.MEDIUM
                else:
                    difficulty = TaskDifficulty.COMPLEX
                
                dataset.add_category(TaskCategory(
                    name=repo.replace("/", "_"),
                    description=f"Issues from {repo}",
                    difficulty=difficulty,
                    instances=instances,
                ))
        
        return dataset
    
    def is_compatible(self, path: Path) -> bool:
        """Check if path contains SWE-bench data."""
        if not path.exists() or not path.is_dir():
            return False
        
        # Look for SWE-bench file patterns
        patterns = ["swebench_*.json", "swe-bench_*.json"]
        for pattern in patterns:
            if list(path.glob(pattern)):
                return True
        
        # Check for HuggingFace-style metadata
        if (path / "dataset_info.json").exists():
            return True
        
        return False
    
    def _parse_json_list(self, value: str | list) -> list[str]:
        """Parse a JSON list from string or pass through list."""
        if isinstance(value, list):
            return value
        if not value:
            return []
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []


# Adapter registry
_ADAPTER_REGISTRY: dict[str, type[DatasetAdapter]] = {
    "bfcl": BFCLAdapter,
    "docile": DocILEAdapter,
    "agentbench": AgentBenchAdapter,
    "swebench": SWEBenchAdapter,
}


def register_adapter(name: str):
    """Decorator to register a dataset adapter.

    Args:
        name: Unique name for the adapter

    Returns:
        Decorator that registers the adapter class
    """

    def decorator(cls: type[DatasetAdapter]) -> type[DatasetAdapter]:
        _ADAPTER_REGISTRY[name] = cls
        cls.name = name
        return cls

    return decorator


class DatasetLoader:
    """Unified loader for all dataset formats."""

    def __init__(self, datasets_dir: Path | str = "datasets") -> None:
        """Initialize the dataset loader.

        Args:
            datasets_dir: Base directory for datasets
        """
        self.datasets_dir = Path(datasets_dir)

    def load(self, name: str, **kwargs: Any) -> Dataset:
        """Load a dataset by name.

        Args:
            name: Dataset name (e.g., "xy_benchmark", "bfcl")
            **kwargs: Additional arguments for the adapter

        Returns:
            Loaded Dataset object

        Raises:
            ValueError: If dataset not found or no compatible adapter
        """
        path = self.datasets_dir / name

        if not path.exists():
            raise ValueError(f"Dataset not found: {path}")

        # Check for XY_Benchmark format (has metadata.yaml)
        if (path / "metadata.yaml").exists() or (path / "metadata.json").exists():
            return Dataset.from_directory(path)

        # Try adapters for external formats
        for adapter_cls in _ADAPTER_REGISTRY.values():
            adapter = adapter_cls()
            if adapter.is_compatible(path):
                return adapter.load(path, **kwargs)

        raise ValueError(f"No compatible adapter found for: {path}")

    def load_external(
        self, adapter_name: str, path: Path | str, **kwargs: Any
    ) -> Dataset:
        """Load an external dataset with a specific adapter.

        Args:
            adapter_name: Name of the adapter to use
            path: Path to the dataset
            **kwargs: Additional arguments for the adapter

        Returns:
            Loaded Dataset object

        Raises:
            ValueError: If adapter not found
        """
        if adapter_name not in _ADAPTER_REGISTRY:
            available = list(_ADAPTER_REGISTRY.keys())
            raise ValueError(
                f"Unknown adapter: {adapter_name}. Available: {available}"
            )

        adapter = _ADAPTER_REGISTRY[adapter_name]()
        return adapter.load(Path(path), **kwargs)

    def list_datasets(self) -> list[str]:
        """List available datasets in the datasets directory.

        Returns:
            List of dataset names
        """
        if not self.datasets_dir.exists():
            return []
        return [p.name for p in self.datasets_dir.iterdir() if p.is_dir()]

    def list_adapters(self) -> list[str]:
        """List available dataset adapters.

        Returns:
            List of adapter names
        """
        return list(_ADAPTER_REGISTRY.keys())

    def load_standardized(self, name: str, **kwargs: Any) -> StandardizedDataset:
        """Load a dataset and convert to standardized format.

        Args:
            name: Dataset name (e.g., "xy_benchmark", "bfcl_v4")
            **kwargs: Additional arguments for the adapter

        Returns:
            StandardizedDataset with unified format

        Raises:
            ValueError: If dataset not found or no compatible adapter
        """
        dataset = self.load(name, **kwargs)
        return transform_dataset(dataset)

    def load_external_standardized(
        self, adapter_name: str, path: Path | str, **kwargs: Any
    ) -> StandardizedDataset:
        """Load an external dataset and convert to standardized format.

        Args:
            adapter_name: Name of the adapter to use
            path: Path to the dataset
            **kwargs: Additional arguments for the adapter

        Returns:
            StandardizedDataset with unified format

        Raises:
            ValueError: If adapter not found
        """
        dataset = self.load_external(adapter_name, path, **kwargs)

        # Use adapter-specific transformer if available
        try:
            transformer = get_transformer(adapter_name)
            return transformer.transform(dataset)
        except ValueError:
            # Fall back to auto-detection
            return transform_dataset(dataset)
