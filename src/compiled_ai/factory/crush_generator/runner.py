"""Crush CLI runner for executing AI coding prompts."""

import subprocess
import shutil
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class CrushOutput:
    """Output from a Crush run."""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    files_created: list[str]
    files_modified: list[str]


class CrushRunner:
    """Wrapper for running Crush CLI commands."""
    
    def __init__(
        self,
        model: str = "bedrock/anthropic.claude-opus-4-5-20251101-v1:0",
        working_dir: Optional[Path] = None,
        timeout: int = 120,
    ):
        """Initialize the Crush runner.
        
        Args:
            model: Model to use (default: Claude Opus 4.5 via Bedrock)
            working_dir: Directory to run Crush in
            timeout: Timeout in seconds for each run
        """
        self.model = model
        self.working_dir = working_dir or Path.cwd()
        self.timeout = timeout
        self._verify_crush_installed()
    
    def _verify_crush_installed(self) -> None:
        """Verify that Crush CLI is installed."""
        if not shutil.which("crush"):
            raise RuntimeError(
                "Crush CLI not found. Install with: brew install charmbracelet/tap/crush"
            )
    
    def _get_file_state(self, directory: Path) -> dict[str, float]:
        """Get modification times of all files in directory."""
        state = {}
        for path in directory.rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                state[str(path)] = path.stat().st_mtime
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
            verbose: Whether to show verbose output
            working_dir: Override working directory for this run
            
        Returns:
            CrushOutput with results
        """
        cwd = working_dir or self.working_dir
        
        # Track file state before
        state_before = self._get_file_state(cwd)
        
        # Build command
        cmd = ["crush", "run"]
        if verbose:
            cmd.append("-v")
        cmd.extend(["-m", self.model])
        cmd.append(prompt)
        
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
            
            return CrushOutput(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                files_created=created,
                files_modified=modified,
            )
            
        except subprocess.TimeoutExpired:
            return CrushOutput(
                success=False,
                stdout="",
                stderr=f"Crush timed out after {self.timeout} seconds",
                return_code=-1,
                files_created=[],
                files_modified=[],
            )
        except Exception as e:
            return CrushOutput(
                success=False,
                stdout="",
                stderr=str(e),
                return_code=-1,
                files_created=[],
                files_modified=[],
            )
    
    def run_with_context(
        self,
        prompt: str,
        context_files: list[str],
        verbose: bool = False,
    ) -> CrushOutput:
        """Run Crush with specific file context.
        
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
                content = path.read_text()
                context_parts.append(f"=== {path.name} ===\n{content}\n")
        
        full_prompt = "\n".join(context_parts) + "\n\n" + prompt if context_parts else prompt
        return self.run(full_prompt, verbose=verbose)
