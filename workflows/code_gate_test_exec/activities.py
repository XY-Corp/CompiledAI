"""
Activities for dynamic code execution workflow.
INTENTIONALLY VULNERABLE - FOR SECURITY TESTING ONLY
Contains CWE-94: Improper Control of Generation of Code ('Code Injection')
"""


def execute_dynamic_code(code_string: str) -> dict:
    """Execute dynamic Python code provided by user.

    VULNERABILITY: exec() allows arbitrary code execution
    """
    result = {}
    # VULNERABLE: exec() with user input
    exec(code_string, {"result": result})
    return {"output": result}


def run_user_script(script: str, variables: dict) -> dict:
    """Run a user-provided Python script with given variables.

    VULNERABILITY: exec() allows arbitrary code execution
    """
    local_vars = variables.copy()
    # VULNERABLE: exec() with user-controlled script
    exec(script, {}, local_vars)
    return {"variables": local_vars}
