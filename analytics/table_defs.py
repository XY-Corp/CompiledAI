import uuid
import datetime
from pydantic import BaseModel
from typing import Optional

class ConfigRow(BaseModel):
    id: uuid.UUID
    dataset: str
    baseline: str
class SummaryRow(BaseModel):
    id: uuid.UUID
    config_id: uuid.UUID
    duration_seconds: float
    overall_success_rate: float
    total_tasks: int
    total_instances: int

class TaskRow(BaseModel):
    id: uuid.UUID
    summary_id: uuid.UUID
    task_id: str
    name: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    success_rate: float
    avg_latency_ms: float
    instance_count: int

class MetricRow(BaseModel):
    id: uuid.UUID
    config_id: uuid.UUID
    benchmark_id: str
    task_name: str
    method: str
    model: str
    notes: str
    timestamp: datetime.datetime

class MetricResultRow(BaseModel):
    id: uuid.UUID
    metric_id: uuid.UUID
    name: str
    value: str | float
    unit: str
    category: str
    timestamp: datetime.datetime