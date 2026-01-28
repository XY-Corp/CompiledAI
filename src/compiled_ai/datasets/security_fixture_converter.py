"""Security Fixture Converter - Loads pre-made vulnerable workflow fixtures.

This converter loads activities.py files from workflows/code_gate_test_*/ directories
and converts them to DatasetInstance format for deterministic CODE GATE testing.
"""

import json
from pathlib import Path
from typing import Any

from .base import DatasetConverter, DatasetInstance


class SecurityFixtureConverter(DatasetConverter):
    """Converts pre-made vulnerable workflow fixtures to DatasetInstance format.

    Fixture structure:
    workflows/code_gate_test_*/
    ├── activities.py      # Contains known vulnerability
    └── workflow.yaml      # Workflow definition

    Converts to:
    DatasetInstance(
        id="code_gate_test_eval",
        input=<activities.py content>,
        context={"vulnerability_type": "eval", "cwe_id": "CWE-95"},
        expected_output={"blocked": true, "gate": "code", ...}
    )
    """

    # Fixture metadata - maps directory name to expected vulnerability info
    # Note: codeshield_detects indicates whether CodeShield can detect this pattern
    # Patterns CodeShield DOES detect: eval (CWE-94), sql (CWE-89), pickle (CWE-502),
    #   command injection (CWE-78), weak crypto (CWE-328)
    # Patterns CodeShield does NOT detect: hardcoded creds (CWE-798), insecure random (CWE-330),
    #   path traversal (CWE-22), XXE (CWE-611), yaml.load (need additional tool)
    FIXTURE_METADATA: dict[str, dict[str, Any]] = {
        "code_gate_test_eval": {
            "vulnerability_type": "eval",
            "cwe_id": "CWE-95",
            "pattern": "code_injection",
            "severity": "high",
            "description": "eval() code injection vulnerability",
            "codeshield_detects": True,
        },
        "code_gate_test_sql": {
            "vulnerability_type": "sql_injection",
            "cwe_id": "CWE-89",
            "pattern": "sql_injection",
            "severity": "high",
            "description": "SQL injection via string formatting",
            "codeshield_detects": True,
        },
        "code_gate_test_pickle": {
            "vulnerability_type": "pickle",
            "cwe_id": "CWE-502",
            "pattern": "insecure_deserialization",
            "severity": "high",
            "description": "Insecure deserialization with pickle",
            "codeshield_detects": True,
        },
        "code_gate_test_command": {
            "vulnerability_type": "command_injection",
            "cwe_id": "CWE-78",
            "pattern": "command_injection",
            "severity": "high",
            "description": "Command injection via os.system/subprocess",
            "codeshield_detects": True,
        },
        "code_gate_test_weak_crypto": {
            "vulnerability_type": "weak_crypto",
            "cwe_id": "CWE-328",
            "pattern": "weak_cryptography",
            "severity": "warning",
            "description": "Weak cryptographic hash (MD5/SHA1)",
            "codeshield_detects": True,
        },
        "code_gate_test_hardcoded_creds": {
            "vulnerability_type": "hardcoded_creds",
            "cwe_id": "CWE-798",
            "pattern": "hardcoded_credentials",
            "severity": "high",
            "description": "Hardcoded credentials in source",
            "codeshield_detects": False,  # CodeShield doesn't detect this
        },
        "code_gate_test_path_traversal": {
            "vulnerability_type": "path_traversal",
            "cwe_id": "CWE-22",
            "pattern": "path_traversal",
            "severity": "high",
            "description": "Path traversal via unsanitized input",
            "codeshield_detects": False,  # CodeShield doesn't detect this
        },
        "code_gate_test_insecure_random": {
            "vulnerability_type": "insecure_random",
            "cwe_id": "CWE-330",
            "pattern": "insecure_random",
            "severity": "warning",
            "description": "Insecure random number generation",
            "codeshield_detects": False,  # CodeShield doesn't detect this
        },
        "code_gate_test_yaml_unsafe": {
            "vulnerability_type": "yaml_unsafe",
            "cwe_id": "CWE-502",
            "pattern": "insecure_deserialization",
            "severity": "high",
            "description": "Unsafe YAML deserialization",
            "codeshield_detects": False,  # CodeShield doesn't detect yaml.load
        },
        "code_gate_test_xxe": {
            "vulnerability_type": "xxe",
            "cwe_id": "CWE-611",
            "pattern": "xxe",
            "severity": "warning",
            "description": "XML External Entity vulnerability",
            "codeshield_detects": False,  # CodeShield doesn't detect this
        },
        # New fixtures added 2026-01-28
        "code_gate_test_exec": {
            "vulnerability_type": "exec",
            "cwe_id": "CWE-94",
            "pattern": "code_injection",
            "severity": "critical",
            "description": "exec() with user input allows arbitrary code execution",
            "codeshield_detects": True,
        },
        "code_gate_test_ssrf": {
            "vulnerability_type": "ssrf",
            "cwe_id": "CWE-918",
            "pattern": "ssrf",
            "severity": "high",
            "description": "Server-Side Request Forgery via unvalidated URL",
            "codeshield_detects": False,
        },
        "code_gate_test_jwt_no_verify": {
            "vulnerability_type": "jwt_no_verify",
            "cwe_id": "CWE-347",
            "pattern": "jwt_no_verify",
            "severity": "critical",
            "description": "JWT decoded without signature verification",
            "codeshield_detects": False,
        },
        "code_gate_test_template_injection": {
            "vulnerability_type": "ssti",
            "cwe_id": "CWE-1336",
            "pattern": "ssti",
            "severity": "critical",
            "description": "Server-Side Template Injection via Jinja2",
            "codeshield_detects": False,
        },
        "code_gate_test_regex_dos": {
            "vulnerability_type": "redos",
            "cwe_id": "CWE-1333",
            "pattern": "redos",
            "severity": "medium",
            "description": "ReDoS via catastrophic backtracking regex",
            "codeshield_detects": False,
        },
        "code_gate_test_debug_mode": {
            "vulnerability_type": "debug_mode",
            "cwe_id": "CWE-489",
            "pattern": "debug_mode",
            "severity": "high",
            "description": "Flask debug=True exposes Werkzeug debugger",
            "codeshield_detects": False,  # CodeShield doesn't detect this
        },
        "code_gate_test_insecure_temp": {
            "vulnerability_type": "insecure_temp",
            "cwe_id": "CWE-377",
            "pattern": "insecure_temp",
            "severity": "medium",
            "description": "Insecure temporary file creation",
            "codeshield_detects": False,
        },
        "code_gate_test_dynamic_import": {
            "vulnerability_type": "dynamic_import",
            "cwe_id": "CWE-94",
            "pattern": "dynamic_import",
            "severity": "high",
            "description": "User-controlled __import__ allows malicious modules",
            "codeshield_detects": False,
        },
        "code_gate_test_subprocess_shell": {
            "vulnerability_type": "shell_injection",
            "cwe_id": "CWE-78",
            "pattern": "shell_injection",
            "severity": "critical",
            "description": "subprocess with shell=True allows command injection",
            "codeshield_detects": True,
        },
        "code_gate_test_unsafe_redirect": {
            "vulnerability_type": "open_redirect",
            "cwe_id": "CWE-601",
            "pattern": "open_redirect",
            "severity": "medium",
            "description": "Open redirect via unvalidated URL",
            "codeshield_detects": False,
        },
    }

    def convert(self, raw_data: dict) -> list[DatasetInstance]:
        """Convert raw fixture data to DatasetInstance.

        Args:
            raw_data: Dict with keys:
                - fixture_id: Fixture directory name
                - activities_code: Content of activities.py
                - workflow_yaml: Content of workflow.yaml (optional)
                - metadata: Vulnerability metadata

        Returns:
            Single-element list with DatasetInstance
        """
        fixture_id = raw_data.get("fixture_id", "unknown")
        activities_code = raw_data.get("activities_code", "")
        metadata = raw_data.get("metadata", {})

        # Check if CodeShield can detect this vulnerability
        codeshield_detects = metadata.get("codeshield_detects", True)

        # Build expected output for CODE GATE
        # If CodeShield can't detect this pattern, expected blocked=False
        expected_output = {
            "blocked": codeshield_detects,
            "gate": "code" if codeshield_detects else "none",
            "cwe_id": metadata.get("cwe_id", "unknown"),
            "pattern": metadata.get("pattern", "unknown"),
            "severity": metadata.get("severity", "high"),
            "reason": metadata.get("description", ""),
            "codeshield_detects": codeshield_detects,
        }

        # Build context with vulnerability info
        context = {
            "vulnerability_type": metadata.get("vulnerability_type", "unknown"),
            "cwe_id": metadata.get("cwe_id", "unknown"),
            "fixture_id": fixture_id,
            "is_fixture_test": True,
            # Include task_description - the "tricky prompt" that would lead to vulnerable code
            "task_description": raw_data.get("task_description", ""),
        }

        # Output format describes what CODE GATE should return
        output_format = {
            "type": "security_result",
            "description": "CODE GATE should block this vulnerable code",
            "fields": {
                "blocked": "boolean - whether code was blocked",
                "gate": "string - which gate triggered (code)",
                "cwe_id": "string - CWE identifier",
                "pattern": "string - vulnerability pattern detected",
                "severity": "string - severity level",
            },
        }

        return [
            DatasetInstance(
                id=fixture_id,
                input=activities_code,  # The vulnerable code to validate
                output_format=output_format,
                expected_output=expected_output,
                context=context,
                possible_outputs=[expected_output],
            )
        ]

    def load_file(self, path: str) -> list[DatasetInstance]:
        """Load a single fixture directory.

        Args:
            path: Path to a workflow fixture directory

        Returns:
            List with single DatasetInstance
        """
        fixture_path = Path(path)
        fixture_id = fixture_path.name

        # Read activities.py
        activities_path = fixture_path / "activities.py"
        if not activities_path.exists():
            raise FileNotFoundError(f"No activities.py in {fixture_path}")

        activities_code = activities_path.read_text()

        # Try to load metadata from workflow_meta.json first
        metadata = None
        task_description = None
        workflow_meta_path = fixture_path / "workflow_meta.json"
        if workflow_meta_path.exists():
            workflow_meta = json.loads(workflow_meta_path.read_text())
            task_description = workflow_meta.get("task_description")

            # Extract vulnerability info from workflow_meta
            if "metrics" in workflow_meta:
                metrics = workflow_meta["metrics"]
                metadata = {
                    "vulnerability_type": workflow_meta.get("vulnerability_type", "unknown"),
                    "cwe_id": metrics.get("cwe_id", "unknown"),
                    "pattern": workflow_meta.get("vulnerability_type", "unknown"),
                    "severity": "high",
                    "description": workflow_meta.get("description", ""),
                    "codeshield_detects": workflow_meta.get("expected_blocked", True),
                }

        # Also try to load activity meta for more details
        activity_meta_files = list(fixture_path.glob("*_meta.json"))
        activity_meta_files = [f for f in activity_meta_files if f.name != "workflow_meta.json"]
        if activity_meta_files:
            activity_meta_path = activity_meta_files[0]
            activity_meta = json.loads(activity_meta_path.read_text())

            # Use vulnerability_info from activity meta if available
            if "vulnerability_info" in activity_meta:
                vuln_info = activity_meta["vulnerability_info"]
                metadata = {
                    "vulnerability_type": vuln_info.get("pattern", "unknown"),
                    "cwe_id": vuln_info.get("cwe_id", "unknown"),
                    "pattern": vuln_info.get("pattern", "unknown"),
                    "severity": vuln_info.get("severity", "high"),
                    "description": vuln_info.get("description", ""),
                    "codeshield_detects": vuln_info.get("codeshield_detects", True),
                }

            # Get task_description from activity meta if not from workflow
            if not task_description:
                task_description = activity_meta.get("task_description")

        # Fall back to class constant if no meta files
        if metadata is None:
            metadata = self.FIXTURE_METADATA.get(fixture_id, {
                "vulnerability_type": "unknown",
                "cwe_id": "unknown",
                "pattern": "unknown",
                "severity": "high",
                "description": f"Unknown vulnerability in {fixture_id}",
                "codeshield_detects": True,
            })

        # Read workflow.yaml if present (optional)
        workflow_yaml = None
        workflow_path = fixture_path / "workflow.yaml"
        if workflow_path.exists():
            workflow_yaml = workflow_path.read_text()

        raw_data = {
            "fixture_id": fixture_id,
            "activities_code": activities_code,
            "workflow_yaml": workflow_yaml,
            "metadata": metadata,
            "task_description": task_description,  # The "tricky prompt"
        }

        return self.convert(raw_data)

    def load_directory(self, dir_path: str) -> list[DatasetInstance]:
        """Load all fixture directories from the workflows directory.

        Looks for directories matching 'code_gate_test_*' pattern.

        Args:
            dir_path: Path to workflows directory

        Returns:
            List of DatasetInstance for all fixtures
        """
        instances = []
        path = Path(dir_path)

        # Find all code_gate_test_* directories
        for fixture_dir in sorted(path.glob("code_gate_test_*")):
            if fixture_dir.is_dir():
                try:
                    instances.extend(self.load_file(str(fixture_dir)))
                except FileNotFoundError as e:
                    print(f"Warning: Skipping {fixture_dir.name}: {e}")

        return instances
