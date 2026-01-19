"""Activity Library - Real executable activities for workflows.

This module provides a registry of activities that can be:
1. Executed directly by the baseline
2. Used as templates by the Code Factory to generate similar activities
3. Searched by category, name, or description
"""

from typing import Any, Dict, List
import importlib
import inspect
from pathlib import Path

class ActivityRegistry:
    """Registry for loading and searching activities."""

    def __init__(self):
        self._activities: Dict[str, Any] = {}
        self._load_activities()

    def _load_activities(self):
        """Load all activities from the activities directory."""
        activities_dir = Path(__file__).parent

        for py_file in activities_dir.glob("*.py"):
            if py_file.name.startswith("_") or py_file.name == "__init__.py":
                continue

            module_name = py_file.stem
            try:
                module = importlib.import_module(f".{module_name}", package=__package__)

                # Find all async functions in the module
                for name, obj in inspect.getmembers(module):
                    if inspect.iscoroutinefunction(obj) and not name.startswith("_"):
                        self._activities[name] = obj
            except Exception as e:
                print(f"Warning: Failed to load activity from {py_file}: {e}")

    def get(self, name: str) -> Any:
        """Get an activity by name."""
        return self._activities.get(name)

    def list(self) -> List[str]:
        """List all available activity names."""
        return list(self._activities.keys())

    def search(self, query: str) -> List[str]:
        """Search activities by name or docstring."""
        results = []
        query_lower = query.lower()

        for name, func in self._activities.items():
            # Search in name
            if query_lower in name.lower():
                results.append(name)
                continue

            # Search in docstring
            if func.__doc__ and query_lower in func.__doc__.lower():
                results.append(name)

        return results

    def get_source(self, name: str) -> str:
        """Get the source code of an activity."""
        func = self._activities.get(name)
        if func:
            return inspect.getsource(func)
        return ""


# Global registry instance
_registry = None

def get_registry() -> ActivityRegistry:
    """Get the global activity registry."""
    global _registry
    if _registry is None:
        _registry = ActivityRegistry()
    return _registry


__all__ = ["ActivityRegistry", "get_registry"]
