"""Crush CLI runner for executing AI coding prompts.

This module provides a Python wrapper around the Crush CLI tool,
enabling programmatic execution of AI-assisted coding tasks.
"""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CrushOutput:
    """Output from a Crush run."""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        return (
            f"CrushOutput({status}, rc={self.return_code}, "
            f"created={len(self.files_created)}, modified={len(self.files_modified)})"
        )


class CrushRunner:
    """Wrapper for running Crush CLI commands.
    
    Crush is an AI coding assistant CLI that uses language models
    to generate and modify code. This runner provides:
    
    - Automatic model configuration
    - File change tracking
    - Timeout management
    - Error handling
    
    Example:
        runner = CrushRunner(model="anthropic/claude-sonnet-4")
        result = runner.run("Create a Python function that sorts a list")
        print(result.files_created)
    """
    
    def __init__(
        self,
        model: str = "bedrock/anthropic.claude-opus-4-5-20251101-v1:0",
        working_dir: Optional[Path] = None,
        timeout: int = 180,
    ):
        """Initialize the Crush runner.
        
        Args:
            model: Model to use (format: provider/model_name)
            working_dir: Directory to run Crush in (default: cwd)
            timeout: Timeout in seconds for each run
            
        Raises:
            RuntimeError: If Crush CLI is not installed
        """
        self.model = model
        self.working_dir = working_dir or Path.cwd()
        self.timeout = timeout
        self._crush_path = self._verify_crush_installed()
        logger.debug(f"CrushRunner initialized: model={model}, timeout={timeout}s")
    
    def _verify_crush_installed(self) -> str:
        """Verify that Crush CLI is installed.
        
        Returns:
            Path to the crush executable
            
        Raises:
            RuntimeError: If Crush is not found
        """
        crush_path = shutil.which("crush")
        if not crush_path:
            raise RuntimeError(
                "Crush CLI not found. Install with: brew install charmbracelet/tap/crush"
            )
        
        # Get version for logging
        try:
            result = subprocess.run(
                [crush_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            version = result.stdout.strip() if result.returncode == 0 else "unknown"
            logger.debug(f"Crush found at {crush_path}: {version}")
        except Exception:
            pass
            
        return crush_path
    
    def _get_file_state(self, directory: Path) -> dict[str, float]:
        """Get modification times of all files in directory.
        
        Args:
            directory: Directory to scan
            
        Returns:
            Dict mapping file paths to modification times
        """
        state = {}
        try:
            for path in directory.rglob("*"):
                if path.is_file() and not path.name.startswith("."):
                    try:
                        state[str(path)] = path.stat().st_mtime
                    except OSError:
                        pass
        except Exception as e:
            logger.warning(f"Error scanning directory {directory}: {e}")
        return state
    
    def run(
        self,
        prompt: str,
        verbose: bool = False,
        working_dir: Optional[Path] = None,
    ) -> CrushOutput:
        """Run a single Crush prompt.
        
        Args:
            prompt: The prompt to send to Crush
            verbose: Whether to show verbose output from Crush
            working_dir: Override working directory for this run
            
        Returns:
            CrushOutput with results and file changes
        """
        import time
        
        start_time = time.time()
        cwd = working_dir or self.working_dir
        cwd = Path(cwd)
        
        # Ensure directory exists
        cwd.mkdir(parents=True, exist_ok=True)
        
        # Track file state before
        state_before = self._get_file_state(cwd)
        
        # Build command
        cmd = [self._crush_path, "run"]
        if verbose:
            cmd.append("-v")
        cmd.extend(["-m", self.model])
        cmd.append(prompt)
        
        logger.debug(f"Running Crush in {cwd} with model {self.model}")
        logger.debug(f"Prompt length: {len(prompt)} chars")
        
        # Run Crush
        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={**os.environ, "NO_COLOR": "1"},  # Disable color codes
            )
            
            duration = time.time() - start_time
            
            # Track file state after
            state_after = self._get_file_state(cwd)
            
            # Determine created and modified files
            created = []
            modified = []
            for path, mtime in state_after.items():
                if path not in state_before:
                    created.append(path)
                elif state_before[path] < mtime:
                    modified.append(path)
            
            # Check for specific error patterns
            stderr = result.stderr
            success = result.returncode == 0
            
            # Some errors come through stdout
            if not success and not stderr and result.stdout:
                if "ERROR" in result.stdout or "error" in result.stdout.lower():
                    stderr = result.stdout
            
            output = CrushOutput(
                success=success,
                stdout=result.stdout,
                stderr=stderr,
                return_code=result.returncode,
                files_created=created,
                files_modified=modified,
                duration_seconds=duration,
            )
            
            logger.debug(f"Crush completed: {output}")
            return output
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            logger.warning(f"Crush timed out after {self.timeout}s")
            return CrushOutput(
                success=False,
                stdout="",
                stderr=f"Crush timed out after {self.timeout} seconds",
                return_code=-1,
                files_created=[],
                files_modified=[],
                duration_seconds=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Crush execution failed: {e}")
            return CrushOutput(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                files_created=[],
                files_modified=[],
                duration_seconds=duration,
            )
    
    def run_with_context(
        self,
        prompt: str,
        context_files: list[str],
        verbose: bool = False,
    ) -> CrushOutput:
        """Run Crush with specific file context.
        
        Prepends file contents to the prompt to give the model
        context about existing code.
        
        Args:
            prompt: The prompt to send
            context_files: List of file paths to include as context
            verbose: Whether to show verbose output
            
        Returns:
            CrushOutput with results
        """
        # Build context string
        context_parts = []
        for file_path in context_files:
            path = Path(file_path)
            if path.exists():
                try:
                    content = path.read_text()
                    context_parts.append(f"=== {path.name} ===\n{content}\n")
                except Exception as e:
                    logger.warning(f"Failed to read context file {path}: {e}")
        
        full_prompt = "\n".join(context_parts) + "\n\n" + prompt if context_parts else prompt
        return self.run(full_prompt, verbose=verbose)
    
    def check_model_available(self) -> bool:
        """Check if the configured model is available.
        
        Returns:
            True if model appears to be available
        """
        # Try a minimal prompt to check if model works
        try:
            result = subprocess.run(
                [self._crush_path, "models"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return self.model in result.stdout
        except Exception:
            pass
        return False
