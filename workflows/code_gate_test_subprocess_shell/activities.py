"""
Activities for subprocess execution workflow.
INTENTIONALLY VULNERABLE - FOR SECURITY TESTING ONLY
Contains CWE-78: OS Command Injection (via shell=True)
"""
import subprocess


def run_command_shell(command: str) -> dict:
    """Run a command using shell=True.

    VULNERABILITY: shell=True with user input allows command injection
    """
    # VULNERABLE: shell=True allows ; && || injection
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    }


def execute_pipeline(commands: str) -> dict:
    """Execute a pipeline of shell commands.

    VULNERABILITY: Direct shell command execution
    """
    # VULNERABLE: User controls the entire command pipeline
    process = subprocess.Popen(
        commands,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()
    return {
        "output": stdout.decode(),
        "errors": stderr.decode()
    }


def run_script(script_content: str) -> dict:
    """Run a shell script from string content.

    VULNERABILITY: Arbitrary shell script execution
    """
    # VULNERABLE: Executes user-provided shell script
    result = subprocess.run(
        ['bash', '-c', script_content],
        capture_output=True,
        text=True
    )
    return {"output": result.stdout, "exit_code": result.returncode}
