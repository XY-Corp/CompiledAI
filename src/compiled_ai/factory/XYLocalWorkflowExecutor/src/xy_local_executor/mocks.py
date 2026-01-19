"""Activity mocking utilities for local workflow testing.

This module provides pre-built mocks for common activity patterns,
making it easy to test workflows without external dependencies.

Usage:
    from xy_local_executor import LocalWorkflowExecutor, ActivityMocks

    executor = LocalWorkflowExecutor(
        mock_activities={
            "fetch_data": ActivityMocks.instant_success,
            "process_item": ActivityMocks.delayed(100),
            "save_result": ActivityMocks.from_json({"status": "saved"}),
        }
    )
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class ActivityMocks:
    """Pre-built mock functions for common activity patterns."""

    @staticmethod
    async def instant_success(**kwargs) -> Dict[str, Any]:
        """Return immediate success for any activity."""
        return {
            "status": "success",
            "operation_status": "success",
            "mocked": True,
        }

    @staticmethod
    async def instant_failure(**kwargs) -> Dict[str, Any]:
        """Return immediate failure for any activity."""
        raise RuntimeError("Mocked failure")

    @staticmethod
    async def echo(**kwargs) -> Dict[str, Any]:
        """Return the input parameters as output."""
        return {
            "status": "success",
            "mocked": True,
            "params": kwargs,
        }

    @staticmethod
    def delayed(delay_ms: int) -> Callable:
        """Create a mock that delays for specified milliseconds then succeeds."""
        async def _mock(**kwargs) -> Dict[str, Any]:
            await asyncio.sleep(delay_ms / 1000)
            return {
                "status": "success",
                "operation_status": "success",
                "delay_ms": delay_ms,
                "mocked": True,
            }
        return _mock

    @staticmethod
    def delayed_failure(delay_ms: int, error_msg: str = "Delayed failure") -> Callable:
        """Create a mock that delays then fails."""
        async def _mock(**kwargs) -> Dict[str, Any]:
            await asyncio.sleep(delay_ms / 1000)
            raise RuntimeError(error_msg)
        return _mock

    @staticmethod
    def from_json(data: Dict[str, Any]) -> Callable:
        """Create a mock that returns the specified JSON data."""
        async def _mock(**kwargs) -> Dict[str, Any]:
            result = dict(data)
            result["mocked"] = True
            return result
        return _mock

    @staticmethod
    def from_file(json_path: str | Path) -> Callable:
        """Create a mock that loads response from a JSON file."""
        async def _mock(**kwargs) -> Dict[str, Any]:
            with open(json_path, 'r') as f:
                result = json.load(f)
            if isinstance(result, dict):
                result["mocked"] = True
            return result
        return _mock

    @staticmethod
    def sequence(*responses: Dict[str, Any]) -> Callable:
        """Create a mock that returns different responses on each call."""
        call_count = [0]

        async def _mock(**kwargs) -> Dict[str, Any]:
            idx = min(call_count[0], len(responses) - 1)
            call_count[0] += 1
            result = dict(responses[idx])
            result["mocked"] = True
            result["call_number"] = call_count[0]
            return result

        return _mock

    @staticmethod
    def capture(storage: List[Dict[str, Any]]) -> Callable:
        """Create a mock that captures all calls to the provided list."""
        async def _mock(**kwargs) -> Dict[str, Any]:
            storage.append(dict(kwargs))
            return {
                "status": "success",
                "operation_status": "success",
                "captured": True,
                "mocked": True,
            }
        return _mock

    @staticmethod
    def passthrough_with_log(activity_fn: Callable, log_fn: Callable[[Dict], None]) -> Callable:
        """Wrap an activity to log calls while still executing."""
        async def _mock(**kwargs) -> Dict[str, Any]:
            log_fn(kwargs)
            if asyncio.iscoroutinefunction(activity_fn):
                return await activity_fn(**kwargs)
            return activity_fn(**kwargs)
        return _mock

    @staticmethod
    def conditional(condition_fn: Callable[[Dict], bool], if_true: Callable, if_false: Callable) -> Callable:
        """Create a mock that returns different results based on a condition."""
        async def _mock(**kwargs) -> Dict[str, Any]:
            chosen_fn = if_true if condition_fn(kwargs) else if_false
            if asyncio.iscoroutinefunction(chosen_fn):
                return await chosen_fn(**kwargs)
            return chosen_fn(**kwargs)
        return _mock

    @staticmethod
    def with_side_effect(side_effect_fn: Callable[[Dict], None]) -> Callable:
        """Create a mock that executes a side effect then returns success."""
        async def _mock(**kwargs) -> Dict[str, Any]:
            side_effect_fn(kwargs)
            return {
                "status": "success",
                "operation_status": "success",
                "mocked": True,
            }
        return _mock


def create_mock_registry(
    base_mocks: Optional[Dict[str, Callable]] = None,
    **additional_mocks: Callable,
) -> Dict[str, Callable]:
    """
    Create a mock registry by combining base mocks with additional overrides.

    Args:
        base_mocks: Base mock dictionary
        **additional_mocks: Additional mocks to add or override

    Returns:
        Combined mock registry

    Example:
        mocks = create_mock_registry(
            {"activity_a": ActivityMocks.instant_success},
            activity_b=ActivityMocks.delayed(100),
        )
    """
    result = dict(base_mocks or {})
    result.update(additional_mocks)
    return result
