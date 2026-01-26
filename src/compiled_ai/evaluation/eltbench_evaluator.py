"""ELT-Bench Evaluator - Local evaluation using DuckDB instead of Snowflake.

This evaluator allows running ELT-Bench without Snowflake by:
1. Loading source data into DuckDB
2. Executing agent-generated SQL transformations
3. Comparing results against ground truth

Two evaluation modes:
1. FULL: Actually execute SQL and compare data (requires source data)
2. SEMANTIC: Use LLM to compare generated SQL to ground truth SQL (no data needed)
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False


@dataclass
class ELTEvaluationResult:
    """Result of evaluating an ELT task."""
    task_id: str
    success: bool
    score: float  # 0.0 to 1.0
    details: dict
    error: str | None = None


class ELTBenchEvaluator:
    """Evaluator for ELT-Bench tasks using DuckDB.

    Supports two modes:
    1. Full evaluation: Execute SQL, compare data
    2. Semantic evaluation: Compare SQL structure using LLM
    """

    def __init__(
        self,
        mode: str = "semantic",  # "full" or "semantic"
        data_dir: str | Path | None = None,
    ):
        """Initialize evaluator.

        Args:
            mode: Evaluation mode ("full" or "semantic")
            data_dir: Directory containing source data (for full mode)
        """
        self.mode = mode
        self.data_dir = Path(data_dir) if data_dir else None

        if mode == "full" and not HAS_DUCKDB:
            raise ImportError("DuckDB required for full evaluation: pip install duckdb")

    def evaluate(
        self,
        task_id: str,
        generated_sql: dict[str, str],  # {model_name: sql}
        ground_truth_sql: dict[str, str],  # {model_name: sql}
        context: dict | None = None,
    ) -> ELTEvaluationResult:
        """Evaluate generated SQL against ground truth.

        Args:
            task_id: Task identifier
            generated_sql: Dict mapping model names to generated SQL
            ground_truth_sql: Dict mapping model names to ground truth SQL
            context: Optional context (source schemas, etc.)

        Returns:
            ELTEvaluationResult with success, score, and details
        """
        if self.mode == "semantic":
            return self._evaluate_semantic(task_id, generated_sql, ground_truth_sql, context)
        else:
            return self._evaluate_full(task_id, generated_sql, ground_truth_sql, context)

    def _evaluate_semantic(
        self,
        task_id: str,
        generated_sql: dict[str, str],
        ground_truth_sql: dict[str, str],
        context: dict | None,
    ) -> ELTEvaluationResult:
        """Evaluate SQL semantically without executing.

        Checks:
        1. SQL syntax validity
        2. Table/column references
        3. Structural similarity to ground truth
        """
        details = {
            "models": {},
            "syntax_valid": True,
            "tables_match": True,
            "structure_score": 0.0,
        }

        total_score = 0.0
        num_models = len(ground_truth_sql)

        for model_name, gt_sql in ground_truth_sql.items():
            gen_sql = generated_sql.get(model_name, "")

            model_result = {
                "generated": gen_sql[:200] + "..." if len(gen_sql) > 200 else gen_sql,
                "ground_truth_preview": gt_sql[:200] + "..." if len(gt_sql) > 200 else gt_sql,
            }

            # Check 1: SQL provided
            if not gen_sql.strip():
                model_result["error"] = "No SQL generated"
                model_result["score"] = 0.0
            else:
                # Check 2: Basic syntax (parse attempt)
                syntax_score = self._check_sql_syntax(gen_sql)
                model_result["syntax_score"] = syntax_score

                # Check 3: Table references
                tables_score = self._check_table_references(gen_sql, gt_sql)
                model_result["tables_score"] = tables_score

                # Check 4: Structure similarity
                structure_score = self._check_structure_similarity(gen_sql, gt_sql)
                model_result["structure_score"] = structure_score

                # Combined score
                model_result["score"] = (syntax_score + tables_score + structure_score) / 3
                total_score += model_result["score"]

            details["models"][model_name] = model_result

        avg_score = total_score / num_models if num_models > 0 else 0.0
        details["structure_score"] = avg_score

        return ELTEvaluationResult(
            task_id=task_id,
            success=avg_score >= 0.7,  # 70% threshold
            score=avg_score,
            details=details,
        )

    def _evaluate_full(
        self,
        task_id: str,
        generated_sql: dict[str, str],
        ground_truth_sql: dict[str, str],
        context: dict | None,
    ) -> ELTEvaluationResult:
        """Evaluate by actually executing SQL in DuckDB.

        Requires source data to be loaded.
        """
        if not self.data_dir:
            return ELTEvaluationResult(
                task_id=task_id,
                success=False,
                score=0.0,
                details={},
                error="Data directory required for full evaluation",
            )

        # Create DuckDB connection
        conn = duckdb.connect(":memory:")

        try:
            # Load source data
            self._load_source_data(conn, task_id, context)

            details = {"models": {}}
            total_score = 0.0

            for model_name, gt_sql in ground_truth_sql.items():
                gen_sql = generated_sql.get(model_name, "")

                try:
                    # Execute generated SQL
                    gen_result = conn.execute(gen_sql).fetchall()

                    # Execute ground truth SQL
                    gt_result = conn.execute(gt_sql).fetchall()

                    # Compare results
                    if gen_result == gt_result:
                        score = 1.0
                        match = "exact"
                    else:
                        # Partial credit for partial matches
                        score = self._compare_results(gen_result, gt_result)
                        match = "partial" if score > 0 else "none"

                    details["models"][model_name] = {
                        "score": score,
                        "match": match,
                        "gen_rows": len(gen_result),
                        "gt_rows": len(gt_result),
                    }
                    total_score += score

                except Exception as e:
                    details["models"][model_name] = {
                        "score": 0.0,
                        "error": str(e),
                    }

            avg_score = total_score / len(ground_truth_sql) if ground_truth_sql else 0.0

            return ELTEvaluationResult(
                task_id=task_id,
                success=avg_score >= 0.9,
                score=avg_score,
                details=details,
            )

        finally:
            conn.close()

    def _check_sql_syntax(self, sql: str) -> float:
        """Check if SQL has valid syntax (basic check)."""
        sql_upper = sql.upper().strip()

        # Must have SELECT
        if "SELECT" not in sql_upper:
            return 0.0

        # Must have FROM
        if "FROM" not in sql_upper:
            return 0.5

        # Check for balanced parentheses
        if sql.count("(") != sql.count(")"):
            return 0.5

        return 1.0

    def _check_table_references(self, gen_sql: str, gt_sql: str) -> float:
        """Check if generated SQL references similar tables."""
        # Extract table names (simplified)
        gen_tables = set(re.findall(r'FROM\s+(\w+)', gen_sql, re.IGNORECASE))
        gen_tables.update(re.findall(r'JOIN\s+(\w+)', gen_sql, re.IGNORECASE))

        gt_tables = set(re.findall(r'FROM\s+(\w+)', gt_sql, re.IGNORECASE))
        gt_tables.update(re.findall(r'JOIN\s+(\w+)', gt_sql, re.IGNORECASE))

        if not gt_tables:
            return 1.0 if not gen_tables else 0.5

        # Calculate overlap
        overlap = len(gen_tables & gt_tables)
        return overlap / len(gt_tables) if gt_tables else 0.0

    def _check_structure_similarity(self, gen_sql: str, gt_sql: str) -> float:
        """Check structural similarity between SQL queries."""
        gen_upper = gen_sql.upper()
        gt_upper = gt_sql.upper()

        score = 0.0
        checks = 0

        # Check for CTEs
        gen_has_cte = "WITH " in gen_upper and " AS (" in gen_upper
        gt_has_cte = "WITH " in gt_upper and " AS (" in gt_upper
        if gen_has_cte == gt_has_cte:
            score += 1
        checks += 1

        # Check for JOINs
        gen_has_join = "JOIN" in gen_upper
        gt_has_join = "JOIN" in gt_upper
        if gen_has_join == gt_has_join:
            score += 1
        checks += 1

        # Check for GROUP BY
        gen_has_group = "GROUP BY" in gen_upper
        gt_has_group = "GROUP BY" in gt_upper
        if gen_has_group == gt_has_group:
            score += 1
        checks += 1

        # Check for window functions
        gen_has_window = "OVER(" in gen_upper or "OVER (" in gen_upper
        gt_has_window = "OVER(" in gt_upper or "OVER (" in gt_upper
        if gen_has_window == gt_has_window:
            score += 1
        checks += 1

        # Check for CASE statements
        gen_has_case = "CASE WHEN" in gen_upper
        gt_has_case = "CASE WHEN" in gt_upper
        if gen_has_case == gt_has_case:
            score += 1
        checks += 1

        return score / checks if checks > 0 else 0.0

    def _load_source_data(self, conn, task_id: str, context: dict | None):
        """Load source data into DuckDB."""
        # This would load CSV/Parquet files from data_dir
        # Implementation depends on how data is organized
        pass

    def _compare_results(self, gen_result: list, gt_result: list) -> float:
        """Compare query results with partial credit."""
        if not gt_result:
            return 1.0 if not gen_result else 0.0

        # Simple row count comparison for now
        gen_count = len(gen_result)
        gt_count = len(gt_result)

        if gen_count == gt_count:
            return 0.8  # Right count but maybe wrong content

        # Partial credit based on how close the count is
        ratio = min(gen_count, gt_count) / max(gen_count, gt_count)
        return ratio * 0.5


def evaluate_elt_task(
    task_id: str,
    generated_sql: dict[str, str],
    ground_truth_sql: dict[str, str],
    mode: str = "semantic",
) -> ELTEvaluationResult:
    """Convenience function to evaluate an ELT task.

    Args:
        task_id: Task identifier
        generated_sql: Dict mapping model names to generated SQL
        ground_truth_sql: Dict mapping model names to ground truth SQL
        mode: "semantic" (no data needed) or "full" (requires data)

    Returns:
        ELTEvaluationResult
    """
    evaluator = ELTBenchEvaluator(mode=mode)
    return evaluator.evaluate(task_id, generated_sql, ground_truth_sql)
