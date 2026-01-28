"""
Activities for dynamic module loading workflow.
INTENTIONALLY VULNERABLE - FOR SECURITY TESTING ONLY
Contains CWE-94: Improper Control of Generation of Code ('Code Injection')
"""
import importlib


def load_module(module_name: str) -> dict:
    """Dynamically load a module by name.

    VULNERABILITY: User-controlled module name allows arbitrary module loading
    """
    # VULNERABLE: User controls which module to import
    module = __import__(module_name)
    return {"module_name": module_name, "loaded": True}


def import_and_call(module_name: str, function_name: str, *args) -> dict:
    """Import a module and call a function from it.

    VULNERABILITY: Arbitrary module/function execution
    """
    # VULNERABLE: User controls module and function to execute
    module = importlib.import_module(module_name)
    func = getattr(module, function_name)
    result = func(*args)
    return {"result": result}


def load_plugin(plugin_path: str) -> dict:
    """Load a plugin from user-specified path.

    VULNERABILITY: Arbitrary code execution through plugin loading
    """
    # VULNERABLE: User controls the import path
    spec = importlib.util.spec_from_file_location("plugin", plugin_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {"plugin_loaded": True, "path": plugin_path}
