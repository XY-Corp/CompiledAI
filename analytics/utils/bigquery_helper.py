from datetime import datetime
import io
from typing import Never
import logging
import sys
from google.cloud import bigquery
import pyarrow as pa
import pyarrow.parquet as pq
from google.api_core import exceptions as api_exceptions
import os
from google.auth.exceptions import DefaultCredentialsError

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.validate import validate_google_credentials

"""
BigQuery class for interacting with BigQuery.
Each service should have its own BigQueryHelper instance.
"""


class BigQueryHelper:
    def __init__(self, project_id: str, dataset: str, logger: logging.Logger):
        """Initialize the BigQueryHelper."""
        try:
            validate_google_credentials()
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"❌ Google Cloud credentials validation failed: {e}")
            sys.exit(1)

        self.project_id = project_id
        self.dataset = dataset
        self.logger = logger
        try:
            self.client: bigquery.Client = bigquery.Client(project=project_id)
        except DefaultCredentialsError as e:
            self.logger.error(f"❌ Failed to initialize BigQuery client: {e}")
            sys.exit(1)
        self.logger.info("🛟 BigQueryHelper initialized")

    # --- Getters ---
    def get_client(self) -> bigquery.Client:
        """Get a BigQuery client."""
        return self.client

    def get_dataset(self) -> bigquery.Dataset:
        """Get a BigQuery dataset."""
        return self.client.dataset(self.dataset)

    def get_table(self, table: str) -> bigquery.Table:
        """Get a BigQuery table."""
        table_ref: str = self.get_full_table_ref_name(table)
        return bigquery.TableReference.from_string(table_ref)

    def table_has_schema(self, table: str) -> bool:
        """Check if a BigQuery table has a schema defined."""
        try:
            table_ref: str = self.get_full_table_ref_name(table)
            bq_client = self.get_client()
            table_obj = bq_client.get_table(table_ref)
            return table_obj.schema is not None and len(table_obj.schema) > 0
        except api_exceptions.NotFound:
            return False
        except Exception as e:
            self.logger.error(f"❌ Error checking schema for table {table}: {e}")
            return False

    def get_full_table_ref_name(self, table: str) -> str:
        """Get the full BigQuery table reference name."""
        return f"{self.project_id}.{self.dataset}.{table}"

    # --- Validation ---
    def ensure_table(self, table: str) -> None:
        """Ensure a BigQuery table exists."""
        table_ref: str = self.get_full_table_ref_name(table)
        self.logger.info(f"🔰 Ensuring table '{table_ref}'")
        bq_client = self.get_client()
        try:
            bq_client.create_table(table_ref, exists_ok=True)
        except Exception as e:
            raise Exception(f"❌ Failed to create table {table_ref}: {e}")

    def ensure_dataset(self) -> None:
        """Ensure a BigQuery dataset exists."""
        self.logger.info(f"🔰 Ensuring dataset '{self.dataset}'")
        bq_client = self.get_client()
        try:
            bq_client.create_dataset(
                f"{self.project_id}.{self.dataset}", exists_ok=True
            )
        except Exception as e:
            raise Exception(f"❌ Failed to create dataset {self.dataset}: {e}")

    # --- Formatting ---
    def format_arrow_table(self, arrow_table: pa.Table) -> pa.Table:
        new_column_names: list[str] = [
            name.replace('.', '_').replace('/', '_')
            for name in arrow_table.column_names
        ]
        return arrow_table.rename_columns(
            new_column_names
        )

    # --- Queries ---
    def table_exists(self, table: str) -> bool:
        """Check if a BigQuery table exists."""
        table_ref: str = self.get_full_table_ref_name(table)
        bq_client = self.get_client()
        try:
            bq_client.get_table(table_ref)
            return True
        except api_exceptions.NotFound:
            return False
        except Exception as e:
            self.logger.error(f"❌ Error checking if table exists: {e}")
            return False

    def get_most_recent_datapoint(
        self, table: str, column: str = "created_at",
        condition: str = ""
    ) -> datetime:
        """Get the most recent datapoint from a BigQuery table.
        If a condition is provided, it will be added to the query."""
        row_count: int = self.get_row_count(table)

        if row_count == 0:
            return datetime(2025, 1, 1)

        try:
            table_ref: str = self.get_full_table_ref_name(table)
            where_clause = f"WHERE {condition}" if condition else ""
            query: str = (
                f"SELECT MAX({column}) FROM {table_ref} {where_clause}"
            )
            result = self.get_one(query)
            self.logger.info(f"📅 Most recent datapoint: {result}")
            return result
        except Exception as e:
            self.logger.error(f"❌ Error getting most recent datapoint: {e}")
            return datetime(2025, 1, 1)

    def get_row_count(self, table: str, condition: str | None = None) -> int:
        """Get the number of rows in a BigQuery table.
        Returns 0 if the table has no schema."""
        # Check if table has a schema before querying
        if not self.table_has_schema(table):
            self.logger.info(
                f"📋 Table {table} has no schema. Returning 0 rows."
            )
            return 0

        table_ref: str = self.get_full_table_ref_name(table)
        if condition is None:
            query = f"SELECT COUNT(*) FROM {table_ref}"
        else:
            query = f"SELECT COUNT(*) FROM {table_ref} WHERE {condition}"
        result = self.get_one(query)
        return result

    def get_one(self, query: str) -> any:
        """Get a single result from a BigQuery query."""
        bq_client = self.get_client()
        result = bq_client.query(query).result()
        results_list = list[Never](result)
        if len(results_list) == 0:
            self.logger.warning(f"❌ No result found for query: {query}")
            return None
        else:
            return results_list[0][0]

    def get(self, query: str) -> list[Never]:
        """Get a list of results from a BigQuery query."""
        bq_client = self.get_client()
        result = bq_client.query(query).result()
        results_list: list[Never] = list[Never](result)
        return results_list

    def upload(
        self,
        table: str,
        arrow_table: pa.Table,
        write_disposition: bigquery.WriteDisposition = (
            bigquery.WriteDisposition.WRITE_APPEND
        )
    ) -> None:
        """Upload an Arrow table to a BigQuery table."""

        self.logger.info(f"📤 Uploading {arrow_table.num_rows:,d} rows to BigQuery")

        # Build job config
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=write_disposition,
            autodetect=True,
            column_name_character_map="V2",
        )

        # Build table reference
        table_ref: bigquery.TableReference = self.get_table(table)

        self.logger.info(f"📋 Loading to BigQuery table: '{table_ref}'")

        # Upload data
        bq_client = self.get_client()

        try:
            # Create buffer
            with io.BytesIO() as buffer:
                # Serialize Arrow table to Parquet
                pq.write_table(arrow_table, buffer)
                buffer.seek(0)

                # Upload data
                job = bq_client.load_table_from_file(
                    buffer, table_ref, job_config=job_config
                )

                # Wait for the job to complete.
                job.result()

                # Log success
                self.logger.info(
                    f"✅ Successfully loaded {job.output_rows:,} rows into "
                    f"{table_ref}."
                )
        except Exception as e:
            self.logger.error(f"❌ BigQuery load failed: {e}")
            raise e
