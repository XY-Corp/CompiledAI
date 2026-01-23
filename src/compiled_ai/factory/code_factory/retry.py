"""Exponential backoff retry utilities for rate-limited API calls."""

import asyncio
import logging
import random
from typing import TypeVar, Callable, Awaitable, Any

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_with_backoff(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    **kwargs: Any,
) -> T:
    """Execute an async function with exponential backoff on rate limit errors.

    Args:
        func: Async function to execute
        *args: Positional arguments to pass to func
        max_retries: Maximum number of retry attempts (default: 5)
        base_delay: Initial delay in seconds (default: 2.0)
        max_delay: Maximum delay cap in seconds (default: 60.0)
        jitter: Add random jitter to delay (default: True)
        **kwargs: Keyword arguments to pass to func

    Returns:
        Result from the function

    Raises:
        ModelHTTPError: If all retries exhausted or non-retryable error
        Exception: Any other exception from func
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)

        except ModelHTTPError as e:
            last_exception = e

            # Only retry on rate limit (429) errors
            if e.status_code != 429:
                raise

            if attempt == max_retries:
                logger.error(f"Rate limit: max retries ({max_retries}) exhausted")
                raise

            # Calculate delay with exponential backoff
            delay = min(base_delay * (2 ** attempt), max_delay)

            # Add jitter (±25% randomization) to prevent thundering herd
            if jitter:
                delay = delay * (0.75 + random.random() * 0.5)

            logger.warning(
                f"Rate limited (429). Retry {attempt + 1}/{max_retries} in {delay:.1f}s"
            )
            print(f"⏳ Rate limited. Waiting {delay:.1f}s before retry {attempt + 1}/{max_retries}...")

            await asyncio.sleep(delay)

        except Exception:
            # Non-retryable errors - raise immediately
            raise

    # Should never reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected retry loop exit")


async def run_agent_with_retry(
    agent: Agent,
    prompt: str,
    model_settings: Any = None,
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
) -> Any:
    """Run a PydanticAI agent with exponential backoff on rate limit errors.

    This is a convenience wrapper around retry_with_backoff specifically
    for PydanticAI Agent.run() calls.

    Args:
        agent: PydanticAI Agent instance
        prompt: Prompt to pass to agent.run()
        model_settings: Optional ModelSettings for agent.run()
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds

    Returns:
        Result from agent.run()

    Example:
        >>> result = await run_agent_with_retry(
        ...     agent=my_agent,
        ...     prompt="Generate code for...",
        ...     max_retries=5,
        ...     base_delay=2.0,
        ... )
    """
    if model_settings is not None:
        return await retry_with_backoff(
            agent.run,
            prompt,
            model_settings=model_settings,
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
        )
    else:
        return await retry_with_backoff(
            agent.run,
            prompt,
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
        )
