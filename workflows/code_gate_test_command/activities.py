"""Vulnerable workflow fixture: command injection (CWE-78)

This fixture contains intentionally vulnerable code for testing CODE GATE.
CodeShield should detect and block this vulnerability.
"""

import os
import subprocess
from typing import Any


async def process_file(
    filename: str,
    command: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Process a file using a shell command.

    VULNERABILITY: os.system() with user input.
    CWE-78: Improper Neutralization of Special Elements used in an OS Command
    """
    # VULNERABLE: os.system() with user-controlled input
    exit_code = os.system(f"{command} {filename}")
    return {"exit_code": exit_code, "command": f"{command} {filename}"}


async def run_shell_command(
    command: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Run a shell command and return output.

    VULNERABILITY: subprocess.run with shell=True.
    """
    # VULNERABLE: shell=True with user input
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}


async def execute_system_command(
    cmd: str,
    org_id: str | None = None,
    user_id: str | None = None,
    workflow_definition_id: str | None = None,
    workflow_instance_id: str | None = None,
) -> dict[str, Any]:
    """Execute system command via Popen.

    VULNERABILITY: Popen with shell=True.
    """
    # VULNERABLE: Popen shell=True
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    return {"stdout": stdout.decode(), "stderr": stderr.decode()}
